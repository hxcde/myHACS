"""Security audit framework."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.core import HomeAssistant

from ..models import Finding

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class AuditContext:
    """Shared input of all checks."""

    hass: HomeAssistant
    options: dict[str, Any]
    cache: dict[str, Any]
    baseline: dict[str, Any]
    errors: list[str] = field(default_factory=list)


CheckFunc = Callable[[AuditContext], Awaitable[list[Finding]]]


def _checks() -> dict[str, CheckFunc]:
    from . import access, config, exposure, firmware, supervisor, supply_chain, updates  # noqa: PLC0415

    return {
        "access": access.async_check,
        "http": exposure.async_check_http,
        "exposure": exposure.async_check,
        "updates": updates.async_check,
        "firmware": firmware.async_check,
        "supply_chain": supply_chain.async_check,
        "config": config.async_check,
        "supervisor": supervisor.async_check,
    }


CHECK_GROUPS = ("access", "http", "exposure", "updates", "firmware", "supply_chain", "config", "supervisor")


async def async_run_audit(ctx: AuditContext, disabled: list[str] | None = None) -> list[Finding]:
    """Run all enabled check groups. A failing group never stops the others."""
    findings: list[Finding] = []
    disabled_set = set(disabled or [])
    for name, func in _checks().items():
        if name in disabled_set:
            continue
        try:
            findings.extend(await func(ctx))
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Bastion check group %s failed", name)
            ctx.errors.append(f"{name}: {err}")
    return [f for f in findings if f.check not in disabled_set]
