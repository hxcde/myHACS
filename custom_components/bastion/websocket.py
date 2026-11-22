"""Websocket API for the panel. Admin only."""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
import probatio

from .alarm.engine import MODES, NOTIFY_EVENTS, SENSOR_TYPES, SUPPORTED_DOMAINS, AlarmError
from .alarm.floorplan import FloorPlanError, clean_floorplan
from .alarm.household import async_probe, valid_address
from .alarm.sounds import BUILTIN, SOUND_KEYS, async_media_files
from .const import ALL_AREAS, DOMAIN
from .texts import alarm_error_text


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
    {
        probatio.Required("type"): "bastion/anomaly/accept",
        probatio.Required("entity_id"): cv.entity_id,
        probatio.Optional("value"): probatio.Coerce(float),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_anomaly_accept(hass, connection, msg) -> None:
    """Mark the deviation of a sensor as normal (learned, never reported again)."""
    if (bastion := _guard(connection, msg)) is None:
        return
    if not await bastion.anomaly.async_accept(msg["entity_id"], msg.get("value")):
        connection.send_error(msg["id"], "not_found", "Sensor wird nicht überwacht oder hat keine aktuelle Abweichung.")
        return
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


# ------------------------------------------------------------------ alarm
_ROOM = probatio.Schema(
    {
        probatio.Optional("id"): probatio.All(str, probatio.Length(max=32)),
        probatio.Required("name"): probatio.All(str, probatio.Length(min=1, max=40)),
        probatio.Optional("icon", default="mdi:door"): probatio.All(str, probatio.Length(max=60)),
        probatio.Optional("sensors", default=[]): [cv.entity_id],
    }
)
_SENSOR = probatio.Schema(
    {
        probatio.Optional("modes", default=list(MODES)): [probatio.In(MODES)],
        probatio.Optional("type", default="delayed"): probatio.In(SENSOR_TYPES),
        probatio.Optional("bypass", default=False): bool,
        probatio.Optional("exit_delay", default=None): probatio.Any(
            None, probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=900))
        ),
        probatio.Optional("entry_delay", default=None): probatio.Any(
            None, probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=900))
        ),
        # Own name; empty or missing = the Home Assistant name.
        probatio.Optional("name", default=None): probatio.Any(
            None, probatio.All(str, probatio.Strip, probatio.Length(max=60), lambda v: v or None)
        ),
    }
)
_DELAY = probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=900))
_CAMERA = probatio.All(cv.entity_id, probatio.Match(r"^camera\."))
_PLAYER = probatio.All(cv.entity_id, probatio.Match(r"^media_player\."))
_VOLUME = probatio.All(probatio.Coerce(float), probatio.Range(min=0.05, max=1.0))
# "" = off, a built-in sound, a media source (e.g. "My media") or an http(s) URL.
_SOUND = probatio.Any(
    "",
    probatio.In([f"bastion:{name}" for name in BUILTIN]),
    probatio.All(str, probatio.Length(max=500), probatio.Match(r"^(media-source://|https?://)\S+$")),
)


def _address(value: Any) -> str:
    value = str(value).strip()
    if not valid_address(value):
        raise probatio.Invalid("IP-Adresse im Heimnetz oder Hostname")
    return value


def _ip_or_tracker(person: dict[str, Any]) -> dict[str, Any]:
    if not person.get("ip") and not person.get("tracker"):
        raise probatio.Invalid("IP-Adresse oder Tracker angeben")
    return person


_PERSON = probatio.All(
    probatio.Schema(
        {
            probatio.Optional("id"): probatio.All(str, probatio.Match(r"^[a-f0-9]{6,16}$")),
            probatio.Required("name"): probatio.All(str, probatio.Strip, probatio.Length(min=1, max=40)),
            probatio.Optional("ip", default=""): probatio.Any("", _address),
            probatio.Optional("tracker", default=None): probatio.Any(
                None, "", probatio.All(cv.entity_id, probatio.Match(r"^device_tracker\."))
            ),
        }
    ),
    _ip_or_tracker,
)


def _floorplan(value: Any) -> dict[str, Any] | None:
    if value in (None, {}):
        return None
    try:
        return clean_floorplan(value)
    except FloorPlanError as err:
        raise probatio.Invalid(str(err)) from err


