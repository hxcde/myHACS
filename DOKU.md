# DOKU — Bastion

Admin- und Wartungsdoku.

## Voraussetzungen

- Home Assistant ≥ 2026.10 (Container, HA OS oder Supervised). Add-on-Prüfungen und Add-on-Sicherung gibt es nur mit Supervisor.
- Für Git: ein **privates** GitHub-Repository mit Deploy-Key mit Schreibrecht (empfohlen) oder ein Fine-grained Token, das nur für dieses Repo Contents lesen/schreiben darf. Andere Git-Server per SSH oder HTTPS funktionieren ebenfalls.
- Optional: Cloudflare-Account für den Probe-Worker.
- Python-Abhängigkeiten installiert HA automatisch: `dulwich`, `paramiko`.

## Konfiguration

Alles läuft über **Einstellungen → Geräte & Dienste → Bastion → Konfigurieren**. YAML gibt es nicht.

| Menü | Wichtige Optionen |
|---|---|
| Sicherheitsaudit | Intervall, Repairs-Schwelle, max. Admins, Token-Alter/-Nutzung, abschaltbare Prüfgruppen, optionaler GitHub-Token (nur lesen, für mehr API-Anfragen) |
| Benachrichtigungen | Ziele (`notify.<entity>` oder `notify.<dienst>`), Schwelle, Login-Benachrichtigung, nur öffentliche IPs, Brute-Force-Schwelle, GeoIP (opt-in, sendet IP an ipwho.is) |
| Git-Versionierung | URL, Branch, Anmeldung, Passphrase, Bereiche, ESPHome-/Z2M-Pfad, Zusatzpfade, Debounce, tägliche Uhrzeit |
| Externe Prüfung | Worker-URL (HTTPS), Token, Intervall |
| Anomalie-Erkennung | Sensoren, Empfindlichkeit, Login-Zeiten, Aktionen, Sabotage (Anzahl/Zeitfenster), Outbound |

Geheime Felder (Tokens, Passphrase) werden im Formular nie angezeigt. Bleibt ein Feld leer, gilt der gespeicherte Wert weiter. Gespeichert werden sie in den Config-Entry-Optionen (`.storage/core.config_entries`), wie bei allen HA-Integrationen.

### Container-Installation: Pfade für ESPHome und Zigbee2MQTT

ESPHome und Zigbee2MQTT laufen bei Container-Installationen meist als eigene Container. Bastion sieht deren Dateien nur, wenn die Datenverzeichnisse in den HA-Container gemountet sind, zum Beispiel:

```yaml
# docker-compose (Ausschnitt, Container homeassistant)
volumes:
  - ./homeassistant:/config
  - ./zigbee2mqtt/data:/z2m:ro
  - ./esphome/config:/esphome:ro
```

Dann in den Git-Optionen `/z2m` und `/esphome` eintragen. Zum Wiederherstellen müssen die Mounts beschreibbar sein (ohne `:ro`).

## Git-Versionierung einrichten

1. Ein privates Repo anlegen, leer oder mit README.
2. Bastion → Konfigurieren → **Git-Versionierung**:
   - URL: `git@github.com:<user>/<repo>.git` (SSH) oder `https://…` (Token)
   - Anmeldung: **SSH-Deploy-Key** (empfohlen)
   - **Passphrase** setzen (Pflicht, mindestens 12 Zeichen). Alle Secrets werden damit verschlüsselt gesichert.
3. Im nächsten Schritt den angezeigten **Public Key** im Repo als Deploy-Key **mit Schreibrecht** eintragen (GitHub: Settings → Deploy keys).
4. Verbindungstest: Fingerprint des Servers mit dem vom Anbieter veröffentlichten vergleichen. Für github.com prüft Bastion zusätzlich gegen die von GitHub veröffentlichten Fingerprints.
5. Speichern. Ist das Repo leer, macht Bastion sofort die erste Sicherung. Enthält das Repo schon einen Stand (zum Beispiel bei einer Neuinstallation), wartet Bastion auf die erste Änderung. So lässt sich vorher wiederherstellen.

