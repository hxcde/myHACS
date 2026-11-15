"""Alarm system: modes, delays, sensor types, codes, entity, worker signature."""

from __future__ import annotations

from datetime import timedelta
import hashlib
import hmac
import json

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.bastion.alarm.engine import AlarmError
from custom_components.bastion.alarm.relay import sign

from .test_integration import _mock_web, _setup

ROOMS = [
    {"id": "r1", "name": "Flur", "icon": "mdi:door", "sensors": ["binary_sensor.door", "binary_sensor.motion"]},
    {"id": "r2", "name": "Küche", "icon": "mdi:stove", "sensors": ["binary_sensor.smoke", "binary_sensor.window"]},
]
SENSORS = {
    "binary_sensor.door": {"modes": ["home", "night", "away"], "type": "delayed", "bypass": False},
    "binary_sensor.motion": {"modes": ["away"], "type": "instant", "bypass": False},
    "binary_sensor.smoke": {"modes": ["home", "night", "away"], "type": "always", "bypass": False},
    "binary_sensor.window": {"modes": ["night", "away"], "type": "instant", "bypass": True},
}


@pytest.fixture
async def alarm(hass: HomeAssistant, tmp_path, aioclient_mock):
    _mock_web(aioclient_mock, latest=HA_VERSION)
    for entity_id in ("binary_sensor.door", "binary_sensor.motion", "binary_sensor.smoke", "binary_sensor.window"):
        hass.states.async_set(entity_id, "off", {"friendly_name": entity_id.split(".")[1].title()})
    hass.states.async_set("siren.flur", "off")
    await async_setup_component(hass, "homeassistant", {})
    entry = await _setup(hass, tmp_path)
    engine = entry.runtime_data.alarm
    await engine.async_update_config(
        {
            "rooms": ROOMS,
            "sensors": SENSORS,
            "modes": {
                "away": {"exit": 30, "entry": 20},
                "home": {"exit": 0, "entry": 10},
                "night": {"exit": 0, "entry": 0},
            },
            "trigger_time": 60,
            "actions": {"sirens": ["siren.flur"]},
        }
    )
    calls = []
    hass.bus.async_listen("call_service", callback(lambda e: calls.append(e.data)))
    engine.test_calls = calls
    return engine


def _fire(hass, seconds):
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))


async def test_arm_away_with_exit_and_entry_delay(hass: HomeAssistant, alarm) -> None:
    entity_id = next(s.entity_id for s in hass.states.async_all("alarm_control_panel"))
    await hass.services.async_call("alarm_control_panel", "alarm_arm_away", {"entity_id": entity_id}, blocking=True)
    assert alarm.state == "arming"
    assert hass.states.get(entity_id).state == "arming"
    # Motion during the exit delay is ignored.
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    assert alarm.state == "arming"
    hass.states.async_set("binary_sensor.motion", "off")
    _fire(hass, 31)
    await hass.async_block_till_done()
    assert alarm.state == "armed_away"
    assert hass.states.get(entity_id).state == "armed_away"

    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    assert alarm.state == "pending"
    _fire(hass, 21)
    await hass.async_block_till_done()
    assert alarm.state == "triggered"
    assert alarm.triggered_by["sensor"] == "binary_sensor.door"
    assert alarm.triggered_by["room"] == "Flur"
    assert any(c["service"] == "turn_on" and "siren.flur" in c["service_data"]["entity_id"] for c in alarm.test_calls)

    # After the siren time it re-arms.
    _fire(hass, 61 + 21)
    await hass.async_block_till_done()
    assert alarm.state == "armed_away"


async def test_instant_and_always_sensors(hass: HomeAssistant, alarm) -> None:
    await alarm.async_arm("night")
    assert alarm.state == "armed_night"
    # Motion is only assigned to away.
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    assert alarm.state == "armed_night"
    await alarm.async_disarm()
    # Smoke triggers even when disarmed.
    hass.states.async_set("binary_sensor.smoke", "on")
    await hass.async_block_till_done()
    assert alarm.state == "triggered"


