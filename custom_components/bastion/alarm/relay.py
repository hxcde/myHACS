"""Link to the Cloudflare worker: heartbeat, alarm log, camera images, acknowledgements.

Home Assistant sends a signed heartbeat every few minutes (every 15 seconds
while an alarm runs). If heartbeats stop while the alarm is armed (power cut,
internet cut, sabotage), the worker alerts you with the last known state. Every
alarm event is stored by the worker (off-site log), alarms are pushed from
there, and Pushover acknowledgements come back with the heartbeat response.

Signature: hex(HMAC-SHA256(secret, f"{timestamp}.{body}")) in
X-Bastion-Signature, timestamp in X-Bastion-Timestamp (replay window 5 min).
"""

from __future__ import annotations

import asyncio
import base64
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

# Events stored by the worker; the push flag decides about notifications.
RELAY_EVENTS = (
    "triggered",
    "pending",
    "disarmed",
    "arming",
    "armed",
    "rearmed",
    "reset",
    "arm_failed",
    "wrong_code",
    "sensor_unavailable",
)
ACTIVE_STATES = ("pending", "triggered")
TICK = 15
SNAPSHOT_INTERVAL = 5
MAX_SNAPSHOT = 1_400_000  # base64 characters
# Process start (module import) and boot time let the worker tell a host reboot,
# a Home Assistant restart and a network outage apart.
PROCESS_START = int(time.time())


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """Signature the worker verifies."""
    return hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def incident_token(secret: str, incident: str) -> str:
    """Link token for an incident page (same value as the worker computes)."""
    return hmac.new(secret.encode(), f"incident.{incident}".encode(), hashlib.sha256).hexdigest()[:32]


def boot_time() -> int:
    """Approximate host boot time (monotonic clock counts from boot)."""
    return int(time.time() - time.monotonic()) // 60 * 60


