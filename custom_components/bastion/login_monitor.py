"""Login and account monitoring.

* Failed logins and IP bans are read from the log records of the HTTP ban
  middleware (the only place Home Assistant reports them).
* Successful logins are detected as new refresh tokens of type "normal".
* New IPs per user, new long lived tokens and user changes raise events.

Everything is persisted, so the log survives restarts.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from datetime import datetime, timedelta
import ipaddress
import logging
import re
import time
from typing import Any

import aiohttp
from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN, TOKEN_TYPE_NORMAL
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BRUTE_FORCE_THRESHOLD,
    CONF_GEOIP,
    CONF_NOTIFY_LOGINS,
    CONF_NOTIFY_PUBLIC_ONLY,
    EVENT_SECURITY,
    SIGNAL_UPDATE,
    STORAGE_KEY_LOGINS,
    STORAGE_VERSION,
)
from .texts import event_text, misc

_LOGGER = logging.getLogger(__name__)

BAN_LOGGER = "homeassistant.components.http.ban"
POLL_INTERVAL = timedelta(seconds=30)
MAX_LOG = 1000
BRUTE_WINDOW = 600

_FAILED_RE = re.compile(
    r"invalid authentication from (?P<host>.+?) \((?P<ip>[0-9a-fA-F:.]+)\)\.(?: Requested URL: '(?P<url>[^']*)'\.)?(?: \((?P<ua>.*)\))?"
)
_BANNED_RE = re.compile(r"Banned IP (?P<ip>[0-9a-fA-F:.]+) for too many login attempts")


def is_public_ip(ip: str | None) -> bool:
    """True for globally routable addresses."""
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return addr.is_global


def network_of(ip: str) -> str:
    """What counts as "the same address": IPv4 exactly, IPv6 its /64.

    Phones and routers change the lower half of an IPv6 address on purpose (privacy
    extensions, RFC 8981) - every few hours a new address in the same network.
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if addr.version == 6:
        if addr.ipv4_mapped:
            return str(addr.ipv4_mapped)
        return str(ipaddress.ip_network(f"{addr}/64", strict=False))
    return str(addr)


class _BanLogHandler(logging.Handler):
    """Forward ban middleware log records into the event loop."""

    def __init__(self, hass: HomeAssistant, sink: Callable[[str, dict[str, Any]], None]) -> None:
        super().__init__(level=logging.WARNING)
        self._hass = hass
        self._sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001
            return
        if (m := _FAILED_RE.search(message)) is not None:
            data = {
                "ip": m.group("ip"),
                "host": m.group("host"),
                "url": m.group("url") or "",
                "user_agent": (m.group("ua") or "")[:200],
            }
            self._forward("failed_login", data)
        elif (m := _BANNED_RE.search(message)) is not None:
            self._forward("ip_banned", {"ip": m.group("ip")})

    def _forward(self, kind: str, data: dict[str, Any]) -> None:
        # A logging handler must never raise into the code that logs.
        try:
            self._hass.loop.call_soon_threadsafe(self._sink, kind, data)
        except RuntimeError:
            pass


