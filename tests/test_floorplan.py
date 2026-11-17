"""Floor plan: validation, websocket, sync to the worker, sensor health."""

from __future__ import annotations

import copy

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bastion.alarm.floorplan import FloorPlanError, clean_floorplan, plan_hash

from .test_alarm import alarm  # noqa: F401
from .test_worker_link import WORKER, _calls, _enable_worker, _payload

PLAN = {
    "size": [400, 300],
    "areas": [
        {"id": "wohnen", "label": "Wohnen", "rect": [0, 0, 250, 300], "room": "Flur", "keywords": ["Wohn"]},
        {"id": "bad", "label": "Bad", "rect": [250, 0, 150, 300], "label_at": [320, 150]},
        {"id": "garten", "label": "Garten", "rect": [0, -80, 400, 80], "outdoor": True},
    ],
    "walls": [{"points": [[0, 0], [400, 0], [400, 300], [0, 300], [0, 0]], "exterior": True}],
    "glazing": [
        {
            "id": "tuer",
            "from": [20, 0],
            "to": [120, 0],
            "panels": 2,
            "door_panels": [1, 7],
            "transom": 0.3,
            "sensor": "Door",
        }
    ],
    "dividers": [[[250, 0], [250, 300]]],
    "entrance": {"from": [300, 300], "to": [360, 300], "area": "bad", "sensor": "Window"},
    "boxes": [{"points": [[10, 10], [60, 10], [60, 40]], "height": 30, "kind": "soft", "group": "bett"}],
    "secret": "dropped",
}


def test_clean_floorplan() -> None:
    plan = clean_floorplan(PLAN)
    assert "secret" not in plan
    assert plan["areas"][0]["keywords"] == ["wohn"]
    assert plan["areas"][2]["outdoor"] is True
    assert plan["glazing"][0]["door_panels"] == [1], "door panels outside the panel count are dropped"
    assert plan["entrance"]["sensor"] == "Window"
    assert plan["boxes"][0]["bottom"] == 0 and plan["boxes"][0]["group"] == "bett"
    assert plan_hash(plan) == plan_hash(clean_floorplan(PLAN))
    assert plan_hash(None) is None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda p: p.pop("size"), "size"),
        (lambda p: p.update(areas=[]), "mindestens eine Fläche"),
        (lambda p: p["areas"].append(dict(p["areas"][0])), "doppelt"),
        (lambda p: p["walls"][0].update(points=[[0, 0]]), "Punkte"),
        (lambda p: p["glazing"][0].update(panels=13), "panels"),
        (lambda p: p["boxes"][0].update(height=0), "Höhe"),
        (lambda p: p["areas"][0].update(rect=[0, 0, "x", 1]), "Zahl"),
        (lambda p: p.update(walls=[{"points": [[0, 0], [1, 1]] * 30}] * 200), "zu groß"),
    ],
)
def test_invalid_floorplans(change, message) -> None:
    plan = copy.deepcopy(PLAN)
    change(plan)
    with pytest.raises(FloorPlanError, match=message):
        clean_floorplan(plan)


async def test_floorplan_websocket(hass: HomeAssistant, alarm, hass_ws_client) -> None:  # noqa: F811
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "bastion/alarm/save", "config": {"floorplan": PLAN}})
    assert (await client.receive_json())["success"]
    assert alarm.config["floorplan"]["areas"][1]["label_at"] == [320.0, 150.0]
    smaller = copy.deepcopy(PLAN)
    del smaller["entrance"]
    await client.send_json({"id": 2, "type": "bastion/alarm/save", "config": {"floorplan": smaller}})
    assert (await client.receive_json())["success"]
    assert "entrance" not in alarm.config["floorplan"], "the plan is replaced, not merged"
    await client.send_json({"id": 3, "type": "bastion/alarm/save", "config": {"floorplan": {"size": [1, 1]}}})
    reply = await client.receive_json()
    assert not reply["success"] and "Fläche" in reply["error"]["message"]
    await client.send_json({"id": 4, "type": "bastion/alarm/save", "config": {"floorplan": None}})
    assert (await client.receive_json())["success"]
    assert alarm.config["floorplan"] is None


async def test_floorplan_travels_once(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    await alarm.async_update_config({"floorplan": clean_floorplan(PLAN)})
    digest = plan_hash(alarm.config["floorplan"])
    relay = await _enable_worker(hass, alarm, aioclient_mock)
    beat = _payload(_calls(aioclient_mock, "/heartbeat")[-1])
    assert beat["floorplan_hash"] == digest and beat["floorplan"]["size"] == [400.0, 300.0]
    # The worker confirms the version: later heartbeats carry only the hash.
    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{WORKER}/heartbeat", json={"ok": True, "acks": [], "floorplan_hash": digest})
    await relay._async_heartbeat()
    await relay._async_heartbeat()
    beat = _payload(_calls(aioclient_mock, "/heartbeat")[-1])
    assert beat["floorplan_hash"] == digest and "floorplan" not in beat
    await alarm.async_update_config({"floorplan": None})
    await relay._async_heartbeat()
    beat = _payload(_calls(aioclient_mock, "/heartbeat")[-1])
    assert beat["floorplan_hash"] is None and "floorplan" not in beat
    relay.unload()


async def test_zone_health(hass: HomeAssistant, alarm) -> None:  # noqa: F811
    entry = MockConfigEntry(domain="zigbee")
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(config_entry_id=entry.entry_id, identifiers={("zigbee", "door")})
    registry = er.async_get(hass)
    door = registry.async_get_or_create("binary_sensor", "zigbee", "door", device_id=device.id)
    battery = registry.async_get_or_create("sensor", "zigbee", "door_battery", device_id=device.id)
    await alarm.async_update_config(
        {"rooms": [{"name": "Flur", "sensors": [door.entity_id, "binary_sensor.window"]}], "sensors": {}}
    )
    hass.states.async_set(door.entity_id, "off", {"friendly_name": "Door"})
    hass.states.async_set(battery.entity_id, "12", {"device_class": "battery"})
    hass.states.async_set("binary_sensor.window", "off", {"friendly_name": "Window", "battery_level": 80})
    await hass.async_block_till_done()
    zones = {z["name"]: z for z in alarm.zones()}
    assert zones["Door"]["battery"] == 12
    assert zones["Window"]["battery"] == 80
    assert zones["Door"]["seen"] > 0
    assert "battery" not in alarm.zones(health=False)[0]


async def test_chain_head_is_echoed(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    relay = await _enable_worker(hass, alarm, aioclient_mock)
    assert _payload(_calls(aioclient_mock, "/heartbeat")[-1])["chain_seen"] is None
    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{WORKER}/heartbeat", json={"ok": True, "acks": [], "chain": {"id": 42, "hash": "ab" * 32}})
    await relay._async_heartbeat()
    await relay._async_heartbeat()
    assert _payload(_calls(aioclient_mock, "/heartbeat")[-1])["chain_seen"] == {"id": 42, "hash": "ab" * 32}
    relay.unload()
