"""Decoys, actionable responses, weekly report, firmware advisories, armored files."""

from __future__ import annotations

from datetime import timedelta
from ipaddress import ip_address

from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN
from homeassistant.components.http.ban import KEY_BAN_MANAGER
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bastion.const import DOMAIN, GITHUB_API
from custom_components.bastion.crypto import MAGIC, FileCipher, armor, new_salt

from .test_integration import _mock_web, _setup


def test_armored_format_and_legacy() -> None:
    cipher = FileCipher.from_passphrase("a long enough passphrase", new_salt(), n=2**10)
    blob = cipher.encrypt("homeassistant/secrets.yaml", b"wifi: secret\n")
    text = blob.decode("ascii")
    assert text.startswith("-----BEGIN BASTION ENCRYPTED FILE-----")
    assert "Path: homeassistant/secrets.yaml" in text
    assert cipher.decrypt("homeassistant/secrets.yaml", blob) == b"wifi: secret\n"
    # Version 1 blobs (raw binary) are still readable.
    raw = armor("x", b"")  # noqa: F841 - armor of empty payload must not crash
    legacy = blob_to_raw(blob)
    assert legacy.startswith(MAGIC)
    assert cipher.decrypt("homeassistant/secrets.yaml", legacy) == b"wifi: secret\n"


def blob_to_raw(blob: bytes) -> bytes:
    from custom_components.bastion.crypto import dearmor

    return dearmor(blob)


async def test_canary_token_and_webhook(hass: HomeAssistant, tmp_path, aioclient_mock, hass_client_no_auth) -> None:
    _mock_web(aioclient_mock, latest=HA_VERSION)
    owner = await hass.auth.async_create_user("Owner", group_ids=["system-admin"])
    assert owner.is_owner
    entry = await _setup(hass, tmp_path, {"canary_enabled": True})
    bastion = entry.runtime_data
    events = []
    hass.bus.async_listen("bastion_security_event", callback(lambda e: events.append(e.data)))
    state = bastion.canary.state
    assert state["token"] and state["user_id"] and state["webhook_id"]
    canary_user = await hass.auth.async_get_user(state["user_id"])
    assert canary_user.local_only and not canary_user.is_admin and not canary_user.is_owner

    client = await hass_client_no_auth()
    resp = await client.get("/api/", headers={"Authorization": f"Bearer {state['token']}"})
    assert resp.status == 401
    await hass.async_block_till_done()
    assert any(e["type"] == "canary" and e["via"] == "token" for e in events)
    assert hass.states.get("binary_sensor.bastion_decoy_triggered").state == "on"

    resp = await client.post(f"/api/webhook/{state['webhook_id']}", json={"x": 1})
    assert resp.status == 200
    await hass.async_block_till_done()
    assert sum(1 for e in events if e["type"] == "canary") == 2
    assert len(state["triggers"]) == 2

    # The decoy user never shows up as a new user or token.
    await bastion.logins._async_poll()  # noqa: SLF001
    assert state["user_id"] not in bastion.logins.users

    # Disabling removes user and token.
    hass.config_entries.async_update_entry(entry, options={**entry.options, "canary_enabled": False})
    await hass.async_block_till_done()
    assert await hass.auth.async_get_user(canary_user.id) is None


async def test_llat_usage_is_tracked(hass: HomeAssistant, tmp_path, aioclient_mock, hass_client_no_auth) -> None:
    _mock_web(aioclient_mock, latest=HA_VERSION)
    entry = await _setup(hass, tmp_path)
    bastion = entry.runtime_data
    user = await hass.auth.async_create_user("Integrator", group_ids=["system-admin"])
    token = await hass.auth.async_create_refresh_token(
        user,
        client_name="nodered",
        token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(days=30),
    )
    access = hass.auth.async_create_access_token(token)
    client = await hass_client_no_auth()
    resp = await client.get("/api/", headers={"Authorization": f"Bearer {access}"})
    assert resp.status == 200
    usage = bastion.logins.token_usage[token.id]
    assert usage["last_used_at"] and usage["ips"]


