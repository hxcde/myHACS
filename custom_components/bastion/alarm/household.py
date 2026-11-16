"""Household: who is home, by a device tracker or the phone's IP address.

A person can follow an existing device tracker (e.g. of the UniFi or FRITZ!Box
integration: the controller knows whether the phone is on the WLAN). Without a
tracker Bastion checks the phone's IP address every 30 seconds, without special
rights:

* TCP connect to a few ports: an accepted connection means the phone is there
  (port 62078 is open on iPhones even when locked). A reset ("connection
  refused") only counts in the own subnet: across a router, a firewall that
  rejects connections sends it in the phone's name.
* ICMP echo (unprivileged, if icmplib is available).
* ARP: a UDP datagram makes the kernel re-check the neighbour; after the probe
  time a still complete entry in /proc/net/arp means the phone answered (a
  stale entry of a phone that left turns incomplete meanwhile).

A phone counts as home as soon as one check answers, and as away only after it
stayed silent for the set number of minutes (phones sleep, WLAN drops briefly).
A tracker is followed directly: its integration already waits before "away".
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import ipaddress
import logging
from pathlib import Path
import socket
from typing import Any

from homeassistant.const import STATE_HOME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SIGNAL_HOUSEHOLD = f"{DOMAIN}_household"
EVENT_PRESENCE = f"{DOMAIN}_presence"
SCAN_INTERVAL = 30
PROBE_PORTS = (62078, 7000, 5353, 80)
CONNECT_TIMEOUT = 1.5
ARP_TABLE = Path("/proc/net/arp")
# Linux: delay_first_probe_time 5 s + 3 unicast probes of 1 s, then a silent neighbour is FAILED.
ARP_SETTLE = 9
DEFAULT_AWAY_MINUTES = 10


def valid_address(value: str) -> bool:
    """IP address in a private network, or a host name."""
    value = value.strip()
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        labels = value.rstrip(".").split(".")
        return 0 < len(value) <= 253 and all(
            0 < len(x) <= 63 and x.replace("-", "").isalnum() and not x.startswith("-") for x in labels
        )
    return ip.is_private and not ip.is_loopback and not ip.is_unspecified


async def _tcp_alive(host: str, port: int, onlink: bool) -> bool:
    try:
        _reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), CONNECT_TIMEOUT)
    except ConnectionRefusedError:
        # A reset proves the phone only in the own subnet; routed, the firewall may send it.
        return onlink
    except (TimeoutError, OSError):
        return False
    writer.close()
    return True


async def _local_networks(hass: HomeAssistant) -> list[ipaddress.IPv4Network]:
    try:
        from homeassistant.components import network  # noqa: PLC0415

        adapters = await network.async_get_adapters(hass)
    except Exception:  # noqa: BLE001 - network integration not loaded
        return []
    nets = []
    for adapter in adapters:
        for addr in adapter.get("ipv4") or []:
            try:
                nets.append(ipaddress.IPv4Network(f"{addr['address']}/{addr['network_prefix']}", strict=False))
            except ValueError:
                continue
    return nets


def _onlink(host: str, nets: list[ipaddress.IPv4Network]) -> bool:
    try:
        ip = ipaddress.IPv4Address(host)
    except ValueError:
        return False
    return any(ip in net for net in nets)


async def _icmp_alive(host: str) -> bool:
    try:
        from icmplib import async_ping  # noqa: PLC0415 - optional
    except ImportError:
        return False
    try:
        result = await async_ping(host, count=2, interval=0.3, timeout=1, privileged=False)
    except Exception:  # noqa: BLE001 - no permission, unknown host, …
        return False
    return bool(result.is_alive)


def _arp_poke(ip: str) -> None:
    """Send one datagram: a stale neighbour entry gets re-checked by the kernel."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(b"", (ip, 9))
    except OSError:
        pass


def _arp_lookup(ip: str) -> bool:
    """Complete ARP entry for the address (Linux)."""
    try:
        lines = ARP_TABLE.read_text().splitlines()[1:]
    except OSError:
        return False
    for line in lines:
        parts = line.split()
        if len(parts) >= 4 and parts[0] == ip and parts[2] != "0x0" and parts[3] != "00:00:00:00:00:00":
            return True
    return False


async def _resolve(hass: HomeAssistant, host: str) -> str:
    """IPv4 address of a host name (the name itself if it cannot be resolved)."""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        try:
            infos = await hass.loop.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
        except OSError:
            return host
        if infos:
            return str(infos[0][4][0])
    return host


async def async_probe(hass: HomeAssistant, host: str) -> str | None:
    """Name of the first check that found the device, None if it is silent."""
    host = await _resolve(hass, host)
    onlink = _onlink(host, await _local_networks(hass))
    results = await asyncio.gather(*(_tcp_alive(host, port, onlink) for port in PROBE_PORTS))
    if any(results):
        return "tcp"
    if await _icmp_alive(host):
        return "ping"
    if not onlink:
        return None  # ARP only sees the own subnet
    await hass.async_add_executor_job(_arp_poke, host)
    await asyncio.sleep(ARP_SETTLE)
    if await hass.async_add_executor_job(_arp_lookup, host):
        return "arp"
    return None


