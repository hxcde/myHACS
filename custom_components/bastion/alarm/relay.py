"""Link to the Cloudflare worker: heartbeat, alarm log, camera images, acknowledgements.

Home Assistant sends a signed heartbeat every few minutes (every 15 seconds
while an alarm runs). If heartbeats stop while the alarm is armed (power cut,
internet cut, sabotage), the worker alerts you with the last known state. Every
alarm event is stored by the worker (off-site log), alarms are pushed from
there, and Pushover acknowledgements come back with the heartbeat response.

Signature: hex(HMAC-SHA256(secret, f"{timestamp}.{body}")) in
X-Bastion-Signature, timestamp in X-Bastion-Timestamp (replay window 5 min).

Remote control: with remote control on, Home Assistant fetches commands from
the worker (every 15 s, every 2 s while someone is about to send one). A
command carries the worker's signature, expires after 90 seconds and is only
run once; disarming needs its own permission.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import logging
import re
import time
from typing import Any

import aiohttp
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.util import dt as dt_util

from ..const import EVENT_SECURITY, SEVERITY_WEIGHT
from .engine import AlarmError
from .floorplan import plan_hash
from .household import SIGNAL_HOUSEHOLD

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
    "unarmed",
)
ACTIVE_STATES = ("pending", "triggered")
TICK = 15
FAST_POLL = 2
COMMAND_MAX_AGE = 180
COMMAND_ID = re.compile(r"^[a-f0-9]{16}$")
# Messages the worker forwards; types that come from the worker are not echoed back to it.
WORKER_TYPES = ("worker_attack", "dashboard_access", "passkey_added")
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


def command_signature(secret: str, cmd: dict[str, Any]) -> str:
    """Signature of a remote command (same value as the worker computes)."""
    force = 1 if cmd.get("force") else 0
    msg = f"command.{cmd.get('id')}.{cmd.get('action')}.{cmd.get('mode') or ''}.{force}.{cmd.get('ts')}.{cmd.get('by') or ''}"
    return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()


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
        self.on_notice = None
        self.dashboard_url: str | None = None
        self._notices_seen: set[int] = set()
        self._notices_done: set[int] = set()
        self._cmd_done: dict[str, float] = {}
        self._cmd_results: list[dict[str, Any]] = []
        self._polling = False
        self._unsub_fast: CALLBACK_TYPE | None = None
        self._unsub_household: CALLBACK_TYPE | None = None
        self._presence_beat = 0.0
        self._zones_sent: str | None = None
        self._floorplan_acked: str | None = None
        self.last_commands: list[dict[str, Any]] = []

    @property
    def cfg(self) -> dict[str, Any]:
        """Worker settings."""
        return self.engine.config.get("worker") or {}

    @property
    def enabled(self) -> bool:
        """True if a worker is configured."""
        return bool(self.cfg.get("enabled") and self.cfg.get("url") and self.cfg.get("secret"))

    @property
    def remote(self) -> dict[str, Any]:
        """Remote control settings."""
        return self.engine.config.get("remote") or {}

    @property
    def remote_enabled(self) -> bool:
        """True if commands are fetched from the worker."""
        return self.enabled and bool(self.remote.get("enabled"))

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
        self._unsub_household = async_dispatcher_connect(self.hass, SIGNAL_HOUSEHOLD, self._on_household)
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
        if self._unsub_fast is not None:
            self._unsub_fast()
            self._unsub_fast = None
        if self._unsub_household is not None:
            self._unsub_household()
            self._unsub_household = None
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
        if not kind or kind in WORKER_TYPES or entry.get("source") == "worker":
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

    @callback
    def _on_household(self) -> None:
        """Someone came or left: tell the dashboard soon (at most every 20 s)."""
        if time.monotonic() - self._presence_beat > 20:
            self._presence_beat = time.monotonic()
            self._spawn(self._async_heartbeat())

    def _presence(self) -> list[dict[str, Any]] | None:
        household = getattr(self._bastion, "household", None)
        return household.worker_payload() if household is not None and household.people else None

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
            "notices_seen": sorted(self._notices_seen),
            "check_urls": self.check_urls(),
            "remote": {"enabled": bool(self.remote.get("enabled")), "disarm": bool(self.remote.get("disarm"))},
            "presence": self._presence(),
            "zones": self.engine.zones(),
            **self._floorplan_payload(),
        }

    def _floorplan_payload(self) -> dict[str, Any]:
        """The plan travels only when the worker does not have this version yet."""
        plan = self.engine.config.get("floorplan")
        digest = plan_hash(plan)
        payload: dict[str, Any] = {"floorplan_hash": digest}
        if digest and digest != self._floorplan_acked:
            payload["floorplan"] = plan
        return payload

    def check_urls(self) -> list[str]:
        """Public address the worker checks from outside (setting, else HA's external URL)."""
        url = (self.cfg.get("public_url") or self.hass.config.external_url or "").strip()
        return [url] if url.startswith(("https://", "http://")) else []

    async def _async_tick(self, _now: datetime | None = None) -> None:
        due = time.monotonic() - self._last_beat >= self.interval - TICK / 2
        # A door opened or a sensor dropped out: the dashboard shows it within one tick.
        zones = hashlib.sha256(json.dumps(self.engine.zones(health=False), sort_keys=True).encode()).hexdigest()
        changed = self._zones_sent is not None and zones != self._zones_sent
        if due or changed or self.engine.state in ACTIVE_STATES:
            self._zones_sent = zones
            await self._async_heartbeat()
        elif self._zones_sent is None:
            self._zones_sent = zones
        if self.remote_enabled:
            await self.async_poll_commands()

    async def _async_heartbeat(self) -> None:
        if not self.enabled:
            return
        self._last_beat = time.monotonic()
        sent_seen = set(self._acks_seen)
        sent_notices = set(self._notices_seen)
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
        self._notices_seen -= sent_notices
        if sent_hash:
            self._sec_hash, self._sec_sent = sent_hash, time.monotonic()
        del self._sec_queue[:sent_events]
        if isinstance(result.get("dashboard"), str) and result["dashboard"].startswith("https://"):
            self.dashboard_url = result["dashboard"].rstrip("/")
        self._floorplan_acked = result.get("floorplan_hash") if isinstance(result.get("floorplan_hash"), str) else None
        self._handle_acks(result.get("acks") or [])
        self._handle_notices(result.get("notices") or [])
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

    def _handle_notices(self, notices: list[dict[str, Any]]) -> None:
        """Decoy uses, dashboard logins and new passkeys reported by the worker."""
        for notice in notices[:20]:
            if not isinstance(notice, dict) or not isinstance(notice.get("id"), int):
                continue
            self._notices_seen.add(notice["id"])
            if notice["id"] in self._notices_done:
                continue
            self._notices_done.add(notice["id"])
            data = notice.get("data") if isinstance(notice.get("data"), dict) else {}
            if self.on_notice is not None:
                self.on_notice(str(notice.get("type") or ""), data)
        if len(self._notices_done) > 300:
            self._notices_done = set(sorted(self._notices_done)[-150:])

    # ------------------------------------------------------------ remote
    async def async_poll_commands(self) -> None:
        """Fetch remote commands (and report results of the last ones)."""
        if self._polling or not self.remote_enabled:
            return
        self._polling = True
        results = self._cmd_results[:10]
        fast = False
        try:
            answer = await self._async_post("/commands", {"ts": int(time.time()), "done": results}, timeout=10)
            del self._cmd_results[: len(results)]
            fast = bool(answer.get("fast"))
            for cmd in (answer.get("commands") or [])[:5]:
                if isinstance(cmd, dict) and await self._async_run_command(cmd):
                    fast = True
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("Bastion command poll failed: %s", err)
        finally:
            self._polling = False
        if (fast or self._cmd_results) and self._unsub_fast is None and self.remote_enabled:
            self._unsub_fast = async_call_later(self.hass, FAST_POLL, self._fast_poll)

    @callback
    def _fast_poll(self, _now: datetime | None = None) -> None:
        self._unsub_fast = None
        self._spawn(self.async_poll_commands())

    async def _async_run_command(self, cmd: dict[str, Any]) -> bool:
        """Verify and run one command; returns True if it was new."""
        cid = str(cmd.get("id") or "")
        now = time.time()
        self._cmd_done = {k: v for k, v in self._cmd_done.items() if now - v < 600}
        if not COMMAND_ID.match(cid) or cid in self._cmd_done:
            return False
        self._cmd_done[cid] = now
        action = cmd.get("action")
        mode = cmd.get("mode")
        by = str(cmd.get("by") or "")[:80]
        error: str | None = None
        detail: Any = None
        if not hmac.compare_digest(command_signature(self.cfg["secret"], cmd), str(cmd.get("sig") or "")):
            error = "signature"
        elif not isinstance(cmd.get("ts"), int) or abs(now - cmd["ts"]) > COMMAND_MAX_AGE:
            error = "stale"
        elif not self.remote.get("enabled"):
            error = "disabled"
        elif action == "disarm" and not self.remote.get("disarm"):
            error = "not_allowed"
        elif action not in ("arm", "disarm"):
            error = "invalid"
        else:
            user = f"Dashboard ({by})" if by else "Dashboard"
            try:
                if action == "arm":
                    await self.engine.async_arm(str(mode), user=user, force=bool(cmd.get("force")), trusted=True)
                else:
                    await self.engine.async_disarm(user=user, trusted=True)
            except AlarmError as err:
                error, detail = err.reason, err.detail
        if error in ("signature", "stale"):
            _LOGGER.warning("Bastion rejected a remote command (%s)", error)
        entry = {"id": cid, "ok": error is None, "error": error, "detail": detail}
        self._cmd_results.append(entry)
        self.last_commands = [
            {**entry, "action": action, "mode": mode, "by": by, "time": dt_util.utcnow().isoformat()},
            *self.last_commands,
        ][:10]
        return True

    async def async_remote(self, op: str, **data: Any) -> dict[str, Any]:
        """Pairing code and passkeys at the worker (for the panel)."""
        if not self.enabled:
            return {"ok": False, "error": "not configured"}
        try:
            answer = await self._async_post("/remote", {"ts": int(time.time()), "op": op, **data})
        except (aiohttp.ClientError, TimeoutError) as err:
            return {"ok": False, "error": str(err)[:200]}
        if isinstance(answer.get("dashboard"), str) and answer["dashboard"].startswith("https://"):
            self.dashboard_url = answer["dashboard"].rstrip("/")
        return answer

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
        detail = {
            k: entry[k] for k in ("target", "delay", "previous", "reason", "minutes") if entry.get(k) not in (None, "")
        }
        for key in ("bypassed", "sensors", "persons"):
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
