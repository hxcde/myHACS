"""Anomaly detection inside Home Assistant."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
import ipaddress
import logging
import socket
import time
from typing import Any

from homeassistant.const import EVENT_CALL_SERVICE, EVENT_STATE_CHANGED, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import (
    CONF_ANOMALY_ACTIONS,
    CONF_ANOMALY_ENTITIES,
    CONF_ANOMALY_LOGIN_TIME,
    CONF_ANOMALY_OUTBOUND,
    CONF_ANOMALY_SABOTAGE,
    CONF_ANOMALY_SENSITIVITY,
    CONF_SABOTAGE_COUNT,
    CONF_SABOTAGE_WINDOW,
    DOMAIN,
    EVENT_ANOMALY,
    EVENT_SECURITY,
    SIGNAL_UPDATE,
    STORAGE_KEY_ANOMALY,
    STORAGE_VERSION,
)
from ..texts import ANOMALY_DETAIL, ANOMALY_WORDS, event_text, fmt, lang
from .stats import HourHistogram, SensorModel, bucket_index

_LOGGER = logging.getLogger(__name__)

SAMPLE_INTERVAL = timedelta(minutes=5)
OUTBOUND_INTERVAL = timedelta(minutes=2)
ACTION_LEARNING = timedelta(days=14)
OUTBOUND_LEARNING = timedelta(days=7)
STARTUP_GRACE = 600
SABOTAGE_HOLD = 1800
LOGIN_MIN = 15
ACTION_MIN = 10

SENSITIVE_SERVICES = {
    ("lock", "unlock"),
    ("lock", "open"),
    ("alarm_control_panel", "alarm_disarm"),
    ("cover", "open_cover"),
    ("valve", "open_valve"),
}
SENSITIVE_COVER_CLASSES = {"garage", "gate", "door"}
SABOTAGE_CLASSES = {
    "door",
    "window",
    "opening",
    "garage_door",
    "motion",
    "occupancy",
    "presence",
    "tamper",
    "vibration",
    "safety",
    "smoke",
    "gas",
    "moisture",
}
SABOTAGE_DOMAINS = {"camera", "alarm_control_panel", "lock"}
# A repeated deviation of the same sensor within this time is one event, not a new one.
EVENT_REPEAT = 6 * 3600

# Room climate swings for everyday reasons (shower, cooking, airing, heating). Per kind of sensor:
# smallest reported distance from the learned mean (absolute in the unit, or relative to the mean),
# how many 5-minute samples a value must stay outside the range before it is reported, and an
# ordinary range that is never unusual (22 °C after a shower is a room temperature, not an alarm).
PROFILES = {
    "temperature": {"margin": 3.0, "need": 6, "ordinary": (15.0, 27.0)},
    "temperature_f": {"margin": 5.4, "need": 6, "ordinary": (59.0, 80.6)},
    "humidity": {"margin": 20.0, "need": 6, "ordinary": (25.0, 75.0)},
    "carbon_dioxide": {"margin": 400.0, "need": 6, "ordinary": (0.0, 1400.0)},
    "volatile_organic_compounds": {"margin_rel": 0.6, "need": 6},
    "volatile_organic_compounds_parts": {"margin_rel": 0.6, "need": 6},
    "pm25": {"margin_rel": 1.0, "need": 6},
    "pm10": {"margin_rel": 1.0, "need": 6},
    "pm1": {"margin_rel": 1.0, "need": 6},
    "illuminance": {"margin_rel": 1.0, "need": 6},
}


def sensor_profile(state) -> tuple[str, dict[str, float]]:
    """Kind of sensor and its tolerance, from device class and unit."""
    attrs = state.attributes if state is not None else {}
    device_class = attrs.get("device_class")
    unit = attrs.get("unit_of_measurement") or ""
    if device_class == "temperature" or unit in ("°C", "°F", "K"):
        kind = "temperature_f" if unit == "°F" else "temperature"
    else:
        kind = device_class or "generic"
    return kind, PROFILES.get(kind, {})


def _number(value: float, language: str) -> str:
    text = f"{value:.1f}" if abs(value) < 1000 else f"{value:.0f}"
    return text.replace(".", ",") if lang(language) == "de" else text


def _read_proc_connections() -> set[str]:
    """Remote addresses of established TCP connections in our network namespace."""
    out: set[str] = set()
    for path, v6 in (("/proc/net/tcp", False), ("/proc/net/tcp6", True)):
        try:
            with open(path, encoding="ascii") as fh:
                lines = fh.readlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) < 4 or parts[3] != "01":
                continue
            addr_hex = parts[2].split(":")[0]
            try:
                raw = bytes.fromhex(addr_hex)
                if v6:
                    words = [raw[i : i + 4][::-1] for i in range(0, 16, 4)]
                    ip = ipaddress.IPv6Address(b"".join(words))
                    if ip.ipv4_mapped:
                        ip = ip.ipv4_mapped
                else:
                    ip = ipaddress.IPv4Address(raw[::-1])
            except ValueError:
                continue
            if ip.is_global:
                out.add(str(ip))
    return out


def _network_key(ip: str) -> str:
    addr = ipaddress.ip_address(ip)
    prefix = 24 if addr.version == 4 else 48
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))


def _reverse(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except (OSError, UnicodeError):
        return ""


class AnomalyEngine:
    """Learns normal behaviour and reports deviations."""

    def __init__(self, hass: HomeAssistant, notifier, options_getter) -> None:
        """Init."""
        self.hass = hass
        self.notifier = notifier
        self._options = options_getter
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY_ANOMALY)
        self.models: dict[str, SensorModel] = {}
        self.active: dict[str, list[dict[str, Any]]] = {}
        self.login_hist: dict[str, HourHistogram] = {}
        self.action_hist: dict[str, HourHistogram] = {}
        self.actors: dict[str, list[str]] = {}
        self.started: str | None = None
        self.outbound_started: str | None = None
        self.outbound_known: set[str] = set()
        self.outbound_new: deque[dict[str, Any]] = deque(maxlen=100)
        self.events: deque[dict[str, Any]] = deque(maxlen=200)
        self.sabotage_until: float = 0
        self._unavailable: deque[tuple[float, str]] = deque(maxlen=200)
        self._setup_time = time.monotonic()
        self._unsubs: list[CALLBACK_TYPE] = []
        self._notified: dict[str, float] = {}
        self._own: set[str] = set()

    # --------------------------------------------------------------- lifecycle
    async def async_setup(self) -> None:
        """Load, seed and start listeners."""
        data = await self._store.async_load() or {}
        self.models = {k: SensorModel.from_dict(v) for k, v in (data.get("models") or {}).items()}
        self.login_hist = {k: HourHistogram(list(v)) for k, v in (data.get("login") or {}).items()}
        self.action_hist = {k: HourHistogram(list(v)) for k, v in (data.get("actions") or {}).items()}
        self.actors = {k: list(v) for k, v in (data.get("actors") or {}).items()}
        self.started = data.get("started") or dt_util.utcnow().isoformat()
        self.outbound_started = data.get("outbound_started")
        self.outbound_known = set(data.get("outbound_known") or [])
        self.outbound_new.extend(data.get("outbound_new") or [])
        self.events.extend(data.get("events") or [])

        opts = self._options()
        entities = list(opts.get(CONF_ANOMALY_ENTITIES) or [])
        for entity_id in list(self.models):
            if entity_id not in entities:
                self.models.pop(entity_id)
        for entity_id in entities:
            if entity_id not in self.models:
                self.models[entity_id] = SensorModel()
                await self._async_seed(entity_id)
        if entities:
            self._unsubs.append(async_track_time_interval(self.hass, self._async_sample, SAMPLE_INTERVAL))
        if opts.get(CONF_ANOMALY_ACTIONS, True):
            self._unsubs.append(
                self.hass.bus.async_listen(EVENT_CALL_SERVICE, self._on_service_call, self._service_filter)
            )
        if opts.get(CONF_ANOMALY_SABOTAGE, True):
            self._unsubs.append(
                self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._on_state_changed, self._state_filter)
            )
        if opts.get(CONF_ANOMALY_OUTBOUND):
            if self.outbound_started is None:
                self.outbound_started = dt_util.utcnow().isoformat()
            self._unsubs.append(async_track_time_interval(self.hass, self._async_outbound, OUTBOUND_INTERVAL))
        self._schedule_save()

    async def async_unload(self) -> None:
        """Stop and save."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self._store.async_save(self._data())

    def _data(self) -> dict[str, Any]:
        return {
            "models": {k: v.to_dict() for k, v in self.models.items()},
            "login": {k: v.counts for k, v in self.login_hist.items()},
            "actions": {k: v.counts for k, v in self.action_hist.items()},
            "actors": self.actors,
            "started": self.started,
            "outbound_started": self.outbound_started,
            "outbound_known": sorted(self.outbound_known),
            "outbound_new": list(self.outbound_new),
            "events": list(self.events),
        }

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._data, 60)

    # ---------------------------------------------------------------- helpers
    async def _async_emit(
        self, kind: str, data: dict[str, Any], *, notify: bool = True, key: str | None = None, rate: float = 3600
    ) -> None:
        entry = {"time": dt_util.utcnow().isoformat(), "type": kind, **data}
        self.events.append(entry)
        self.hass.bus.async_fire(EVENT_SECURITY if kind != "anomaly" else EVENT_ANOMALY, entry)
        self._schedule_save()
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)
        if notify:
            title, message = event_text(kind, self.hass.config.language, data)
            await self.notifier.async_send(title, message, key=key or kind, rate_limit=rate)

    async def _async_seed(self, entity_id: str) -> None:
        """Seed a model with the last 30 days of hourly statistics."""
        if "recorder" not in self.hass.config.components:
            return
        try:
            from homeassistant.components.recorder import get_instance  # noqa: PLC0415
            from homeassistant.components.recorder.statistics import statistics_during_period  # noqa: PLC0415

            end = dt_util.utcnow()
            start = end - timedelta(days=30)
            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period, self.hass, start, end, {entity_id}, "hour", None, {"mean", "min", "max"}
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("No statistics for %s: %s", entity_id, err)
            return
        model = self.models[entity_id]
        for row in stats.get(entity_id, []):
            start_ts = row.get("start")
            ts = dt_util.utc_from_timestamp(start_ts) if isinstance(start_ts, (int, float)) else start_ts
            if ts is None:
                continue
            # Mean, lowest and highest value of the hour: hourly means alone hide short peaks
            # (a shower) and make the usual range far too narrow.
            for key in ("mean", "min", "max"):
                if (value := row.get(key)) is not None:
                    model.seed(dt_util.as_local(ts), float(value))

    # ---------------------------------------------------------------- sensors
    async def _async_sample(self, _now: datetime | None = None) -> None:
        z = float(self._options().get(CONF_ANOMALY_SENSITIVITY) or 3.5)
        now = dt_util.now()
        language = self.hass.config.language
        changed = False
        for entity_id, model in self.models.items():
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            try:
                value = float(state.state)
            except (TypeError, ValueError):
                continue
            model.configure(**sensor_profile(state)[1])
            anomalies = model.observe(now, value, z)
            previous = {a["type"] for a in self.active.get(entity_id, [])}
            self.active[entity_id] = anomalies
            new_types = {a["type"] for a in anomalies} - previous
            changed = changed or bool(new_types) or (bool(previous) and not anomalies)
            for anomaly in anomalies:
                if anomaly["type"] not in new_types or self._recent_event(entity_id, anomaly["type"]):
                    continue
                name = state.attributes.get("friendly_name") or entity_id
                detail = fmt(
                    ANOMALY_DETAIL[anomaly["type"]][lang(language)], self._detail_values(anomaly, state, language)
                )
                await self._async_emit(
                    "anomaly",
                    {"entity_id": entity_id, "name": name, "detail": detail, **anomaly},
                    key=f"anomaly_{entity_id}_{anomaly['type']}",
                    rate=6 * 3600,
                )
        self._schedule_save()
        if changed:
            async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    def _recent_event(self, entity_id: str, kind: str) -> bool:
        """An event of this kind for this sensor within EVENT_REPEAT: the same episode, no new entry."""
        limit = dt_util.utcnow() - timedelta(seconds=EVENT_REPEAT)
        for event in reversed(self.events):
            if event.get("entity_id") == entity_id and event.get("type") == kind and not event.get("accepted"):
                return (dt_util.parse_datetime(event.get("time") or "") or limit) > limit
        return False

    @staticmethod
    def _detail_values(anomaly: dict[str, Any], state, language: str) -> dict[str, Any]:
        """Readable numbers with unit and direction for the event text."""
        if anomaly["type"] != "deviation":
            return anomaly
        unit = state.attributes.get("unit_of_measurement") or ""
        sep = "" if unit in ("", "%") else " "
        words = ANOMALY_WORDS[lang(language)]
        return {
            **anomaly,
            "value": f"{_number(anomaly['value'], language)}{sep}{unit}",
            "low": _number(anomaly["low"], language),
            "high": f"{_number(anomaly['high'], language)}{sep}{unit}",
            "direction": words["above"] if anomaly["value"] > anomaly["high"] else words["below"],
        }

    async def async_accept(self, entity_id: str, value: float | None = None) -> bool:
        """The user marks one deviation as normal: the chosen value, else the current one.

        Only that value (and values close to it) becomes normal - never the rest of the history,
        which may hold a real incident.
        """
        model = self.models.get(entity_id)
        if model is None:
            return False
        if value is None:
            current = [a["value"] for a in self.active.get(entity_id, []) if a.get("type") == "deviation"]
            if not current:
                return False
            value = current[-1]
        model.accept(float(value))
        self.active[entity_id] = [
            a
            for a in self.active.get(entity_id, [])
            if a.get("type") != "deviation" or not model.is_accepted(a["value"])
        ]
        for event in self.events:
            if (
                event.get("entity_id") == entity_id
                and event.get("type") == "deviation"
                and isinstance(event.get("value"), (int, float))
                and model.is_accepted(event["value"])
            ):
                event["accepted"] = True
        self._schedule_save()
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)
        return True

    def entity_state(self, entity_id: str) -> dict[str, Any]:
        """State for the per sensor binary sensor."""
        model = self.models.get(entity_id)
        active = self.active.get(entity_id, [])
        info: dict[str, Any] = {"active": bool(active), "anomalies": active}
        if model is not None:
            bucket = model.buckets[bucket_index(dt_util.now())]
            info["expected_mean"] = round(bucket.mean, 3) if bucket.n else None
            info["expected_std"] = round(bucket.std, 3) if bucket.n > 1 else None
            info["samples"] = model.samples
            info["learned_buckets"] = sum(1 for b in model.buckets if b.n >= 36)
            info["accepted"] = model.accepted
        return info

    # ----------------------------------------------------------------- logins
    async def async_on_login(self, user_id: str, user_name: str) -> None:
        """Called by the login monitor for every successful login."""
        if not self._options().get(CONF_ANOMALY_LOGIN_TIME, True):
            return
        hour = dt_util.now().hour
        hist = self.login_hist.setdefault(user_id, HourHistogram())
        if hist.unusual(hour, LOGIN_MIN):
            await self._async_emit(
                "unusual_login_time",
                {"user": user_name, "user_id": user_id, "hour": f"{hour:02d}"},
                key=f"login_time_{user_id}",
            )
        hist.add(hour)
        self._schedule_save()

    # ---------------------------------------------------------------- actions
    @callback
    def _service_filter(self, event_data: dict[str, Any]) -> bool:
        return (event_data.get("domain"), event_data.get("service")) in SENSITIVE_SERVICES

    @callback
    def _on_service_call(self, event: Event) -> None:
        self.hass.async_create_task(self._async_on_service_call(event), eager_start=True)

    async def _async_on_service_call(self, event: Event) -> None:
        domain = event.data.get("domain")
        service = event.data.get("service")
        service_data = event.data.get("service_data") or {}
        entities = service_data.get("entity_id") or []
        if isinstance(entities, str):
            entities = [entities]
        if domain == "cover":
            entities = [
                e
                for e in entities
                if (s := self.hass.states.get(e)) is not None
                and s.attributes.get("device_class") in SENSITIVE_COVER_CLASSES
            ]
            if not entities:
                return
        user_id = event.context.user_id
        actor_name = "automation"
        if user_id:
            user = await self.hass.auth.async_get_user(user_id)
            actor_name = (user.name if user else None) or user_id[:8]
        actor = user_id or "automation"
        key = f"{domain}.{service}"
        hour = dt_util.now().hour
        learning = dt_util.utcnow() - (dt_util.parse_datetime(self.started or "") or dt_util.utcnow()) < ACTION_LEARNING
        actors = self.actors.setdefault(key, [])
        hist = self.action_hist.setdefault(f"{key}|{actor}", HourHistogram())
        reason = None
        if not learning and user_id:
            if actor not in actors:
                reason = "first time" if lang(self.hass.config.language) == "en" else "erstmals"
            elif hist.unusual(hour, ACTION_MIN):
                reason = (
                    "unusual time"
                    if lang(self.hass.config.language) == "en"
                    else f"ungewöhnliche Uhrzeit {hour:02d} Uhr"
                )
        if reason:
            await self._async_emit(
                "unusual_action",
                {
                    "actor": actor_name,
                    "user_id": user_id,
                    "service": key,
                    "entities": ", ".join(entities) or "—",
                    "reason": reason,
                },
                key=f"action_{key}_{actor}",
                rate=900,
            )
        if actor not in actors:
            actors.append(actor)
        hist.add(hour)
        self._schedule_save()

    # --------------------------------------------------------------- sabotage
    def _is_own(self, entity_id: str) -> bool:
        """Bastion's own entities (alarm panel, decoy, sabotage, presence) are no sensors to watch."""
        if entity_id in self._own:
            return True
        entry = er.async_get(self.hass).async_get(entity_id)
        if entry is not None and entry.platform == DOMAIN:
            self._own.add(entity_id)
            return True
        return False

    def _watched(self, entity_id: str, state) -> bool:
        domain = entity_id.split(".", 1)[0]
        if domain in SABOTAGE_DOMAINS:
            return True
        if domain == "binary_sensor" and state is not None:
            return state.attributes.get("device_class") in SABOTAGE_CLASSES
        return False

    @callback
    def _state_filter(self, event_data: dict[str, Any]) -> bool:
        entity_id = event_data.get("entity_id", "")
        new = event_data.get("new_state")
        old = event_data.get("old_state")
        if new is None:
            return False
        ref = old if old is not None else new
        if not self._watched(entity_id, ref) or self._is_own(entity_id):
            return False
        if new.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            # "restored" marks entities of an integration that is being unloaded or reloaded
            # (update, restart of the integration): no radio loss, no sabotage.
            if new.attributes.get("restored"):
                return False
            return old is not None and old.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        return (
            new.attributes.get("device_class") == "tamper" and new.state == "on" and (old is None or old.state != "on")
        )

    @callback
    def _on_state_changed(self, event: Event) -> None:
        entity_id = event.data["entity_id"]
        new = event.data["new_state"]
        now = time.monotonic()
        if new.state == "on":
            self.hass.async_create_task(
                self._async_emit("tamper", {"entity": entity_id}, key=f"tamper_{entity_id}", rate=1800),
                eager_start=True,
            )
            return
        if now - self._setup_time < STARTUP_GRACE:
            return
        window = float(self._options().get(CONF_SABOTAGE_WINDOW) or 120)
        count = int(self._options().get(CONF_SABOTAGE_COUNT) or 3)
        self._unavailable.append((now, entity_id))
        recent = {e for t, e in self._unavailable if now - t <= window}
        if len(recent) >= count and now > self.sabotage_until:
            self.sabotage_until = now + SABOTAGE_HOLD
            self.hass.async_create_task(
                self._async_emit(
                    "sabotage",
                    {"count": len(recent), "entities": ", ".join(sorted(recent)[:10])},
                    key="sabotage",
                    rate=SABOTAGE_HOLD,
                ),
                eager_start=True,
            )
            async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    @property
    def sabotage_active(self) -> bool:
        """True while a sabotage alert is held."""
        return time.monotonic() < self.sabotage_until

    # --------------------------------------------------------------- outbound
    async def _async_outbound(self, _now: datetime | None = None) -> None:
        ips = await self.hass.async_add_executor_job(_read_proc_connections)
        learning = (
            dt_util.utcnow() - (dt_util.parse_datetime(self.outbound_started or "") or dt_util.utcnow())
            < OUTBOUND_LEARNING
        )
        new_keys = []
        for ip in ips:
            key = _network_key(ip)
            if key in self.outbound_known:
                continue
            self.outbound_known.add(key)
            if not learning:
                new_keys.append((key, ip))
        for key, ip in new_keys[:10]:
            host = await self.hass.async_add_executor_job(_reverse, ip)
            target = f"{host} ({ip})" if host else ip
            item = {"time": dt_util.utcnow().isoformat(), "network": key, "ip": ip, "host": host}
            self.outbound_new.append(item)
            await self._async_emit("new_destination", {"target": target, "network": key}, notify=False)
        if new_keys or learning:
            self._schedule_save()

    # ----------------------------------------------------------------- panel
    def summary(self) -> dict[str, Any]:
        """Data for the panel."""
        sensors = []
        for entity_id, model in self.models.items():
            state = self.hass.states.get(entity_id)
            sensors.append(
                {
                    "entity_id": entity_id,
                    "name": state.attributes.get("friendly_name") if state else entity_id,
                    "samples": model.samples,
                    "learned_buckets": sum(1 for b in model.buckets if b.n >= 36),
                    "active": self.active.get(entity_id, []),
                    "accepted": model.accepted,
                    "unit": (state.attributes.get("unit_of_measurement") or "") if state else "",
                }
            )
        return {
            "sensors": sensors,
            "events": list(self.events)[-100:][::-1],
            "sabotage": self.sabotage_active,
            "outbound": {
                "enabled": bool(self._options().get(CONF_ANOMALY_OUTBOUND)),
                "known": len(self.outbound_known),
                "new": list(self.outbound_new)[::-1],
                "learning_since": self.outbound_started,
            },
            "learning_since": self.started,
        }
