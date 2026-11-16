"""Household presence by phone IP, device trackers, reminder and websocket."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.bastion.alarm.household import valid_address

from .test_alarm import alarm  # noqa: F401
from .test_worker_link import _calls, _enable_worker, _payload

PEOPLE = [
    {"id": "aaaa1111", "name": "Anna", "ip": "192.168.1.20"},
    {"id": "bbbb2222", "name": "Ben", "ip": "192.168.1.21"},
]


def _fake_probe(answers: dict[str, str | None]):
    async def probe(_hass, host):
        return answers.get(host)

    return probe


async def _household(hass, alarm, answers):  # noqa: F811
    await alarm.async_update_config({"people": PEOPLE, "presence": {"away_minutes": 10}})
    household = alarm.bastion.household
    household.probe = _fake_probe(answers)
    household.setup()
    await hass.async_block_till_done(wait_background_tasks=True)
    return household


async def _advance(hass, freezer, minutes):
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def test_valid_address() -> None:
    assert valid_address("192.168.1.20")
    assert valid_address("10.0.0.5")
    assert valid_address("iphone-anna.fritz.box")
    assert not valid_address("8.8.8.8"), "public addresses are not probed"
    assert not valid_address("127.0.0.1")
    assert not valid_address("bad host!")


async def test_presence_detection_and_entities(hass: HomeAssistant, alarm, freezer) -> None:  # noqa: F811
    answers = {"192.168.1.20": "tcp", "192.168.1.21": None}
    household = await _household(hass, alarm, answers)
    assert household.is_home("aaaa1111") is True
    assert household.is_home("bbbb2222") is None, "silent phone: unknown until the away time passed"
    assert household.anyone_home() is True
    registry = er.async_get(hass)
    trackers = [e for e in registry.entities.values() if e.domain == "device_tracker" and e.platform == "bastion"]
    assert len(trackers) == 2
    anna = next(e.entity_id for e in trackers if e.unique_id.endswith("aaaa1111"))
    assert hass.states.get(anna).state == "home"
    assert hass.states.get(anna).attributes["ip"] == "192.168.1.20"

    # Anna leaves: away only after 10 minutes without answer
    answers["192.168.1.20"] = None
    await _advance(hass, freezer, 5)
    assert household.is_home("aaaa1111") is True
    await _advance(hass, freezer, 6)
    assert household.is_home("aaaa1111") is False
    assert household.is_home("bbbb2222") is False
    assert household.all_away()
    assert hass.states.get(anna).state == "not_home"
    occupancy = next(e.entity_id for e in registry.entities.values() if e.unique_id.endswith("_anyone_home"))
    assert hass.states.get(occupancy).state == "off"
    # back home: immediately
    answers["192.168.1.21"] = "arp"
    await _advance(hass, freezer, 1)
    assert household.is_home("bbbb2222") is True
    assert hass.states.get(occupancy).state == "on"
    assert hass.states.get(occupancy).attributes["home"] == ["Ben"]

    # removing a person removes its tracker
    await alarm.async_update_config({"people": PEOPLE[:1]})
    household.setup()
    await hass.async_block_till_done(wait_background_tasks=True)
    trackers = [e for e in registry.entities.values() if e.domain == "device_tracker" and e.platform == "bastion"]
    assert len(trackers) == 1
    household.unload()


async def test_reminder_uses_the_household(hass: HomeAssistant, alarm, aioclient_mock, freezer) -> None:  # noqa: F811
    relay = await _enable_worker(hass, alarm, aioclient_mock)
    answers = {"192.168.1.20": None, "192.168.1.21": None}
    household = await _household(hass, alarm, answers)
    await alarm.async_update_config({"remote": {"reminder": True, "reminder_minutes": 5}})
    presence = alarm.bastion.presence
    presence.setup()
    assert presence.source == "household"
    await _advance(hass, freezer, 11)  # both silent long enough: away
    assert household.all_away()
    await _advance(hass, freezer, 6)
    reminders = [e for e in alarm.log if e["type"] == "unarmed"]
    assert len(reminders) == 1 and reminders[0]["persons"] == ["Anna", "Ben"]
    beat = _payload(_calls(aioclient_mock, "/heartbeat")[-1])
    assert [p["name"] for p in beat["presence"]] == ["Anna", "Ben"]
    assert all(p["home"] is False for p in beat["presence"])
    assert "ip" not in beat["presence"][0], "addresses stay at home"
    presence.unload()
    household.unload()
    relay.unload()


async def test_people_websocket(hass: HomeAssistant, alarm, hass_ws_client) -> None:  # noqa: F811
    alarm.bastion.household.probe = _fake_probe({})
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "bastion/alarm/save",
            "config": {"people": [{"name": " Anna ", "ip": "192.168.1.20"}], "presence": {"away_minutes": 15}},
        }
    )
    res = await client.receive_json()
    assert res["success"]
    people = res["result"]["config"]["people"]
    assert people[0]["name"] == "Anna" and len(people[0]["id"]) == 8
    assert res["result"]["household"][0]["ip"] == "192.168.1.20"
    await client.send_json(
        {"id": 2, "type": "bastion/alarm/save", "config": {"people": [{"name": "X", "ip": "8.8.8.8"}]}}
    )
    assert not (await client.receive_json())["success"]
    alarm.bastion.household.unload()

    async def fake(_hass, host):
        return "ping" if host == "192.168.1.30" else None

    from unittest.mock import patch  # noqa: PLC0415

    with patch("custom_components.bastion.websocket.async_probe", fake):
        await client.send_json({"id": 3, "type": "bastion/alarm/presence_test", "address": "192.168.1.30"})
        assert (await client.receive_json())["result"] == {"found": True, "method": "ping"}
        await client.send_json({"id": 4, "type": "bastion/alarm/presence_test", "address": "8.8.8.8"})
        assert not (await client.receive_json())["success"]