class Household:
    """People of the household and whether their phone is in the home network."""

    def __init__(self, hass: HomeAssistant, engine) -> None:
        """Init."""
        self.hass = hass
        self.engine = engine
        self.status: dict[str, dict[str, Any]] = {}
        self._unsub: CALLBACK_TYPE | None = None
        self._unsub_trackers: CALLBACK_TYPE | None = None
        self._scanning = False
        self._started = dt_util.utcnow()
        self.probe = async_probe

    @property
    def people(self) -> list[dict[str, Any]]:
        """Configured people (id, name, ip and/or tracker)."""
        return [p for p in self.engine.config.get("people") or [] if p.get("id") and (p.get("ip") or p.get("tracker"))]

    @property
    def away_after(self) -> timedelta:
        """Silence after which a phone counts as away."""
        minutes = int((self.engine.config.get("presence") or {}).get("away_minutes") or DEFAULT_AWAY_MINUTES)
        return timedelta(minutes=max(1, minutes))

    def setup(self) -> None:
        """Start scanning (again) with the current people."""
        self.unload()
        ids = {p["id"] for p in self.people}
        self.status = {k: v for k, v in self.status.items() if k in ids}
        # The list may have changed: trackers and sensors follow right away.
        async_dispatcher_send(self.hass, SIGNAL_HOUSEHOLD)
        if not ids:
            return
        self._started = dt_util.utcnow()
        self._unsub = async_track_time_interval(self.hass, self._async_scan, timedelta(seconds=SCAN_INTERVAL))
        trackers = [p["tracker"] for p in self.people if p.get("tracker")]
        if trackers:
            self._unsub_trackers = async_track_state_change_event(self.hass, trackers, self._tracker_changed)
        self.hass.async_create_background_task(self._async_scan(), "bastion_household")

    def unload(self) -> None:
        """Stop scanning."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        if self._unsub_trackers is not None:
            self._unsub_trackers()
            self._unsub_trackers = None

    @callback
    def _tracker_changed(self, _event) -> None:
        changed = False
        now = dt_util.utcnow()
        for person in self.people:
            if person.get("tracker"):
                changed |= self._apply_tracker(person, now)
        if changed:
            async_dispatcher_send(self.hass, SIGNAL_HOUSEHOLD)

    def _apply_tracker(self, person: dict[str, Any], now: datetime) -> bool:
        """Follow the linked tracker; unknown/unavailable keeps the last state."""
        state = self.hass.states.get(person["tracker"])
        if state is None or state.state in ("unknown", "unavailable"):
            return False
        home = state.state == STATE_HOME  # not_home or another zone: away
        st = self.status.setdefault(person["id"], {"home": None, "last_seen": None, "since": None, "method": None})
        st["method"] = "tracker"
        if home:
            st["last_seen"] = now.isoformat()
        return self._set(person, st, home, now)

    async def _async_scan(self, _now: datetime | None = None) -> None:
        if self._scanning:
            return
        self._scanning = True
        try:
            now = dt_util.utcnow()
            changed = False
            for person in self.people:
                if person.get("tracker"):
                    changed |= self._apply_tracker(person, now)
            people = [p for p in self.people if not p.get("tracker")]
            found = await asyncio.gather(*(self.probe(self.hass, p["ip"].strip()) for p in people))
            now = dt_util.utcnow()
            for person, method in zip(people, found, strict=True):
                changed |= self._update(person, method, now)
            if changed:
                async_dispatcher_send(self.hass, SIGNAL_HOUSEHOLD)
        finally:
            self._scanning = False

    def _update(self, person: dict[str, Any], method: str | None, now: datetime) -> bool:
        st = self.status.setdefault(person["id"], {"home": None, "last_seen": None, "since": None, "method": None})
        if method:
            st["last_seen"] = now.isoformat()
            st["method"] = method
            home = True
        else:
            seen = dt_util.parse_datetime(st["last_seen"] or "")
            silent_since = seen or self._started
            if now - silent_since < self.away_after:
                return False
            home = False
        return self._set(person, st, home, now)

    def _set(self, person: dict[str, Any], st: dict[str, Any], home: bool, now: datetime) -> bool:
        if st["home"] is home:
            return False
        previous = st["home"]
        st["home"] = home
        st["since"] = now.isoformat()
        if previous is not None:
            self.hass.bus.async_fire(EVENT_PRESENCE, {"person": person["name"], "home": home})
        return True

    # ---------------------------------------------------------------- queries
    def is_home(self, person_id: str) -> bool | None:
        """True/False, None while unknown (just started)."""
        return (self.status.get(person_id) or {}).get("home")

    def all_away(self) -> bool:
        """True if every person is known to be away."""
        people = self.people
        return bool(people) and all(self.is_home(p["id"]) is False for p in people)

    def anyone_home(self) -> bool | None:
        """True if someone is home, None if unknown."""
        states = [self.is_home(p["id"]) for p in self.people]
        if any(s is True for s in states):
            return True
        if states and all(s is False for s in states):
            return False
        return None

    def names(self, home: bool) -> list[str]:
        """Names of the people at home (or away)."""
        return [p["name"] for p in self.people if self.is_home(p["id"]) is home]

    def summary(self) -> list[dict[str, Any]]:
        """For the panel."""
        return [
            {
                "id": p["id"],
                "name": p["name"],
                "ip": p.get("ip") or "",
                "tracker": p.get("tracker"),
                **(self.status.get(p["id"]) or {"home": None, "last_seen": None, "since": None, "method": None}),
            }
            for p in self.people
        ]

    def worker_payload(self) -> list[dict[str, Any]]:
        """Names and state only, for the worker dashboard (no addresses)."""
        return [
            {"name": p["name"], "home": self.is_home(p["id"]), "since": (self.status.get(p["id"]) or {}).get("since")}
            for p in self.people
        ]
