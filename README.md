<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="custom_components/bastion/brand/dark_logo@2x.png">
    <img src="custom_components/bastion/brand/logo@2x.png" alt="Bastion" height="96">
  </picture>
</p>

# Bastion

Home-Assistant-Integration für Sicherheit, Alarmanlage und Konfigurationsschutz:

- **Alarmanlage:** Alarm-Entität mit den Modi Aus, Zuhause, Nacht und Abwesend, Räumen und Sensor-Zuordnung pro Modus. Dazu Aktivierungs- und Auslöseverzögerung pro Sensor, gehashte Codes, Sirenen, Lichter, Töne auf Lautsprechern (mitgeliefert oder eigene MP3) und Benachrichtigungen.
- **Cloud-Worker (Cloudflare):** Totmannschalter mit letztem bekannten Stand, Alarm-Pushs über Pushover (mit Quittierung und Entwarnung), Telegram oder ntfy, Protokoll und Kamerabilder außer Haus. Dazu ein Dashboard hinter Cloudflare Access mit Verfügbarkeitsverlauf, Zugriffsprotokoll und Fernsteuerung per Passkey (scharf/unscharf, Erinnerung „niemand zuhause“).
- **Sicherheitsaudit:** prüft Konten, MFA, Tokens, HTTP-Konfiguration, Webhooks, Sprachassistenten-Freigaben, Updates und GitHub-Advisories, Custom-Integrationen, Klartext-Secrets und Backups.
- **Login-Monitor:** protokolliert Anmeldungen, Fehlversuche, neue IPs, neue Tokens und Benutzer dauerhaft.
- **Git-Versionierung:** sichert die komplette Smart-Home-Konfiguration in ein **privates** Repository. Secrets landen dort verschlüsselt. Jeder Stand lässt sich vergleichen und wiederherstellen.
- **Anomalie-Erkennung:** lernt Sensoren (Strom, Wasser, …), Login-Zeiten und sensible Aktionen. Erkennt Sabotage und neue Verbindungsziele.
- **Reaktion per Knopfdruck:** Benachrichtigungen in der Companion App mit „War ich“ / „Sperren“ (Token widerrufen, IP sperren, Benutzer deaktivieren).
- **Köder:** Köder-Token und Köder-Webhook in HA und im Worker, optional als `.env` im Git-Repo. Jede Benutzung wird abgewiesen und meldet Alarm, die Worker-Köder auch bei ausgefallenem HA.
- **Wochenbericht:** Score-Verlauf, neue und behobene Befunde, Anmeldungen, Köder, Git, offene Ports.
- **Firmware-Schwachstellen:** ESPHome-, Tasmota-, WLED- und Zigbee2MQTT-Versionen gegen GitHub-Advisories.
- **Externe Prüfung:** ein Cloudflare Worker prüft, welche Ports der eigenen öffentlichen IP offen sind.

## Setup

1. In Home Assistant **Einstellungen → Marketplace → ⋮ → Custom-Repository** öffnen und `https://github.com/hxcde/myHACS` als Typ *Integration* hinzufügen.
2. Bastion installieren und Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → Bastion** wählen.
4. Unter **Bastion → Konfigurieren** Git, Benachrichtigungen, Anomalien und die externe Prüfung einrichten.
5. Das Panel **Bastion** erscheint in der Seitenleiste (nur für Admins).

Mindestversion: Home Assistant 2026.10.

## Dokumentation

- [CODEINFO.md](./CODEINFO.md): Code-Struktur und Aufbau
- [DOKU.md](./DOKU.md): Admin- und Wartungsdoku (Einrichtung, Git, Restore, Worker, Troubleshooting)

## Entwicklung

```bash
pip install -r requirements_test.txt
pytest
ruff check . && ruff format --check .
```

## Lizenz

MIT, siehe [LICENSE](./LICENSE).
