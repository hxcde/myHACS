"""Websocket API for the panel. Admin only."""

from __future__ import annotations

from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import probatio

from .const import ALL_AREAS


def _bastion(hass: HomeAssistant):
    from . import get_bastion  # noqa: PLC0415

    return get_bastion(hass)


def _guard(connection, msg) -> Any:
    bastion = _bastion(connection.hass)
    if bastion is None:
        connection.send_error(msg["id"], "not_loaded", "Bastion is not loaded")
    return bastion


def _with_usage(monitor, token_id: str, token: dict[str, Any]) -> dict[str, Any]:
    out = {**token, "id": token_id}
    if token.get("type") == "long_lived_access_token":
        usage = monitor.token_usage.get(token_id) or {}
        out["last_used_at"] = usage.get("last_used_at")
        out["last_used_ip"] = usage.get("last_ip")
    return out


def _overview(bastion) -> dict[str, Any]:
    return {
        "summary": bastion.summary(),
        "findings": [f.as_dict() for f in bastion.findings],
        "git": bastion.git.status(),
        "logins": bastion.logins.stats(),
        "anomaly": bastion.anomaly.summary(),
        "probe": bastion.data.get("probe"),
        "canary": bastion.canary.summary(),
        "report": bastion.data.get("last_report"),
        "history": bastion.data.get("history", [])[-30:],
        "language": bastion.hass.config.language,
    }


