"""Known vulnerabilities in device firmware (ESPHome, Tasmota, WLED, Zigbee2MQTT).

The firmware version comes from the device registry (sw_version), the
vulnerabilities from the published GitHub security advisories of the firmware
projects.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import aiohttp
from homeassistant.helpers import device_registry as dr

from ..const import CONF_GITHUB_TOKEN, GITHUB_API, Category, Severity
from ..models import Finding, make_finding
from . import AuditContext
from .updates import _SEVERITY, _async_get_json, is_vulnerable

_LOGGER = logging.getLogger(__name__)

TTL = 12 * 3600
_VERSION = re.compile(r"\d+\.\d+(?:\.\d+)?")

FIRMWARE: dict[str, dict[str, str]] = {
    "esphome": {"repo": "esphome/esphome", "label": "ESPHome"},
    "tasmota": {"repo": "arendst/Tasmota", "label": "Tasmota"},
    "wled": {"repo": "wled/WLED", "label": "WLED"},
    "zigbee2mqtt": {"repo": "Koenkk/zigbee2mqtt", "label": "Zigbee2MQTT"},
}


def firmware_family(domains: set[str], manufacturer: str | None, model: str | None) -> str | None:
    """Which firmware a device runs."""
    for family in ("esphome", "tasmota", "wled"):
        if family in domains:
            return family
    if "mqtt" in domains and (manufacturer or "").lower() == "zigbee2mqtt" and "bridge" in (model or "").lower():
        return "zigbee2mqtt"
    return None


def firmware_version(raw: str | None) -> str | None:
    """Version number out of a sw_version string."""
    if not raw:
        return None
    m = _VERSION.search(str(raw))
    return m.group(0) if m else None


def collect_devices(hass) -> dict[str, list[tuple[str, str]]]:
    """family -> [(device name, version)]."""
    registry = dr.async_get(hass)
    out: dict[str, list[tuple[str, str]]] = {}
    for device in registry.devices.values():
        if device.disabled_by is not None:
            continue
        domains = set()
        for entry_id in device.config_entries:
            if (entry := hass.config_entries.async_get_entry(entry_id)) is not None:
                domains.add(entry.domain)
        family = firmware_family(domains, device.manufacturer, device.model)
        version = firmware_version(device.sw_version)
        if family and version:
            out.setdefault(family, []).append((device.name_by_user or device.name or device.id[:8], version))
    return out


async def _async_advisories(ctx: AuditContext, repo: str) -> list[dict[str, Any]]:
    cache = ctx.cache.setdefault("firmware_advisories", {})
    entry = cache.get(repo)
    if entry and time.time() - entry["time"] < TTL:
        return entry["data"]
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token := ctx.options.get(CONF_GITHUB_TOKEN):
        headers["Authorization"] = f"Bearer {token}"
    url = f"{GITHUB_API}/repos/{repo}/security-advisories?state=published&per_page=100"
    try:
        data = await _async_get_json(ctx, url, headers)
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        _LOGGER.debug("Firmware advisories of %s not available: %s", repo, err)
        return entry["data"] if entry else []
    advisories = [a for a in (data if isinstance(data, list) else []) if not a.get("withdrawn_at")]
    cache[repo] = {"time": time.time(), "data": advisories}
    return advisories


def match(
    advisories: list[dict[str, Any]], devices: list[tuple[str, str]]
) -> list[tuple[dict[str, Any], dict[str, Any], list[str]]]:
    """(advisory, vulnerability, affected device names)."""
    out = []
    for adv in advisories:
        for vuln in adv.get("vulnerabilities") or []:
            affected = [name for name, version in devices if is_vulnerable(version, vuln)]
            if affected:
                out.append((adv, vuln, sorted(affected)))
                break
    return out


async def async_check(ctx: AuditContext) -> list[Finding]:
    """Firmware vulnerabilities."""
    out: list[Finding] = []
    for family, devices in collect_devices(ctx.hass).items():
        source = FIRMWARE[family]
        for adv, vuln, affected in match(await _async_advisories(ctx, source["repo"]), devices):
            out.append(
                make_finding(
                    "firmware_advisory",
                    _SEVERITY.get(str(adv.get("severity", "")).lower(), Severity.MEDIUM),
                    Category.UPDATES,
                    adv.get("ghsa_id"),
                    family,
                    firmware=source["label"],
                    count=len(affected),
                    devices=", ".join(affected[:8]) + (" …" if len(affected) > 8 else ""),
                    summary=str(adv.get("summary", ""))[:140],
                    ghsa=adv.get("ghsa_id", ""),
                    cve=f" / {adv['cve_id']}" if adv.get("cve_id") else "",
                    level=adv.get("severity", "?"),
                    patched=vuln.get("patched_versions") or "?",
                    url=adv.get("html_url", ""),
                )
            )
    return out
