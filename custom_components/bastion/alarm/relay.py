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
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import dt as dt_util

from ..const import EVENT_SECURITY, SEVERITY_WEIGHT

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
SECURITY_RESEND = 1800  # seconds: overview is sent on change, at least this often
BACKFILL_DELAY = 30  # seconds after setup: the login monitor has loaded its history by then
BACKFILL_CHUNK = 200
MAX_QUEUE = 300
EVENTS_PER_BEAT = 50
DETAIL_KEYS = ("count", "minutes", "name", "public", "reason", "action", "kind")
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
        self._sec_queue: list[dict[str, Any]] = []
        self._sec_hash: str | None = None
        self._sec_sent = 0.0
        self._unsub_security: CALLBACK_TYPE | None = None
        self._unsub_backfill: CALLBACK_TYPE | None = None
        self.backfill_result: dict[str, Any] | None = None
        self.on_exposure = None

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
        self._unsub_security = self.hass.bus.async_listen(EVENT_SECURITY, self._on_security_event)
        self._unsub_backfill = async_call_later(self.hass, BACKFILL_DELAY, self._start_backfill)
        self._spawn(self._async_heartbeat())

    def unload(self) -> None:
        """Stop the heartbeat timer and running uploads."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        if self._unsub_security is not None:
            self._unsub_security()
            self._unsub_security = None
        if self._unsub_backfill is not None:
            self._unsub_backfill()
            self._unsub_backfill = None
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

    # ----------------------------------------------------------- security
    @property
    def _bastion(self):
        return getattr(self.engine, "bastion", None)

    @staticmethod
    def _security_event(entry: dict[str, Any]) -> dict[str, Any] | None:
        """Compact login/security event for the worker (ids and tokens stay at home)."""
        kind = str(entry.get("type") or "")
        if not kind or kind == "worker_attack":
            return None
        when = dt_util.parse_datetime(str(entry.get("time") or "")) or dt_util.utcnow()
        ip = entry.get("ip")
        user = entry.get("user")
        uid = hashlib.sha256(f"{when.isoformat()}|{kind}|{ip}|{user}".encode()).hexdigest()[:24]
        return {
            "uid": uid,
            "ts": int(when.timestamp()),
            "type": kind[:40],
            "ip": str(ip)[:64] if ip else None,
            "user": str(user)[:80] if user else None,
            "geo": str(entry.get("geo"))[:80] if entry.get("geo") else None,
            "detail": {k: entry[k] for k in DETAIL_KEYS if isinstance(entry.get(k), (str, int, float, bool))},
        }

    @callback
    def _on_security_event(self, event: Event) -> None:
        if (item := self._security_event({"time": dt_util.utcnow().isoformat(), **event.data})) is not None:
            self._sec_queue.append(item)
            del self._sec_queue[:-MAX_QUEUE]

    @callback
    def _start_backfill(self, _now: datetime | None = None) -> None:
        self._unsub_backfill = None
        self._spawn(self.async_backfill())

    async def async_backfill(self) -> dict[str, Any]:
        """Send the whole alarm and login log once; the worker skips what it has."""
        if not self.enabled:
            return {}
        alarm = [self._alarm_event(e["type"], e) for e in list(self.engine.log) if e.get("type") in RELAY_EVENTS]
        logins = getattr(self._bastion, "logins", None)
        security = [item for e in list(logins.log if logins else []) if (item := self._security_event(e)) is not None]
        result = {"alarm": 0, "security": 0, "sent": len(alarm) + len(security)}
        try:
            for i in range(0, max(len(alarm), len(security)), BACKFILL_CHUNK):
                chunk = {
                    "ts": int(time.time()),
                    "alarm_events": alarm[i : i + BACKFILL_CHUNK],
                    "security_events": security[i : i + BACKFILL_CHUNK],
                }
                answer = await self._async_post("/backfill", chunk, timeout=30)
                result["alarm"] += int(answer.get("alarm") or 0)
                result["security"] += int(answer.get("security") or 0)
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Bastion backfill to the worker failed: %s", err)
            result["error"] = str(err)[:200]
        self.backfill_result = {**result, "time": dt_util.utcnow().isoformat()}
        _LOGGER.debug("Bastion backfill: %s", result)
        return result

    def _security_overview(self) -> dict[str, Any] | None:
        bastion = self._bastion
        if bastion is None:
            return None
        summary = bastion.summary()
        active = sorted(
            (f for f in bastion.findings if not f.dismissed and SEVERITY_WEIGHT.get(f.severity, 0) > 0),
            key=lambda f: -SEVERITY_WEIGHT.get(f.severity, 0),
        )
        git = bastion.git.status() if getattr(bastion, "git", None) is not None else {}
        return {
            "score": summary["score"],
            "counts": summary["counts"],
            "open": summary["open"],
            "last_audit": summary.get("last_audit"),
            "failed_24h": bastion.logins.failed_last_24h() if getattr(bastion, "logins", None) else 0,
            "findings": [
                {
                    "id": f.id,
                    "severity": str(f.severity),
                    "category": str(f.category),
                    "title": (f.title or f.text_key)[:200],
                    "since": f.first_seen,
                }
                for f in active[:40]
            ],
            "git": {"status": git.get("status"), "last": git.get("last_commit_time")} if git else None,
            "history": [
                {"date": h.get("date"), "score": h.get("score")} for h in (bastion.data.get("history") or [])[-400:]
            ],
        }

    def _security_payload(self) -> tuple[dict[str, Any], str | None, int]:
        """Overview (when changed) and queued events for the next heartbeat."""
        extra: dict[str, Any] = {}
        sent_hash = None
        if (overview := self._security_overview()) is not None:
            digest = hashlib.sha256(json.dumps(overview, sort_keys=True, default=str).encode()).hexdigest()
            if digest != self._sec_hash or time.monotonic() - self._sec_sent > SECURITY_RESEND:
                extra["security"] = overview
                sent_hash = digest
        batch = self._sec_queue[:EVENTS_PER_BEAT]
        if batch:
            extra["security_events"] = batch
        return extra, sent_hash, len(batch)

    def _handle_attack(self, attack: dict[str, Any] | None) -> None:
        """The worker rejected forged requests: log it in HA and fire an event for automations."""
        if not isinstance(attack, dict):
            return
        sources = [s for s in attack.get("sources") or [] if isinstance(s, dict)][:5]
        data = {
            "count": int(attack.get("total") or 0),
            "ip": ", ".join(str(s.get("ip")) for s in sources)[:200],
            "sources": sources,
        }
        if (logins := getattr(self._bastion, "logins", None)) is not None:
            logins.record("worker_attack", data)
        self.hass.bus.async_fire(EVENT_SECURITY, {"type": "worker_attack", **data})

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
            "check_urls": self.check_urls(),
        }

    def check_urls(self) -> list[str]:
        """Public address the worker checks from outside (setting, else HA's external URL)."""
        url = (self.cfg.get("public_url") or self.hass.config.external_url or "").strip()
        return [url] if url.startswith(("https://", "http://")) else []

    async def _async_tick(self, _now: datetime | None = None) -> None:
        due = time.monotonic() - self._last_beat >= self.interval - TICK / 2
        if due or self.engine.state in ACTIVE_STATES:
            await self._async_heartbeat()

    async def _async_heartbeat(self) -> None:
        if not self.enabled:
            return
        self._last_beat = time.monotonic()
        sent_seen = set(self._acks_seen)
        extra, sent_hash, sent_events = self._security_payload()
        try:
            result = await self._async_post("/heartbeat", {**self._heartbeat_payload(), **extra})
        except (aiohttp.ClientError, TimeoutError) as err:
            self.last_error = str(err)[:200]
            _LOGGER.debug("Bastion heartbeat failed: %s", err)
            return
        self.last_ok = dt_util.utcnow().isoformat()
        self.last_error = None
        self._acks_seen -= sent_seen
        if sent_hash:
            self._sec_hash, self._sec_sent = sent_hash, time.monotonic()
        del self._sec_queue[:sent_events]
        self._handle_acks(result.get("acks") or [])
        self._handle_attack(result.get("attack"))
        if isinstance(result.get("exposure"), dict) and self.on_exposure is not None:
            self.on_exposure(result["exposure"])

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

    @staticmethod
    def _alarm_event(kind: str, entry: dict[str, Any]) -> dict[str, Any]:
        """Alarm log entry as the worker stores it; the uid makes resending safe."""
        detail = {k: entry[k] for k in ("target", "delay", "previous", "reason") if entry.get(k) not in (None, "")}
        for key in ("bypassed", "sensors"):
            if entry.get(key):
                detail[key] = [str(x)[:60] for x in entry[key]][:20]
        when = dt_util.parse_datetime(str(entry.get("time") or "")) or dt_util.utcnow()
        sensor = entry.get("name") or entry.get("sensor")
        uid = hashlib.sha256(f"{when.isoformat()}|{kind}|{sensor}|{entry.get('user')}".encode()).hexdigest()[:24]
        return {
            "uid": uid,
            "ts": int(when.timestamp()),
            "event": kind,
            "state": entry.get("state"),
            "mode": entry.get("mode"),
            "incident": entry.get("incident"),
            "sensor": sensor,
            "room": entry.get("room"),
            "user": entry.get("user"),
            "reason": entry.get("reason"),
            "sensors": detail.get("sensors"),
            "detail": detail,
        }

    async def async_send_event(self, kind: str, entry: dict[str, Any], *, push: bool) -> None:
        """Store an alarm event at the worker (and push it if requested)."""
        if not self.enabled or kind not in RELAY_EVENTS:
            return
        event = self._alarm_event(kind, entry)
        payload = {
            **self._snapshot(),
            **event,
            "incident": event["incident"] or self.engine.incident,
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
