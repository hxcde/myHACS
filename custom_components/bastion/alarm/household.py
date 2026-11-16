"""Household: who is home, detected by the phone's IP address in the home network.

Every 30 seconds Bastion checks each phone, without special rights:

* TCP connect to a few ports: an answer (also "connection refused") means the
  phone is awake; port 62078 is open on iPhones even when locked.
* ICMP echo (unprivileged, if icmplib is available).
* ARP: a UDP datagram makes the host resolve the address; a complete entry in
  /proc/net/arp means the phone is in the WLAN (iPhones answer ARP in sleep).

A phone counts as home as soon as one check answers, and as away only after it
stayed silent for the set number of minutes (phones sleep, WLAN drops briefly).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import ipaddress
import logging
from pathlib import Path
import socket
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SIGNAL_HOUSEHOLD = f"{DOMAIN}_household"
EVENT_PRESENCE = f"{DOMAIN}_presence"
SCAN_INTERVAL = 30
PROBE_PORTS = (62078, 7000, 5353, 80)
CONNECT_TIMEOUT = 1.5
ARP_TABLE = Path("/proc/net/arp")
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


async def _tcp_alive(host: str, port: int) -> bool:
    try:
        _reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), CONNECT_TIMEOUT)
    except ConnectionRefusedError:
        return True  # the phone answered with a reset: it is there
    except (TimeoutError, OSError):
        return False
    writer.close()
    return True


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


def _arp_lookup(ip: str) -> bool:
    """Complete ARP entry for the address (Linux)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(b"", (ip, 9))
    except OSError:
        pass
    try:
        lines = ARP_TABLE.read_text().splitlines()[1:]
    except OSError:
        return False
    for line in lines:
        parts = line.split()
        if len(parts) >= 4 and parts[0] == ip and parts[2] != "0x0" and parts[3] != "00:00:00:00:00:00":
            return True
    return False


async def async_probe(hass: HomeAssistant, host: str) -> str | None:
    """Name of the first check that found the device, None if it is silent."""
    results = await asyncio.gather(*(_tcp_alive(host, port) for port in PROBE_PORTS))
    if any(results):
        return "tcp"
    if await _icmp_alive(host):
        return "ping"
    try:
        ipaddress.IPv4Address(host)
    except ValueError:
        return None
    await asyncio.sleep(0.3)
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
        self._scanning = False
        self._started = dt_util.utcnow()
        self.probe = async_probe

    @property
    def people(self) -> list[dict[str, Any]]:
        """Configured people (id, name, ip)."""
        return [p for p in self.engine.config.get("people") or [] if p.get("id") and p.get("ip")]

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
        self.hass.async_create_background_task(self._async_scan(), "bastion_household")

    def unload(self) -> None:
        """Stop scanning."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    async def _async_scan(self, _now: datetime | None = None) -> None:
        if self._scanning:
            return
        self._scanning = True
        try:
            people = self.people
            found = await asyncio.gather(*(self.probe(self.hass, p["ip"].strip()) for p in people))
            changed = False
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
                "ip": p["ip"],
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
