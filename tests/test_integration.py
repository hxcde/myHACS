"""Integration tests in a real (test) Home Assistant instance."""

from __future__ import annotations

from datetime import timedelta
import logging
import os

from dulwich.repo import Repo
from homeassistant.auth.models import TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN, Credentials
from homeassistant.components import webhook
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bastion.const import ADVISORY_REPOS, DEFAULT_OPTIONS, DOMAIN, GITHUB_API, VERSION_URL
from custom_components.bastion.crypto import new_salt
from custom_components.bastion.gitsync.manager import apply_pending_restore


def _mock_web(aioclient_mock, latest: str = "2099.1.0", advisories: list | None = None) -> None:
    aioclient_mock.get(VERSION_URL, json={"homeassistant": {"default": latest}})
    for repo in ADVISORY_REPOS:
        data = advisories if (advisories and repo == "home-assistant/core") else []
        aioclient_mock.get(f"{GITHUB_API}/repos/{repo}/security-advisories?state=published&per_page=100", json=data)


async def _setup(hass: HomeAssistant, tmp_path, options: dict | None = None) -> MockConfigEntry:
    hass.config.config_dir = str(tmp_path)
    (tmp_path / "configuration.yaml").write_text("homeassistant:\n  name: Test\n")
    await async_setup_component(hass, "webhook", {})
    entry = MockConfigEntry(domain=DOMAIN, title="Bastion", data={}, options={**DEFAULT_OPTIONS, **(options or {})})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_config_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "anomaly"})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "anomaly_entities": [],
            "anomaly_sensitivity": 4,
            "anomaly_login_time": True,
            "anomaly_actions": True,
            "anomaly_sabotage": True,
            "sabotage_count": 3,
            "sabotage_window_seconds": 120,
            "anomaly_outbound": False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["anomaly_sensitivity"] == 4.0


async def test_git_options_require_passphrase(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    await hass.config_entries.flow.async_configure(result["flow_id"], {})
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    base = {
        "git_enabled": True,
        "git_url": "git@github.com:me/config.git",
        "git_branch": "main",
        "git_auth": "ssh",
        "git_areas": ["config", "storage"],
        "git_debounce_seconds": 120,
        "git_daily_time": "03:17:00",
        "git_author_name": "HA",
        "git_author_email": "ha@example.invalid",
        "git_allow_unverified_private": False,
    }
    for passphrase, error in (("", "passphrase_required"), ("short", "passphrase_too_short")):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "git"})
        schema = result["data_schema"].schema
        assert "clear_passphrase" not in {str(k) for k in schema}
        areas = next(v for k, v in schema.items() if str(k) == "git_areas")
        assert "addons" not in areas.config["options"]  # no Supervisor in Container installs
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {**base, "git_passphrase": passphrase}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"git_passphrase": error}
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "git"})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**base, "git_passphrase": "a long enough passphrase"}
    )
    assert result["step_id"] == "git_key"
    assert result["description_placeholders"]["public_key"].startswith("ssh-ed25519 ")


async def test_setup_and_audit(hass: HomeAssistant, tmp_path, aioclient_mock, hass_ws_client) -> None:
    advisory = {
        "ghsa_id": "GHSA-test-0001",
        "summary": "Test vulnerability",
        "severity": "critical",
        "html_url": "https://example.invalid",
        "vulnerabilities": [
            {
                "package": {"ecosystem": "pip", "name": "homeassistant"},
                "vulnerable_version_range": "< 2099.1.0",
                "patched_versions": "2099.1.0",
            }
        ],
    }
    _mock_web(aioclient_mock, advisories=[advisory])
    (tmp_path / "packages").mkdir()
    (tmp_path / "packages" / "mqtt.yaml").write_text("sensor:\n  - platform: x\n    password: literalsecret\n")
    entry = await _setup(hass, tmp_path)

    user = await hass.auth.async_create_user("Alice", group_ids=["system-admin"])
    await hass.auth.async_link_user(
        user,
        Credentials(
            auth_provider_type="homeassistant", auth_provider_id=None, data={"username": "alice"}, is_new=False
        ),
    )
    token = await hass.auth.async_create_refresh_token(
        user,
        client_name="old token",
        token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(days=3650),
    )
    token.created_at = dt_util.utcnow() - timedelta(days=500)
    webhook.async_register(hass, "automation", "Door", "abc123", lambda *a: None, local_only=False)
    await hass.config.async_update(external_url="http://my-home.example.com:8123")
    hass.config.components.add("debug_console")

    await hass.services.async_call(DOMAIN, "run_audit", {}, blocking=True)
    bastion = entry.runtime_data
    checks = {f.check for f in bastion.findings}
    for expected in (
        "mfa_missing",
        "token_old",
        "webhook_weak_id",
        "external_url_http",
        "debug_console_enabled",
        "plaintext_secret",
        "advisory",
        "ha_outdated",
    ):
        assert expected in checks, (expected, checks)
    advisory_finding = next(f for f in bastion.findings if f.check == "advisory")
    assert advisory_finding.severity.value == "critical"
    assert HA_VERSION in advisory_finding.description

    issues = [i for (domain, _), i in ir.async_get(hass).issues.items() if domain == DOMAIN]
    assert issues, "high findings must create repairs"

    score = hass.states.get("sensor.bastion_security_score")
    assert score is not None and int(score.state) < 100
    assert hass.states.get("binary_sensor.bastion_critical_findings").state == "on"

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "bastion/overview"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["summary"]["counts"]["critical"] >= 1

    finding = next(f for f in bastion.findings if f.check == "debug_console_enabled")
    await client.send_json_auto_id({"type": "bastion/finding/dismiss", "finding_id": finding.id})
    msg = await client.receive_json()
    assert msg["success"]
    assert any(f["id"] == finding.id and f["dismissed"] for f in msg["result"]["findings"])
    assert "frontend_panels" in hass.data and "bastion" in hass.data["frontend_panels"]