_ALARM_CONFIG = probatio.Schema(
    {
        probatio.Optional("floorplan"): _floorplan,
        probatio.Optional("rooms"): [_ROOM],
        probatio.Optional("sensors"): {cv.entity_id: _SENSOR},
        probatio.Optional("modes"): {
            probatio.In(MODES): probatio.Schema({probatio.Required("exit"): _DELAY, probatio.Required("entry"): _DELAY})
        },
        probatio.Optional("trigger_time"): probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=3600)),
        probatio.Optional("rearm"): bool,
        probatio.Optional("require_code_arm"): bool,
        probatio.Optional("sabotage_triggers"): bool,
        probatio.Optional("actions"): probatio.Schema(
            {
                probatio.Optional("sirens"): [cv.entity_id],
                probatio.Optional("lights"): [cv.entity_id],
                probatio.Optional("warning"): [cv.entity_id],
                probatio.Optional("notify_events"): [probatio.In(NOTIFY_EVENTS)],
                probatio.Optional("critical_push"): bool,
            }
        ),
        probatio.Optional("worker"): probatio.Schema(
            {
                probatio.Optional("url"): probatio.All(str, probatio.Match(r"^(https://\S+)?$")),
                probatio.Optional("interval"): probatio.All(probatio.Coerce(int), probatio.Range(min=30, max=3600)),
                probatio.Optional("enabled"): bool,
                probatio.Optional("cameras"): [_CAMERA],
                probatio.Optional("snapshots"): probatio.All(probatio.Coerce(int), probatio.Range(min=0, max=5)),
                probatio.Optional("public_url"): probatio.All(
                    str, probatio.Strip, probatio.Length(max=200), probatio.Match(r"^(https?://[^\s/@]+(/\S*)?)?$")
                ),
            }
        ),
        probatio.Optional("people"): probatio.All([_PERSON], probatio.Length(max=20)),
        probatio.Optional("presence"): probatio.Schema(
            {probatio.Optional("away_minutes"): probatio.All(probatio.Coerce(int), probatio.Range(min=2, max=60))}
        ),
        probatio.Optional("remote"): probatio.Schema(
            {
                probatio.Optional("enabled"): bool,
                probatio.Optional("disarm"): bool,
                probatio.Optional("reminder"): bool,
                probatio.Optional("reminder_minutes"): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=5, max=240)
                ),
                probatio.Optional("persons"): [probatio.All(cv.entity_id, probatio.Match(r"^person\."))],
            }
        ),
        probatio.Optional("sounds"): probatio.Schema(
            {
                probatio.Optional("players"): [_PLAYER],
                probatio.Optional("volume"): _VOLUME,
                probatio.Optional("notice_volume"): _VOLUME,
                **{probatio.Optional(key): _SOUND for key in SOUND_KEYS},
            }
        ),
    }
)


def _alarm_payload(hass: HomeAssistant, bastion) -> dict[str, Any]:
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)
    candidates = []
    for state in hass.states.async_all(SUPPORTED_DOMAINS):
        if state.domain == "switch":
            continue
        area_id = None
        if (entry := ent_reg.async_get(state.entity_id)) is not None:
            area_id = entry.area_id
            if area_id is None and entry.device_id and (device := dev_reg.async_get(entry.device_id)) is not None:
                area_id = device.area_id
        area = area_reg.async_get_area(area_id) if area_id else None
        candidates.append(
            {
                "entity_id": state.entity_id,
                "name": state.attributes.get("friendly_name") or state.entity_id,
                "device_class": state.attributes.get("device_class"),
                "area": area.name if area else None,
                "area_icon": area.icon if area else None,
            }
        )
    candidates.sort(key=lambda c: (c["area"] or "~", c["name"]))
    actors = [
        {"entity_id": s.entity_id, "name": s.attributes.get("friendly_name") or s.entity_id}
        for s in hass.states.async_all(("siren", "switch", "light", "script", "scene", "input_boolean", "media_player"))
    ]
    actors.sort(key=lambda a: a["name"].lower())
    cameras = sorted(
        (
            {"entity_id": s.entity_id, "name": s.attributes.get("friendly_name") or s.entity_id}
            for s in hass.states.async_all("camera")
        ),
        key=lambda c: c["name"].lower(),
    )
    players = sorted(
        (
            {"entity_id": s.entity_id, "name": s.attributes.get("friendly_name") or s.entity_id}
            for s in hass.states.async_all("media_player")
        ),
        key=lambda c: c["name"].lower(),
    )
    persons = sorted(
        (
            {"entity_id": s.entity_id, "name": s.attributes.get("friendly_name") or s.entity_id, "state": s.state}
            for s in hass.states.async_all("person")
        ),
        key=lambda c: c["name"].lower(),
    )
    trackers = sorted(
        (
            {"entity_id": s.entity_id, "name": s.attributes.get("friendly_name") or s.entity_id, "state": s.state}
            for s in hass.states.async_all("device_tracker")
            if (entry := ent_reg.async_get(s.entity_id)) is None or entry.platform != DOMAIN
        ),
        key=lambda c: c["name"].lower(),
    )
    relay = bastion.relay
    return {
        "config": bastion.alarm.public_config(),
        "status": bastion.alarm.status(),
        "log": bastion.alarm.log[-60:][::-1],
        "candidates": candidates,
        "actors": actors,
        "cameras": cameras,
        "players": players,
        "persons": persons,
        "household": bastion.household.summary(),
        "trackers": trackers,
        "sounds_builtin": list(BUILTIN),
        "relay": {
            "enabled": relay.enabled,
            "last_ok": relay.last_ok,
            "last_error": relay.last_error,
            "check_urls": relay.check_urls(),
            "backfill": relay.backfill_result,
            "dashboard": relay.dashboard_url,
            "last_commands": relay.last_commands,
        },
        "external_url": hass.config.external_url,
        "exposure": bastion.data.get("exposure"),
    }


