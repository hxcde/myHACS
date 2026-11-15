"""Versions, security advisories, companion apps, ESPHome, pending updates."""

from __future__ import annotations

from datetime import timedelta
from importlib import metadata
import logging
import re
import time
from typing import Any

import aiohttp
from awesomeversion import AwesomeVersion, AwesomeVersionException
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from ..const import ADVISORY_REPOS, CONF_GITHUB_TOKEN, GITHUB_API, VERSION_URL, Category, Severity
from ..models import Finding, make_finding
from . import AuditContext

_LOGGER = logging.getLogger(__name__)

ADVISORY_TTL = 12 * 3600
VERSION_TTL = 6 * 3600
PENDING_DAYS = 14
_VERSION_RE = re.compile(r"\d{4}\.\d{1,2}(?:\.\d+)?")
_SEVERITY = {
    "critical": Severity.CRITICAL,
    "high": Severity.HIGH,
    "moderate": Severity.MEDIUM,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
}


def extract_version(raw: str | None) -> str | None:
    """Pull a CalVer version out of an app version string."""
    if not raw:
        return None
    m = _VERSION_RE.search(str(raw))
    return m.group(0) if m else None


def version_in_range(version: str, spec: str) -> bool | None:
    """Evaluate a GitHub vulnerable_version_range such as '>= 1.0, < 2.0'."""
    try:
        ver = AwesomeVersion(version)
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            m = re.match(r"^(<=|>=|<|>|=|==)?\s*(.+)$", part)
            if m is None:
                return None
            op, value = m.group(1) or "=", AwesomeVersion(m.group(2).strip())
            ok = {
                "<": ver < value,
                "<=": ver <= value,
                ">": ver > value,
                ">=": ver >= value,
                "=": ver == value,
                "==": ver == value,
            }[op]
            if not ok:
                return False
        return True
    except (AwesomeVersionException, KeyError, TypeError, ValueError):
        return None


def is_vulnerable(version: str, vuln: dict[str, Any]) -> bool:
    """True if version is affected by a vulnerabilities entry."""
    if spec := vuln.get("vulnerable_version_range"):
        return bool(version_in_range(version, spec))
    if patched := vuln.get("patched_versions"):
        first = str(patched).split(",")[0].strip()
        return bool(version_in_range(version, f"< {first}"))
    return False


def classify(repo: str, vuln: dict[str, Any], summary: str) -> str | None:
    """Which component an advisory entry refers to."""
    pkg = (vuln.get("package") or {}).get("name") or ""
    pkg_l = pkg.lower()
    text = f"{pkg_l} {summary.lower()}"
    if repo.endswith("/android") or "android" in text:
        return "android"
    if repo.endswith("/iOS") or re.search(r"\bios\b", text):
        return "ios"
    if repo.endswith("/frontend") or pkg_l == "home-assistant-frontend":
        return "frontend"
    if pkg_l in ("homeassistant", "home-assistant") or repo.endswith("/core"):
        return "core"
    return None


async def _async_get_json(ctx: AuditContext, url: str, headers: dict[str, str]) -> Any:
    session = async_get_clientsession(ctx.hass)
    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as resp:
        if resp.status != 200:
            raise aiohttp.ClientResponseError(resp.request_info, resp.history, status=resp.status)
        return await resp.json(content_type=None)


async def async_fetch_advisories(ctx: AuditContext) -> list[dict[str, Any]]:
    """Published advisories of the Home Assistant repositories (cached)."""
    cached = ctx.cache.get("advisories")
    if cached and time.time() - cached["time"] < ADVISORY_TTL:
        return cached["data"]
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token := ctx.options.get(CONF_GITHUB_TOKEN):
        headers["Authorization"] = f"Bearer {token}"
    out: list[dict[str, Any]] = []
    failed = False
    for repo in ADVISORY_REPOS:
        url = f"{GITHUB_API}/repos/{repo}/security-advisories?state=published&per_page=100"
        try:
            data = await _async_get_json(ctx, url, headers)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Advisories of %s not available: %s", repo, err)
            failed = True
            continue
        for adv in data if isinstance(data, list) else []:
            if adv.get("withdrawn_at"):
                continue
            out.append({**adv, "_repo": repo})
    if out or not failed:
        ctx.cache["advisories"] = {"time": time.time(), "data": out}
    elif cached:
        return cached["data"]
    return out