**Passphrase im Passwortmanager ablegen.** Ohne sie lassen sich `*.bastion.enc` nicht entschlüsseln, auch nicht von dir.

### Was gesichert wird

| Bereich | Repo-Pfad | Inhalt |
|---|---|---|
| YAML | `homeassistant/` | Alle `*.yaml/json/jinja/py/…` unter `/config`, ohne `custom_components`, `www`, `.storage`, `deps`, `tts`, `ssl`, Datenbanken, Logs. `secrets.yaml` immer verschlüsselt |
| UI | `homeassistant/.storage/` | Dashboards, Helfer, Bereiche/Etagen/Labels, Registries, Personen, Zonen, Exposed Entities, Energy. Verschlüsselt: `core.config_entries`, `application_credentials`, `backup` |
| Inventar | `bastion/inventory/` | HA-Version, Custom-Integrationen mit Version, Dashboard-Ressourcen |
| ESPHome | `esphome/` | `*.yaml`, `secrets.yaml` verschlüsselt |
| Zigbee2MQTT | `zigbee2mqtt/` | `configuration.yaml`, `devices.yaml`, `groups.yaml`, `database.db`. Verschlüsselt: `secret.yaml`, `coordinator_backup.json` |
| Add-ons | `addons/` | Optionen pro Add-on (nur Supervisor, immer verschlüsselt). Bei Container-Installationen ausgeblendet |
| Extra | `extra/<label>/` | Frei konfigurierte Pfade |

Nie gesichert, auch nicht verschlüsselt: `.storage/auth*`, `onboarding`, `cloud`, `mobile_app`, `core.uuid`, `core.restore_state`.

Zusätzlich verschlüsselt Bastion jede Datei automatisch, in der der Secret-Scanner Zugangsdaten findet. Die Commit-Nachricht nennt diese Dateien.

### Wann committet wird

- **Automatisch:** Alle 60 s prüft Bastion, ob sich Dateien geändert haben. Nach der Debounce-Zeit (Standard 120 s) ohne weitere Änderung folgt ein Commit.
- **Täglich:** um die eingestellte Uhrzeit (Standard 03:17).
- **Manuell:** Button „Konfiguration jetzt sichern“, Panel oder Aktion `bastion.git_commit`.
- Ändert sich YAML ohne vorherige Aktion in der HA-UI, meldet Bastion das als „außerhalb der UI geändert“ (Event und Benachrichtigung) und vermerkt es im Commit.

### Wiederherstellen

**Panel → Git → Commit wählen.** Bastion zeigt pro Datei, ob sie seitdem geändert wurde, und auf Klick den Diff. Wiederherstellen lässt sich der komplette Stand, ausgewählte Bereiche oder eine einzelne Datei.

Ablauf:

1. Zuerst committet Bastion den aktuellen Stand (Sicherungs-Commit), falls er sich vom letzten Commit unterscheidet.
2. YAML-Dateien werden geschrieben. Die alten Fassungen landen in `/config/.bastion/restore-backup/<zeit>/`. Es bleiben die letzten 5 Sicherungen.
3. Danach läuft die HA-Konfigurationsprüfung. Bei Fehlern rollt Bastion automatisch zurück.
4. `.storage`-Dateien werden nur vorbereitet und **beim nächsten Neustart** eingespielt, nachdem HA seinen Zustand geschrieben hat. Für einen sofortigen Neustart „Danach neu starten“ wählen.
5. Beim Wiederherstellen von `core.config_entries` gelten danach auch die Einstellungen aller Integrationen von damals, Bastion eingeschlossen.
6. Bastion überspringt alles außerhalb der erlaubten Bereiche, zum Beispiel `.storage/auth`, `custom_components` oder Pfade mit `..`. Das schützt gegen ein manipuliertes Repo.

**Per Aktion:**

```yaml
action: bastion.git_restore
data:
  commit: <40-stellige SHA>
  paths: [homeassistant/automations.yaml]   # optional
  areas: [config, storage]                  # optional
  restart: false
```

