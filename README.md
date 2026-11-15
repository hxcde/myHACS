# Bastion

Home-Assistant-Integration für Sicherheit und Konfigurationsschutz:

- **Sicherheitsaudit:** prüft Konten, MFA, Tokens, HTTP-Konfiguration, Webhooks, Sprachassistenten-Freigaben, Updates und GitHub-Advisories, Custom-Integrationen, Klartext-Secrets und Backups.
- **Login-Monitor:** protokolliert Anmeldungen, Fehlversuche, neue IPs, neue Tokens und Benutzer dauerhaft.
- **Git-Versionierung:** sichert die komplette Smart-Home-Konfiguration in ein **privates** Repository. Secrets landen dort verschlüsselt. Jeder Stand lässt sich vergleichen und wiederherstellen.
- **Anomalie-Erkennung:** lernt Sensoren (Strom, Wasser, …), Login-Zeiten und sensible Aktionen. Erkennt Sabotage und neue Verbindungsziele.
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