class AlarmRelay:
    """Heartbeat, event, snapshot and acknowledgement handling."""

    def __init__(self, hass: HomeAssistant, engine) -> None:
        """Init."""
        self.hass = hass
        self.engine = engine
        self._unsub: CALLBACK_TYPE | None = None
        self._last_beat = 0.0
        self._acks_seen: set[str] = set()
        self._acks_done: set[str] = set()
        self._tasks: set[asyncio.Task] = set()
        self.last_ok: str | None = None
        self.last_error: str | None = None
        self.version = ""

    @property
    def cfg(self) -> dict[str, Any]:
        """Worker settings."""
        return self.engine.config.get("worker") or {}

    @property
    def enabled(self) -> bool:
        """True if a worker is configured."""
        return bool(self.cfg.get("enabled") and self.cfg.get("url") and self.cfg.get("secret"))

    @property
    def interval(self) -> int:
        """Heartbeat interval in seconds."""
        return max(30, int(self.cfg.get("interval") or 120))

    def setup(self) -> None:
        """Start the heartbeat timer."""
        self.unload()
        if not self.enabled:
            return
        self._last_beat = 0.0
        self._unsub = async_track_time_interval(self.hass, self._async_tick, timedelta(seconds=TICK))
        self._spawn(self._async_heartbeat())

    def unload(self) -> None:
        """Stop the heartbeat timer and running uploads."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        for task in list(self._tasks):
            task.cancel()

    def _spawn(self, coro) -> None:
        task = self.hass.async_create_background_task(coro, "bastion_relay")
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def incident_url(self, incident: str | None) -> str | None:
        """Link to the worker's incident page (events and camera images)."""
        if not (incident and self.enabled):
            return None
        return f"{self.cfg['url'].rstrip('/')}/i/{incident}?t={incident_token(self.cfg['secret'], incident)}"

    async def _async_post(self, path: str, payload: dict[str, Any], timeout: float = 15) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        headers = {
            "Content-Type": "application/json",
            "X-Bastion-Timestamp": timestamp,
            "X-Bastion-Signature": sign(self.cfg["secret"], timestamp, body),
        }
        session = async_get_clientsession(self.hass)
        async with session.post(
            self.cfg["url"].rstrip("/") + path, data=body, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout)
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
            "armed": status["state"] != "disarmed",
            "incident": status.get("incident"),
            "interval": self.interval,
            "instance": self.hass.config.location_name,
        }

    def _heartbeat_payload(self, *, stopping: bool = False) -> dict[str, Any]:
        return {
            "ts": int(time.time()),
            **self._snapshot(),
            **self.engine.context(),
            "tz": str(self.hass.config.time_zone),
            "started": PROCESS_START,
            "boot": boot_time(),
            "version": self.version,
            "stopping": stopping,
            "acks_seen": sorted(self._acks_seen),
        }

    async def _async_tick(self, _now: datetime | None = None) -> None:
        due = time.monotonic() - self._last_beat >= self.interval - TICK / 2
        if due or self.engine.state in ACTIVE_STATES:
            await self._async_heartbeat()

    async def _async_heartbeat(self) -> None:
        if not self.enabled:
            return
        self._last_beat = time.monotonic()
        sent_seen = set(self._acks_seen)
        try:
            result = await self._async_post("/heartbeat", self._heartbeat_payload())
        except (aiohttp.ClientError, TimeoutError) as err:
            self.last_error = str(err)[:200]
            _LOGGER.debug("Bastion heartbeat failed: %s", err)
            return
        self.last_ok = dt_util.utcnow().isoformat()
        self.last_error = None
        self._acks_seen -= sent_seen
        self._handle_acks(result.get("acks") or [])

    def _handle_acks(self, acks: list[dict[str, Any]]) -> None:
        for ack in acks[:10]:
            receipt = str(ack.get("receipt") or "")
            if not receipt:
                continue
            self._acks_seen.add(receipt)
            if receipt in self._acks_done:
                continue
            self._acks_done.add(receipt)
            incident = ack.get("incident") if isinstance(ack.get("incident"), str) else None
            self.engine.record_ack(str(ack.get("by") or "Pushover")[:60], incident, ack.get("kind"))
        if len(self._acks_done) > 200:
            self._acks_done = set(sorted(self._acks_done)[-100:])

    async def async_stop(self) -> None:
        """Planned shutdown: tell the worker, so a restart is not mistaken for sabotage."""
        if not self.enabled:
            return
        try:
            await self._async_post("/heartbeat", self._heartbeat_payload(stopping=True), timeout=5)
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("Bastion stop heartbeat failed: %s", err)

    async def async_send_event(self, kind: str, entry: dict[str, Any], *, push: bool) -> None:
        """Store an alarm event at the worker (and push it if requested)."""
        if not self.enabled or kind not in RELAY_EVENTS:
            return
        detail = {k: entry[k] for k in ("target", "delay", "previous", "reason") if entry.get(k) not in (None, "")}
        for key in ("bypassed", "sensors"):
            if entry.get(key):
                detail[key] = [str(x)[:60] for x in entry[key]][:20]
        payload = {
            "ts": int(time.time()),
            "event": kind,
            **self._snapshot(),
            "incident": entry.get("incident") or self.engine.incident,
            "sensor": entry.get("name") or entry.get("sensor"),
            "room": entry.get("room"),
            "user": entry.get("user"),
            "reason": entry.get("reason"),
            "sensors": detail.get("sensors"),
            "detail": detail,
            "push": push,
        }
        try:
            await self._async_post("/alert", payload)
            self.last_ok = dt_util.utcnow().isoformat()
        except (aiohttp.ClientError, TimeoutError) as err:
            self.last_error = str(err)[:200]
            _LOGGER.warning("Bastion alarm relay failed: %s", err)
        if kind in ACTIVE_STATES and payload["incident"]:
            self.start_snapshots(payload["incident"])

    # ---------------------------------------------------------- snapshots
    def start_snapshots(self, incident: str) -> None:
        """Send camera images of the incident to the worker (off-site evidence)."""
        cameras = [c for c in self.cfg.get("cameras") or [] if self.hass.states.get(c) is not None]
        count = int(self.cfg.get("snapshots", 3) or 0)
        if self.enabled and cameras and count > 0:
            self._spawn(self._async_snapshots(incident, cameras, count))

    async def _async_snapshots(self, incident: str, cameras: list[str], count: int) -> None:
        for round_ in range(count):
            if round_:
                await asyncio.sleep(SNAPSHOT_INTERVAL)
            await asyncio.gather(*(self._async_snapshot(incident, camera) for camera in cameras))

    async def _async_snapshot(self, incident: str, camera: str) -> None:
        from homeassistant.components import camera as camera_component  # noqa: PLC0415

        state = self.hass.states.get(camera)
        name = (state.attributes.get("friendly_name") if state else None) or camera
        data = None
        for width in (1280, 640):
            try:
                image = await camera_component.async_get_image(self.hass, camera, timeout=10, width=width)
            except Exception as err:  # noqa: BLE001 - a broken camera must not stop the others
                _LOGGER.warning("Bastion snapshot of %s failed: %s", camera, err)
                return
            data = base64.b64encode(image.content).decode()
            content_type = image.content_type or "image/jpeg"
            if len(data) <= MAX_SNAPSHOT:
                break
            data = None
        if data is None:
            _LOGGER.warning("Bastion snapshot of %s is too large for the worker", camera)
            return
        try:
            await self._async_post(
                "/snapshot",
                {"ts": int(time.time()), "incident": incident, "camera": name, "type": content_type, "data": data},
                timeout=30,
            )
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Bastion snapshot upload failed: %s", err)

    async def async_test(self) -> dict[str, Any]:
        """Heartbeat plus a test alert, result for the panel."""
        if not (self.cfg.get("url") and self.cfg.get("secret")):
            return {"ok": False, "error": "not configured"}
        try:
            result = await self._async_post("/heartbeat", self._heartbeat_payload())
            self._handle_acks(result.get("acks") or [])
            result = await self._async_post("/alert", {"ts": int(time.time()), "event": "test", **self._snapshot()})
            self.last_ok = dt_util.utcnow().isoformat()
            self.last_error = None
            return {"ok": True, "channels": result.get("channels", [])}
        except (aiohttp.ClientError, TimeoutError) as err:
            self.last_error = str(err)[:200]
            return {"ok": False, "error": self.last_error}