**Neuinstallation / Umzug:** Frische HA aufsetzen, Bastion installieren und dasselbe Repo, denselben Key (oder einen neuen Deploy-Key) und **dieselbe Passphrase** eintragen. Dann im Panel den gewünschten Stand komplett wiederherstellen und neu starten. Custom-Integrationen stehen im Inventar und müssen über den Marketplace neu installiert werden.

ESPHome und Z2M: Zigbee2MQTT vor dem Wiederherstellen stoppen, sonst überschreibt es `database.db`.

## Reaktion, Köder, Wochenbericht

**Aktionen in Benachrichtigungen:** Benachrichtigungsziele vom Typ `notify.mobile_app_*` bekommen bei Anmeldungen, neuen IPs, neuen Tokens und Benutzern die Buttons „War ich“ und „Sperren“. „Sperren“ hat folgende Wirkung:

- Der betroffene Token wird widerrufen.
- Die IP landet auf der HA-Bannliste (`ip_bans.yaml`). Loopback und Reverse-Proxy-IPs werden nie gesperrt.
- Neu angelegte oder hochgestufte Benutzer werden deaktiviert. Besitzer und du selbst sind geschützt.

Jeder Button gilt 48 Stunden, nur einmal und nur für Admins. Dieselbe Funktion gibt es im Panel und als Aktion `bastion.block`.

**Köder** (Konfigurieren → Köder): Bastion legt den Benutzer `api-backup` an (nur lesen, nur lokal) und dazu einen Long-Lived-Token und einen Webhook. Der Token-Wächter weist jede Benutzung des Tokens ab (HTTP 401), jeder Aufruf des Webhooks löst ebenfalls aus. Folgen eines Auslösers:

- Bastion meldet sofort kritisch mit Absender-IP, Event `bastion_security_event` vom Typ `canary`.
- `binary_sensor.bastion_decoy_triggered` geht für 24 Stunden an.

Token und URL stehen im Panel unter „Anomalien & Köder“. Leg sie dort ab, wo ein Eindringling suchen würde (Notizen, NAS-Freigabe, alte Backups). Ist „Köder ins Git-Repo“ aktiv, liegt zusätzlich `homeassistant/.env` mit diesen Daten unverschlüsselt im Repo. Ein Leck des Repos fällt damit beim ersten Benutzungsversuch auf. Diese Datei wird beim Wiederherstellen nie nach `/config` geschrieben.

**Token-Nutzung:** HA selbst protokolliert nicht, wann ein Long-Lived-Token per API benutzt wird. Bastion erfasst das ab der Installation selbst, mit Zeit und IP. Darauf beruhen der Befund „ungenutzter Token“ (erst nach genügend Beobachtungszeit) und der Alarm „Token von neuer IP“.

**Wochenbericht** (Konfigurieren → Wochenbericht): standardmäßig montags 08:13 an alle Benachrichtigungsziele, manuell per Button oder Aktion `bastion.send_report`.

**Firmware:** Die Firmware-Versionen von ESPHome-, Tasmota- und WLED-Geräten sowie der Zigbee2MQTT-Bridge aus der Geräteübersicht werden gegen die GitHub-Advisories dieser Projekte geprüft.

## Externe Prüfung (Cloudflare Worker)

```bash
cd extras/cloudflare-worker
npx wrangler deploy
npx wrangler secret put PROBE_TOKEN   # zufälligen Wert setzen
```

Danach die Worker-URL (`https://bastion-probe.<account>.workers.dev`) und den Token in Bastion → Externe Prüfung eintragen.

Der Worker baut eine TCP-Verbindung zur IP des Aufrufers auf (`CF-Connecting-IP`), also zur eigenen öffentlichen IP. Fremde Adressen prüft er nie. Geprüfte Ports sind 21, 22, 23, 80, 139, 443, 445, 1880, 1883, 2375/2376, 3000, 3389, 5000/5001, 5900, 6052, 8080, 8086, 8123, 8883, 9000 und 9443. Verlässt HA das Netz über IPv6, prüft der Worker diese IPv6-Adresse, oft direkt den Host ohne NAT.

