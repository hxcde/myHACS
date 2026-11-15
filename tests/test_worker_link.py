"""Worker link: incidents, heartbeat context, acknowledgements, snapshots, media sounds, phone cleanup."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from unittest.mock import patch

from homeassistant.components.camera import Image
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.bastion.alarm.relay import incident_token, sign

from .test_alarm import _fire, alarm  # noqa: F401

WORKER = "https://worker.example.invalid"


def _calls(aioclient_mock, path):
    return [c for c in aioclient_mock.mock_calls if str(c[1]).endswith(path)]


def _payload(call):
    return json.loads(call[2])


async def _enable_worker(hass, alarm, aioclient_mock, acks=None, **worker):  # noqa: F811
    aioclient_mock.post(f"{WORKER}/heartbeat", json={"ok": True, "acks": acks or []})
    aioclient_mock.post(f"{WORKER}/alert", json={"ok": True, "channels": []})
    aioclient_mock.post(f"{WORKER}/snapshot", json={"ok": True, "id": 1})
    await alarm.async_update_config({"worker": {"url": WORKER, "enabled": True, "interval": 60, **worker}})
    alarm.bastion.relay.setup()
    await hass.async_block_till_done()
    return alarm.bastion.relay


async def test_incident_spans_warning_alarm_and_disarm(hass: HomeAssistant, alarm) -> None:  # noqa: F811
    await alarm.async_arm("away")
    _fire(hass, 31)
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    assert alarm.state == "pending"
    incident = alarm.incident
    assert incident and len(incident) == 12
    _fire(hass, 60)
    await hass.async_block_till_done()
    assert alarm.state == "triggered"
    assert alarm.incident == incident, "alarm after the warning is the same incident"
    await alarm.async_disarm()
    assert alarm.incident is None
    entries = {e["type"]: e for e in alarm.log}
    assert (
        entries["pending"]["incident"]
        == entries["triggered"]["incident"]
        == entries["disarmed"]["incident"]
        == incident
    )
    assert "incident" not in entries["armed"]


async def test_heartbeat_context_and_acknowledgements(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    hass.states.async_set("binary_sensor.window", "on", {"friendly_name": "Window"})
    hass.states.async_set("binary_sensor.smoke", "unavailable", {"friendly_name": "Smoke"})
    ack = {"receipt": "r123", "kind": "alarm", "incident": "abcdef123456", "at": 1, "by": "iphone"}
    relay = await _enable_worker(hass, alarm, aioclient_mock, acks=[ack])
    beat = _payload(_calls(aioclient_mock, "/heartbeat")[-1])
    assert beat["open"] == ["Window"]
    assert beat["unavailable"] == ["Smoke"]
    assert beat["tz"] == str(hass.config.time_zone)
    assert beat["started"] > 0 and beat["boot"] > 0
    assert beat["stopping"] is False
    acks = [e for e in alarm.log if e["type"] == "acknowledged"]
    assert len(acks) == 1 and acks[0]["user"] == "iphone" and acks[0]["incident"] == "abcdef123456"

    # next heartbeat confirms the receipt, the same acknowledgement is not logged twice
    await relay._async_heartbeat()
    await hass.async_block_till_done()
    assert _payload(_calls(aioclient_mock, "/heartbeat")[-1])["acks_seen"] == ["r123"]
    assert len([e for e in alarm.log if e["type"] == "acknowledged"]) == 1

    await relay.async_stop()
    assert _payload(_calls(aioclient_mock, "/heartbeat")[-1])["stopping"] is True


async def test_events_carry_incident_detail_and_push_flag(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    await _enable_worker(hass, alarm, aioclient_mock)
    await alarm.async_update_config({"actions": {"notify_events": ["triggered"]}})
    await alarm.async_set_code("Yann", "1234")
    await alarm.async_trigger("manual")
    await hass.async_block_till_done()
    with __import__("pytest").raises(Exception):
        await alarm.async_disarm("0000", user="Gast")
    await alarm.async_disarm("1234")
    await hass.async_block_till_done()
    alerts = [_payload(c) for c in _calls(aioclient_mock, "/alert")]
    by_event = {a["event"]: a for a in alerts}
    assert by_event["triggered"]["push"] is True
    assert by_event["wrong_code"]["push"] is False, "logged off-site, but not pushed"
    assert by_event["disarmed"]["push"] is False
    incident = by_event["triggered"]["incident"]
    assert incident and by_event["disarmed"]["incident"] == incident
    assert by_event["disarmed"]["detail"]["previous"] == "triggered"
    call = _calls(aioclient_mock, "/alert")[-1]
    assert call[3]["X-Bastion-Signature"] == sign(
        alarm.config["worker"]["secret"], call[3]["X-Bastion-Timestamp"], call[2]
    )


async def test_incident_link_token(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    relay = await _enable_worker(hass, alarm, aioclient_mock)
    secret = alarm.config["worker"]["secret"]
    expected = hmac.new(secret.encode(), b"incident.abcdef123456", hashlib.sha256).hexdigest()[:32]
    assert incident_token(secret, "abcdef123456") == expected
    assert relay.incident_url("abcdef123456") == f"{WORKER}/i/abcdef123456?t={expected}"
    assert relay.incident_url(None) is None


async def test_camera_snapshots_are_sent_for_the_incident(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    hass.states.async_set("camera.flur", "idle", {"friendly_name": "Flur"})
    await _enable_worker(hass, alarm, aioclient_mock, cameras=["camera.flur"], snapshots=2)
    with (
        patch(
            "homeassistant.components.camera.async_get_image", return_value=Image("image/jpeg", b"jpeg-bytes")
        ) as get,
        patch("custom_components.bastion.alarm.relay.SNAPSHOT_INTERVAL", 0),
    ):
        await alarm.async_trigger("manual")
        await hass.async_block_till_done(wait_background_tasks=True)
    shots = [_payload(c) for c in _calls(aioclient_mock, "/snapshot")]
    assert len(shots) == 2
    assert shots[0]["incident"] == alarm.incident
    assert shots[0]["camera"] == "Flur"
    assert base64.b64decode(shots[0]["data"]) == b"jpeg-bytes"
    assert get.call_args.kwargs["width"] == 1280


async def test_media_player_sounds(hass: HomeAssistant, alarm) -> None:  # noqa: F811
    hass.config.internal_url = "http://ha.local:8123"
    hass.states.async_set("media_player.kitchen", "idle", {"volume_level": 0.3, "supported_features": 4 | 512 | 4096})
    play = async_mock_service(hass, "media_player", "play_media")
    volume = async_mock_service(hass, "media_player", "volume_set")
    stop = async_mock_service(hass, "media_player", "media_stop")
    await alarm.async_update_config(
        {"sounds": {"players": ["media_player.kitchen"], "volume": 1.0, "notice_volume": 0.4, "armed": "bastion:armed"}}
    )

    await alarm.async_arm("away")  # 30 s exit delay -> exit beeps
    await hass.async_block_till_done()
    assert "/bastion_static/sounds/exit.mp3" in play[-1].data["media_content_id"]
    assert play[-1].data["media_content_id"].startswith("http://ha.local:8123/")
    assert volume[-1].data["volume_level"] == 0.4

    _fire(hass, 31)  # armed -> beeps stop, volume back, chime once
    await hass.async_block_till_done()
    assert stop, "exit beeps stopped"
    assert any(c.data["volume_level"] == 0.3 for c in volume), "volume restored"
    assert "/sounds/armed.mp3" in play[-1].data["media_content_id"]

    await alarm.async_trigger("manual")  # siren loop at alarm volume
    await hass.async_block_till_done()
    assert "/sounds/siren.mp3" in play[-1].data["media_content_id"]
    assert volume[-1].data["volume_level"] == 1.0
    plays = len(play)
    alarm.sounds._last_start.clear()  # the sound finished long ago
    hass.states.async_set(
        "media_player.kitchen", "playing", {"volume_level": 1.0, "supported_features": 4 | 512 | 4096}
    )
    await hass.async_block_till_done()
    hass.states.async_set("media_player.kitchen", "idle", {"volume_level": 1.0, "supported_features": 4 | 512 | 4096})
    await hass.async_block_till_done()
    assert len(play) == plays + 1, "siren repeats while the alarm lasts"

    stops = len(stop)
    await alarm.async_disarm()
    await hass.async_block_till_done()
    assert len(stop) > stops
    assert volume[-1].data["volume_level"] == 0.3
    assert alarm.sounds.active is None


async def test_sound_websocket(hass: HomeAssistant, alarm, hass_ws_client) -> None:  # noqa: F811
    hass.config.internal_url = "http://ha.local:8123"
    hass.states.async_set("media_player.office", "idle", {"volume_level": 0.2, "supported_features": 4 | 512 | 4096})
    play = async_mock_service(hass, "media_player", "play_media")
    async_mock_service(hass, "media_player", "volume_set")
    async_mock_service(hass, "media_player", "media_stop")
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "bastion/alarm/sound",
            "action": "play",
            "sound": "bastion:siren",
            "players": ["media_player.office"],
        }
    )
    msg = await client.receive_json()
    assert msg["success"] and msg["result"]["ok"]
    assert play[-1].data["entity_id"] == "media_player.office"
    await client.send_json({"id": 2, "type": "bastion/alarm/sound", "action": "play", "sound": "file:///etc/passwd"})
    msg = await client.receive_json()
    assert not msg["success"], "only built-in, media source or http(s) sounds"
    await client.send_json({"id": 3, "type": "bastion/alarm/sound", "action": "stop"})
    assert (await client.receive_json())["success"]
    await client.send_json({"id": 4, "type": "bastion/alarm/media"})
    msg = await client.receive_json()
    assert msg["success"] and msg["result"]["files"] == []
    await client.send_json({"id": 5, "type": "bastion/alarm/get"})
    msg = await client.receive_json()
    assert {"entity_id": "media_player.office", "name": "media_player.office"} in msg["result"]["players"]
    assert "siren" in msg["result"]["sounds_builtin"]


async def test_phone_notifications_are_cleared_on_disarm(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    phone = async_mock_service(hass, "notify", "mobile_app_phone")
    await _enable_worker(hass, alarm, aioclient_mock)
    alarm.bastion.notifier._targets = ["notify.mobile_app_phone"]
    await alarm.async_trigger("manual")
    await hass.async_block_till_done()
    data = phone[-1].data["data"]
    assert data["tag"] == "bastion_alarm"
    assert data["url"].startswith(f"{WORKER}/i/{alarm.incident}?t=")
    await alarm.async_disarm()
    await hass.async_block_till_done()
    clear = [c for c in phone if c.data["message"] == "clear_notification"]
    assert clear and clear[-1].data["data"] == {"tag": "bastion_alarm"}


async def test_own_sensor_names(hass: HomeAssistant, alarm, hass_ws_client) -> None:  # noqa: F811
    client = await hass_ws_client(hass)
    sensors = {k: dict(v) for k, v in alarm.config["sensors"].items()}
    sensors["binary_sensor.door"]["name"] = "  Haustür  "
    sensors["binary_sensor.motion"]["name"] = "   "
    await client.send_json({"id": 1, "type": "bastion/alarm/save", "config": {"sensors": sensors}})
    msg = await client.receive_json()
    assert msg["success"], msg
    assert alarm.config["sensors"]["binary_sensor.door"]["name"] == "Haustür"
    assert alarm.config["sensors"]["binary_sensor.motion"]["name"] is None, "blank = Home Assistant name"
    await client.send_json(
        {"id": 2, "type": "bastion/alarm/save", "config": {"sensors": {"binary_sensor.door": {"name": "x" * 61}}}}
    )
    assert not (await client.receive_json())["success"]

    await alarm.async_arm("home")
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    pending = [e for e in alarm.log if e["type"] == "pending"][-1]
    assert pending["name"] == "Haustür"
    assert alarm.triggered_by["name"] == "Haustür"
    assert alarm._name("binary_sensor.motion") == "Motion"


async def test_security_overview_login_events_and_worker_attack(hass: HomeAssistant, alarm, aioclient_mock) -> None:  # noqa: F811
    bastion = alarm.bastion
    bastion.logins.log.append({"time": "2000-01-01T00:00:00+00:00", "type": "failed_login", "ip": "203.0.113.1"})
    bastion.logins.record("failed_login", {"ip": "203.0.113.5"})
    attack = {
        "ts": 1,
        "total": 7,
        "sources": [{"ip": "198.51.100.66", "country": "NL", "n": 7, "kinds": ["signature"], "blocked": True}],
    }
    aioclient_mock.post(f"{WORKER}/heartbeat", json={"ok": True, "acks": [], "attack": attack})
    aioclient_mock.post(f"{WORKER}/alert", json={"ok": True, "channels": []})
    seen = []
    hass.bus.async_listen("bastion_security_event", lambda e: seen.append(e.data))
    await alarm.async_update_config({"worker": {"url": WORKER, "enabled": True, "interval": 60}})
    relay = bastion.relay
    relay.setup()
    await hass.async_block_till_done()

    beat = _payload(_calls(aioclient_mock, "/heartbeat")[-1])
    assert set(beat["security"]) >= {"score", "counts", "open", "findings", "failed_24h"}
    events = beat["security_events"]
    assert [e["ip"] for e in events] == ["203.0.113.5"], "only the last 7 days are backfilled"
    assert "user_id" not in events[0] and len(events[0]["uid"]) == 24

    # worker attack is logged in HA and fired for automations, but not sent back
    assert any(e["type"] == "worker_attack" and e["count"] == 7 for e in bastion.logins.log)
    assert any(e.get("type") == "worker_attack" for e in seen)

    hass.bus.async_fire("bastion_security_event", {"type": "new_ip", "ip": "192.0.2.4", "user": "Yann", "user_id": "x"})
    await hass.async_block_till_done()
    await relay._async_heartbeat()
    beat = _payload(_calls(aioclient_mock, "/heartbeat")[-1])
    assert "security" not in beat, "unchanged overview is not resent"
    types = [e["type"] for e in beat["security_events"]]
    assert "new_ip" in types and "worker_attack" not in types
