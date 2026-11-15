# CODEINFO — Bastion

Code-Struktur und Aufbau. Bei strukturellen Änderungen aktualisieren.

## Überblick

Custom-Integration für Home Assistant (Python 3.14, HA ≥ 2026.10), verteilt über den Marketplace (ehemals HACS). Es gibt keinen Build-Schritt. Das Panel ist eine Web-Komponente in reinem JavaScript. Git läuft über `dulwich` (pure Python), SSH über `paramiko`, damit das Ganze ohne `git`- oder `ssh`-Binary im Container funktioniert. Optional gibt es einen Cloudflare Worker für die externe Port-Prüfung.

## Verzeichnislayout

```
custom_components/bastion/
  __init__.py            Setup, Options-Merge (get_options), Plattformen
  coordinator.py         Klasse Bastion: hält alle Komponenten, Audit-Lauf, Repairs, Score
  config_flow.py         Einrichtung + Options-Menü (Audit, Benachrichtigungen, Git, Probe, Anomalien)
  const.py               Konstanten, Option-Keys, Defaults
  models.py              Finding-Datenklasse, stabile IDs
  texts.py               Alle dynamischen Texte (de/en) für Befunde, Events, Commits
  notifier.py            Persistente Benachrichtigung + Notify-Ziele, Rate-Limit
  login_monitor.py       Logins, Fehlversuche (Log-Handler), Tokens, Benutzer
  secret_scan.py         Mustererkennung für Zugangsdaten (ohne HA-Abhängigkeit)
  crypto.py              scrypt + AES-256-GCM für Secrets im Repo
  probe.py               Client der externen Prüfung + Port-Bewertung
  services.py            Service-Aktionen (nur Admins)
  websocket.py           Websocket-API für das Panel (require_admin)
  panel.py               Registrierung des Seitenleisten-Panels
  sensor.py / binary_sensor.py / button.py / entity.py   Entities
  diagnostics.py         Diagnose ohne Secrets
  audit/                 Prüfgruppen
    access.py            Benutzer, MFA, Admins, Tokens, trusted_networks
    exposure.py          HTTP, Webhooks, Sprachassistenten, Alarm-Codes, MQTT-TLS
    updates.py           HA-Version, GitHub-Advisories, Companion-Apps, ESPHome, Updates
    supply_chain.py      Integrität custom_components/www, Repo-Check, ungenutzte Integrationen, externe Ressourcen
    config.py            Klartext-Secrets, Shell-Templates, Debug-Konsole, Backups
    supervisor.py        Add-on-Rechte (nur mit Supervisor)
  gitsync/
    remote.py            URL-Parsing, SSH-Vendor mit Hostkey-Pinning, Schlüsselerzeugung
    collector.py         Dateiauswahl pro Bereich, Pfad-Schutz
    repo.py              Snapshot, Commit, Fetch/Push, Historie, Diff (synchron, Executor)
    manager.py           Orchestrierung in HA: Änderungserkennung, Auto-Commit, Restore
  anomaly/
    stats.py             Welford-Statistik, Sensor-Modell, Stunden-Histogramm (ohne HA-Abhängigkeit)
    engine.py            Sampling, Login-/Aktions-Anomalien, Sabotage, Outbound
  frontend/bastion-panel.js   Panel (Tabs: Übersicht, Anmeldungen, Git, Anomalien, Extern)
  brand/                 Icon und Logo (hell/dunkel), lädt HA ab 2026 direkt aus der Integration
  strings.json, translations/{en,de}.json, services.yaml, manifest.json
extras/cloudflare-worker/     Worker für die externe Port-Prüfung
extras/brand/                 Quelle des Logos: icon.svg, render.js (Playwright) und build.py (Zuschnitt und Größen)
tests/                        pytest (reine Logik, HA-Integration, SSH Ende-zu-Ende)
hacs.json                     Marketplace-Metadaten
```

## Module & Zuständigkeiten

- **Bastion (`coordinator.py`):** Eine Instanz pro Config-Entry (`entry.runtime_data`). Startet Login-Monitor, Anomalie-Engine und Git-Manager. Plant das Audit (Standard: alle 6 h, erster Lauf 2 min nach dem Start) und die Probe. Nach jedem Audit übersetzt sie die Befunde, legt Repairs an oder entfernt sie, benachrichtigt bei neuen Befunden und speichert den Zustand.
- **Audit (`audit/`):** Jede Gruppe ist eine `async_check(ctx) -> list[Finding]`. Fehler einer Gruppe werden geloggt, die anderen laufen weiter. Befunde haben stabile IDs (`models.finding_id`), damit Ausblenden und Benachrichtigungen über mehrere Läufe hinweg funktionieren.
- **Git-Sync (`gitsync/`):** Der lokale Bare-Cache liegt unter `/config/.bastion/repo.git`. Jeder Commit ist ein vollständiger Snapshot auf dem neuesten Remote-Head, ein Merge ist nie nötig. Dateien außerhalb der von Bastion verwalteten Präfixe bleiben im Repo erhalten.
- **Login-Monitor:** Fehlversuche kommen aus den Log-Records von `homeassistant.components.http.ban`. Erfolgreiche Logins erkennt er als neue Refresh-Tokens vom Typ `normal`. Abfrage alle 30 s.
- **Anomalie-Engine:** Nimmt alle 5 min einen Messwert pro Sensor. Pro Wochentag/Wochenende × Stunde gibt es 48 Buckets. Sie startet mit Werten aus den Recorder-Statistiken der letzten 30 Tage. Sicherheitsereignisse erkennt sie über Event-Listener mit Filter.

## Zusammenspiel / Datenfluss

```
Timer/Events ─► Bastion.async_run_audit ─► audit/* + git.findings() + probe_findings()
                     │
                     ├─► texts.finding_text (de/en) ─► Repairs (ab Schwelle) / Notifier (neue Befunde)
                     └─► Store bastion.data ─► Dispatcher ─► Entities / Panel (Websocket)

Dateiänderung (Scan 60 s) ─► Debounce ─► GitSyncManager.async_commit
   collector.collect ─► secret_scan ─► crypto (verschlüsseln) ─► repo.build_snapshot ─► commit ─► push
Restore: repo.decode_entry ─► Pfadprüfung ─► YAML schreiben (Backup + check_config, sonst Rollback)
         .storage ─► .bastion/staged + pending_restore.json ─► beim HA-Close einspielen
```

## Wichtige Einstiegspunkte

- `custom_components/bastion/__init__.py`: `async_setup` (Services, Websocket, Close-Hook), `async_setup_entry`
- `coordinator.py`: `Bastion.async_run_audit`, `register_close_listener`
- `gitsync/manager.py`: `async_commit`, `async_restore`, `apply_pending_restore`, `async_test_connection`
- `extras/cloudflare-worker/src/worker.js`: Endpoint `POST /probe`

## Persistenz (`/config/.storage`)

| Key | Inhalt |
|---|---|
| `bastion.data` | Befunde, ausgeblendete IDs, Integritäts-Baseline, Repo-Cache, Probe-Ergebnis |
| `bastion.logins` | Login-Protokoll (max. 1000), Token-/Benutzer-Snapshot, bekannte IPs |
| `bastion.git` | Git-Status, Hostkey (TOFU), Privatheits-Status |
| `bastion.anomaly` | Sensor-Modelle, Histogramme, Outbound-Baseline, Ereignisse |
