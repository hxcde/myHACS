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
  guard.py               Token-Wächter: umhüllt hass.auth.async_validate_access_token (LLAT-Nutzung + IP, Köder-Abweisung)
  canary.py              Köder: Benutzer „api-backup“ (nur lesen, nur lokal), Token, Webhook, .env fürs Git-Repo; Worker-Köder (Token + Webhook, aus ALARM_SECRET abgeleitet)
  responder.py           Aktions-Buttons in Benachrichtigungen (Nonce, 48 h), Sperren: Token/IP/Benutzer
  report.py              Wochenbericht aus Score-Verlauf, Befunden, Login-Log, Köder, Git, Probe
  services.py            Service-Aktionen (nur Admins)
  websocket.py           Websocket-API für das Panel (require_admin)
  panel.py               Registrierung des Seitenleisten-Panels
  sensor.py / binary_sensor.py / button.py / entity.py   Entities
  device_tracker.py      Ein ScannerEntity pro Person des Haushalts (folgt Änderungen der Liste)
  diagnostics.py         Diagnose ohne Secrets
  audit/                 Prüfgruppen
    access.py            Benutzer, MFA, Admins, Tokens, trusted_networks
    exposure.py          HTTP, Webhooks, Sprachassistenten, Alarm-Codes, MQTT-TLS
    updates.py           HA-Version, GitHub-Advisories, Companion-Apps, ESPHome, Updates
    firmware.py          Geräte-Firmware (Device-Registry sw_version) gegen Advisories von ESPHome/Tasmota/WLED/Z2M
    supply_chain.py      Integrität custom_components/www, Repo-Check, ungenutzte Integrationen, externe Ressourcen
    config.py            Klartext-Secrets, Shell-Templates, Debug-Konsole, Backups
    supervisor.py        Add-on-Rechte (nur mit Supervisor)
  alarm/
    engine.py            Zustandsmaschine (disarmed/arming/armed_*/pending/triggered), Räume, Sensoren, Codes (scrypt), Aktionen
    relay.py             Worker-Anbindung (HMAC-SHA256): Lebenszeichen mit Kontext, Ereignisse, Kamerabilder, Quittierungen,
                         Meldungen des Workers (notices), Fernbefehle abholen/prüfen/ausführen, Passkey-Verwaltung (/remote)
    presence.py          Erinnerung „niemand zuhause, nicht scharf“ (Haushalt oder person.*, einmal pro Abwesenheit)
    household.py         Personen im Haushalt: verknüpfter Tracker oder Handy-IP alle 30 s (TCP, ICMP, ARP mit Neuprüfung)
    floorplan.py         Grundriss-JSON prüfen (clean_floorplan, nur bekannte Felder, ≤ 64 KB) und Prüfsumme (plan_hash)
    sounds.py            Töne auf Medienplayern: Schleifen (Alarm/Countdown), Einmal-Töne, Lautstärke sichern/wiederherstellen
  alarm_control_panel.py Alarm-Entität (Aus/Zuhause/Nacht/Abwesend/Panik)
  gitsync/
    remote.py            URL-Parsing, SSH-Vendor mit Hostkey-Pinning, Schlüsselerzeugung
    collector.py         Dateiauswahl pro Bereich, Pfad-Schutz
    repo.py              Snapshot, Commit, Fetch/Push, Historie, Diff (synchron, Executor)
    manager.py           Orchestrierung in HA: Änderungserkennung, Auto-Commit, Restore
  anomaly/
    stats.py             Welford-Statistik, Sensor-Modell, Stunden-Histogramm (ohne HA-Abhängigkeit)
    engine.py            Sampling, Login-/Aktions-Anomalien, Sabotage, Outbound
  frontend/bastion-panel.js   Panel (Tabs: Alarmanlage, Übersicht, Anmeldungen, Git, Anomalien, Extern)
  frontend/sounds/*.mp3  Mitgelieferte Alarmtöne (aus extras/sounds/build.py), ausgeliefert unter /bastion_static/sounds/
  brand/                 Icon und Logo (hell/dunkel), lädt HA ab 2026 direkt aus der Integration
  strings.json, translations/{en,de}.json, services.yaml, manifest.json
extras/cloudflare-worker/     Worker: Port-Prüfung, Totmannschalter, Protokoll in D1, Pushover, Vorfallseite, Dashboard
  src/worker.js        Routen, Signaturprüfung, Lebenszeichen, Alarm-Ereignisse, Funkstille-Analyse, Cron
  src/store.js         D1: events, snapshots, receipts, state, secevents, attempts, blocked, outages, sessions, canary_hits,
                       notices, passkeys, challenges, commands (Schema legt der Worker selbst an), Aufbewahrung
  src/util.js          Gemeinsame Helfer: JSON-Antwort, HMAC, Zeitvergleich, IP/Geo, Schreibbudget, Gerätename aus User-Agent
  src/webauthn.js      Passkeys ohne Abhängigkeiten: CBOR, COSE-Schlüssel (ES256, RS256, EdDSA), Registrierung, Assertion
  src/remote.js        Fernsteuerung: Kopplungscode, Passkey anlegen, Befehle (Challenge, Prüfung), /commands und /remote für HA
  src/canary.js        Worker-Köder erkennen (Bearer-Token, Webhook-Pfad), wie HA antworten, protokollieren, melden
  src/sessions.js      Zugriffsprotokoll des Dashboards (Sitzungen pro Gerät/IP, Meldung bei neuem Gerät/Land)
  src/uptime.js        Ausfälle aus Lücken im Lebenszeichen (Art, Ursache), Übernahme alter Ausfälle aus dem Protokoll
  src/notify.js        Kanäle Pushover/Telegram/ntfy/Webhook, Pushover-Receipts (Quittierung, Abbruch)
  src/access.js        Prüfung des Cloudflare-Access-JWT (RS256, Audience, Aussteller, Ablauf, Alter), ALLOWED_EMAILS
  src/login.js         Passkey-Login nach Access (LOGIN=passkey): Sitzungen, Leerlauf/Höchstdauer, Sperre, Wandtablet-Code, Push
  src/chain.js         HMAC-Kette über das Ereignisprotokoll: versiegeln, scheibenweise prüfen, Echo von HA, Aufbewahrung
  src/app.html         Dashboard und Vorfallseite (ein Text-Modul, CSP mit Nonce): Alarmanlage mit Tagesverlauf,
                       Hausansicht (3D-Grundriss, Sensor-Gesundheit), Wandtablet (#tablet), Verfügbarkeit, Sicherheit
  src/login.html       Login-Seite (Passkey, Koppeln mit HA-Code, Wandtablet-Code)
  src/pwa.js           Web-App-Manifest, Service Worker (nur Offline-Hinweis, kein Cache), Icons (base64)
  test/                node:test mit D1-Nachbildung über node:sqlite
extras/sounds/build.py        Erzeugt die Alarmtöne synthetisch (ffmpeg)
extras/pwa/icons.cjs          Rendert die App-Icons (Playwright); danach mit PIL auf 128 Farben verkleinert und in src/pwa.js eingebettet
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
- `extras/cloudflare-worker/src/worker.js`: `POST /probe`, `/heartbeat`, `/alert`, `/snapshot`, `/backfill`, `/commands`, `/remote`, `/pushover/<token>`, `POST /api/passkey/*`, `/api/command/*`, `GET /i/<vorfall>`, `/`, `/api/*`, Köder vor allen Routen, `scheduled()` (Ausfall-Historie, Funkstille, Receipts, Aufbewahrung, Außenprüfung)

## Alarmanlage

```
arm(mode) ─► offene Sensoren prüfen (Ausnahme: Sensoren mit eigener Aktivierungsverzögerung, „darf offen sein“)
          ─► arming (Ausgangsverzögerung des Modus) ─► armed_<mode>
Sensor aktiv ─► „immer“: sofort bzw. nach eigener Bestätigungszeit Alarm (auch unscharf)
             ─► nicht im Modus / noch nicht aktiv (eigene Aktivierungsverzögerung) / überbrückt: ignoriert
             ─► sofort: triggered │ verzögert: pending (Auslöseverzögerung Sensor oder Modus) ─► triggered
triggered ─► Sirenen/Lichter an, Benachrichtigung, Worker-Alarm ─► nach Sirenendauer wieder scharf oder aus
```

Vorwarnung und Alarm erzeugen eine Vorfall-ID (`engine.incident`), die bis zum Unscharf- oder erneuten Scharfschalten an allen Protokolleinträgen hängt.

```
engine._record ─► EVENT bastion_alarm, Coordinator (Benachrichtigung, Tag + Vorfall-Link) ─► relay.async_send_event ─► POST /alert
               └► sounds.on_event(kind, state) ─► Schleife (arming/pending/triggered) oder Einmal-Ton (armed/disarmed)
pending/triggered ─► relay.start_snapshots ─► camera.async_get_image ─► POST /snapshot
relay (alle 15 s Tick, Intervall bzw. während Alarm) ─► POST /heartbeat {Zustand, offen, nicht erreichbar, Start/Boot, acks_seen,
                                                      security (bei Änderung), security_events (aus bastion_security_event, dedupliziert)}
                                                    ◄─ {acks, attack} ─► engine.record_ack / logins.record("worker_attack")
                                                    ◄─ {notices: Köder, Dashboard-Zugriff, Passkey} ─► canary.async_trigger / logins.record
                                                       (bestätigt mit notices_seen im nächsten Lebenszeichen)
HA-Stopp ─► relay.async_stop ─► Lebenszeichen mit stopping=true (Worker wartet länger, meldet „geplant“)

Fernsteuerung:
Dashboard (Access) ─► /api/command/begin ─► Challenge (D1, einmalig) ─► navigator.credentials.get (Passkey, UV)
                   ─► /api/command/finish ─► webauthn.verifyAssertion ─► commands (pending, 90 s), remote_hot
HA relay (Tick 15 s, bei fast=true alle 2 s) ─► POST /commands {done} ◄─ {commands mit HMAC, fast}
   ─► Signatur, Alter, Freigabe prüfen ─► engine.async_arm/async_disarm(trusted=True) ─► Ergebnis mit nächstem Poll
Kopplung: HA ws bastion/alarm/remote pair ─► POST /remote {code_hash} ─► Dashboard /api/passkey/begin {code} ─► finish

Grundriss: Panel ─► ws bastion/alarm/save {floorplan} ─► clean_floorplan ─► config (ersetzt, nicht gemischt)
   relay ─► Lebenszeichen {floorplan_hash, floorplan nur wenn Worker die Prüfsumme nicht bestätigt hat}
         ◄─ {floorplan_hash} ─► nächste Lebenszeichen nur mit Prüfsumme; Zonen mit battery/seen (engine._health)
Dashboard-Login (LOGIN=passkey): Access-JWT ─► login.currentLogin (Cookie-Hash in logins, Identität, Gerät, Leerlauf)
   ohne Sitzung: GET / = login.html, /api/* = 401 ─► /api/login/begin|finish (Passkey) ─► Set-Cookie
Prüfkette: Lebenszeichen/Cron ─► chain.seal (HMAC über Vorgänger + Eintrag) ─► Antwort {chain} ─► relay ─► chain_seen
   Cron ─► chain.verifySlice (500 Einträge pro Minute, endlos) ─► state chain_check ─► Dashboard/Push bei Bruch

Lebenszeichen ─► uptime.onHeartbeat (Lücke/Neustart ─► outages) │ Cron Funkstille ─► uptime.onOffline (offener Ausfall)
Jeder Request ─► canary.detectCanary (Token/Webhook) ─► 401/200 wie HA, canary_hits, notice, Meldung

Start + 30 s ─► relay.async_backfill ─► POST /backfill {alarm_events, security_events} (uid-dedupliziert)
Worker-Cron (jede Minute): Funkstille-Analyse (letzter Stand + Ereignisse aus D1), offene Pushover-Receipts prüfen, Aufbewahrung,
                           Außenprüfung der check_urls (alle 6 h) ─► Lebenszeichen-Antwort {exposure} ─► probe.exposure_findings
```

Sensoren mit eigener Aktivierungsverzögerung werden per Timer freigegeben. Ist ein solcher Sensor danach noch offen, startet die Vorwarnung. Zustand, Scharfschaltzeitpunkt und laufende Verzögerungen werden gespeichert und nach einem Neustart fortgesetzt. Ein Neustart während der Vorwarnung führt zum Alarm.

## Persistenz (`/config/.storage`)

| Key | Inhalt |
|---|---|
| `bastion.data` | Befunde, ausgeblendete IDs, Integritäts-Baseline, Repo-Cache, Probe-Ergebnis |
| `bastion.logins` | Login-Protokoll (max. 1000), Token-/Benutzer-Snapshot, bekannte IPs |
| `bastion.git` | Git-Status, Hostkey (TOFU), Privatheits-Status |
| `bastion.anomaly` | Sensor-Modelle, Histogramme, Outbound-Baseline, Ereignisse |
| `bastion.alarm` | Alarm-Konfiguration (Räume, Sensoren, Zeiten, Aktionen, Code-Hashes, Worker, Fernsteuerung/Erinnerung), Zustand, Protokoll |
