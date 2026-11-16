"""Alarm system: state machine, sensors, codes and actions.

States: disarmed -> arming (exit delay) -> armed_home | armed_night | armed_away
        armed_* -> pending (entry delay) -> triggered -> armed_* (re-arm) | disarmed

Sensor types
    instant   triggers immediately in the modes it is assigned to
    delayed   starts the entry delay (pending) first
    always    triggers in every state, also when disarmed (smoke, water, tamper)

The configuration and the current state are persisted, so the alarm stays
armed across restarts. Codes are stored as scrypt hashes only.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from functools import partial
import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import DOMAIN, EVENT_SECURITY, STORAGE_VERSION
from .sounds import AlarmSounds, default_sounds

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY_ALARM = f"{DOMAIN}.alarm"
SIGNAL_ALARM = f"{DOMAIN}_alarm"
EVENT_ALARM = f"{DOMAIN}_alarm"

DISARMED = "disarmed"
ARMING = "arming"
PENDING = "pending"
TRIGGERED = "triggered"
MODES = ("home", "night", "away")
ARMED = {"home": "armed_home", "night": "armed_night", "away": "armed_away"}

SENSOR_TYPES = ("instant", "delayed", "always")
ACTIVE_STATES = {"on", "open", "opening", "unlocked", "detected", "wet", "home"}
SUPPORTED_DOMAINS = ("binary_sensor", "lock", "cover", "input_boolean", "switch")

MAX_WRONG_CODES = 5
LOCKOUT_SECONDS = 300
LOG_SIZE = 300
NOTIFY_EVENTS = (
    "triggered",
    "pending",
    "armed",
    "disarmed",
    "arm_failed",
    "wrong_code",
    "sensor_unavailable",
    "acknowledged",
    "unarmed",
)


def default_config() -> dict[str, Any]:
    """Factory defaults."""
    return {
        "rooms": [],
        "sensors": {},
        "modes": {
            "away": {"exit": 60, "entry": 30},
            "home": {"exit": 0, "entry": 30},
            "night": {"exit": 0, "entry": 15},
        },
        "trigger_time": 180,
        "rearm": True,
        "require_code_arm": False,
        "sabotage_triggers": True,
        "actions": {
            "sirens": [],
            "lights": [],
            "warning": [],
            "notify_events": ["triggered", "pending", "armed", "disarmed", "arm_failed", "wrong_code", "acknowledged"],
            "critical_push": True,
        },
        "sounds": default_sounds(),
        "codes": [],
        "worker": {
            "url": "",
            "secret": secrets.token_urlsafe(32),
            "interval": 120,
            "enabled": False,
            "cameras": [],
            "snapshots": 3,
            "public_url": "",
        },
        # Remote control from the worker dashboard (passkey) and the "nobody home" reminder.
        "remote": {
            "enabled": False,
            "disarm": False,
            "reminder": False,
            "reminder_minutes": 20,
            "persons": [],
        },
    }


def _hash_code(code: str, salt: bytes) -> str:
    return hashlib.scrypt(code.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32).hex()


def _match_code(code: str, codes: list[tuple[str, str, str]]) -> str | None:
    """Name of the matching code (executor, constant time per code)."""
    found = None
    for name, salt, digest in codes:
        if hmac.compare_digest(_hash_code(code, bytes.fromhex(salt)), digest):
            found = found or name
    return found


def is_active(state: State | None) -> bool | None:
    """True if a sensor reports an open/active state, None if unavailable."""
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    return state.state in ACTIVE_STATES


class AlarmError(HomeAssistantError):
    """Arming or disarming failed."""

    def __init__(self, reason: str, detail: Any = None) -> None:
        """Init with a reason key."""
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class AlarmEngine:
    """The alarm system."""

    def __init__(self, hass: HomeAssistant, bastion) -> None:
        """Init."""
        self.hass = hass
        self.bastion = bastion
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY_ALARM)
        self.config: dict[str, Any] = default_config()
        self.state: str = DISARMED
        self.mode: str | None = None
        self.target: str | None = None
        self.since: str = dt_util.utcnow().isoformat()
        self.until: str | None = None
        self.triggered_by: dict[str, Any] | None = None
        self.bypassed: list[str] = []
        self.armed_at: str | None = None
        # One id per alarm incident (entry delay and/or alarm until disarm or re-arm).
        self.incident: str | None = None
        self.sounds = AlarmSounds(hass, lambda: self.config.get("sounds"))
        self._activation_timers: list[CALLBACK_TYPE] = []
        self._not_live: set[str] = set()
        self.log: list[dict[str, Any]] = []
        self._timer: CALLBACK_TYPE | None = None
        self._siren_timer: CALLBACK_TYPE | None = None
        self._unsub_sensors: CALLBACK_TYPE | None = None
        self._unsub_security: CALLBACK_TYPE | None = None
        self._wrong: list[float] = []
        self._locked_until: float = 0
        self.on_event: Callable[[str, dict[str, Any]], None] | None = None

    # ---------------------------------------------------------------- storage
    async def async_setup(self) -> None:
        """Load config and state, resume timers, start listening."""
        data = await self._store.async_load() or {}
        config = default_config()
        for key, value in (data.get("config") or {}).items():
            if isinstance(config.get(key), dict) and isinstance(value, dict):
                config[key] = {**config[key], **value}
            else:
                config[key] = value
        self.config = config
        saved = data.get("state") or {}
        self.state = saved.get("state", DISARMED)
        self.mode = saved.get("mode")
        self.target = saved.get("target")
        self.since = saved.get("since") or self.since
        self.until = saved.get("until")
        self.triggered_by = saved.get("triggered_by")
        self.bypassed = list(saved.get("bypassed") or [])
        self.armed_at = saved.get("armed_at")
        self.incident = saved.get("incident")
        self.log = list(data.get("log") or [])[-LOG_SIZE:]
        self._listen()
        self._resume()
        if not data:
            self._save()

    async def async_unload(self) -> None:
        """Stop timers and listeners."""
        self._cancel_activation()
        for unsub in (self._timer, self._siren_timer, self._unsub_sensors, self._unsub_security):
            if unsub is not None:
                unsub()
        self._timer = self._siren_timer = self._unsub_sensors = self._unsub_security = None
        await self.sounds.async_unload()
        await self._store.async_save(self._data())

    def _data(self) -> dict[str, Any]:
        return {
            "config": self.config,
            "state": {
                "state": self.state,
                "mode": self.mode,
                "target": self.target,
                "since": self.since,
                "until": self.until,
                "triggered_by": self.triggered_by,
                "bypassed": self.bypassed,
                "armed_at": self.armed_at,
                "incident": self.incident,
            },
            "log": self.log[-LOG_SIZE:],
        }

    def _save(self) -> None:
        self._store.async_delay_save(self._data, 1)
        async_dispatcher_send(self.hass, SIGNAL_ALARM)

    # ------------------------------------------------------------- configuration
    async def async_update_config(self, changes: dict[str, Any]) -> None:
        """Apply configuration from the panel (already validated)."""
        for key, value in changes.items():
            if key in ("codes",):
                continue
            if isinstance(self.config.get(key), dict) and isinstance(value, dict):
                self.config[key] = {**self.config[key], **value}
            else:
                self.config[key] = value
        known = {s for room in self.config["rooms"] for s in room.get("sensors", [])}
        self.config["sensors"] = {k: v for k, v in self.config["sensors"].items() if k in known}
        self._listen()
        self._save()

    async def async_set_code(self, name: str, code: str, code_id: str | None = None) -> str:
        """Add or replace a code (stored hashed, hashing runs in the executor)."""
        if len(code) < 4:
            raise AlarmError("code_too_short")
        salt = os.urandom(16)
        digest = await self.hass.async_add_executor_job(_hash_code, code, salt)
        entry = {
            "id": code_id or secrets.token_hex(4),
            "name": name.strip()[:40] or "Code",
            "salt": salt.hex(),
            "hash": digest,
            "numeric": code.isdigit(),
        }
        self.config["codes"] = [c for c in self.config["codes"] if c["id"] != entry["id"]] + [entry]
        self._save()
        return entry["id"]

    def delete_code(self, code_id: str) -> None:
        """Remove a code."""
        self.config["codes"] = [c for c in self.config["codes"] if c["id"] != code_id]
        self._save()

    def regenerate_worker_secret(self) -> str:
        """New shared secret for the Cloudflare worker."""
        self.config["worker"]["secret"] = secrets.token_urlsafe(32)
        self._save()
        return self.config["worker"]["secret"]

    @property
    def has_codes(self) -> bool:
        """True if at least one code is configured."""
        return bool(self.config["codes"])

    @property
    def numeric_codes(self) -> bool:
        """True if all codes are digits only."""
        return all(c.get("numeric") for c in self.config["codes"])

    async def _async_check_code(self, code: str | None, user_name: str | None) -> str | None:
        """Return the matching code name; raises on wrong code or lockout."""
        if not self.has_codes:
            return user_name
        now = time.monotonic()
        if now < self._locked_until:
            raise AlarmError("locked", int(self._locked_until - now))
        if code:
            codes = [(c["name"], c["salt"], c["hash"]) for c in self.config["codes"]]
            match = await self.hass.async_add_executor_job(_match_code, code, codes)
            if match is not None:
                self._wrong.clear()
                return match
        now = time.monotonic()
        self._wrong = [t for t in self._wrong if now - t < LOCKOUT_SECONDS] + [now]
        if len(self._wrong) >= MAX_WRONG_CODES:
            self._locked_until = now + LOCKOUT_SECONDS
            self._wrong.clear()
        self._record("wrong_code", user=user_name)
        raise AlarmError("wrong_code")

    # ------------------------------------------------------------------ helpers
    def sensor_config(self, entity_id: str) -> dict[str, Any]:
        """Per sensor settings with defaults."""
        return {
            "modes": list(MODES),
            "type": "delayed",
            "bypass": False,
            "exit_delay": None,
            "entry_delay": None,
            "name": None,
            **self.config["sensors"].get(entity_id, {}),
        }

    def _mode_delay(self, mode: str | None, kind: str) -> int:
        return int((self.config["modes"].get(mode or "", {}) or {}).get(kind, 0) or 0)

    def activation_delay(self, entity_id: str, mode: str | None = None) -> int:
        """Seconds after the arm command until the sensor is watched."""
        own = self.sensor_config(entity_id).get("exit_delay")
        mode_exit = self._mode_delay(mode or self.mode, "exit")
        return max(mode_exit, int(own)) if own is not None else mode_exit

    def entry_delay(self, entity_id: str) -> int:
        """Seconds between the sensor opening and the alarm."""
        own = self.sensor_config(entity_id).get("entry_delay")
        return int(own) if own is not None else self._mode_delay(self.mode, "entry")

    def _is_live(self, entity_id: str) -> bool:
        """True once the activation delay of the sensor has passed."""
        return entity_id not in self._not_live

    def room_of(self, entity_id: str) -> dict[str, Any] | None:
        """Room a sensor belongs to."""
        return next((r for r in self.config["rooms"] if entity_id in r.get("sensors", [])), None)

    def all_sensors(self) -> list[str]:
        """Every sensor assigned to a room."""
        out: list[str] = []
        for room in self.config["rooms"]:
            out.extend(s for s in room.get("sensors", []) if s not in out)
        return out

    def open_sensors(self, mode: str) -> list[str]:
        """Sensors of a mode that are open right now (bypassable ones excluded)."""
        out = []
        for entity_id in self.all_sensors():
            cfg = self.sensor_config(entity_id)
            if mode not in cfg["modes"] and cfg["type"] != "always":
                continue
            # Exit route sensors (own activation delay) may be open while leaving.
            if cfg["type"] != "always" and (cfg.get("exit_delay") or 0) > 0:
                continue
            if is_active(self.hass.states.get(entity_id)) and not cfg["bypass"]:
                out.append(entity_id)
        return out

    def _name(self, entity_id: str) -> str:
        """Own name from the alarm settings, else the Home Assistant name."""
        if own := (self.config["sensors"].get(entity_id) or {}).get("name"):
            return str(own)
        state = self.hass.states.get(entity_id)
        return (state.attributes.get("friendly_name") if state else None) or entity_id

    def _record(self, kind: str, **data: Any) -> dict[str, Any]:
        entry = {"time": dt_util.utcnow().isoformat(), "type": kind, "state": self.state, "mode": self.mode, **data}
        if self.incident and "incident" not in data:
            entry["incident"] = self.incident
        self.log.append(entry)
        del self.log[:-LOG_SIZE]
        self.hass.bus.async_fire(EVENT_ALARM, entry)
        if self.on_event is not None:
            self.on_event(kind, entry)
        self.sounds.on_event(kind, self.state)
        self._save()
        return entry

    def _new_incident(self) -> None:
        if self.incident is None:
            self.incident = secrets.token_hex(6)

    def _end_incident(self) -> None:
        if self.incident is not None:
            self.incident = None
            self._save()

    def record_ack(self, by: str, incident: str | None, kind: str | None = None) -> None:
        """A Pushover alarm was acknowledged (reported by the worker)."""
        self._record("acknowledged", user=by, channel="pushover", incident=incident, ack=kind)

    def record_unarmed(self, minutes: int, persons: list[str]) -> None:
        """Everybody left, the alarm is still disarmed (reminder)."""
        self._record("unarmed", minutes=minutes, persons=persons[:10])

    def context(self) -> dict[str, list[str]]:
        """Open and unavailable sensors (for the worker's offline report)."""
        open_now: list[str] = []
        unavailable: list[str] = []
        for entity_id in self.all_sensors():
            active = is_active(self.hass.states.get(entity_id))
            if active is None:
                unavailable.append(self._name(entity_id))
            elif active:
                open_now.append(self._name(entity_id))
        return {"open": open_now[:10], "unavailable": unavailable[:10]}

    def _set_state(self, state: str, *, mode: str | None = None, until: float | None = None) -> None:
        self.state = state
        if mode is not None or state == DISARMED:
            self.mode = mode
        self.since = dt_util.utcnow().isoformat()
        self.until = (dt_util.utcnow() + timedelta(seconds=until)).isoformat() if until else None
        self._save()

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer()
            self._timer = None

    # ----------------------------------------------------------------- commands
    async def async_arm(
        self,
        mode: str,
        code: str | None = None,
        *,
        user: str | None = None,
        force: bool = False,
        trusted: bool = False,
    ) -> None:
        """Arm in a mode (with exit delay). trusted = authenticated elsewhere (passkey)."""
        if mode not in MODES:
            raise AlarmError("invalid_mode", mode)
        # Re-arming silences the sirens, so during an alarm a code is always required.
        needs_code = not trusted and (
            self.config["require_code_arm"] or bool(code) or self.state in (TRIGGERED, PENDING)
        )
        who = await self._async_check_code(code, user) if needs_code else user
        open_now = self.open_sensors(mode)
        if open_now and not force:
            self._record("arm_failed", target=mode, user=who, sensors=[self._name(s) for s in open_now])
            raise AlarmError("open_sensors", [self._name(s) for s in open_now])
        self._cancel_timer()
        self._sirens(False)
        self.triggered_by = None
        self.armed_at = dt_util.utcnow().isoformat()
        self.bypassed = open_now + [
            s for s in self.all_sensors() if self.sensor_config(s)["bypass"] and is_active(self.hass.states.get(s))
        ]
        delay = int(self.config["modes"].get(mode, {}).get("exit", 0) or 0)
        self.target = mode
        if delay > 0:
            self._set_state(ARMING, mode=mode, until=delay)
            self._timer = async_call_later(self.hass, delay, self._exit_done)
            self._record("arming", target=mode, user=who, delay=delay, bypassed=[self._name(s) for s in self.bypassed])
            self._warning(True)
        else:
            self._set_state(ARMED[mode], mode=mode)
            self._record("armed", target=mode, user=who, bypassed=[self._name(s) for s in self.bypassed])
        self._end_incident()
        self._schedule_activation()

    @callback
    def _exit_done(self, _now: datetime | None = None) -> None:
        self._timer = None
        self._warning(False)
        if self.state == ARMING and self.target:
            self._set_state(ARMED[self.target], mode=self.target)
            self._record("armed", target=self.target)
            self._activation_check()

    def _cancel_activation(self) -> None:
        for unsub in self._activation_timers:
            unsub()
        self._activation_timers = []
        self._not_live = set()

    def _schedule_activation(self) -> None:
        """Sensors with their own activation delay become live by timer (also after a restart)."""
        self._cancel_activation()
        self._not_live = set()
        armed_at = dt_util.parse_datetime(self.armed_at or "")
        if armed_at is None or self.mode not in MODES:
            return
        elapsed = max(0.0, (dt_util.utcnow() - armed_at).total_seconds())
        system_exit = self._mode_delay(self.mode, "exit")
        groups: dict[int, set[str]] = {}
        for sensor in self.all_sensors():
            delay = self.activation_delay(sensor)
            if delay > system_exit and delay > elapsed:
                groups.setdefault(delay, set()).add(sensor)
        for delay, sensors in groups.items():
            self._not_live |= sensors
            self._activation_timers.append(
                async_call_later(self.hass, delay - elapsed, partial(self._activate, frozenset(sensors)))
            )

    @callback
    def _activate(self, sensors: frozenset[str], _now: datetime | None = None) -> None:
        self._not_live -= sensors
        self._activation_check()

    @callback
    def _activation_check(self, _now: datetime | None = None) -> None:
        """Sensors that became live while open start the entry delay / alarm."""
        if not self.state.startswith("armed_"):
            return
        for entity_id in self.all_sensors():
            cfg = self.sensor_config(entity_id)
            if cfg["type"] == "always" or entity_id in self.bypassed or self.mode not in cfg["modes"]:
                continue
            if self._is_live(entity_id) and is_active(self.hass.states.get(entity_id)):
                self._handle_active(entity_id)
                if self.state in (PENDING, TRIGGERED):
                    return

    async def async_disarm(self, code: str | None = None, *, user: str | None = None, trusted: bool = False) -> None:
        """Disarm (code required when codes exist, unless authenticated elsewhere)."""
        who = user if trusted else await self._async_check_code(code, user)
        was = self.state
        self._cancel_timer()
        self._cancel_activation()
        self._sirens(False)
        self._warning(False)
        self.bypassed = []
        self.target = None
        self.armed_at = None
        self._set_state(DISARMED)
        self._record("disarmed", user=who, previous=was)
        self._end_incident()

    async def async_trigger(self, reason: str, *, sensor: str | None = None, user: str | None = None) -> None:
        """Raise the alarm."""
        if self.state == TRIGGERED:
            return
        self._cancel_timer()
        self._warning(False)
        room = self.room_of(sensor) if sensor else None
        self.triggered_by = {
            "reason": reason,
            "sensor": sensor,
            "name": self._name(sensor) if sensor else None,
            "room": room["name"] if room else None,
            "time": dt_util.utcnow().isoformat(),
        }
        trigger_time = int(self.config.get("trigger_time") or 0)
        self._new_incident()
        self._set_state(TRIGGERED, mode=self.mode, until=trigger_time or None)
        self._sirens(True)
        if trigger_time:
            self._siren_timer = async_call_later(self.hass, trigger_time, self._trigger_done)
        self._record("triggered", **self.triggered_by, user=user)

    @callback
    def _trigger_done(self, _now: datetime | None = None) -> None:
        self._siren_timer = None
        self._sirens(False)
        if self.state != TRIGGERED:
            return
        if self.mode not in ARMED:
            # Alarm of a 24 h sensor while disarmed: back to disarmed after the sirens.
            self._set_state(DISARMED)
            self._record("reset")
            self._end_incident()
        elif self.config.get("rearm", True):
            self._set_state(ARMED[self.mode], mode=self.mode)
            self._record("rearmed", target=self.mode)
            self._end_incident()
        else:
            self.until = None
            self._save()

    # ------------------------------------------------------------------ sensors
    def _listen(self) -> None:
        if self._unsub_sensors is not None:
            self._unsub_sensors()
            self._unsub_sensors = None
        sensors = self.all_sensors()
        if sensors:
            self._unsub_sensors = async_track_state_change_event(self.hass, sensors, self._on_sensor)
        if self._unsub_security is None:
            self._unsub_security = self.hass.bus.async_listen(EVENT_SECURITY, self._on_security)

    @callback
    def _on_sensor(self, event: Event) -> None:
        entity_id = event.data["entity_id"]
        new = event.data.get("new_state")
        active = is_active(new)
        cfg = self.sensor_config(entity_id)
        if active is None:
            if self.state.startswith("armed_") and self.mode in cfg["modes"]:
                self._record("sensor_unavailable", sensor=entity_id, name=self._name(entity_id))
            return
        if not active:
            if entity_id in self.bypassed:
                # A bypassed sensor that closes is watched again from now on.
                self.bypassed.remove(entity_id)
                self._save()
            return
        self._handle_active(entity_id)

    @callback
    def _handle_active(self, entity_id: str) -> None:
        """A sensor reports open / active."""
        cfg = self.sensor_config(entity_id)
        if self.state == TRIGGERED:
            return
        if cfg["type"] == "always":
            delay = int(cfg.get("entry_delay") or 0)
            if delay > 0:
                if self.state != PENDING:
                    self._start_pending(entity_id, delay)
            else:
                self.hass.async_create_task(self.async_trigger("sensor", sensor=entity_id), eager_start=True)
            return
        if entity_id in self.bypassed:
            return
        if self.state == PENDING:
            if cfg["type"] == "instant" and self.mode in cfg["modes"] and self._is_live(entity_id):
                self.hass.async_create_task(self.async_trigger("sensor", sensor=entity_id), eager_start=True)
            return
        if not self.state.startswith("armed_") or self.mode not in cfg["modes"] or not self._is_live(entity_id):
            return
        delay = self.entry_delay(entity_id)
        if cfg["type"] == "instant" or delay <= 0:
            self.hass.async_create_task(self.async_trigger("sensor", sensor=entity_id), eager_start=True)
            return
        self._start_pending(entity_id, delay)

    def _start_pending(self, entity_id: str, delay: int) -> None:
        room = self.room_of(entity_id)
        self.triggered_by = {
            "reason": "sensor",
            "sensor": entity_id,
            "name": self._name(entity_id),
            "room": room["name"] if room else None,
            "time": dt_util.utcnow().isoformat(),
        }
        self._new_incident()
        self._set_state(PENDING, mode=self.mode, until=delay)
        self._timer = async_call_later(self.hass, delay, self._entry_done)
        self._warning(True)
        self._record(
            "pending", sensor=entity_id, name=self._name(entity_id), room=self.triggered_by["room"], delay=delay
        )

    @callback
    def _entry_done(self, _now: datetime | None = None) -> None:
        self._timer = None
        if self.state == PENDING:
            sensor = (self.triggered_by or {}).get("sensor")
            self.hass.async_create_task(self.async_trigger("entry_timeout", sensor=sensor), eager_start=True)

    @callback
    def _on_security(self, event: Event) -> None:
        kind = event.data.get("type")
        if kind not in ("sabotage", "tamper", "canary") or not self.config.get("sabotage_triggers", True):
            return
        if self.state.startswith("armed_") or self.state == PENDING:
            self.hass.async_create_task(self.async_trigger(kind), eager_start=True)

    def _resume(self) -> None:
        """Continue a countdown that was running when HA stopped."""
        until = dt_util.parse_datetime(self.until or "")
        remaining = (until - dt_util.utcnow()).total_seconds() if until else 0
        if self.state == ARMING:
            if remaining > 0:
                self._timer = async_call_later(self.hass, remaining, self._exit_done)
            else:
                self._exit_done()
        elif self.state == PENDING:
            # HA went down during the entry delay: treat as an alarm.
            if remaining > 0:
                self._timer = async_call_later(self.hass, remaining, self._entry_done)
            else:
                self._entry_done()
        elif self.state == TRIGGERED:
            if remaining > 0:
                self._siren_timer = async_call_later(self.hass, remaining, self._trigger_done)
            else:
                self._trigger_done()
        elif self.state.startswith("armed_"):
            self._schedule_activation()

    # ------------------------------------------------------------------ actions
    def _switch(self, entities: list[str], on: bool) -> None:
        if entities:
            self.hass.async_create_task(self._async_switch(entities, on), eager_start=True)

    async def _async_switch(self, entities: list[str], on: bool) -> None:
        # A broken siren or light must never stop the alarm logic.
        try:
            await self.hass.services.async_call(
                "homeassistant", "turn_on" if on else "turn_off", {"entity_id": entities}, blocking=False
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Bastion alarm action failed for %s", entities)

    def _sirens(self, on: bool) -> None:
        actions = self.config["actions"]
        self._switch(list(actions.get("sirens") or []), on)
        if on:
            self._switch(list(actions.get("lights") or []), True)
        else:
            self.sounds.sirens_off()
            if self._siren_timer is not None:
                self._siren_timer()
                self._siren_timer = None

    def _warning(self, on: bool) -> None:
        self._switch(list(self.config["actions"].get("warning") or []), on)

    # ------------------------------------------------------------------ status
    def status(self) -> dict[str, Any]:
        """For the entity and the panel."""
        return {
            "state": self.state,
            "mode": self.mode,
            "target": self.target,
            "since": self.since,
            "until": self.until,
            "triggered_by": self.triggered_by,
            "bypassed": self.bypassed,
            "has_codes": self.has_codes,
            "numeric_codes": self.numeric_codes,
            "require_code_arm": self.config["require_code_arm"],
            "locked": max(0, int(self._locked_until - time.monotonic())),
            "incident": self.incident,
        }

    def public_config(self) -> dict[str, Any]:
        """Configuration without code hashes."""
        cfg = {k: v for k, v in self.config.items() if k != "codes"}
        cfg["codes"] = [{"id": c["id"], "name": c["name"]} for c in self.config["codes"]]
        return cfg