async def test_integrity(hass: HomeAssistant, tmp_path, aioclient_mock) -> None:
    _mock_web(aioclient_mock, latest=HA_VERSION)
    comp = tmp_path / "custom_components" / "foo"
    comp.mkdir(parents=True)
    (comp / "manifest.json").write_text('{"domain": "foo", "name": "Foo", "version": "1.0.0"}')
    (comp / "__init__.py").write_text("x = 1\n")
    entry = await _setup(hass, tmp_path, {"disabled_checks": ["access", "updates", "config"]})
    bastion = entry.runtime_data
    await bastion.async_run_audit()
    assert "custom_code_changed" not in {f.check for f in bastion.findings}

    (comp / "__init__.py").write_text("import os; os.system('evil')\n")
    await bastion.async_run_audit()
    assert "custom_code_changed" in {f.check for f in bastion.findings}

    await bastion.async_accept_integrity("foo")
    assert "custom_code_changed" not in {f.check for f in bastion.findings}


async def test_login_monitor(hass: HomeAssistant, tmp_path, aioclient_mock) -> None:
    _mock_web(aioclient_mock, latest=HA_VERSION)
    entry = await _setup(hass, tmp_path, {"brute_force_threshold": 3})
    bastion = entry.runtime_data
    events = []
    hass.bus.async_listen("bastion_security_event", callback(lambda e: events.append(e.data["type"])))
    logger = logging.getLogger("homeassistant.components.http.ban")
    for _ in range(3):
        logger.warning(
            "Login attempt or request with invalid authentication from attacker.example (203.0.113.7). Requested URL: '/auth/login_flow'. (curl)"
        )
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert events.count("failed_login") == 3
    assert "brute_force" in events
    assert bastion.logins.failed_last_24h() == 3

    user = await hass.auth.async_create_user("Bob")
    await hass.async_block_till_done()
    await hass.auth.async_create_refresh_token(
        user,
        client_name="nodered",
        token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
        access_token_expiration=timedelta(days=30),
    )
    await bastion.logins._async_poll()  # noqa: SLF001
    assert "user_added" in events
    assert "token_created" in events


@pytest.fixture
def git_remote(tmp_path):
    path = tmp_path / "remote.git"
    Repo.init_bare(str(path), mkdir=True)
    return path


