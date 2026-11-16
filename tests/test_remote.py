"""Remote control via the worker, "nobody home" reminder, worker notices and worker decoys."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.bastion.alarm.relay import command_signature
from custom_components.bastion.canary import worker_decoys

from .test_alarm import _fire, alarm  # noqa: F401
from .test_worker_link import WORKER, _calls, _enable_worker, _payload

# Shared test vector with extras/cloudflare-worker/test/worker.test.mjs.
VECTOR_SECRET = "topsecret"
VECTOR_ID = "0123456789abcdef0123456789abcdef"
VECTOR_CREATED = 1700000000
VECTOR_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiIwMTIzNDU2Nzg5YWJjZGVmMDEyMzQ1Njc4OWFiY2RlZiIsImlhdCI6MTcwMDAwMDAwMCwiZXhwIjoyMDE1MzYwMDAwfQ."
)


def _cmd(secret, cid, action="arm", mode="away", *, force=False, ts=None, by="me@example.invalid"):
    cmd = {
        "id": cid,
        "ts": int(time.time()) if ts is None else ts,
        "action": action,
        "mode": mode,
        "force": force,
        "by": by,
    }
    return {**cmd, "sig": command_signature(secret, cmd)}


async def _remote(hass, alarm, aioclient_mock, commands, **remote):  # noqa: F811
    relay = await _enable_worker(hass, alarm, aioclient_mock)
    await alarm.async_update_config({"remote": {"enabled": True, **remote}})
    aioclient_mock.post(f"{WORKER}/commands", json={"ok": True, "commands": commands, "fast": False})
    return relay


async def test_command_signature_matches_the_worker_formula() -> None:
    cmd = {
        "id": "a" * 16,
        "ts": 1700000000,
        "action": "arm",
        "mode": "away",
        "force": False,
        "by": "me@example.invalid",
    }
    expected = hmac.new(
        b"topsecret", b"command.aaaaaaaaaaaaaaaa.arm.away.0.1700000000.me@example.invalid", hashlib.sha256
    ).hexdigest()
    assert command_signature("topsecret", cmd) == expected


async def test_remote_arm_runs_once_and_reports_the_result(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    secret = alarm.config["worker"]["secret"]
    relay = await _remote(hass, alarm, aioclient_mock, [_cmd(secret, "0" * 15 + "1")])
    await relay.async_poll_commands()
    await hass.async_block_till_done()
    assert alarm.state == "arming" and alarm.target == "away"
    armed = [e for e in alarm.log if e["type"] == "arming"]
    assert armed[-1]["user"] == "Dashboard (me@example.invalid)"
    # the same command again is ignored, the result goes back with the next poll
    await relay.async_poll_commands()
    await hass.async_block_till_done()
    assert len([e for e in alarm.log if e["type"] == "arming"]) == 1
    polls = _calls(aioclient_mock, "/commands")
    assert _payload(polls[-1])["done"] == [{"id": "0" * 15 + "1", "ok": True, "error": None, "detail": None}]
    assert relay.last_commands[0]["ok"] is True
    assert relay._unsub_fast is not None, "results pending -> fast poll scheduled"
    relay.unload()


async def test_remote_commands_are_checked(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    secret = alarm.config["worker"]["secret"]
    await alarm.async_set_code("Haus", "1234")
    commands = [
        _cmd("wrong", "0" * 15 + "2"),
        _cmd(secret, "0" * 15 + "3", ts=int(time.time()) - 600),
        _cmd(secret, "0" * 15 + "4", action="disarm", mode=None),
        {**_cmd(secret, "0" * 15 + "5"), "action": "disarm"},
    ]
    relay = await _remote(hass, alarm, aioclient_mock, commands)
    await relay.async_poll_commands()
    await hass.async_block_till_done()
    assert alarm.state == "disarmed"
    errors = {r["id"][-1]: r["error"] for r in relay._cmd_results}
    assert errors == {"2": "signature", "3": "stale", "4": "not_allowed", "5": "signature"}


async def test_remote_disarm_skips_the_code_and_open_sensors_block_arming(
    hass: HomeAssistant,
    alarm,  # noqa: F811
    aioclient_mock,
) -> None:
    secret = alarm.config["worker"]["secret"]
    await alarm.async_set_code("Haus", "1234")
    await alarm.async_arm("night", "1234")
    relay = await _remote(
        hass, alarm, aioclient_mock, [_cmd(secret, "0" * 15 + "6", action="disarm", mode=None)], disarm=True
    )
    await relay.async_poll_commands()
    await hass.async_block_till_done()
    assert alarm.state == "disarmed", "passkey replaces the code"

    hass.states.async_set("binary_sensor.motion", "on", {"friendly_name": "Motion"})
    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{WORKER}/alert", json={"ok": True, "channels": []})
    aioclient_mock.post(f"{WORKER}/heartbeat", json={"ok": True})
    aioclient_mock.post(f"{WORKER}/commands", json={"ok": True, "commands": [_cmd(secret, "0" * 15 + "7")]})
    await relay.async_poll_commands()
    await hass.async_block_till_done()
    result = relay._cmd_results[-1]
    assert result["error"] == "open_sensors" and result["detail"] == ["Motion"]
    assert alarm.state == "disarmed"
    relay.unload()


async def test_no_polling_without_remote_control(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    relay = await _enable_worker(hass, alarm, aioclient_mock)
    aioclient_mock.post(f"{WORKER}/commands", json={"ok": True, "commands": []})
    await relay.async_poll_commands()
    assert not _calls(aioclient_mock, "/commands")
    beat = _payload(_calls(aioclient_mock, "/heartbeat")[-1])
    assert beat["remote"] == {"enabled": False, "disarm": False}


async def test_nobody_home_reminder(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    async_mock_service(hass, "notify", "notify")
    hass.states.async_set("person.anna", "home", {"friendly_name": "Anna"})
    hass.states.async_set("person.ben", "not_home", {"friendly_name": "Ben"})
    relay = await _enable_worker(hass, alarm, aioclient_mock)
    await alarm.async_update_config({"remote": {"reminder": True, "reminder_minutes": 15}})
    presence = alarm.bastion.presence
    presence.setup()
    hass.states.async_set("person.anna", "not_home", {"friendly_name": "Anna"})
    await hass.async_block_till_done()
    _fire(hass, 14 * 60)
    await hass.async_block_till_done()
    assert not [e for e in alarm.log if e["type"] == "unarmed"]
    _fire(hass, 16 * 60)
    await hass.async_block_till_done()
    reminders = [e for e in alarm.log if e["type"] == "unarmed"]
    assert len(reminders) == 1 and reminders[0]["minutes"] == 15 and reminders[0]["persons"] == ["Anna", "Ben"]
    alerts = [_payload(c) for c in _calls(aioclient_mock, "/alert")]
    assert alerts[-1]["event"] == "unarmed" and alerts[-1]["push"] is True
    assert alerts[-1]["detail"]["minutes"] == 15
    # only once per absence; coming home resets it
    _fire(hass, 60 * 60)
    await hass.async_block_till_done()
    assert len([e for e in alarm.log if e["type"] == "unarmed"]) == 1
    hass.states.async_set("person.ben", "home", {"friendly_name": "Ben"})
    await hass.async_block_till_done()
    assert presence.reminded is False
    presence.unload()
    relay.unload()


async def test_reminder_is_cancelled_by_arming(hass: HomeAssistant, alarm) -> None:  # noqa: F811
    hass.states.async_set("person.anna", "not_home")
    await alarm.async_update_config({"remote": {"reminder": True, "reminder_minutes": 10}})
    presence = alarm.bastion.presence
    presence.setup()
    assert presence._timer is not None
    await alarm.async_arm("away")
    await hass.async_block_till_done()
    assert presence._timer is None
    _fire(hass, 20 * 60)
    await hass.async_block_till_done()
    assert not [e for e in alarm.log if e["type"] == "unarmed"]
    presence.unload()


async def test_worker_notices(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    bastion = alarm.bastion
    notices = [
        {
            "id": 7,
            "ts": 1,
            "type": "dashboard_access",
            "data": {
                "email": "me@example.invalid",
                "ip": "203.0.113.9",
                "country": "DE",
                "device": "iPhone · Safari",
                "new_device": True,
            },
        },
        {"id": 8, "ts": 2, "type": "canary", "data": {"kind": "token", "ip": "198.51.100.4", "agent": "curl/8"}},
    ]
    aioclient_mock.post(
        f"{WORKER}/heartbeat", json={"ok": True, "notices": notices, "dashboard": "https://dash.example.invalid"}
    )
    await alarm.async_update_config({"worker": {"url": WORKER, "enabled": True, "interval": 60}})
    relay = bastion.relay
    events = []
    hass.bus.async_listen("bastion_security_event", lambda e: events.append(e.data))
    await relay._async_heartbeat()
    await hass.async_block_till_done()
    assert relay.dashboard_url == "https://dash.example.invalid"
    types = [e["type"] for e in bastion.logins.log]
    assert "dashboard_access" in types
    triggers = bastion.canary.state.get("triggers", [])
    assert triggers and triggers[-1]["via"] == "Worker-Token" and triggers[-1]["ip"] == "198.51.100.4"
    # worker events are not echoed back to the worker
    assert all(relay._security_event({"time": "2026-01-01T00:00:00+00:00", **e}) is None for e in events)
    # confirmed with the next heartbeat, not handled twice
    await relay._async_heartbeat()
    await hass.async_block_till_done()
    beat = _payload(_calls(aioclient_mock, "/heartbeat")[-1])
    assert beat["notices_seen"] == [7, 8]
    assert len(bastion.canary.state.get("triggers", [])) == 1


async def test_worker_decoys_shared_vector() -> None:
    decoy = worker_decoys(WORKER + "/", VECTOR_SECRET, VECTOR_ID, VECTOR_CREATED)
    assert decoy["url"] == WORKER
    assert decoy["token"].startswith(VECTOR_TOKEN)
    header, payload, sig = decoy["token"].split(".")
    assert json.loads(__import__("base64").urlsafe_b64decode(payload + "==")) == {
        "iss": VECTOR_ID,
        "iat": VECTOR_CREATED,
        "exp": VECTOR_CREATED + 10 * 365 * 86400,
    }
    key = hmac.new(VECTOR_SECRET.encode(), b"canary-token", hashlib.sha256).hexdigest()
    raw = hmac.new(key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    assert sig == __import__("base64").urlsafe_b64encode(raw).rstrip(b"=").decode()
    hook = hmac.new(VECTOR_SECRET.encode(), f"canary-webhook.{VECTOR_ID}".encode(), hashlib.sha256).hexdigest()[:32]
    assert decoy["webhook"] == f"{WORKER}/api/webhook/{VECTOR_ID}{hook}"


async def test_decoy_file_contains_worker_decoys(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    bastion = alarm.bastion
    await _enable_worker(hass, alarm, aioclient_mock)
    assert bastion.canary.worker_decoy() is None, "decoys off"
    bastion.canary.state["token"] = "ha-token"
    decoy = bastion.canary.worker_decoy()
    text = bastion.canary.decoy_text()
    assert f"HA_REMOTE_TOKEN={decoy['token']}" in text and f"HA_REMOTE_WEBHOOK={decoy['webhook']}" in text
    assert bastion.canary.worker_decoy() == decoy, "stable"
    assert bastion.canary.summary()["worker"] == decoy


async def test_remote_websocket(hass: HomeAssistant, alarm, aioclient_mock, hass_ws_client) -> None:  # noqa: F811
    await _enable_worker(hass, alarm, aioclient_mock)
    aioclient_mock.post(
        f"{WORKER}/remote",
        json={"ok": True, "passkeys": [], "pairing": {"expires": 1}, "dashboard": "https://dash.example.invalid"},
    )
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "bastion/alarm/remote", "action": "pair"})
    res = await client.receive_json()
    assert res["success"]
    code = res["result"]["code"]
    assert len(code) == 9 and code[4] == "-"
    sent = _payload(_calls(aioclient_mock, "/remote")[-1])
    assert sent["op"] == "pair"
    assert sent["code_hash"] == hashlib.sha256(code.replace("-", "").encode()).hexdigest()
    assert "code" not in sent, "the worker only gets the hash"
    assert alarm.bastion.relay.dashboard_url == "https://dash.example.invalid"

    await client.send_json(
        {
            "id": 2,
            "type": "bastion/alarm/save",
            "config": {
                "remote": {
                    "enabled": True,
                    "disarm": True,
                    "reminder": True,
                    "reminder_minutes": 30,
                    "persons": ["person.anna"],
                }
            },
        }
    )
    res = await client.receive_json()
    assert res["success"]
    assert res["result"]["config"]["remote"]["reminder_minutes"] == 30
    await client.send_json({"id": 3, "type": "bastion/alarm/save", "config": {"remote": {"persons": ["light.x"]}}})
    assert not (await client.receive_json())["success"]


async def test_reminder_finds_persons_created_later(hass: HomeAssistant, alarm) -> None:  # noqa: F811
    await alarm.async_update_config({"remote": {"reminder": True, "reminder_minutes": 10}})
    presence = alarm.bastion.presence
    presence.setup()  # no person entities yet (startup order)
    hass.states.async_set("person.anna", "not_home", {"friendly_name": "Anna"})
    await hass.async_block_till_done()
    _fire(hass, 11 * 60)
    await hass.async_block_till_done()
    reminders = [e for e in alarm.log if e["type"] == "unarmed"]
    assert len(reminders) == 1 and reminders[0]["persons"] == ["Anna"]
    presence.unload()
