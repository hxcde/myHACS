"""Diagnostics with all secrets removed."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import get_options
from .const import (
    CONF_GIT_HOST_KEY,
    CONF_GIT_PUBLIC_KEY,
    CONF_GIT_URL,
    CONF_NOTIFY_TARGETS,
    CONF_PROBE_URL,
    SECRET_OPTIONS,
)

TO_REDACT = SECRET_OPTIONS | {CONF_GIT_URL, CONF_PROBE_URL, CONF_GIT_PUBLIC_KEY, CONF_GIT_HOST_KEY, CONF_NOTIFY_TARGETS}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics."""
    bastion = entry.runtime_data
    status = bastion.git.status()
    status.pop("url", None)
    return {
        "options": async_redact_data(get_options(entry), TO_REDACT),
        "summary": bastion.summary(),
        "findings": [
            {"check": f.check, "severity": f.severity.value, "dismissed": f.dismissed} for f in bastion.findings
        ],
        "git": status,
        "audit_errors": bastion.audit_errors,
    }