async def test_git_sync_and_restore(hass: HomeAssistant, tmp_path, aioclient_mock, hass_ws_client, git_remote) -> None:
    _mock_web(aioclient_mock, latest=HA_VERSION)
    config = tmp_path / "config"
    config.mkdir()
    (config / ".storage").mkdir()
    (config / "automations.yaml").write_text("- id: '1'\n  alias: Original\n  triggers: []\n  actions: []\n")
    (config / "secrets.yaml").write_text("wifi: supersecret\n")
    (config / ".storage" / "input_boolean").write_text('{"version": 1, "data": {"items": []}}')
    (config / ".storage" / "auth").write_text('{"secret": true}')
    options = {
        "git_enabled": True,
        "git_url": str(git_remote),
        "git_auth": "none",
        "git_passphrase": "correct horse battery staple",
        "git_salt": new_salt(),
        "git_areas": ["config", "storage", "inventory"],
    }
    entry = await _setup(hass, config, options)
    bastion = entry.runtime_data

    result = await bastion.git.async_commit("manual", "first")
    assert result["committed"] and result["pushed"]
    remote = Repo(str(git_remote))
    head = remote.refs[b"refs/heads/main"]
    tree = remote[remote[head].tree]
    paths = {e.path.decode() for e in remote.object_store.iter_tree_contents(tree.id)}
    remote.close()
    assert "homeassistant/automations.yaml" in paths
    assert "homeassistant/secrets.yaml.bastion.enc" in paths
    assert "homeassistant/secrets.yaml" not in paths
    assert "homeassistant/.storage/input_boolean" in paths
    assert not any("auth" in p.split("/")[-1] for p in paths)
    first_sha = result["sha"]

    (config / "automations.yaml").write_text("- id: '1'\n  alias: Changed\n  triggers: []\n  actions: []\n")
    (config / ".storage" / "input_boolean").write_text('{"version": 1, "data": {"items": [{"id": "x"}]}}')
    second = await bastion.git.async_commit("manual")
    assert second["committed"]
    assert "homeassistant/automations.yaml" in second["modified"]

    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "bastion/git/history"})
    msg = await client.receive_json()
    assert msg["success"]
    assert [c["sha"] for c in msg["result"]["commits"]][-1] == first_sha

    await client.send_json_auto_id({"type": "bastion/git/files", "commit": first_sha})
    msg = await client.receive_json()
    status = {f["path"]: f["status"] for f in msg["result"]["files"]}
    assert status["homeassistant/automations.yaml"] == "changed"
    assert status["homeassistant/secrets.yaml"] == "same"

    await client.send_json_auto_id(
        {"type": "bastion/git/diff", "commit": first_sha, "path": "homeassistant/automations.yaml"}
    )
    msg = await client.receive_json()
    assert "+  alias: Original" in msg["result"]["diff"]

    restored = await bastion.git.async_restore(first_sha, areas=["config", "storage"])
    assert "homeassistant/automations.yaml" in restored["written"]
    assert "Original" in (config / "automations.yaml").read_text()
    assert "homeassistant/.storage/input_boolean" in restored["staged"]
    assert restored["restart_required"]
    assert '"id": "x"' in (config / ".storage" / "input_boolean").read_text()
    assert await hass.async_add_executor_job(apply_pending_restore, str(config)) == 1
    assert '"items": []' in (config / ".storage" / "input_boolean").read_text()

    # Nothing changed since the second commit, so no empty safety commit.
    history = await bastion.git.async_history(refresh=False)
    assert [c["sha"] for c in history["commits"]] == [second["sha"], first_sha]

    # With local changes a safety commit is created before restoring.
    (config / "automations.yaml").write_text("- id: '1'\n  alias: Local edit\n  triggers: []\n  actions: []\n")
    await bastion.git.async_restore(first_sha, paths=["homeassistant/automations.yaml"])
    history = await bastion.git.async_history(refresh=False)
    assert len(history["commits"]) == 3
    assert "Original" in (config / "automations.yaml").read_text()


async def test_git_restore_rejects_dangerous_paths(hass: HomeAssistant, tmp_path, aioclient_mock, git_remote) -> None:
    """A manipulated repository must not plant auth data or custom code."""
    from dulwich.index import commit_tree
    from dulwich.objects import Blob, Commit

    _mock_web(aioclient_mock, latest=HA_VERSION)
    config = tmp_path / "config"
    config.mkdir()
    remote = Repo(str(git_remote))
    blobs = []
    for path, data in (
        ("homeassistant/.storage/auth", b'{"evil": 1}'),
        ("homeassistant/custom_components/evil/__init__.py", b"import os"),
        ("homeassistant/ok.yaml", b"a: 1\n"),
    ):
        blob = Blob.from_string(data)
        remote.object_store.add_object(blob)
        blobs.append((path.encode(), blob.id, 0o100644))
    commit = Commit()
    commit.tree = commit_tree(remote.object_store, blobs)
    commit.author = commit.committer = b"x <x@x>"
    commit.author_time = commit.commit_time = 0
    commit.author_timezone = commit.commit_timezone = 0
    commit.message = b"evil"
    remote.object_store.add_object(commit)
    remote.refs[b"refs/heads/main"] = commit.id
    remote.close()

    entry = await _setup(
        hass,
        config,
        {"git_enabled": True, "git_url": str(git_remote), "git_auth": "none", "git_areas": ["config", "storage"]},
    )
    result = await entry.runtime_data.git.async_restore(commit.id.decode())
    skipped = {s["path"] for s in result["skipped"]}
    assert "homeassistant/.storage/auth" in skipped
    assert "homeassistant/custom_components/evil/__init__.py" in skipped
    assert result["written"] == ["homeassistant/ok.yaml"]
    assert not os.path.exists(config / "custom_components")
    assert not os.path.exists(config / ".bastion" / "pending_restore.json")