@websocket_api.websocket_command({probatio.Required("type"): "bastion/overview"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_overview(hass, connection, msg) -> None:
    """Everything the panel shows on its first tab."""
    if (bastion := _guard(connection, msg)) is None:
        return
    connection.send_result(msg["id"], _overview(bastion))


@websocket_api.websocket_command({probatio.Required("type"): "bastion/audit/run"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_run_audit(hass, connection, msg) -> None:
    """Run the audit now."""
    if (bastion := _guard(connection, msg)) is None:
        return
    await bastion.async_run_audit()
    connection.send_result(msg["id"], _overview(bastion))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "bastion/finding/dismiss",
        probatio.Required("finding_id"): str,
        probatio.Optional("dismissed", default=True): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_dismiss(hass, connection, msg) -> None:
    """Hide or show a finding."""
    if (bastion := _guard(connection, msg)) is None:
        return
    await bastion.async_dismiss(msg["finding_id"], msg["dismissed"])
    connection.send_result(msg["id"], _overview(bastion))


@websocket_api.websocket_command(
    {probatio.Required("type"): "bastion/integrity/accept", probatio.Optional("domain"): str}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_accept_integrity(hass, connection, msg) -> None:
    """Accept the current custom_components / www state."""
    if (bastion := _guard(connection, msg)) is None:
        return
    await bastion.async_accept_integrity(msg.get("domain"))
    connection.send_result(msg["id"], _overview(bastion))


@websocket_api.websocket_command({probatio.Required("type"): "bastion/logins"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_logins(hass, connection, msg) -> None:
    """Login log, tokens and users."""
    if (bastion := _guard(connection, msg)) is None:
        return
    monitor = bastion.logins
    connection.send_result(
        msg["id"],
        {
            "log": list(monitor.log)[-400:][::-1],
            "tokens": sorted(
                (_with_usage(monitor, token_id, token) for token_id, token in monitor.tokens.items()),
                key=lambda t: t.get("last_used_at") or "",
                reverse=True,
            ),
            "users": monitor.users,
            "stats": monitor.stats(),
        },
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "bastion/git/history",
        probatio.Optional("limit", default=100): int,
        probatio.Optional("refresh", default=True): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_git_history(hass, connection, msg) -> None:
    """Commit history."""
    if (bastion := _guard(connection, msg)) is None:
        return
    try:
        result = await bastion.git.async_history(min(msg["limit"], 500), msg["refresh"])
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "git_error", str(err))
        return
    result["status"] = bastion.git.status()
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {probatio.Required("type"): "bastion/git/files", probatio.Required("commit"): probatio.Match(r"^[0-9a-f]{40}$")}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_git_files(hass, connection, msg) -> None:
    """Files of a commit compared to the current configuration."""
    if (bastion := _guard(connection, msg)) is None:
        return
    try:
        files = await bastion.git.async_commit_files(msg["commit"])
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "git_error", str(err))
        return
    connection.send_result(msg["id"], {"files": files})


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "bastion/git/diff",
        probatio.Required("commit"): probatio.Match(r"^[0-9a-f]{40}$"),
        probatio.Required("path"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_git_diff(hass, connection, msg) -> None:
    """Diff of one file."""
    if (bastion := _guard(connection, msg)) is None:
        return
    try:
        result = await bastion.git.async_file_diff(msg["commit"], msg["path"])
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "git_error", str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({probatio.Required("type"): "bastion/git/commit", probatio.Optional("message"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_git_commit(hass, connection, msg) -> None:
    """Commit now."""
    if (bastion := _guard(connection, msg)) is None:
        return
    try:
        result = await bastion.git.async_commit("manual", msg.get("message"))
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "git_error", str(err))
        return
    await bastion.async_run_audit(notify=False)
    connection.send_result(
        msg["id"],
        {
            k: v
            for k, v in result.items()
            if k
            in (
                "committed",
                "pushed",
                "sha",
                "summary",
                "push_error",
                "added",
                "modified",
                "deleted",
                "skipped_secrets",
            )
        },
    )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "bastion/git/restore",
        probatio.Required("commit"): probatio.Match(r"^[0-9a-f]{40}$"),
        probatio.Optional("areas"): [probatio.In(ALL_AREAS)],
        probatio.Optional("paths"): [str],
        probatio.Optional("restart", default=False): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_git_restore(hass, connection, msg) -> None:
    """Restore a commit."""
    if (bastion := _guard(connection, msg)) is None:
        return
    try:
        result = await bastion.git.async_restore(
            msg["commit"], areas=msg.get("areas"), paths=msg.get("paths"), restart=msg["restart"]
        )
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "git_error", str(err))
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({probatio.Required("type"): "bastion/probe/run"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_probe(hass, connection, msg) -> None:
    """Run the external probe."""
    if (bastion := _guard(connection, msg)) is None:
        return
    await bastion.async_run_probe()
    connection.send_result(msg["id"], _overview(bastion))


@websocket_api.websocket_command({probatio.Required("type"): "bastion/report/send"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_report(hass, connection, msg) -> None:
    """Build and send the weekly report now."""
    if (bastion := _guard(connection, msg)) is None:
        return
    await bastion.async_send_report()
    connection.send_result(msg["id"], _overview(bastion))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "bastion/security/block",
        probatio.Optional("ip"): str,
        probatio.Optional("token_id"): str,
        probatio.Optional("user_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_block(hass, connection, msg) -> None:
    """Revoke a token, ban an IP and/or deactivate a user."""
    if (bastion := _guard(connection, msg)) is None:
        return
    result = await bastion.responder.async_block(
        ip=msg.get("ip"),
        token_id=msg.get("token_id"),
        user_id=msg.get("user_id"),
        actor_id=connection.user.id,
    )
    bastion.logins.record(
        "blocked",
        {
            "ip": msg.get("ip"),
            "token_id": msg.get("token_id"),
            "user_id": msg.get("user_id"),
            "result": "; ".join(result),
            "actor": connection.user.id,
        },
    )
    connection.send_result(msg["id"], {"result": result})


def async_register_websocket(hass: HomeAssistant) -> None:
    """Register all commands."""
    for command in (
        ws_overview,
        ws_run_audit,
        ws_dismiss,
        ws_accept_integrity,
        ws_logins,
        ws_git_history,
        ws_git_files,
        ws_git_diff,
        ws_git_commit,
        ws_git_restore,
        ws_probe,
        ws_report,
        ws_block,
    ):
        websocket_api.async_register_command(hass, command)
