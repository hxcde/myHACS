"""External reachability check through a small Cloudflare Worker.

The worker connects back to the public IP the request came from, so it can
only ever test the caller itself and cannot be abused as a port scanner.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import Category, Severity
from .models import Finding, make_finding
from .texts import lang

_LOGGER = logging.getLogger(__name__)

# port: (service, severity, advice de, advice en)
PORTS: dict[int, tuple[str, Severity, str, str]] = {
    21: ("FTP", Severity.HIGH, "FTP nicht ins Internet freigeben.", "Do not expose FTP to the internet."),
    22: (
        "SSH",
        Severity.MEDIUM,
        "Nur mit Schlüssel-Login und Fail2ban oder besser über VPN.",
        "Key based login only plus fail2ban, better via VPN.",
    ),
    23: ("Telnet", Severity.CRITICAL, "Telnet sofort schließen.", "Close telnet immediately."),
    139: ("NetBIOS", Severity.CRITICAL, "Windows-Freigaben nie freigeben.", "Never expose Windows shares."),
    445: ("SMB", Severity.CRITICAL, "Windows-Freigaben nie freigeben.", "Never expose Windows shares."),
    1880: (
        "Node-RED",
        Severity.CRITICAL,
        "Node-RED erlaubt Codeausführung, Portfreigabe entfernen.",
        "Node-RED allows code execution, remove the port forward.",
    ),
    1883: ("MQTT", Severity.CRITICAL, "Unverschlüsseltes MQTT nie freigeben.", "Never expose unencrypted MQTT."),
    2375: (
        "Docker API",
        Severity.CRITICAL,
        "Docker-API ohne TLS bedeutet Root-Zugriff, sofort schließen.",
        "Docker API without TLS means root access, close it now.",
    ),
    2376: (
        "Docker API (TLS)",
        Severity.HIGH,
        "Docker-API nicht ins Internet freigeben.",
        "Do not expose the Docker API.",
    ),
    3000: (
        "Grafana",
        Severity.HIGH,
        "Über VPN oder Reverse-Proxy mit Login erreichbar machen.",
        "Use VPN or an authenticated reverse proxy.",
    ),
    3389: ("RDP", Severity.HIGH, "RDP nur über VPN.", "RDP only through VPN."),
    5000: (
        "Synology DSM",
        Severity.HIGH,
        "DSM nicht direkt freigeben, QuickConnect/VPN nutzen.",
        "Do not expose DSM directly, use VPN.",
    ),
    5001: (
        "Synology DSM (HTTPS)",
        Severity.HIGH,
        "DSM nicht direkt freigeben, QuickConnect/VPN nutzen.",
        "Do not expose DSM directly, use VPN.",
    ),
    5900: ("VNC", Severity.HIGH, "VNC nur über VPN.", "VNC only through VPN."),
    6052: (
        "ESPHome Dashboard",
        Severity.CRITICAL,
        "Das ESPHome-Dashboard erlaubt Firmware-Uploads, Portfreigabe entfernen.",
        "The ESPHome dashboard allows firmware uploads, remove the port forward.",
    ),
    8080: (
        "Web (Zigbee2MQTT u. a.)",
        Severity.HIGH,
        "Weboberflächen nur über VPN oder Reverse-Proxy mit Login.",
        "Web UIs only via VPN or authenticated reverse proxy.",
    ),
    8086: ("InfluxDB", Severity.HIGH, "Datenbanken nie direkt freigeben.", "Never expose databases directly."),
    8123: (
        "Home Assistant",
        Severity.HIGH,
        "Portweiterleitung entfernen und Cloudflare Tunnel, VPN oder Nabu Casa nutzen.",
        "Remove the port forward and use Cloudflare Tunnel, VPN or Nabu Casa.",
    ),
    8883: (
        "MQTT (TLS)",
        Severity.MEDIUM,
        "Nur mit Client-Zertifikaten oder starken Passwörtern betreiben.",
        "Only with client certificates or strong passwords.",
    ),
    9000: (
        "Portainer",
        Severity.CRITICAL,
        "Portainer bedeutet Root-Zugriff auf den Host, nie freigeben.",
        "Portainer means root on the host, never expose it.",
    ),
    9443: ("Portainer (HTTPS)", Severity.HIGH, "Portainer nicht ins Internet freigeben.", "Do not expose Portainer."),
    80: ("HTTP", Severity.INFO, "", ""),
    443: ("HTTPS", Severity.INFO, "", ""),
}


async def async_run_probe(hass: HomeAssistant, url: str, token: str) -> dict[str, Any]:
    """Ask the worker to probe our public IP."""
    session = async_get_clientsession(hass)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with session.post(
        url.rstrip("/") + "/probe",
        json={"ports": sorted(PORTS)},
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=45),
    ) as resp:
        if resp.status != 200:
            raise aiohttp.ClientResponseError(
                resp.request_info, resp.history, status=resp.status, message=await resp.text()
            )
        data = await resp.json(content_type=None)
    data["time"] = dt_util.utcnow().isoformat()
    return data


def probe_findings(result: dict[str, Any] | None, language: str) -> list[Finding]:
    """Findings for open ports."""
    if not result:
        return []
    if "error" in result:
        return [make_finding("probe_failed", Severity.LOW, Category.EXPOSURE, "probe", error=result["error"])]
    out: list[Finding] = []
    ip = result.get("ip", "?")
    index = 2 if lang(language) == "de" else 3
    for item in result.get("results", []):
        if not item.get("open"):
            continue
        port = int(item.get("port", 0))
        service, severity, *_ = PORTS.get(port, (f"Port {port}", Severity.MEDIUM, "", ""))
        if severity == Severity.INFO:
            continue
        advice = PORTS[port][index] if port in PORTS else ""
        out.append(
            make_finding(
                "port_open",
                severity,
                Category.EXPOSURE,
                port,
                port=port,
                service=service,
                ip=ip,
                advice=advice,
            )
        )
    return out
