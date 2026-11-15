"""Link to the Cloudflare worker: heartbeat (dead man's switch) and alarm relay.

Home Assistant sends a signed heartbeat every few minutes. If heartbeats stop
while the alarm is armed (power cut, internet cut, sabotage), the worker
alerts you through its own channels (Telegram, ntfy, webhook). Alarms are also
relayed through the worker, independent of Home Assistant's notify services.

Signature: hex(HMAC-SHA256(secret, f"{timestamp}.{body}")) in
X-Bastion-Signature, timestamp in X-Bastion-Timestamp (replay window 5 min).
"""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import hmac
import json
import logging
import time
from typing import Any

import aiohttp
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

RELAY_EVENTS = ("triggered", "pending", "disarmed", "armed", "sensor_unavailable")


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """Signature the worker verifies."""
    return hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


class AlarmRelay:
    """Heartbeat and alert sender."""

    def __init__(self, hass: HomeAssistant, engine) -> None:
        """Init."""
        self.hass = hass
        self.engine = engine
        self._unsub: CALLBACK_TYPE | None = None
        self.last_ok: str | None = None
        self.last_error: str | None = None

    @property
    def cfg(self) -> dict[str, Any]:
        """Worker settings."""
        return self.engine.config.get("worker") or {}

    @property
    def enabled(self) -> bool:
        """True if a worker is configured."""
        return bool(self.cfg.get("enabled") and self.cfg.get("url") and self.cfg.get("secret"))

    def setup(self) -> None:
        """Start the heartbeat timer."""
        self.unload()
        if not self.enabled:
            return
        interval = max(30, int(self.cfg.get("interval") or 120))
        self._unsub = async_track_time_interval(self.hass, self._async_heartbeat, timedelta(seconds=interval))
        self.hass.async_create_task(self._async_heartbeat(), eager_start=False)

    def unload(self) -> None:
        """Stop the heartbeat timer."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    async def _async_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-Bastion-Timestamp": timestamp,
            "X-Bastion-Signature": sign(self.cfg["secret"], timestamp, body),
        }
        session = async_get_clientsession(self.hass)
        async with session.post(
            self.cfg["url"].rstrip("/") + path, data=body, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise aiohttp.ClientResponseError(
                    resp.request_info, resp.history, status=resp.status, message=text[:200]
                )
            try:
                return json.loads(text)
            except ValueError:
                return {}

    def _snapshot(self) -> dict[str, Any]:
        status = self.engine.status()
        return {
            "state": status["state"],
            "mode": status["mode"],
            "armed": status["state"] not in ("disarmed",),
            "interval": int(self.cfg.get("interval") or 120),
            "instance": self.hass.config.location_name,
        }

    async def _async_heartbeat(self, _now: datetime | None = None) -> None:
        if not self.enabled:
            return
        try:
            await self._async_post("/heartbeat", {"ts": int(time.time()), **self._snapshot()})
            self.last_ok = dt_util.utcnow().isoformat()
            self.last_error = None
        except (aiohttp.ClientError, TimeoutError) as err:
            self.last_error = str(err)[:200]
            _LOGGER.debug("Bastion heartbeat failed: %s", err)

    async def async_send_event(self, kind: str, entry: dict[str, Any]) -> None:
        """Relay an alarm event."""
        if not self.enabled or kind not in RELAY_EVENTS:
            return
        payload = {
            "ts": int(time.time()),
            "event": kind,
            **self._snapshot(),
            "sensor": entry.get("name") or entry.get("sensor"),
            "room": entry.get("room"),
            "user": entry.get("user"),
            "reason": entry.get("reason"),
        }
        try:
            await self._async_post("/alert", payload)
            self.last_ok = dt_util.utcnow().isoformat()
        except (aiohttp.ClientError, TimeoutError) as err:
            self.last_error = str(err)[:200]
            _LOGGER.warning("Bastion alarm relay failed: %s", err)

    async def async_test(self) -> dict[str, Any]:
        """Heartbeat plus a test alert, result for the panel."""
        if not (self.cfg.get("url") and self.cfg.get("secret")):
            return {"ok": False, "error": "not configured"}
        try:
            await self._async_post("/heartbeat", {"ts": int(time.time()), **self._snapshot()})
            result = await self._async_post("/alert", {"ts": int(time.time()), "event": "test", **self._snapshot()})
            self.last_ok = dt_util.utcnow().isoformat()
            self.last_error = None
            return {"ok": True, "channels": result.get("channels", [])}
        except (aiohttp.ClientError, TimeoutError) as err:
            self.last_error = str(err)[:200]
            return {"ok": False, "error": self.last_error}