def match_advisories(advisories: list[dict[str, Any]], component: str, version: str) -> list[dict[str, Any]]:
    """Advisories affecting a component version."""
    hits = []
    for adv in advisories:
        summary = str(adv.get("summary", ""))
        for vuln in adv.get("vulnerabilities") or []:
            if classify(adv.get("_repo", ""), vuln, summary) != component:
                continue
            if is_vulnerable(version, vuln):
                hits.append({**adv, "_vuln": vuln})
                break
    return hits


def _advisory_finding(adv: dict[str, Any], component: str, installed: str, label: str, *id_parts: Any) -> Finding:
    vuln = adv.get("_vuln") or {}
    return make_finding(
        "advisory",
        _SEVERITY.get(str(adv.get("severity", "")).lower(), Severity.MEDIUM),
        Category.UPDATES,
        adv.get("ghsa_id"),
        component,
        *id_parts,
        summary=str(adv.get("summary", ""))[:140],
        component=label,
        installed=installed,
        ghsa=adv.get("ghsa_id", ""),
        cve=f" / {adv['cve_id']}" if adv.get("cve_id") else "",
        level=adv.get("severity", "?"),
        patched=vuln.get("patched_versions") or "?",
        url=adv.get("html_url", ""),
    )


async def async_check(ctx: AuditContext) -> list[Finding]:
    """Run update related checks."""
    hass = ctx.hass
    out: list[Finding] = []

    # Latest release
    cached = ctx.cache.get("latest_version")
    latest = None
    if cached and time.time() - cached["time"] < VERSION_TTL:
        latest = cached["version"]
    else:
        try:
            data = await _async_get_json(ctx, VERSION_URL, {})
            latest = str(data["homeassistant"]["default"])
            ctx.cache["latest_version"] = {"time": time.time(), "version": latest}
        except (aiohttp.ClientError, TimeoutError, KeyError, TypeError, ValueError):
            latest = cached["version"] if cached else None
    if latest:
        try:
            inst, lat = AwesomeVersion(HA_VERSION), AwesomeVersion(latest)
            if inst < lat:
                months = (int(lat.section(0)) - int(inst.section(0))) * 12 + int(lat.section(1)) - int(inst.section(1))
                severity = Severity.MEDIUM if months >= 2 else Severity.LOW
                out.append(
                    make_finding("ha_outdated", severity, Category.UPDATES, "core", installed=HA_VERSION, latest=latest)
                )
        except (AwesomeVersionException, ValueError):
            pass

    # Advisories
    advisories = await async_fetch_advisories(ctx)
    if advisories:
        for adv in match_advisories(advisories, "core", HA_VERSION):
            out.append(_advisory_finding(adv, "core", HA_VERSION, "Home Assistant Core"))
        frontend_version = await hass.async_add_executor_job(_frontend_version)
        if frontend_version:
            for adv in match_advisories(advisories, "frontend", frontend_version):
                out.append(_advisory_finding(adv, "frontend", frontend_version, "Home Assistant Frontend"))
        for entry in hass.config_entries.async_entries("mobile_app"):
            data = entry.data
            app_id = str(data.get("app_id", "")).lower()
            os_name = str(data.get("os_name", "")).lower()
            platform = "android" if ("android" in app_id or "android" in os_name) else "ios"
            version = extract_version(data.get("app_version"))
            if not version:
                continue
            device = data.get("device_name") or entry.title
            for adv in match_advisories(advisories, platform, version):
                out.append(_advisory_finding(adv, platform, version, f"Companion App ({device})", entry.entry_id))

    # ESPHome encryption
    for entry in hass.config_entries.async_entries("esphome"):
        if entry.disabled_by is not None:
            continue
        if not entry.data.get("noise_psk"):
            out.append(
                make_finding(
                    "esphome_no_encryption",
                    Severity.MEDIUM,
                    Category.UPDATES,
                    entry.entry_id,
                    device=entry.title or entry.data.get("host", "?"),
                )
            )

    # Long pending updates
    cutoff = dt_util.utcnow() - timedelta(days=PENDING_DAYS)
    pending = [
        s.attributes.get("friendly_name") or s.entity_id
        for s in hass.states.async_all("update")
        if s.state == "on" and s.last_changed < cutoff
    ]
    if pending:
        out.append(
            make_finding(
                "updates_pending",
                Severity.LOW,
                Category.UPDATES,
                "updates",
                count=len(pending),
                days=PENDING_DAYS,
                entities=", ".join(sorted(pending)[:15]),
            )
        )
    return out


def _frontend_version() -> str | None:
    try:
        return metadata.version("home-assistant-frontend")
    except metadata.PackageNotFoundError:
        return None