def _alarm_error(connection, msg, err: AlarmError) -> None:
    connection.send_error(
        msg["id"], err.reason, alarm_error_text(err.reason, connection.hass.config.language, err.detail)
    )


@websocket_api.websocket_command({probatio.Required("type"): "bastion/alarm/get"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_alarm_get(hass, connection, msg) -> None:
    """Configuration, state and sensor candidates."""
    if (bastion := _guard(connection, msg)) is None:
        return
    connection.send_result(msg["id"], _alarm_payload(hass, bastion))


@websocket_api.websocket_command({probatio.Required("type"): "bastion/alarm/save", probatio.Required("config"): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_alarm_save(hass, connection, msg) -> None:
    """Save rooms, sensors, modes, actions and worker settings."""
    if (bastion := _guard(connection, msg)) is None:
        return
    try:
        config = _ALARM_CONFIG(msg["config"])
    except probatio.Invalid as err:
        connection.send_error(msg["id"], "invalid", str(err))
        return
    for room in config.get("rooms", []):
        room.setdefault("id", f"r_{secrets.token_hex(3)}")
    for person in config.get("people", []):
        person.setdefault("id", secrets.token_hex(4))
    await bastion.alarm.async_update_config(config)
    bastion.relay.setup()
    bastion.household.setup()
    bastion.presence.setup()
    connection.send_result(msg["id"], _alarm_payload(hass, bastion))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "bastion/alarm/arm",
        probatio.Required("mode"): probatio.In(MODES),
        probatio.Optional("code"): str,
        probatio.Optional("force", default=False): bool,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_alarm_arm(hass, connection, msg) -> None:
    """Arm from the panel."""
    if (bastion := _guard(connection, msg)) is None:
        return
    try:
        await bastion.alarm.async_arm(
            msg["mode"], msg.get("code") or None, user=connection.user.name, force=msg["force"]
        )
    except AlarmError as err:
        _alarm_error(connection, msg, err)
        return
    connection.send_result(msg["id"], _alarm_payload(hass, bastion))


@websocket_api.websocket_command({probatio.Required("type"): "bastion/alarm/disarm", probatio.Optional("code"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_alarm_disarm(hass, connection, msg) -> None:
    """Disarm from the panel."""
    if (bastion := _guard(connection, msg)) is None:
        return
    try:
        await bastion.alarm.async_disarm(msg.get("code") or None, user=connection.user.name)
    except AlarmError as err:
        _alarm_error(connection, msg, err)
        return
    connection.send_result(msg["id"], _alarm_payload(hass, bastion))


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "bastion/alarm/code",
        probatio.Optional("delete"): str,
        probatio.Optional("name"): probatio.All(str, probatio.Length(max=40)),
        probatio.Optional("code"): probatio.All(str, probatio.Length(min=4, max=32)),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_alarm_code(hass, connection, msg) -> None:
    """Add or delete a code."""
    if (bastion := _guard(connection, msg)) is None:
        return
    try:
        if msg.get("delete"):
            bastion.alarm.delete_code(msg["delete"])
        elif msg.get("code"):
            await bastion.alarm.async_set_code(msg.get("name") or "Code", msg["code"])
    except AlarmError as err:
        _alarm_error(connection, msg, err)
        return
    connection.send_result(msg["id"], _alarm_payload(hass, bastion))


@websocket_api.websocket_command(
    {probatio.Required("type"): "bastion/alarm/worker", probatio.Required("action"): probatio.In(("test", "secret"))}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_alarm_worker(hass, connection, msg) -> None:
    """Test the worker or create a new shared secret."""
    if (bastion := _guard(connection, msg)) is None:
        return
    result: dict[str, Any] = {}
    if msg["action"] == "secret":
        bastion.alarm.regenerate_worker_secret()
        bastion.relay.setup()
    else:
        result = await bastion.relay.async_test()
    connection.send_result(msg["id"], {"result": result, **_alarm_payload(hass, bastion)})


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "bastion/alarm/remote",
        probatio.Required("action"): probatio.In(("list", "pair", "unpair", "revoke", "revoke_all")),
        probatio.Optional("passkey"): probatio.All(str, probatio.Length(max=400)),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_alarm_remote(hass, connection, msg) -> None:
    """Passkeys for the remote control: pairing code, list, revoke (stored at the worker)."""
    if (bastion := _guard(connection, msg)) is None:
        return
    relay = bastion.relay
    action = msg["action"]
    code = None
    if action == "pair":
        # One-time code for adding a passkey in the dashboard; the worker only gets its hash.
        code = f"{secrets.randbelow(10**8):08d}"
        result = await relay.async_remote(
            "pair", code_hash=hashlib.sha256(code.encode()).hexdigest(), expires=int(time.time()) + 600
        )
    elif action == "revoke":
        result = await relay.async_remote("revoke", id=msg.get("passkey") or "")
    elif action == "revoke_all":
        result = await relay.async_remote("revoke", all=True)
    else:
        result = await relay.async_remote(action)
    if code and result.get("ok"):
        result["code"] = f"{code[:4]}-{code[4:]}"
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {probatio.Required("type"): "bastion/alarm/presence_test", probatio.Required("address"): str}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_alarm_presence_test(hass, connection, msg) -> None:
    """Check once whether a phone answers in the home network."""
    if _guard(connection, msg) is None:
        return
    address = msg["address"].strip()
    if not valid_address(address):
        connection.send_error(msg["id"], "invalid", "IP-Adresse im Heimnetz oder Hostname")
        return
    method = await async_probe(hass, address)
    connection.send_result(msg["id"], {"found": method is not None, "method": method})


@websocket_api.websocket_command({probatio.Required("type"): "bastion/alarm/media"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_alarm_media(hass, connection, msg) -> None:
    """Audio files from "My media" for the sound picker."""
    if _guard(connection, msg) is None:
        return
    connection.send_result(msg["id"], {"files": await async_media_files(hass)})


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "bastion/alarm/sound",
        probatio.Required("action"): probatio.In(("play", "stop")),
        probatio.Optional("sound", default=""): _SOUND,
        probatio.Optional("players"): [_PLAYER],
        probatio.Optional("volume"): _VOLUME,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_alarm_sound(hass, connection, msg) -> None:
    """Test a sound on the configured (or given) media players."""
    if (bastion := _guard(connection, msg)) is None:
        return
    sounds = bastion.alarm.sounds
    if msg["action"] == "stop":
        await sounds.async_stop_test()
        connection.send_result(msg["id"], {"ok": True})
        return
    if not msg["sound"]:
        connection.send_error(msg["id"], "no_sound", "Kein Ton gewählt")
        return
    ok = await sounds.async_test(msg["sound"], msg.get("players"), msg.get("volume"))
    connection.send_result(msg["id"], {"ok": ok})


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
        ws_alarm_get,
        ws_alarm_save,
        ws_alarm_arm,
        ws_alarm_disarm,
        ws_alarm_code,
        ws_alarm_worker,
        ws_alarm_remote,
        ws_alarm_presence_test,
        ws_alarm_media,
        ws_alarm_sound,
        ws_anomaly_accept,
    ):
        websocket_api.async_register_command(hass, command)