async def test_block_action_revokes_and_bans(hass: HomeAssistant, tmp_path, aioclient_mock) -> None:
    _mock_web(aioclient_mock, latest=HA_VERSION)
    entry = await _setup(hass, tmp_path)
    bastion = entry.runtime_data
    admin = await hass.auth.async_create_user("Admin", group_ids=["system-admin"])
    victim = await hass.auth.async_create_user("Bob")
    token = await hass.auth.async_create_refresh_token(victim, client_id="https://example.invalid/")
    actions = bastion.responder.actions_for(
        "login", {"user": "Bob", "user_id": victim.id, "ip": "203.0.113.9", "token_id": token.id}
    )
    assert [a["title"] for a in actions] and actions[-1]["action"].startswith("BASTION_BLOCK_")
    from homeassistant.core import Context

    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": actions[-1]["action"]}, context=Context(user_id=admin.id)
    )
    await hass.async_block_till_done()
    assert hass.auth.async_get_refresh_token(token.id) is None
    assert ip_address("203.0.113.9") in hass.http.app[KEY_BAN_MANAGER].ip_bans_lookup
    assert any(e["type"] == "blocked" for e in bastion.logins.log)

    # Replaying the same action does nothing.
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": actions[-1]["action"]}, context=Context(user_id=admin.id)
    )
    await hass.async_block_till_done()
    assert sum(1 for e in bastion.logins.log if e["type"] == "blocked") == 1

    # Non admins cannot trigger actions.
    actions = bastion.responder.actions_for("brute_force", {"ip": "198.51.100.4"})
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": actions[-1]["action"]}, context=Context(user_id=victim.id)
    )
    await hass.async_block_till_done()
    assert ip_address("198.51.100.4") not in hass.http.app[KEY_BAN_MANAGER].ip_bans_lookup


async def test_weekly_report(hass: HomeAssistant, tmp_path, aioclient_mock) -> None:
    _mock_web(aioclient_mock, latest="2099.1.0")
    entry = await _setup(hass, tmp_path)
    bastion = entry.runtime_data
    await bastion.async_run_audit(notify=False)
    result = await hass.services.async_call(DOMAIN, "send_report", {}, blocking=True, return_response=True)
    assert "Sicherheitswert" in result["message"] or "Security score" in result["message"]
    assert bastion.data["last_report"]["title"] == result["title"]
    assert bastion.data["history"][-1]["score"] == bastion.summary()["score"]


async def test_firmware_advisory(hass: HomeAssistant, tmp_path, aioclient_mock) -> None:
    _mock_web(aioclient_mock, latest=HA_VERSION)
    aioclient_mock.get(
        f"{GITHUB_API}/repos/esphome/esphome/security-advisories?state=published&per_page=100",
        json=[
            {
                "ghsa_id": "GHSA-esph-0001",
                "summary": "web_server auth bypass",
                "severity": "high",
                "html_url": "https://example.invalid",
                "vulnerabilities": [
                    {
                        "package": {"name": "esphome"},
                        "vulnerable_version_range": "< 2025.9.0",
                        "patched_versions": "2025.9.0",
                    }
                ],
            }
        ],
    )
    esp_entry = MockConfigEntry(domain="esphome", data={"host": "10.0.0.5", "noise_psk": "x"})
    esp_entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    registry.async_get_or_create(
        config_entry_id=esp_entry.entry_id,
        identifiers={("esphome", "plug1")},
        name="Steckdose Flur",
        sw_version="2025.5.2 (May 1 2025, 10:00:00)",
    )
    entry = await _setup(
        hass, tmp_path, {"disabled_checks": ["access", "http", "exposure", "updates", "supply_chain", "config"]}
    )
    bastion = entry.runtime_data
    await bastion.async_run_audit(notify=False)
    finding = next(f for f in bastion.findings if f.check == "firmware_advisory")
    assert "Steckdose Flur" in finding.description
    assert finding.severity.value == "high"


async def test_canary_never_becomes_owner(hass: HomeAssistant, tmp_path, aioclient_mock) -> None:
    _mock_web(aioclient_mock, latest=HA_VERSION)
    entry = await _setup(hass, tmp_path, {"canary_enabled": True})
    assert not entry.runtime_data.canary.state.get("user_id")
    assert not [u for u in await hass.auth.async_get_users() if not u.system_generated]
