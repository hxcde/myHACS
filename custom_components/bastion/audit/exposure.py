"""HTTP configuration, webhooks, voice assistant exposure, MQTT."""

from __future__ import annotations

import ipaddress
import math
from typing import Any
from urllib.parse import urlsplit

from ..const import Category, Severity
from ..models import Finding, make_finding
from ..texts import misc
from . import AuditContext

SENSITIVE_COVER_CLASSES = {"garage", "gate", "door"}
ASSISTANT_NAMES = {
    "conversation": "Assist",
    "cloud.google_assistant": "Google Assistant",
    "cloud.alexa": "Alexa",
}


def _is_local_host(host: str) -> bool:
    if host in ("localhost",) or host.endswith((".local", ".lan", ".home", ".internal", ".home.arpa")):
        return True
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return False


def _http_conf(hass) -> dict[str, Any]:
    """Active HTTP configuration (store based since 2026)."""
    try:
        from homeassistant.components.http.config import DATA_STORE  # noqa: PLC0415

        store = hass.data.get(DATA_STORE)
        if store is not None:
            conf = (
                store.pending
                if getattr(store, "active_config_type", "") == "pending" and store.pending
                else store.stable
            )
            return dict(conf or {})
    except ImportError:
        pass
    return {}


async def async_check_http(ctx: AuditContext) -> list[Finding]:
    """HTTP server configuration."""
    hass = ctx.hass
    out: list[Finding] = []
    if (url := hass.config.external_url) and url.startswith("http://"):
        host = urlsplit(url).hostname or ""
        if not _is_local_host(host):
            out.append(make_finding("external_url_http", Severity.HIGH, Category.EXPOSURE, url, url=url))

    http = getattr(hass, "http", None)
    if http is not None:
        app = http.app
        try:
            from homeassistant.components.http.ban import KEY_BAN_MANAGER, KEY_LOGIN_THRESHOLD  # noqa: PLC0415

            if KEY_BAN_MANAGER not in app:
                out.append(make_finding("ip_ban_disabled", Severity.MEDIUM, Category.EXPOSURE, "ban"))
            else:
                threshold = app.get(KEY_LOGIN_THRESHOLD, 0)
                if threshold < 1:
                    out.append(make_finding("ip_ban_disabled", Severity.MEDIUM, Category.EXPOSURE, "ban"))
                elif threshold > 10:
                    out.append(
                        make_finding(
                            "login_threshold_high", Severity.LOW, Category.EXPOSURE, "threshold", threshold=threshold
                        )
                    )
        except ImportError:
            pass
        for net in getattr(http, "trusted_proxies", []) or []:
            wide = net.prefixlen < (24 if net.version == 4 else 64) or net.is_global
            if wide:
                out.append(
                    make_finding(
                        "trusted_proxies_wide",
                        Severity.HIGH if net.prefixlen == 0 else Severity.MEDIUM,
                        Category.EXPOSURE,
                        str(net),
                        network=str(net),
                    )
                )
    conf = _http_conf(hass)
    if "*" in (conf.get("cors_allowed_origins") or []):
        out.append(make_finding("cors_wildcard", Severity.HIGH, Category.EXPOSURE, "cors"))
    return out


def _entropy_bits(value: str) -> float:
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    per_char = -sum((c / len(value)) * math.log2(c / len(value)) for c in counts.values())
    return per_char * len(value)


def _webhooks(hass) -> dict[str, Any]:
    try:
        from homeassistant.components.webhook import _HANDLERS  # noqa: PLC0415

        return dict(hass.data.get(_HANDLERS, {}) or {})
    except ImportError:
        return {}


async def async_check(ctx: AuditContext) -> list[Finding]:
    """Webhooks, exposed entities, alarm codes, MQTT."""
    hass = ctx.hass
    language = hass.config.language
    out: list[Finding] = []

    for webhook_id, info in _webhooks(hass).items():
        local_only = bool(getattr(info, "local_only", True))
        domain = getattr(info, "domain", "?")
        name = getattr(info, "name", webhook_id)
        weak = len(webhook_id) < 16 or _entropy_bits(webhook_id) < 64
        if weak:
            out.append(
                make_finding(
                    "webhook_weak_id",
                    Severity.HIGH if not local_only else Severity.LOW,
                    Category.EXPOSURE,
                    webhook_id,
                    name=name,
                    domain=domain,
                    length=len(webhook_id),
                    remote=misc("remote_yes" if not local_only else "remote_no", language),
                )
            )
        elif not local_only and domain == "automation":
            out.append(make_finding("webhook_remote", Severity.LOW, Category.EXPOSURE, webhook_id, name=name))

    sensitive: list[str] = []
    for state in hass.states.async_all(("lock", "alarm_control_panel", "cover", "valve")):
        if state.domain == "cover" and state.attributes.get("device_class") not in SENSITIVE_COVER_CLASSES:
            continue
        sensitive.append(state.entity_id)
    if sensitive:
        try:
            from homeassistant.components.homeassistant.exposed_entities import async_should_expose  # noqa: PLC0415
        except ImportError:
            async_should_expose = None  # type: ignore[assignment]
        google_pin = _google_pin(hass)
        if async_should_expose is not None:
            for entity_id in sensitive:
                for assistant, assistant_name in ASSISTANT_NAMES.items():
                    if assistant.startswith("cloud.") and "cloud" not in hass.config.components:
                        continue
                    try:
                        exposed = async_should_expose(hass, assistant, entity_id)
                    except (KeyError, AttributeError):
                        continue
                    if not exposed:
                        continue
                    if assistant == "cloud.google_assistant":
                        severity = Severity.LOW if google_pin else Severity.HIGH
                        pin = misc("pin_set" if google_pin else "pin_none", language)
                    else:
                        severity = Severity.MEDIUM
                        pin = ""
                    out.append(
                        make_finding(
                            "voice_exposed_sensitive",
                            severity,
                            Category.EXPOSURE,
                            entity_id,
                            assistant,
                            entity=entity_id,
                            assistant=assistant_name,
                            pin=pin,
                        )
                    )

    for state in hass.states.async_all("alarm_control_panel"):
        if state.attributes.get("code_format") is None:
            out.append(
                make_finding(
                    "alarm_no_code", Severity.MEDIUM, Category.EXPOSURE, state.entity_id, entity=state.entity_id
                )
            )

    for entry in hass.config_entries.async_entries("mqtt"):
        data = {**entry.data, **entry.options}
        broker = str(data.get("broker", ""))
        port = int(data.get("port", 1883) or 1883)
        tls = (
            bool(data.get("certificate") or data.get("client_cert") or data.get("tls_insecure") is not None)
            or port == 8883
        )
        if data.get("transport") == "websockets" and port == 443:
            tls = True
        if tls:
            continue
        anonymous = not data.get("username")
        local = broker in ("localhost", "127.0.0.1", "::1", "core-mosquitto", "mosquitto")
        if local and not anonymous:
            continue
        severity = Severity.MEDIUM if (anonymous or not _is_local_host(broker)) else Severity.LOW
        out.append(
            make_finding(
                "mqtt_unencrypted",
                severity,
                Category.EXPOSURE,
                broker,
                port,
                broker=broker,
                port=port,
                anon=misc("anon", language) if anonymous else "",
            )
        )
    return out


def _google_pin(hass) -> bool:
    try:
        cloud = hass.data.get("cloud")
        prefs = getattr(getattr(cloud, "client", None), "prefs", None)
        return bool(getattr(prefs, "google_secure_devices_pin", None))
    except Exception:  # noqa: BLE001
        return False
