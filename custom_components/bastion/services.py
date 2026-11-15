"""Service actions."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import config_validation as cv
import probatio

from .const import ALL_AREAS, DOMAIN


def _bastion(hass: HomeAssistant):
    from . import get_bastion  # noqa: PLC0415

    if (bastion := get_bastion(hass)) is None:
        raise HomeAssistantError("Bastion is not loaded")
    return bastion


async def _require_admin(hass: HomeAssistant, call: ServiceCall) -> None:
    """Bastion services change security relevant state: admins only."""
    if call.context.user_id is None:
        return
    user = await hass.auth.async_get_user(call.context.user_id)
    if user is None or not user.is_admin:
        raise Unauthorized(context=call.context)


def async_register_services(hass: HomeAssistant) -> None:
    """Register all services."""

    async def run_audit(call: ServiceCall) -> ServiceResponse:
        await _require_admin(hass, call)
        bastion = _bastion(hass)
        await bastion.async_run_audit()
        return bastion.summary()

    async def external_scan(call: ServiceCall) -> ServiceResponse:
        await _require_admin(hass, call)
        return await _bastion(hass).async_run_probe()

    async def git_commit(call: ServiceCall) -> ServiceResponse:
        await _require_admin(hass, call)
        result = await _bastion(hass).git.async_commit("manual", call.data.get("message"))
        return {k: v for k, v in result.items() if k in ("committed", "pushed", "sha", "summary", "push_error")}

    async def git_restore(call: ServiceCall) -> ServiceResponse:
        await _require_admin(hass, call)
        return await _bastion(hass).git.async_restore(
            call.data["commit"],
            areas=call.data.get("areas"),
            paths=call.data.get("paths"),
            restart=call.data.get("restart", False),
        )

    async def dismiss_finding(call: ServiceCall) -> None:
        await _require_admin(hass, call)
        await _bastion(hass).async_dismiss(call.data["finding_id"], call.data.get("dismissed", True))

    async def accept_integrity(call: ServiceCall) -> None:
        await _require_admin(hass, call)
        await _bastion(hass).async_accept_integrity(call.data.get("domain"))

    async def send_report(call: ServiceCall) -> ServiceResponse:
        await _require_admin(hass, call)
        return await _bastion(hass).async_send_report()

    async def block(call: ServiceCall) -> ServiceResponse:
        await _require_admin(hass, call)
        result = await _bastion(hass).responder.async_block(
            ip=call.data.get("ip"),
            token_id=call.data.get("token_id"),
            user_id=call.data.get("user_id"),
            actor_id=call.context.user_id,
        )
        return {"result": result}

    async def reset_host_key(call: ServiceCall) -> None:
        await _require_admin(hass, call)
        await _bastion(hass).git.async_reset_host_key()

    hass.services.async_register(DOMAIN, "run_audit", run_audit, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "external_scan", external_scan, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(
        DOMAIN,
        "git_commit",
        git_commit,
        schema=probatio.Schema({probatio.Optional("message"): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "git_restore",
        git_restore,
        schema=probatio.Schema(
            {
                probatio.Required("commit"): probatio.All(cv.string, probatio.Match(r"^[0-9a-f]{40}$")),
                probatio.Optional("areas"): [probatio.In(ALL_AREAS)],
                probatio.Optional("paths"): [cv.string],
                probatio.Optional("restart", default=False): cv.boolean,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        "dismiss_finding",
        dismiss_finding,
        schema=probatio.Schema(
            {probatio.Required("finding_id"): cv.string, probatio.Optional("dismissed", default=True): cv.boolean}
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "accept_integrity",
        accept_integrity,
        schema=probatio.Schema({probatio.Optional("domain"): cv.string}),
    )
    hass.services.async_register(DOMAIN, "reset_git_host_key", reset_host_key)
    hass.services.async_register(DOMAIN, "send_report", send_report, supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(
        DOMAIN,
        "block",
        block,
        schema=probatio.Schema(
            {
                probatio.Optional("ip"): cv.string,
                probatio.Optional("token_id"): cv.string,
                probatio.Optional("user_id"): cv.string,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
