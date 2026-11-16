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
    assert household.is_home("bbbb2222") is False, "nothing known yet: a silent phone is away, not unavailable"
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


async def test_zones_in_heartbeat(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    relay = await _enable_worker(hass, alarm, aioclient_mock)
    beat = _payload(_calls(aioclient_mock, "/heartbeat")[-1])
    zones = {z["name"]: z for z in beat["zones"]}
    assert zones["Door"] == {"room": "Flur", "name": "Door", "state": "closed", "type": "delayed", "watched": False}
    assert zones["Smoke"]["watched"] is True, "always-on sensors are watched while disarmed"
    await alarm.async_arm("night")
    await relay._async_tick()
    await relay._async_tick()
    count = len(_calls(aioclient_mock, "/heartbeat"))
    hass.states.async_set("binary_sensor.window", "on", {"friendly_name": "Window"})
    await relay._async_tick()
    assert len(_calls(aioclient_mock, "/heartbeat")) == count + 1, "a zone change is sent right away"
    zones = {z["name"]: z for z in _payload(_calls(aioclient_mock, "/heartbeat")[-1])["zones"]}
    assert zones["Window"]["state"] == "open"
    assert zones["Door"]["watched"] is True
    relay.unload()


async def test_person_follows_a_linked_tracker(hass: HomeAssistant, alarm) -> None:  # noqa: F811
    hass.states.async_set("device_tracker.unifi_phone", "home", {"friendly_name": "Annas iPhone"})
    await alarm.async_update_config(
        {"people": [{"id": "cccc3333", "name": "Anna", "ip": "", "tracker": "device_tracker.unifi_phone"}]}
    )
    household = alarm.bastion.household
    household.probe = _fake_probe({})
    household.setup()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert household.is_home("cccc3333") is True
    registry = er.async_get(hass)
    sensor = next(e.entity_id for e in registry.entities.values() if e.unique_id.endswith("_presence_cccc3333"))
    assert hass.states.get(sensor).state == "on"
    assert hass.states.get(sensor).attributes["device_class"] == "presence"
    # the controller says the phone left: away right away (no extra waiting)
    hass.states.async_set("device_tracker.unifi_phone", "not_home")
    await hass.async_block_till_done(wait_background_tasks=True)
    assert household.is_home("cccc3333") is False
    assert hass.states.get(sensor).state == "off"
    # unavailable keeps the last state
    hass.states.async_set("device_tracker.unifi_phone", "unavailable")
    await hass.async_block_till_done(wait_background_tasks=True)
    assert household.is_home("cccc3333") is False
    hass.states.async_set("device_tracker.unifi_phone", "Arbeit")
    await hass.async_block_till_done(wait_background_tasks=True)
    assert household.is_home("cccc3333") is False, "another zone counts as away"
    household.unload()


async def test_probe_without_false_positives(hass: HomeAssistant) -> None:
    import ipaddress  # noqa: PLC0415
    from unittest.mock import patch  # noqa: PLC0415

    from custom_components.bastion.alarm import household as hh  # noqa: PLC0415

    async def refused(*_args, **_kwargs):
        raise ConnectionRefusedError

    with patch.object(hh.asyncio, "open_connection", refused):
        assert await hh._tcp_alive("192.168.1.20", 62078, True) is True
        assert await hh._tcp_alive("192.168.20.5", 62078, False) is False, "a reset across the router proves nothing"

    lan = [ipaddress.IPv4Network("192.168.1.0/24")]
    arp = {"192.168.1.20": True}

    async def no(*_args):
        return False

    async def nets(_hass):
        return lan

    with (
        patch.object(hh, "_tcp_alive", no),
        patch.object(hh, "_icmp_alive", no),
        patch.object(hh, "_local_networks", nets),
        patch.object(hh, "_arp_poke", lambda _ip: None),
        patch.object(hh, "_arp_lookup", lambda ip: arp.get(ip, False)),
        patch.object(hh, "ARP_SETTLE", 0),
    ):
        assert await hh.async_probe(hass, "192.168.1.20") == "arp"
        arp["192.168.1.20"] = False  # stale entry turned incomplete after the re-check
        assert await hh.async_probe(hass, "192.168.1.20") is None
        arp["10.0.0.5"] = True
        assert await hh.async_probe(hass, "10.0.0.5") is None, "ARP is only used in the own subnet"


async def test_person_needs_ip_or_tracker(hass: HomeAssistant, alarm, hass_ws_client) -> None:  # noqa: F811
    alarm.bastion.household.probe = _fake_probe({})
    hass.states.async_set("device_tracker.unifi_phone", "home")
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "bastion/alarm/save", "config": {"people": [{"name": "Anna"}]}})
    assert not (await client.receive_json())["success"]
    await client.send_json(
        {
            "id": 2,
            "type": "bastion/alarm/save",
            "config": {"people": [{"name": "Anna", "tracker": "device_tracker.unifi_phone"}]},
        }
    )
    res = await client.receive_json()
    assert res["success"]
    assert res["result"]["household"][0]["tracker"] == "device_tracker.unifi_phone"
    assert any(t["entity_id"] == "device_tracker.unifi_phone" for t in res["result"]["trackers"])
    assert not any(t["entity_id"].startswith("device_tracker.bastion") for t in res["result"]["trackers"])
    alarm.bastion.household.unload()


async def test_hostnames_are_resolved_before_the_subnet_check(hass: HomeAssistant) -> None:
    import ipaddress  # noqa: PLC0415
    import socket  # noqa: PLC0415
    from unittest.mock import patch  # noqa: PLC0415

    from custom_components.bastion.alarm import household as hh  # noqa: PLC0415

    async def getaddrinfo(host, *_args, **_kwargs):
        assert host == "phone.lan"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.20", 0))]

    async def no(*_args):
        return False

    async def nets(_hass):
        return [ipaddress.IPv4Network("192.168.1.0/24")]

    seen = []

    async def tcp(host, _port, onlink):
        seen.append((host, onlink))
        return False

    with (
        patch.object(hass.loop, "getaddrinfo", getaddrinfo),
        patch.object(hh, "_tcp_alive", tcp),
        patch.object(hh, "_icmp_alive", no),
        patch.object(hh, "_local_networks", nets),
        patch.object(hh, "_arp_poke", lambda _ip: None),
        patch.object(hh, "_arp_lookup", lambda ip: ip == "192.168.1.20"),
        patch.object(hh, "ARP_SETTLE", 0),
    ):
        assert await hh.async_probe(hass, "phone.lan") == "arp"
    assert seen and all(s == ("192.168.1.20", True) for s in seen)


async def test_presence_survives_restarts(hass: HomeAssistant, alarm, freezer) -> None:  # noqa: F811
    household = await _household(hass, alarm, {"192.168.1.20": "tcp", "192.168.1.21": None})
    assert alarm.bastion.data["household"]["aaaa1111"]["home"] is True
    assert alarm.bastion.data["household"]["bbbb2222"]["home"] is False
    registry = er.async_get(hass)
    ben = next(e.entity_id for e in registry.entities.values() if e.unique_id.endswith("_presence_bbbb2222"))
    assert hass.states.get(ben).state == "off", "away, not unavailable"
    # restart: state comes back, Anna's phone sleeps -> still home during the grace period
    household.unload()
    household.status = {}
    household.probe = _fake_probe({})
    household.setup()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert household.is_home("aaaa1111") is True
    assert household.is_home("bbbb2222") is False
    await _advance(hass, freezer, 11)
    assert household.is_home("aaaa1111") is False
    household.unload()
