"""Configuration hygiene: plain text secrets, shell templates, debug tools, backups."""

from __future__ import annotations

from datetime import timedelta
import logging
import os
import stat
from typing import Any

from homeassistant.util import dt as dt_util

from ..const import Category, Severity
from ..gitsync.collector import CONFIG_EXCLUDE_DIRS
from ..models import Finding, make_finding
from ..secret_scan import scan_text
from ..texts import misc
from . import AuditContext

_LOGGER = logging.getLogger(__name__)

BACKUP_MAX_AGE = timedelta(days=8)
MAX_SCAN_SIZE = 2 * 1024 * 1024
LOCAL_AGENTS = ("backup.local", "hassio.local")


def scan_config_secrets(config_dir: str) -> dict[str, list[tuple[int, str]]]:
    """Plain text credentials in YAML below config_dir (executor)."""
    out: dict[str, list[tuple[int, str]]] = {}
    base = os.path.realpath(config_dir)
    for root, dirs, files in os.walk(base, followlinks=False):
        rel_root = os.path.relpath(root, base)
        if rel_root == ".":
            dirs[:] = [d for d in dirs if d not in CONFIG_EXCLUDE_DIRS and not d.startswith(".")]
        else:
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git") and not d.startswith(".")]
        for name in files:
            if not name.endswith((".yaml", ".yml")) or name in ("secrets.yaml", "secrets.yml"):
                continue
            full = os.path.join(root, name)
            if os.path.islink(full):
                continue
            try:
                if os.path.getsize(full) > MAX_SCAN_SIZE:
                    continue
                with open(full, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            hits = scan_text(text)
            if hits:
                rel = os.path.relpath(full, base).replace(os.sep, "/")
                out[rel] = [(h.line, h.key or h.kind) for h in hits]
    return out


def _has_template(value: Any) -> bool:
    return isinstance(value, str) and ("{{" in value or "{%" in value)


def _command_line_templates(conf: Any) -> list[tuple[str, str]]:
    """(platform, name) of command_line entries with templated commands."""
    out = []
    for item in conf or []:
        if not isinstance(item, dict):
            continue
        for platform, cfg in item.items():
            if not isinstance(cfg, dict):
                continue
            for key in (
                "command",
                "command_on",
                "command_off",
                "command_state",
                "command_open",
                "command_close",
                "command_stop",
            ):
                if _has_template(cfg.get(key)):
                    out.append((platform, str(cfg.get("name") or cfg.get("unique_id") or platform)))
                    break
    return out


async def async_check(ctx: AuditContext) -> list[Finding]:
    """Run configuration checks."""
    hass = ctx.hass
    language = hass.config.language
    out: list[Finding] = []

    secrets = await hass.async_add_executor_job(scan_config_secrets, hass.config.path())
    for rel, hits in sorted(secrets.items()):
        out.append(
            make_finding(
                "plaintext_secret",
                Severity.MEDIUM,
                Category.CONFIG,
                rel,
                ",".join(str(h[0]) for h in hits),
                file=rel,
                lines=", ".join(str(h[0]) for h in hits[:10]),
                kinds=", ".join(sorted({h[1] for h in hits})),
            )
        )

    try:
        from homeassistant import config as conf_util  # noqa: PLC0415

        conf = await conf_util.async_hass_config_yaml(hass)
    except Exception as err:  # noqa: BLE001 - invalid YAML is reported by HA itself
        _LOGGER.debug("Could not load configuration for checks: %s", err)
        conf = {}
    for name, command in (conf.get("shell_command") or {}).items():
        if _has_template(command):
            out.append(
                make_finding(
                    "shell_template",
                    Severity.MEDIUM,
                    Category.CONFIG,
                    "shell_command",
                    name,
                    kind="shell_command",
                    name=name,
                    shell="",
                )
            )
    for platform, name in _command_line_templates(conf.get("command_line")):
        out.append(
            make_finding(
                "shell_template",
                Severity.HIGH,
                Category.CONFIG,
                "command_line",
                platform,
                name,
                kind=f"command_line {platform}",
                name=name,
                shell=misc("shell_yes", language),
            )
        )

    for domain, label in (("python_script", "python_script"), ("pyscript", "pyscript")):
        if domain in hass.config.components:
            out.append(make_finding("python_script_enabled", Severity.LOW, Category.CONFIG, domain, name=label))
    if "debug_console" in hass.config.components:
        out.append(make_finding("debug_console_enabled", Severity.HIGH, Category.CONFIG, "debug_console"))

    secrets_path = hass.config.path("secrets.yaml")
    try:
        mode = (await hass.async_add_executor_job(os.stat, secrets_path)).st_mode
        if mode & (stat.S_IROTH | stat.S_IWOTH):
            out.append(
                make_finding(
                    "secrets_world_readable", Severity.LOW, Category.CONFIG, "secrets", mode=format(mode & 0o777, "o")
                )
            )
    except OSError:
        pass

    out.extend(_backup_findings(hass, language))
    return out


def _backup_findings(hass, language: str) -> list[Finding]:
    try:
        from homeassistant.components.backup.const import DATA_MANAGER  # noqa: PLC0415
    except ImportError:
        return []
    manager = hass.data.get(DATA_MANAGER)
    if manager is None:
        return []
    out: list[Finding] = []
    data = manager.config.data
    create = data.create_backup
    agent_ids = list(create.agent_ids or [])
    last = data.last_completed_automatic_backup
    if last is None or dt_util.utcnow() - last > BACKUP_MAX_AGE:
        when = dt_util.as_local(last).strftime("%Y-%m-%d %H:%M") if last else misc("never", language)
        out.append(make_finding("backup_stale", Severity.MEDIUM, Category.CONFIG, "backup", when=when))
    if not agent_ids:
        return out
    if create.password is None:
        out.append(make_finding("backup_unencrypted", Severity.MEDIUM, Category.CONFIG, "backup", agents=""))
    else:
        unprotected = [
            agent_id
            for agent_id in agent_ids
            if agent_id not in LOCAL_AGENTS and (cfg := data.agents.get(agent_id)) is not None and not cfg.protected
        ]
        if unprotected:
            out.append(
                make_finding(
                    "backup_unencrypted",
                    Severity.MEDIUM,
                    Category.CONFIG,
                    "backup",
                    ",".join(unprotected),
                    agents=f" ({', '.join(unprotected)})",
                )
            )
    if all(agent_id in LOCAL_AGENTS for agent_id in agent_ids):
        out.append(make_finding("backup_local_only", Severity.MEDIUM, Category.CONFIG, "backup_local"))
    return out
