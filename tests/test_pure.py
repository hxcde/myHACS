"""Tests for pure helpers: secret scanner, crypto, versions, statistics."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from custom_components.bastion.anomaly.stats import HourHistogram, SensorModel
from custom_components.bastion.audit.updates import (
    classify,
    extract_version,
    is_vulnerable,
    match_advisories,
    version_in_range,
)
from custom_components.bastion.crypto import DecryptionError, FileCipher, new_salt
from custom_components.bastion.gitsync.collector import is_safe_relative, resolve_target
from custom_components.bastion.gitsync.remote import RemoteError, parse_remote, safe_branch
from custom_components.bastion.secret_scan import scan_text


@pytest.mark.parametrize(
    "text",
    [
        "password: hunter2hunter",
        "  api_key: 'abcdef123456'",
        "token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnopqrstuv",
        "url: mqtt://user:secretpass@broker.local",
        "-----BEGIN OPENSSH PRIVATE KEY-----",
        "github: ghp_abcdefghijklmnopqrstuvwxyz0123456789AB",
        "network_key: [1, 2, 3, 4]",
        "    key: 'aGVsbG8gd29ybGQgdGhpcyBpcyBhIHRlc3Qga2V5IQ=='",
    ],
)
def test_scanner_finds(text: str) -> None:
    assert scan_text(text), text


@pytest.mark.parametrize(
    "text",
    [
        "password: !secret db_password",
        "token: !env_var TOKEN",
        "password: \"{{ states('input_text.pw') }}\"",
        "pin: GPIO4",
        "password_entity: input_text.x",
        "show_password: true",
        "# password: commented",
        "password: ${wifi_password}",
        "max_tokens: 500",
        "token: ''",
    ],
)
def test_scanner_ignores(text: str) -> None:
    assert not scan_text(text), text


def test_scanner_never_returns_value() -> None:
    hits = scan_text("password: supersecretvalue")
    assert hits[0].line == 1
    assert "supersecret" not in repr(hits)


def test_crypto_roundtrip_and_binding() -> None:
    salt = new_salt()
    cipher = FileCipher.from_passphrase("correct horse", salt, n=2**10)
    blob = cipher.encrypt("a/secrets.yaml", b"x: 1")
    assert cipher.decrypt("a/secrets.yaml", blob) == b"x: 1"
    with pytest.raises(DecryptionError):
        cipher.decrypt("b/other.yaml", blob)
    wrong = FileCipher.from_passphrase("wrong", salt, n=2**10)
    with pytest.raises(DecryptionError):
        wrong.decrypt("a/secrets.yaml", blob)
    assert cipher.mac("p", b"1") == cipher.mac("p", b"1") != cipher.mac("p", b"2")


def test_version_ranges() -> None:
    assert version_in_range("2026.6.0", "< 2026.7.0")
    assert not version_in_range("2026.7.0", "< 2026.7.0")
    assert version_in_range("2025.1.0", ">= 2024.1.0, < 2026.7.0")
    assert not version_in_range("2023.1.0", ">= 2024.1.0, < 2026.7.0")
    assert is_vulnerable("2026.5.0", {"patched_versions": "2026.5.4"})
    assert not is_vulnerable("2026.5.4", {"patched_versions": "2026.5.4"})
    assert extract_version("2026.8.1-full") == "2026.8.1"
    assert extract_version("2026.4.1 (2026.1234)") == "2026.4.1"


def test_advisory_matching() -> None:
    advisories = [
        {
            "_repo": "home-assistant/core",
            "ghsa_id": "GHSA-1",
            "summary": "Auth bypass in Konnected",
            "severity": "high",
            "vulnerabilities": [
                {
                    "package": {"name": "homeassistant"},
                    "vulnerable_version_range": "< 2026.6.0",
                    "patched_versions": "2026.6.0",
                }
            ],
        },
        {
            "_repo": "home-assistant/core",
            "ghsa_id": "GHSA-2",
            "summary": "Android Companion app forwards NFC scans",
            "severity": "high",
            "vulnerabilities": [
                {"package": {"name": "io.homeassistant.companion.android"}, "patched_versions": "2026.8.1"}
            ],
        },
    ]
    assert [a["ghsa_id"] for a in match_advisories(advisories, "core", "2026.5.0")] == ["GHSA-1"]
    assert match_advisories(advisories, "core", "2026.6.0") == []
    assert [a["ghsa_id"] for a in match_advisories(advisories, "android", "2026.7.0")] == ["GHSA-2"]
    assert classify("home-assistant/iOS", {}, "x") == "ios"


def test_remote_parsing() -> None:
    spec = parse_remote("git@github.com:me/conf.git")
    assert (spec.kind, spec.host, spec.user, spec.path) == ("ssh", "github.com", "git", "me/conf.git")
    assert spec.https_url == "https://github.com/me/conf.git"
    spec = parse_remote("ssh://git@git.example.com:2222/me/conf.git")
    assert spec.port == 2222 and spec.path == "/me/conf.git"
    spec = parse_remote("https://user:tok@gitea.local/me/conf.git")
    assert spec.display == "https://gitea.local/me/conf.git"
    with pytest.raises(RemoteError):
        parse_remote("not a url")
    assert safe_branch("main") == "main"
    for bad in ("../x", "a..b", "-x", "a b", "x.lock"):
        with pytest.raises(RemoteError):
            safe_branch(bad)


def test_path_guards(tmp_path) -> None:
    assert is_safe_relative("a/b.yaml")
    for bad in ("../a", "/etc/passwd", "a/../../b", "a//b", "", "a\\b"):
        assert not is_safe_relative(bad)
    assert resolve_target(str(tmp_path), "x/y.yaml") == str(tmp_path / "x" / "y.yaml")
    assert resolve_target(str(tmp_path), "../escape") is None
    (tmp_path / "link").symlink_to("/etc")
    assert resolve_target(str(tmp_path), "link/passwd") is None


def test_sensor_model_deviation() -> None:
    model = SensorModel()
    start = datetime(2026, 1, 5, 0, 0)
    for day in range(10):
        for minute in range(0, 60, 5):
            ts = start + timedelta(days=day, hours=3, minutes=minute)
            assert model.observe(ts, 100 + (minute % 10), 3.5) == [] or day < 4
    ts = start + timedelta(days=10, hours=3)
    results = [model.observe(ts + timedelta(minutes=5 * i), 500, 3.5) for i in range(3)]
    assert results[-1] and results[-1][0]["type"] == "deviation"


def test_sensor_model_roundtrip() -> None:
    model = SensorModel()
    model.observe(datetime(2026, 1, 1, 1), 5.0, 3)
    clone = SensorModel.from_dict(model.to_dict())
    assert clone.samples == 1 and clone.overall.mean == 5.0


def test_hour_histogram() -> None:
    hist = HourHistogram()
    for _ in range(20):
        hist.add(9)
    assert hist.unusual(3, 15)
    assert not hist.unusual(10, 15)