## Betrieb & Wartung

- **Entities** (IDs je nach Systemsprache, hier Englisch): `sensor.bastion_security_score`, `sensor.bastion_open_findings`, `sensor.bastion_failed_logins_24_h`, `sensor.bastion_git_status`, `sensor.bastion_last_commit`, `binary_sensor.bastion_critical_findings`, `binary_sensor.bastion_sabotage_suspicion`, pro Anomalie-Sensor ein `binary_sensor`, Buttons für Audit, Sicherung und Probe.
- **Events für Automationen:** `bastion_finding`, `bastion_security_event` (Typen: `login`, `new_ip`, `failed_login`, `brute_force`, `ip_banned`, `token_created`, `user_added`, `admin_granted`, `sabotage`, `tamper`, `unusual_action`, `unusual_login_time`, `external_config_change`, `new_destination`), `bastion_anomaly`.
- **Befunde ausblenden:** im Panel oder per Aktion `bastion.dismiss_finding`. Ausgeblendete Befunde zählen nicht in den Score.
- **Custom-Integration aktualisiert:** Ändert sich die Version, übernimmt Bastion die neue Baseline automatisch. Ändert sich Code ohne Versionswechsel, entsteht ein Befund „Code geändert ohne Update“. Ist die Änderung gewollt, „Baseline übernehmen“ (Aktion `bastion.accept_integrity`).
- **Hostkey-Wechsel des Git-Servers:** Der Sync stoppt mit einem kritischen Befund. Den neuen Fingerprint beim Anbieter prüfen, dann Aktion `bastion.reset_git_host_key` ausführen.
- **Deploy-Key rotieren:** In den Git-Optionen „Neuen SSH-Schlüssel erzeugen“ wählen, den neuen Key eintragen und den alten im Repo löschen.
- **Passphrase ändern:** Die Passphrase lässt sich neu setzen, Bastion erzeugt dann einen neuen Salt. Ältere Commits brauchen weiter die **alte** Passphrase. Die alte daher aufbewahren.
- **Lokaler Cache:** `/config/.bastion/` (Git-Objekte, vorbereitete Restores, Restore-Backups). Bastion baut ihn neu auf, wenn er gelöscht wird.

## Troubleshooting

| Problem | Diagnose | Lösung |
|---|---|---|
| Git-Status `blocked` | Panel → Git, Befund „Repo ist öffentlich“ oder „Hostkey geändert“ | Repo auf privat stellen bzw. Fingerprint prüfen und Hostkey zurücksetzen |
| Git-Status `pending`, Befund „privat nicht überprüfbar“ | Self-hosted ohne anonym erreichbares HTTPS | In den Git-Optionen bestätigen, dass das Repo privat ist |
| `auth_failed` | Deploy-Key ohne Schreibrecht oder Token abgelaufen | Key mit „Allow write access“ eintragen, Token erneuern |
| Befund „Dateien mit Secrets nicht gesichert“ | Passphrase fehlt (z. B. alte Konfiguration) | Passphrase in den Git-Optionen setzen |
| Restore meldet „decrypt“ | Falsche oder geänderte Passphrase | Passphrase der Zeit des Commits verwenden |
| Restore: UI-Konfiguration unverändert | `.storage` wird erst beim Neustart eingespielt | HA neu starten. Der Befund „Wiederherstellung wartet auf Neustart“ zeigt den offenen Stand |
| Viele Befunde „Klartext-Zugangsdaten“ | Werte stehen direkt in YAML | Nach `secrets.yaml` verschieben und mit `!secret` referenzieren |
| Advisories fehlen | GitHub-API-Limit (60/h ohne Token) | Lese-Token in den Audit-Optionen hinterlegen |
| Probe `401` | Token falsch | `PROBE_TOKEN` im Worker und in Bastion abgleichen |
| Fehlversuche werden nicht gezählt | Logger `homeassistant.components.http.ban` steht in der Logger-Konfiguration auf `error` | Bastion setzt ihn auf `warning`. Diese Einstellung in `logger:` nicht wieder überschreiben |