async def test_open_sensor_blocks_arming_and_bypass(hass: HomeAssistant, alarm) -> None:
    hass.states.async_set("binary_sensor.door", "on")
    with pytest.raises(AlarmError) as err:
        await alarm.async_arm("home")
    assert err.value.reason == "open_sensors"
    assert alarm.state == "disarmed"
    await alarm.async_arm("home", force=True)
    assert alarm.state == "armed_home"
    assert "binary_sensor.door" in alarm.bypassed
    hass.states.async_set("binary_sensor.door", "off")
    await hass.async_block_till_done()
    assert "binary_sensor.door" not in alarm.bypassed
    await alarm.async_disarm()

    # A window marked "may be open" does not block arming but is bypassed.
    hass.states.async_set("binary_sensor.window", "on")
    await alarm.async_arm("night")
    assert alarm.state == "armed_night"
    assert "binary_sensor.window" in alarm.bypassed


async def test_codes_and_lockout(hass: HomeAssistant, alarm) -> None:
    await alarm.async_set_code("Yann", "4711")
    assert "4711" not in json.dumps(alarm.config)
    await alarm.async_arm("home")
    with pytest.raises(AlarmError):
        await alarm.async_disarm("0000")
    entity_id = next(s.entity_id for s in hass.states.async_all("alarm_control_panel"))
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "alarm_control_panel", "alarm_disarm", {"entity_id": entity_id, "code": "1234"}, blocking=True
        )
    await hass.services.async_call(
        "alarm_control_panel", "alarm_disarm", {"entity_id": entity_id, "code": "4711"}, blocking=True
    )
    assert alarm.state == "disarmed"
    assert alarm.log[-1]["user"] == "Yann"
    # Five wrong codes lock the keypad.
    await alarm.async_arm("home")
    for _ in range(5):
        with pytest.raises(AlarmError):
            await alarm.async_disarm("9999")
    with pytest.raises(AlarmError) as err:
        await alarm.async_disarm("4711")
    assert err.value.reason == "locked"


async def test_rearm_during_alarm_needs_code(hass: HomeAssistant, alarm) -> None:
    await alarm.async_set_code("Yann", "4711")
    await alarm.async_arm("away", force=True)
    _fire(hass, 31)
    await hass.async_block_till_done()
    await alarm.async_trigger("manual")
    with pytest.raises(AlarmError):
        await alarm.async_arm("home")
    assert alarm.state == "triggered"


async def test_state_survives_restart(hass: HomeAssistant, tmp_path, aioclient_mock) -> None:
    _mock_web(aioclient_mock, latest=HA_VERSION)
    hass.states.async_set("binary_sensor.door", "off")
    entry = await _setup(hass, tmp_path)
    engine = entry.runtime_data.alarm
    await engine.async_update_config(
        {"rooms": ROOMS[:1], "sensors": {"binary_sensor.door": SENSORS["binary_sensor.door"]}}
    )
    await engine.async_arm("night")
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.alarm.state == "armed_night"


async def test_sabotage_triggers_when_armed(hass: HomeAssistant, alarm) -> None:
    await alarm.async_arm("night")
    hass.bus.async_fire("bastion_security_event", {"type": "sabotage"})
    await hass.async_block_till_done()
    assert alarm.state == "triggered"
    assert alarm.triggered_by["reason"] == "sabotage"