class LoginMonitor:
    """Tracks logins, tokens and users."""

    def __init__(
        self, hass: HomeAssistant, notifier, options_getter: Callable[[], dict[str, Any]], anomaly=None
    ) -> None:
        """Init."""
        self.hass = hass
        self.notifier = notifier
        self._options = options_getter
        self.anomaly = anomaly
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY_LOGINS)
        self.log: deque[dict[str, Any]] = deque(maxlen=MAX_LOG)
        self.tokens: dict[str, dict[str, Any]] = {}
        self.users: dict[str, dict[str, Any]] = {}
        self.known_ips: dict[str, list[str]] = {}
        # Providers (ASN + country) a user has logged in from: a new address there is no news.
        self.known_providers: dict[str, list[str]] = {}
        self._lookup_cache: dict[str, dict[str, Any]] = {}
        self._pending_logins: dict[str, float] = {}
        self._failed_times: deque[float] = deque(maxlen=500)
        self._brute_alerted: float | None = None
        self._handler: _BanLogHandler | None = None
        self._unsubs: list[CALLBACK_TYPE] = []
        self._first_poll = True
        self._poll_lock = asyncio.Lock()
        self.responder = None
        self.ignored_user_ids: Callable[[], set[str]] = set
        # Long-lived token usage observed by the token guard (HA does not record it).
        self.token_usage: dict[str, dict[str, Any]] = {}
        self.usage_since: str | None = None

    async def async_setup(self) -> None:
        """Load state, hook the logger, start polling."""
        if (data := await self._store.async_load()) is not None:
            self.log.extend(data.get("log", [])[-MAX_LOG:])
            self.tokens = data.get("tokens", {})
            self.users = data.get("users", {})
            self.known_ips = data.get("known_ips", {})
            self.known_providers = data.get("known_providers", {})
            self.token_usage = data.get("token_usage", {})
            self.usage_since = data.get("usage_since")
            self._first_poll = not bool(self.tokens or self.users)
        if self.usage_since is None:
            self.usage_since = dt_util.utcnow().isoformat()
        logger = logging.getLogger(BAN_LOGGER)
        if logger.getEffectiveLevel() > logging.WARNING:
            logger.setLevel(logging.WARNING)
        self._handler = _BanLogHandler(self.hass, self._on_log_event)
        logger.addHandler(self._handler)
        self._unsubs.append(async_track_time_interval(self.hass, self._async_poll, POLL_INTERVAL))
        for event_type in ("user_added", "user_updated", "user_removed"):
            self._unsubs.append(self.hass.bus.async_listen(event_type, self._on_user_event))
        await self._async_poll()

    async def async_unload(self) -> None:
        """Remove hooks and save."""
        if self._handler is not None:
            logging.getLogger(BAN_LOGGER).removeHandler(self._handler)
            self._handler = None
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self._async_save()

    def _data(self) -> dict[str, Any]:
        return {
            "log": list(self.log),
            "tokens": self.tokens,
            "users": self.users,
            "known_ips": self.known_ips,
            "known_providers": self.known_providers,
            "token_usage": self.token_usage,
            "usage_since": self.usage_since,
        }

    async def _async_save(self) -> None:
        await self._store.async_save(self._data())

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._data, 10)
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    @callback
    def record(self, kind: str, data: dict[str, Any]) -> None:
        """Add an entry to the log (used by responder and decoys)."""
        self.log.append({"time": dt_util.utcnow().isoformat(), "type": kind, **data})
        self._schedule_save()

    # ------------------------------------------------------------ token usage
    @callback
    def on_token_used(self, token, ip: str | None) -> None:
        """Called by the token guard for every use of a long-lived token."""
        usage = self.token_usage.setdefault(token.id, {"ips": []})
        usage["last_used_at"] = dt_util.utcnow().isoformat()
        usage["last_ip"] = ip
        if ip and network_of(ip) not in {network_of(x) for x in usage["ips"]}:
            first = not usage["ips"]
            usage["ips"].append(ip)
            del usage["ips"][:-50]
            if not first and token.user.id not in self.ignored_user_ids():
                self.hass.async_create_task(self._async_token_new_ip(token, ip), eager_start=True)
        self._store.async_delay_save(self._data, 60)

    async def _async_token_new_ip(self, token, ip: str) -> None:
        opts = self._options()
        public = is_public_ip(ip)
        look = await self._async_lookup(ip)
        known_provider = self._remember_provider(token.user.id, look)
        notify = (
            bool(opts.get(CONF_NOTIFY_LOGINS, True))
            and (public or not opts.get(CONF_NOTIFY_PUBLIC_ONLY, True))
            and not known_provider
        )
        data = {
            "user": token.user.name,
            "user_id": token.user.id,
            "name": token.client_name or token.id[:8],
            "token_id": token.id,
            "ip": ip,
            "public": public,
            "geo": look["geo"],
            "isp": look["isp"],
            "known_provider": known_provider,
        }
        await self._async_event("token_new_ip", data, notify=notify, rate_key=f"tokenip_{token.id}_{ip}", rate=3600)

    def token_last_used(self, token_id: str) -> str | None:
        """Observed last use of a long-lived token."""
        return (self.token_usage.get(token_id) or {}).get("last_used_at")

    # ---------------------------------------------------------------- events
    async def _async_event(
        self, kind: str, data: dict[str, Any], *, notify: bool, rate_key: str | None = None, rate: float = 0
    ) -> None:
        entry = {"time": dt_util.utcnow().isoformat(), "type": kind, **data}
        self.log.append(entry)
        self.hass.bus.async_fire(EVENT_SECURITY, entry)
        self._schedule_save()
        if notify:
            title, message = event_text(kind, self.hass.config.language, _render_data(data))
            actions = self.responder.actions_for(kind, data) if self.responder is not None else None
            await self.notifier.async_send(title, message, key=rate_key or kind, rate_limit=rate, actions=actions)

    @callback
    def _on_log_event(self, kind: str, data: dict[str, Any]) -> None:
        self.hass.async_create_task(self._async_on_log_event(kind, data), eager_start=True)

    async def _async_on_log_event(self, kind: str, data: dict[str, Any]) -> None:
        opts = self._options()
        if kind == "failed_login":
            now = time.monotonic()
            self._failed_times.append(now)
            await self._async_event(kind, data, notify=False)
            threshold = int(opts.get(CONF_BRUTE_FORCE_THRESHOLD) or 5)
            recent = sum(1 for t in self._failed_times if now - t <= BRUTE_WINDOW)
            if recent >= threshold and (self._brute_alerted is None or now - self._brute_alerted > 3600):
                self._brute_alerted = now
                await self._async_event(
                    "brute_force",
                    {"count": recent, "minutes": BRUTE_WINDOW // 60, "ip": data["ip"]},
                    notify=True,
                )
        elif kind == "ip_banned":
            await self._async_event(kind, data, notify=True, rate_key=f"ban_{data['ip']}", rate=3600)

    @callback
    def _on_user_event(self, event: Event) -> None:
        self.hass.async_create_task(self._async_poll(), eager_start=True)

    # ---------------------------------------------------------------- polling
    async def _async_poll(self, _now: datetime | None = None) -> None:
        try:
            # Polls are triggered by the timer and by user events; never interleave them.
            async with self._poll_lock:
                await self._async_poll_inner()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Bastion login poll failed")

    async def _async_poll_inner(self) -> None:
        opts = self._options()
        notify_logins = bool(opts.get(CONF_NOTIFY_LOGINS, True))
        public_only = bool(opts.get(CONF_NOTIFY_PUBLIC_ONLY, True))
        users = await self.hass.auth.async_get_users()
        silent = self._first_poll
        ignored = self.ignored_user_ids()
        current_users: dict[str, dict[str, Any]] = {}
        current_tokens: dict[str, dict[str, Any]] = {}
        for user in users:
            if user.system_generated or user.id in ignored:
                continue
            is_admin = user.is_admin
            current_users[user.id] = {
                "name": user.name or user.id[:8],
                "admin": is_admin,
                "active": user.is_active,
                "owner": user.is_owner,
            }
            for token in user.refresh_tokens.values():
                if token.token_type not in (TOKEN_TYPE_NORMAL, TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN):
                    continue
                current_tokens[token.id] = {
                    "user_id": user.id,
                    "user": user.name or user.id[:8],
                    "type": token.token_type,
                    "client_id": token.client_id,
                    "name": token.client_name or token.client_id or "",
                    "created_at": token.created_at.isoformat(),
                    "last_used_at": token.last_used_at.isoformat() if token.last_used_at else None,
                    "last_used_ip": token.last_used_ip,
                }

        # Users
        for user_id, info in current_users.items():
            old = self.users.get(user_id)
            if old is None:
                if not silent:
                    suffix = misc("admin_suffix", self.hass.config.language) if info["admin"] else ""
                    await self._async_event(
                        "user_added", {"user": info["name"], "user_id": user_id, "admin": suffix}, notify=True
                    )
            else:
                if info["admin"] and not old.get("admin"):
                    await self._async_event("admin_granted", {"user": info["name"], "user_id": user_id}, notify=True)
                if info["active"] and not old.get("active"):
                    await self._async_event("user_activated", {"user": info["name"], "user_id": user_id}, notify=True)
        for user_id, old in self.users.items():
            if user_id not in current_users and not silent:
                await self._async_event("user_removed", {"user": old.get("name"), "user_id": user_id}, notify=True)

        # Tokens
        now = time.monotonic()
        for token_id, info in current_tokens.items():
            old = self.tokens.get(token_id)
            ip = info["last_used_ip"]
            if old is None:
                if silent:
                    pass
                elif info["type"] == TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN:
                    await self._async_event(
                        "token_created",
                        {"user": info["user"], "user_id": info["user_id"], "name": info["name"], "token_id": token_id},
                        notify=True,
                    )
                else:
                    self._pending_logins[token_id] = now
            if token_id in self._pending_logins and (ip or now - self._pending_logins[token_id] > 600):
                self._pending_logins.pop(token_id)
                await self._async_login(info, token_id, notify_logins, public_only)
            elif ip and old is not None and ip != old.get("last_used_ip"):
                await self._async_check_ip(info, token_id, ip, notify_logins, public_only)
            elif ip and silent:
                self._remember_ip(info["user_id"], ip)
        for token_id, old in self.tokens.items():
            if token_id not in current_tokens and old.get("type") == TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN:
                await self._async_event(
                    "token_removed",
                    {
                        "user": old.get("user"),
                        "user_id": old.get("user_id"),
                        "name": old.get("name"),
                        "token_id": token_id,
                    },
                    notify=False,
                )
        for token_id in list(self.token_usage):
            if token_id not in current_tokens:
                self.token_usage.pop(token_id)
        changed = current_tokens != self.tokens or current_users != self.users
        self.users = current_users
        self.tokens = current_tokens
        self._first_poll = False
        if changed:
            self._schedule_save()

    def _remember_ip(self, user_id: str, ip: str) -> bool:
        """Store ip for user, True if its network was new (IPv6: the /64, see network_of)."""
        ips = self.known_ips.setdefault(user_id, [])
        if network_of(ip) in {network_of(x) for x in ips}:
            return False
        ips.append(ip)
        del ips[:-200]
        return True

    def _remember_provider(self, user_id: str, look: dict[str, Any]) -> bool:
        """Remember the provider of an address, True if the user has used it before."""
        if not look.get("asn"):
            return False
        key = f"{look['asn']}|{look.get('country') or ''}"
        known = self.known_providers.setdefault(user_id, [])
        if key in known:
            return True
        known.append(key)
        del known[:-50]
        return False

    async def _async_login(self, info: dict[str, Any], token_id: str, notify_logins: bool, public_only: bool) -> None:
        ip = info["last_used_ip"]
        new_ip = bool(ip) and self._remember_ip(info["user_id"], ip)
        look = await self._async_lookup(ip)
        known_provider = self._remember_provider(info["user_id"], look)
        data = {
            "user": info["user"],
            "user_id": info["user_id"],
            "ip": ip or "?",
            "client": info["name"],
            "token_id": token_id,
            "public": is_public_ip(ip),
            "geo": look["geo"],
            "isp": look["isp"],
            "new_ip": new_ip and not known_provider,
        }
        notify = notify_logins and (not public_only or is_public_ip(ip))
        await self._async_event("login", data, notify=notify, rate_key=f"login_{info['user_id']}_{ip}", rate=300)
        if self.anomaly is not None:
            await self.anomaly.async_on_login(info["user_id"], info["user"])

    async def _async_check_ip(
        self, info: dict[str, Any], token_id: str, ip: str, notify_logins: bool, public_only: bool
    ) -> None:
        if not self._remember_ip(info["user_id"], ip):
            return
        look = await self._async_lookup(ip)
        known_provider = self._remember_provider(info["user_id"], look)
        data = {
            "user": info["user"],
            "user_id": info["user_id"],
            "ip": ip,
            "client": info["name"],
            "token_id": token_id,
            "public": is_public_ip(ip),
            "geo": look["geo"],
            "isp": look["isp"],
            "known_provider": known_provider,
        }
        # A new address of a provider this user already uses (mobile network, home connection,
        # iCloud Private Relay) is logged, but no push.
        notify = notify_logins and (not public_only or is_public_ip(ip)) and not known_provider
        await self._async_event("new_ip", data, notify=notify, rate_key=f"newip_{info['user_id']}_{ip}", rate=3600)

    async def _async_geo(self, ip: str | None) -> str:
        """Optional city/country lookup (opt-in, public IPs only)."""
        return (await self._async_lookup(ip))["geo"]

    async def _async_lookup(self, ip: str | None) -> dict[str, Any]:
        """City, country and provider (ASN) of a public IP (opt-in geo lookup)."""
        empty = {"geo": "", "asn": None, "isp": "", "country": ""}
        if not ip or not is_public_ip(ip) or not self._options().get(CONF_GEOIP):
            return empty
        if ip in self._lookup_cache:
            return self._lookup_cache[ip]
        session = async_get_clientsession(self.hass)
        result = empty
        try:
            async with session.get(
                f"https://ipwho.is/{ip}?fields=country,country_code,city,connection",
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                data = await resp.json(content_type=None)
            if isinstance(data, dict):
                conn = data.get("connection") if isinstance(data.get("connection"), dict) else {}
                parts = [data.get("city"), data.get("country")]
                asn = conn.get("asn")
                result = {
                    "geo": ", ".join(str(p) for p in parts if p),
                    "asn": int(asn) if isinstance(asn, int) or (isinstance(asn, str) and asn.isdigit()) else None,
                    "isp": str(conn.get("isp") or conn.get("org") or "")[:80],
                    "country": str(data.get("country_code") or "")[:4],
                }
        except (aiohttp.ClientError, TimeoutError, ValueError):
            result = empty
        if len(self._lookup_cache) > 500:
            self._lookup_cache.clear()
        self._lookup_cache[ip] = result
        return result

    # ---------------------------------------------------------------- queries
    def failed_last_24h(self) -> int:
        """Failed logins within the last 24 hours."""
        cutoff = dt_util.utcnow() - timedelta(hours=24)
        count = 0
        for entry in reversed(self.log):
            if dt_util.parse_datetime(entry["time"]) < cutoff:
                break
            if entry["type"] == "failed_login":
                count += 1
        return count

    def stats(self) -> dict[str, Any]:
        """Aggregates for the panel."""
        cutoff = dt_util.utcnow() - timedelta(hours=24)
        per_hour = [0] * 24
        sources: dict[str, int] = {}
        for entry in self.log:
            if entry["type"] != "failed_login":
                continue
            ts = dt_util.parse_datetime(entry["time"])
            if ts is None or ts < cutoff:
                continue
            per_hour[int((dt_util.utcnow() - ts).total_seconds() // 3600) % 24] += 1
            sources[entry.get("ip", "?")] = sources.get(entry.get("ip", "?"), 0) + 1
        top = sorted(sources.items(), key=lambda x: -x[1])[:5]
        return {"failed_24h": sum(per_hour), "failed_per_hour": per_hour[::-1], "top_sources": top}


def _render_data(data: dict[str, Any]) -> dict[str, Any]:
    out = dict(data)
    geo = out.get("geo")
    out["geo"] = f" ({geo})" if geo else ""
    return out
