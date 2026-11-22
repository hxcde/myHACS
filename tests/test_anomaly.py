"""Anomaly detection: tolerant of everyday climate swings, still strict on real deviations."""

from __future__ import annotations

from datetime import datetime, timedelta
import time

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.bastion.anomaly.engine import PROFILES, sensor_profile
from custom_components.bastion.anomaly.stats import SensorModel

from .test_alarm import alarm  # noqa: F401

MONDAY = datetime(2026, 11, 2)


class _State:
    def __init__(self, attrs):
        self.attributes = attrs


def _trained(profile: dict, days: int = 21, base: float = 18.4, wobble: float = 0.3) -> SensorModel:
    """Weekday mornings around 18.4 °C, sampled every 5 minutes."""
    model = SensorModel()
    model.configure(**profile)
    for day in range(days):
        start = MONDAY + timedelta(days=day)
        if start.weekday() >= 5:
            continue
        for minute in range(5 * 60, 10 * 60, 5):
            model.observe(start + timedelta(minutes=minute), base + wobble * ((minute // 5) % 3 - 1), 3.5)
    return model


def _run(model: SensorModel, day: datetime, value: float, minutes: int, at: int = 7 * 60) -> list:
    out = []
    for i in range(minutes // 5):
        out = model.observe(day + timedelta(minutes=at + 5 * i), value, 3.5)
    return out


def test_profiles_from_device_class_and_unit() -> None:
    assert sensor_profile(_State({"device_class": "temperature", "unit_of_measurement": "°C"}))[0] == "temperature"
    assert sensor_profile(_State({"unit_of_measurement": "°F"}))[0] == "temperature_f"
    assert sensor_profile(_State({"device_class": "humidity", "unit_of_measurement": "%"}))[0] == "humidity"
    assert sensor_profile(_State({"device_class": "power", "unit_of_measurement": "W"})) == ("power", {})


def test_shower_warmth_is_normal_fire_is_not() -> None:
    model = _trained(PROFILES["temperature"])
    day = MONDAY + timedelta(days=28)
    assert _run(model, day, 22.0, 45) == [], "22 °C after a shower is an ordinary room temperature"
    assert _run(model, day, 23.5, 60, at=8 * 60) == []
    found = _run(model, day + timedelta(days=1), 45.0, 30)
    assert found and found[0]["type"] == "deviation", "a fire still is"
    assert _run(model, day + timedelta(days=2), 6.0, 30), "and so is a cold flat (heating, window)"


def test_generic_sensor_keeps_its_sensitivity_but_learns_recurring_peaks() -> None:
    model = _trained({}, base=100.0, wobble=2.0)
    flagged = []
    for day in range(28, 56):
        ts = MONDAY + timedelta(days=day)
        if ts.weekday() >= 5:
            continue
        flagged.append(bool(_run(model, ts, 140.0, 30)))
        _run(model, ts, 100.0, 30, at=8 * 60)
    assert flagged[0], "first time: unusual"
    assert not any(flagged[-5:]), "every morning: learned"
    assert _run(model, MONDAY + timedelta(days=60), 900.0, 15), "an extreme value is still found"


def test_marked_as_normal() -> None:
    model = _trained({}, base=100.0, wobble=2.0)
    day = MONDAY + timedelta(days=28)
    assert _run(model, day, 160.0, 15)
    model.accept(160.0)
    assert _run(model, day + timedelta(days=1), 158.0, 15) == []
    assert _run(model, day + timedelta(days=2), 400.0, 15), "only the accepted values"
    clone = SensorModel.from_dict(model.to_dict())
    assert clone.accepted == [[160.0, 160.0]]
    assert SensorModel.from_dict({"a": [150.0, 160.0]}).accepted == [[150.0, 160.0]], "0.7.1 format"


def test_accepting_two_values_does_not_accept_the_range_between() -> None:
    model = _trained({}, base=100.0, wobble=2.0)
    model.accept(160.0)
    model.accept(400.0)
    assert model.accepted == [[160.0, 160.0], [400.0, 400.0]]
    assert _run(model, MONDAY + timedelta(days=28), 280.0, 15), "280 lies between, still unusual"
    model.accept(161.0)
    assert model.accepted == [[160.0, 161.0], [400.0, 400.0]], "close values join"


async def test_one_event_per_episode_and_accept(hass: HomeAssistant, alarm, hass_ws_client) -> None:  # noqa: F811
    engine = alarm.bastion.anomaly
    model = _trained({}, base=100.0, wobble=2.0)
    engine.models["sensor.bad_feuchte"] = model
    attrs = {"friendly_name": "Bad Feuchte", "unit_of_measurement": "%", "device_class": "moisture"}
    # Model trained on weekday mornings; sample at such a time.
    now = MONDAY + timedelta(days=28, hours=7)
    from unittest.mock import patch  # noqa: PLC0415

    async def sample(value, at):
        hass.states.async_set("sensor.bad_feuchte", str(value), attrs)
        with patch("custom_components.bastion.anomaly.engine.dt_util.now", return_value=at):
            for _ in range(3):
                await engine._async_sample()

    # An earlier, real incident stays in the log.
    await sample(900, now - timedelta(days=3))  # Friday morning
    engine.events[-1]["time"] = (dt_util.utcnow() - timedelta(days=3)).isoformat()
    await sample(100, now - timedelta(days=3, minutes=-20))
    await sample(170, now)
    events = [e for e in engine.events if e.get("entity_id") == "sensor.bad_feuchte" and e["value"] == 170]
    assert len(events) == 1
    assert events[0]["detail"].startswith("170,0 % liegt über dem üblichen Bereich") or events[0]["detail"].startswith(
        "170.0% is above"
    )
    await sample(100, now + timedelta(minutes=20))
    await sample(170, now + timedelta(minutes=40))
    assert len([e for e in engine.events if e.get("entity_id") == "sensor.bad_feuchte"]) == 2, "same episode, one entry"

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "bastion/anomaly/accept", "entity_id": "sensor.bad_feuchte"})
    msg = await client.receive_json()
    assert msg["success"]
    sensor = next(s for s in msg["result"]["anomaly"]["sensors"] if s["entity_id"] == "sensor.bad_feuchte")
    assert sensor["accepted"] == [[170.0, 170.0]] and sensor["active"] == []
    events = [e for e in msg["result"]["anomaly"]["events"] if e.get("entity_id") == "sensor.bad_feuchte"]
    assert {e["value"]: e.get("accepted", False) for e in events} == {170: True, 900: False}, "not the real incident"
    # Event button: exactly that value.
    await client.send_json_auto_id({"type": "bastion/anomaly/accept", "entity_id": "sensor.bad_feuchte", "value": 900})
    msg = await client.receive_json()
    sensor = next(s for s in msg["result"]["anomaly"]["sensors"] if s["entity_id"] == "sensor.bad_feuchte")
    assert sensor["accepted"] == [[170.0, 170.0], [900.0, 900.0]]
    # Sensor button without a current deviation: nothing to accept.
    await client.send_json_auto_id({"type": "bastion/anomaly/accept", "entity_id": "sensor.bad_feuchte"})
    assert not (await client.receive_json())["success"]
    await client.send_json_auto_id({"type": "bastion/anomaly/accept", "entity_id": "sensor.unknown"})
    assert not (await client.receive_json())["success"]


async def test_own_entities_and_reloads_are_no_sabotage(hass: HomeAssistant, alarm) -> None:  # noqa: F811
    engine = alarm.bastion.anomaly
    engine._setup_time = time.monotonic() - 3600
    own = [
        e.entity_id
        for e in er.async_entries_for_config_entry(er.async_get(hass), alarm.bastion.entry.entry_id)
        if e.domain in ("binary_sensor", "alarm_control_panel")
    ]
    assert len(own) >= 3
    for entity_id in own:
        hass.states.async_set(entity_id, "unavailable", {"device_class": "tamper"})
    # An integration being reloaded writes "restored" unavailable states.
    for entity_id in ("binary_sensor.door", "binary_sensor.window", "binary_sensor.motion"):
        hass.states.async_set(entity_id, "off", {"device_class": "door"})
    await hass.async_block_till_done()
    for entity_id in ("binary_sensor.door", "binary_sensor.window", "binary_sensor.motion"):
        hass.states.async_set(entity_id, "unavailable", {"device_class": "door", "restored": True})
    await hass.async_block_till_done()
    assert not engine.sabotage_active
    assert not [e for e in engine.events if e["type"] in ("sabotage", "tamper")]
    # Real radio loss of three sensors still is.
    for entity_id in ("binary_sensor.door", "binary_sensor.window", "binary_sensor.motion"):
        hass.states.async_set(entity_id, "off", {"device_class": "door"})
    await hass.async_block_till_done()
    for entity_id in ("binary_sensor.door", "binary_sensor.window", "binary_sensor.motion"):
        hass.states.async_set(entity_id, "unavailable", {"device_class": "door"})
    await hass.async_block_till_done()
    assert engine.sabotage_active
