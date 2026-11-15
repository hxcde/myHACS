"""Add-on privileges (only with Supervisor; skipped on Container installs)."""

from __future__ import annotations

from ..const import Category, Severity
from ..models import Finding, make_finding
from . import AuditContext

RISKY_PRIVILEGES = {"SYS_ADMIN", "SYS_MODULE", "SYS_RAWIO", "SYS_PTRACE", "DAC_READ_SEARCH", "NET_ADMIN"}


async def async_check(ctx: AuditContext) -> list[Finding]:
    """Check installed add-ons."""
    hass = ctx.hass
    if "hassio" not in hass.config.components:
        return []
    try:
        from homeassistant.components.hassio import get_addons_info  # noqa: PLC0415
    except ImportError:
        return []
    out: list[Finding] = []
    for slug, info in (get_addons_info(hass) or {}).items():
        if not info:
            continue
        name = info.get("name") or slug
        flags: list[str] = []
        if info.get("full_access"):
            flags.append("full_access")
        if info.get("host_network"):
            flags.append("host_network")
        if info.get("protected") is False:
            flags.append("protection mode off")
        if info.get("apparmor") == "disable":
            flags.append("AppArmor off")
        privileged = set(info.get("privileged") or [])
        if risky := sorted(privileged & RISKY_PRIVILEGES):
            flags.append("privileged: " + ", ".join(risky))
        if flags:
            severity = Severity.HIGH if ("protection mode off" in flags or "full_access" in flags) else Severity.MEDIUM
            out.append(
                make_finding("addon_risky", severity, Category.EXPOSURE, slug, name=name, flags=", ".join(flags))
            )
        ports = [str(v) for v in (info.get("network") or {}).values() if v]
        if ports:
            out.append(
                make_finding(
                    "addon_port_exposed", Severity.LOW, Category.EXPOSURE, slug, name=name, ports=", ".join(ports)
                )
            )
    return out