async def test_websocket_config_and_arm(hass: HomeAssistant, alarm, hass_ws_client) -> None:
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "bastion/alarm/get"})
    msg = await client.receive_json()
    assert msg["success"] and len(msg["result"]["config"]["rooms"]) == 2
    rooms = msg["result"]["config"]["rooms"] + [{"name": "Garage", "icon": "mdi:garage", "sensors": []}]
    await client.send_json_auto_id({"type": "bastion/alarm/save", "config": {"rooms": rooms, "trigger_time": 90}})
    msg = await client.receive_json()
    assert msg["success"] and msg["result"]["config"]["trigger_time"] == 90
    assert msg["result"]["config"]["rooms"][-1]["id"].startswith("r_")
    hass.states.async_set("binary_sensor.door", "on")
    await client.send_json_auto_id({"type": "bastion/alarm/arm", "mode": "home"})
    msg = await client.receive_json()
    assert not msg["success"] and msg["error"]["code"] == "open_sensors"
    await client.send_json_auto_id({"type": "bastion/alarm/arm", "mode": "home", "force": True})
    msg = await client.receive_json()
    assert msg["success"] and msg["result"]["status"]["state"] == "armed_home"
    await client.send_json_auto_id({"type": "bastion/alarm/code", "name": "Test", "code": "1234"})
    msg = await client.receive_json()
    assert msg["success"] and msg["result"]["config"]["codes"][0]["name"] == "Test"
    assert "hash" not in msg["result"]["config"]["codes"][0]


def test_worker_signature_matches_spec() -> None:
    body = json.dumps({"ts": 1, "state": "armed_away"}, separators=(",", ":")).encode()
    expected = hmac.new(b"secret", b"1700000000." + body, hashlib.sha256).hexdigest()
    assert sign("secret", "1700000000", body) == expected


async def test_relay_sends_signed_events(hass: HomeAssistant, alarm, aioclient_mock) -> None:
    aioclient_mock.post("https://worker.example.invalid/heartbeat", json={"ok": True})
    aioclient_mock.post("https://worker.example.invalid/alert", json={"ok": True, "channels": ["ntfy"]})
    await alarm.async_update_config(
        {"worker": {"url": "https://worker.example.invalid", "enabled": True, "interval": 60}}
    )
    relay = alarm.bastion.relay
    relay.setup()
    await hass.async_block_till_done()
    result = await relay.async_test()
    assert result == {"ok": True, "channels": ["ntfy"]}
    await alarm.async_trigger("manual")
    await hass.async_block_till_done()
    alert_calls = [c for c in aioclient_mock.mock_calls if str(c[1]).endswith("/alert")]
    assert alert_calls
    method, url, data, headers = alert_calls[-1][:4]
    assert headers["X-Bastion-Signature"] == sign(
        alarm.config["worker"]["secret"], headers["X-Bastion-Timestamp"], data
    )
    assert json.loads(data)["event"] == "triggered"


async def test_per_sensor_delays(hass: HomeAssistant, alarm) -> None:
    await alarm.async_update_config(
        {
            "sensors": {
                **SENSORS,
                # Front door: watched 45 s after arming, alarm 5 s after opening.
                "binary_sensor.door": {
                    "modes": ["home", "night", "away"],
                    "type": "delayed",
                    "exit_delay": 45,
                    "entry_delay": 5,
                },
                # Smoke: 3 s confirmation time.
                "binary_sensor.smoke": {"modes": ["home", "night", "away"], "type": "always", "entry_delay": 3},
            }
        }
    )
    # The open front door does not block arming (exit route).
    hass.states.async_set("binary_sensor.door", "on")
    await alarm.async_arm("home")
    assert alarm.state == "armed_home"
    hass.states.async_set("binary_sensor.door", "off")
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    assert alarm.state == "armed_home", "door is not watched before its activation delay"
    # Still open when its activation delay ends: entry delay of the sensor starts.
    _fire(hass, 46)
    await hass.async_block_till_done()
    assert alarm.state == "pending"
    assert alarm.until is not None
    _fire(hass, 46 + 6)
    await hass.async_block_till_done()
    assert alarm.state == "triggered"
    await alarm.async_disarm()

    # Smoke with confirmation time, while disarmed.
    hass.states.async_set("binary_sensor.door", "off")
    hass.states.async_set("binary_sensor.smoke", "on")
    await hass.async_block_till_done()
    assert alarm.state == "pending"
    hass.states.async_set("binary_sensor.smoke", "off")
    _fire(hass, 46 + 6 + 4)
    await hass.async_block_till_done()
    assert alarm.state == "triggered"
    # After the siren time a 24 h alarm returns to disarmed.
    _fire(hass, 46 + 6 + 4 + 61)
    await hass.async_block_till_done()
    assert alarm.state == "disarmed"
