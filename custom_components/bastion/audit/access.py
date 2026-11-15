"""Accounts, MFA, tokens and auth providers."""

from __future__ import annotations

from datetime import timedelta
import ipaddress

from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
from homeassistant.util import dt as dt_util

from ..const import CONF_MAX_ADMINS, CONF_TOKEN_MAX_AGE_DAYS, CONF_TOKEN_UNUSED_DAYS, Category, Severity
from ..models import Finding, make_finding
from ..texts import ROLE, lang, misc
from . import AuditContext

INACTIVE_DAYS = 90


def _too_wide(net: ipaddress.IPv4Network | ipaddress.IPv6Network) -> bool:
    if net.version == 4:
        return net.prefixlen < 16 or not net.is_private
    return net.prefixlen < 48 or net.is_global


async def async_check(ctx: AuditContext) -> list[Finding]:
    """Run access checks."""
    hass = ctx.hass
    language = hass.config.language
    roles = ROLE[lang(language)]
    out: list[Finding] = []
    now = dt_util.utcnow()
    max_age = int(ctx.options.get(CONF_TOKEN_MAX_AGE_DAYS) or 365)
    unused_days = int(ctx.options.get(CONF_TOKEN_UNUSED_DAYS) or 90)

    canary_user = ctx.cache.get("canary_user")
    usage: dict = ctx.cache.get("token_usage") or {}
    usage_since = dt_util.parse_datetime(ctx.cache.get("usage_since") or "")
    users = [u for u in await hass.auth.async_get_users() if not u.system_generated and u.id != canary_user]
    admins = []
    for user in users:
        if not user.is_active:
            continue
        name = user.name or user.id[:8]
        if user.is_admin:
            admins.append(name)
        has_password = any(c.auth_provider_type == "homeassistant" for c in user.credentials)
        if has_password and not await hass.auth.async_get_enabled_mfa(user):
            out.append(
                make_finding(
                    "mfa_missing",
                    Severity.HIGH if user.is_admin else Severity.MEDIUM,
                    Category.ACCESS,
                    user.id,
                    user=name,
                    user_id=user.id,
                    role=roles["admin" if user.is_admin else "user"],
                )
            )
        last_used = None
        for token in user.refresh_tokens.values():
            if token.last_used_at and (last_used is None or token.last_used_at > last_used):
                last_used = token.last_used_at
            if token.token_type != TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN:
                continue
            token_name = token.client_name or token.client_id or token.id[:8]
            age = (now - token.created_at).days
            if age > max_age:
                out.append(
                    make_finding(
                        "token_old",
                        Severity.MEDIUM,
                        Category.ACCESS,
                        token.id,
                        name=token_name,
                        user=name,
                        days=age,
                        token_id=token.id,
                    )
                )
            # HA does not record API use of long-lived tokens; Bastion's token guard does.
            observed = dt_util.parse_datetime(usage.get(token.id, {}).get("last_used_at") or "")
            if observed is not None and (last_used is None or observed > last_used):
                last_used = observed
            if observed is None and (usage_since is None or (now - usage_since).days < unused_days):
                continue  # not observed long enough to judge
            reference = observed or max(usage_since, token.created_at)
            idle = (now - reference).days
            if idle > unused_days:
                out.append(
                    make_finding(
                        "token_unused",
                        Severity.MEDIUM,
                        Category.ACCESS,
                        token.id,
                        name=token_name,
                        user=name,
                        when=misc("unused_days", language, days=idle),
                        token_id=token.id,
                    )
                )
        if not user.is_owner and last_used is not None and now - last_used > timedelta(days=INACTIVE_DAYS):
            out.append(
                make_finding(
                    "inactive_user",
                    Severity.LOW,
                    Category.ACCESS,
                    user.id,
                    user=name,
                    days=(now - last_used).days,
                    user_id=user.id,
                )
            )

    max_admins = int(ctx.options.get(CONF_MAX_ADMINS) or 2)
    if len(admins) > max_admins:
        out.append(
            make_finding(
                "too_many_admins",
                Severity.LOW,
                Category.ACCESS,
                "admins",
                count=len(admins),
                users=", ".join(sorted(admins)),
            )
        )

    trusted_proxies = []
    if (http := getattr(hass, "http", None)) is not None:
        trusted_proxies = list(getattr(http, "trusted_proxies", []) or [])
    for provider in hass.auth.auth_providers:
        if provider.type != "trusted_networks":
            continue
        networks = list(getattr(provider, "trusted_networks", []) or [])
        for net in networks:
            if _too_wide(net):
                out.append(
                    make_finding(
                        "trusted_networks_wide",
                        Severity.CRITICAL if net.prefixlen == 0 or net.is_global else Severity.HIGH,
                        Category.ACCESS,
                        str(net),
                        network=str(net),
                    )
                )
            for proxy in trusted_proxies:
                if net.version == proxy.version and net.overlaps(proxy):
                    out.append(
                        make_finding(
                            "trusted_networks_proxy",
                            Severity.HIGH,
                            Category.ACCESS,
                            str(net),
                            str(proxy),
                            network=str(net),
                            proxy=str(proxy),
                        )
                    )
        if getattr(provider, "_allow_bypass_login", False) or provider.config.get("allow_bypass_login"):
            out.append(make_finding("trusted_networks_bypass", Severity.MEDIUM, Category.ACCESS, provider.id or "tn"))
    return out
