"""Custom integrations, frontend resources and their origin."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from typing import Any
from urllib.parse import urlsplit

import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_custom_components
from homeassistant.util import dt as dt_util

from ..const import CONF_GITHUB_TOKEN, DOMAIN, GITHUB_API, Category, Severity
from ..models import Finding, make_finding
from . import AuditContext

_LOGGER = logging.getLogger(__name__)

REPO_TTL = 24 * 3600
STALE_DAYS = 540
NEW_OWNER_DAYS = 90
WWW_EXTENSIONS = (".js", ".mjs", ".html", ".htm", ".css")
_GITHUB_RE = re.compile(r"^https?://github\.com/(?P<owner>[A-Za-z0-9_.\-]+)/(?P<repo>[A-Za-z0-9_.\-]+)")


def _hash_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scan_tree(
    base: str,
    previous: dict[str, list[Any]] | None,
    *,
    extensions: tuple[str, ...] | None = None,
    skip_dirs: set[str] | None = None,
) -> dict[str, list[Any]]:
    """Map rel path -> [size, mtime_ns, sha256]; reuses hashes of unchanged files."""
    out: dict[str, list[Any]] = {}
    if not os.path.isdir(base):
        return out
    previous = previous or {}
    skip = {"__pycache__", ".git"} | (skip_dirs or set())
    for root, dirs, files in os.walk(base, followlinks=False):
        dirs[:] = [d for d in dirs if d not in skip and not os.path.islink(os.path.join(root, d))]
        for name in files:
            if name.endswith((".pyc", ".pyo")):
                continue
            if extensions and not name.lower().endswith(extensions):
                continue
            full = os.path.join(root, name)
            if os.path.islink(full):
                continue
            try:
                st = os.stat(full)
            except OSError:
                continue
            rel = os.path.relpath(full, base).replace(os.sep, "/")
            old = previous.get(rel)
            if old and old[0] == st.st_size and old[1] == st.st_mtime_ns:
                out[rel] = old
                continue
            try:
                out[rel] = [st.st_size, st.st_mtime_ns, _hash_file(full)]
            except OSError:
                continue
    return out


def _diff(old: dict[str, list[Any]], new: dict[str, list[Any]]) -> list[str]:
    changed = [p for p, v in new.items() if p not in old or old[p][2] != v[2]]
    changed += [p for p in old if p not in new]
    return sorted(changed)


def compute_integrity(config_dir: str, baseline: dict[str, Any], versions: dict[str, str | None]) -> dict[str, Any]:
    """Current state of custom_components and www (executor)."""
    custom_dir = os.path.join(config_dir, "custom_components")
    current: dict[str, Any] = {"custom": {}, "www": {}}
    old_custom = baseline.get("custom", {})
    if os.path.isdir(custom_dir):
        for name in sorted(os.listdir(custom_dir)):
            path = os.path.join(custom_dir, name)
            if not os.path.isdir(path) or os.path.islink(path) or name.startswith((".", "__")):
                continue
            current["custom"][name] = {
                "version": versions.get(name),
                "files": scan_tree(path, (old_custom.get(name) or {}).get("files")),
            }
    current["www"] = scan_tree(
        os.path.join(config_dir, "www"), baseline.get("www"), extensions=WWW_EXTENSIONS, skip_dirs={"community"}
    )
    return current


def evaluate_integrity(
    baseline: dict[str, Any], current: dict[str, Any]
) -> tuple[list[Finding], dict[str, Any], list[str]]:
    """Return findings, the baseline to keep (auto accepted updates) and updated domains."""
    findings: list[Finding] = []
    new_baseline = {"custom": dict(baseline.get("custom", {})), "www": baseline.get("www", {})}
    updated: list[str] = []
    for domain, info in current["custom"].items():
        old = baseline.get("custom", {}).get(domain)
        if old is None:
            findings.append(
                make_finding(
                    "custom_new",
                    Severity.MEDIUM,
                    Category.SUPPLY_CHAIN,
                    domain,
                    info.get("version"),
                    domain=domain,
                    version=info.get("version") or "?",
                )
            )
            continue
        changed = _diff(old.get("files", {}), info["files"])
        if not changed:
            new_baseline["custom"][domain] = info
            continue
        if info.get("version") != old.get("version"):
            new_baseline["custom"][domain] = info
            updated.append(domain)
            continue
        findings.append(
            make_finding(
                "custom_code_changed",
                Severity.HIGH,
                Category.SUPPLY_CHAIN,
                domain,
                ",".join(changed[:50]),
                domain=domain,
                version=info.get("version") or "?",
                files=", ".join(changed[:10]),
            )
        )
    for domain in list(new_baseline["custom"]):
        if domain not in current["custom"]:
            new_baseline["custom"].pop(domain)
    www_changed = _diff(baseline.get("www", {}), current["www"])
    if www_changed:
        findings.append(
            make_finding(
                "www_changed",
                Severity.MEDIUM,
                Category.SUPPLY_CHAIN,
                ",".join(www_changed[:50]),
                files=", ".join(www_changed[:10]),
            )
        )
    return findings, new_baseline, updated


def github_repo(url: str | None) -> str | None:
    """owner/repo from a GitHub URL."""
    if not url:
        return None
    m = _GITHUB_RE.match(url)
    if m is None:
        return None
    repo = m.group("repo").removesuffix(".git")
    return f"{m.group('owner')}/{repo}"


async def _async_repo_info(ctx: AuditContext, full: str) -> dict[str, Any] | None:
    cache: dict[str, Any] = ctx.baseline.setdefault("repo_cache", {})
    entry = cache.get(full)
    if entry and time.time() - entry.get("time", 0) < REPO_TTL:
        return entry.get("data")
    session = async_get_clientsession(ctx.hass)
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token := ctx.options.get(CONF_GITHUB_TOKEN):
        headers["Authorization"] = f"Bearer {token}"
    timeout = aiohttp.ClientTimeout(total=15)
    try:
        async with session.get(f"{GITHUB_API}/repos/{full}", headers=headers, timeout=timeout) as resp:
            if resp.status == 404:
                data: dict[str, Any] | None = {"missing": True}
            elif resp.status != 200:
                return entry.get("data") if entry else None
            else:
                repo = await resp.json(content_type=None)
                data = {
                    "full_name": repo.get("full_name"),
                    "archived": bool(repo.get("archived")),
                    "pushed_at": repo.get("pushed_at"),
                    "owner": (repo.get("owner") or {}).get("login"),
                    "owner_created_at": None,
                }
                owner = data["owner"]
                if owner:
                    async with session.get(f"{GITHUB_API}/users/{owner}", headers=headers, timeout=timeout) as uresp:
                        if uresp.status == 200:
                            data["owner_created_at"] = (await uresp.json(content_type=None)).get("created_at")
    except (aiohttp.ClientError, TimeoutError, ValueError):
        return entry.get("data") if entry else None
    cache[full] = {"time": time.time(), "data": data}
    return data


async def async_check(ctx: AuditContext) -> list[Finding]:
    """Integrity, repository health, unused integrations, external resources."""
    hass = ctx.hass
    out: list[Finding] = []
    custom = await async_get_custom_components(hass)
    versions = {domain: (str(i.version) if i.version else None) for domain, i in custom.items()}

    baseline = ctx.baseline.get("integrity")
    current = await hass.async_add_executor_job(compute_integrity, hass.config.path(), baseline or {}, versions)
    ctx.cache["integrity_current"] = current
    if baseline is None:
        ctx.baseline["integrity"] = current
    else:
        findings, new_baseline, updated = evaluate_integrity(baseline, current)
        out.extend(findings)
        ctx.baseline["integrity"] = new_baseline
        if updated:
            ctx.cache["integrity_updated"] = updated

    # Repository health
    now = dt_util.utcnow()
    for domain, integ in custom.items():
        if domain == DOMAIN:
            continue
        full = github_repo(integ.issue_tracker) or github_repo(integ.documentation)
        if full is None:
            continue
        info = await _async_repo_info(ctx, full)
        if not info:
            continue
        if info.get("missing"):
            out.append(
                make_finding(
                    "repo_missing", Severity.MEDIUM, Category.SUPPLY_CHAIN, domain, full, domain=domain, repo=full
                )
            )
            continue
        actual = info.get("full_name") or full
        if actual.lower() != full.lower():
            out.append(
                make_finding(
                    "repo_moved",
                    Severity.HIGH,
                    Category.SUPPLY_CHAIN,
                    domain,
                    actual,
                    domain=domain,
                    old=full,
                    new=actual,
                )
            )
        if info.get("archived"):
            out.append(
                make_finding(
                    "repo_archived", Severity.MEDIUM, Category.SUPPLY_CHAIN, domain, domain=domain, repo=actual
                )
            )
        elif (pushed := dt_util.parse_datetime(info.get("pushed_at") or "")) and (now - pushed).days > STALE_DAYS:
            out.append(
                make_finding(
                    "repo_stale",
                    Severity.LOW,
                    Category.SUPPLY_CHAIN,
                    domain,
                    domain=domain,
                    repo=actual,
                    days=(now - pushed).days,
                )
            )
        if (created := dt_util.parse_datetime(info.get("owner_created_at") or "")) and (
            now - created
        ).days < NEW_OWNER_DAYS:
            out.append(
                make_finding(
                    "repo_new_owner",
                    Severity.MEDIUM,
                    Category.SUPPLY_CHAIN,
                    domain,
                    info.get("owner"),
                    domain=domain,
                    repo=actual,
                    days=(now - created).days,
                )
            )

    # Installed but not loaded
    components = hass.config.components
    for domain in custom:
        if domain == DOMAIN:
            continue
        loaded = domain in components or any(c.startswith(f"{domain}.") or c.endswith(f".{domain}") for c in components)
        if not loaded:
            out.append(make_finding("custom_unused", Severity.LOW, Category.SUPPLY_CHAIN, domain, domain=domain))

    # Frontend resources from third party hosts
    own_hosts = {urlsplit(u).hostname for u in (hass.config.external_url, hass.config.internal_url) if u}
    for url in await _async_resource_urls(hass):
        parts = urlsplit(url)
        if parts.scheme in ("http", "https") and parts.hostname and parts.hostname not in own_hosts:
            out.append(
                make_finding(
                    "external_resource",
                    Severity.MEDIUM,
                    Category.SUPPLY_CHAIN,
                    url,
                    host=parts.hostname,
                    url=url,
                )
            )
    return out


async def _async_resource_urls(hass) -> list[str]:
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA  # noqa: PLC0415
    except ImportError:
        return []
    data = hass.data.get(LOVELACE_DATA)
    if data is None:
        return []
    resources = data.resources
    try:
        if hasattr(resources, "loaded") and not resources.loaded:
            await resources.async_load()
            resources.loaded = True
        return [str(item.get("url", "")) for item in resources.async_items()]
    except Exception:  # noqa: BLE001
        return []


def accept_integrity(baseline: dict[str, Any], current: dict[str, Any] | None, domain: str | None) -> None:
    """Accept the current state as new baseline (all or one domain)."""
    if current is None:
        return
    integrity = baseline.setdefault("integrity", {"custom": {}, "www": {}})
    if domain is None:
        baseline["integrity"] = current
        return
    if domain == "www":
        integrity["www"] = current.get("www", {})
        return
    if domain in current.get("custom", {}):
        integrity.setdefault("custom", {})[domain] = current["custom"][domain]
