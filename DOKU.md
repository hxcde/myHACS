# DOKU — Bastion

Admin- und Wartungsdoku.

## Voraussetzungen

- Home Assistant ≥ 2026.10 (Container, HA OS oder Supervised). Add-on-Prüfungen und Add-on-Sicherung gibt es nur mit Supervisor.
- Für Git: ein **privates** GitHub-Repository mit Deploy-Key mit Schreibrecht (empfohlen) oder ein Fine-grained Token, das nur für dieses Repo Contents lesen/schreiben darf. Andere Git-Server per SSH oder HTTPS funktionieren ebenfalls.
- Optional: Cloudflare-Account für den Worker (Workers, D1, für das Dashboard Zero Trust Access).
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

## Alarmanlage

Die Alarmanlage liegt im Panel als erster Tab, die Entität heißt `alarm_control_panel.bastion_alarmanlage` (Name je nach Systemsprache). Die Entität funktioniert mit allen HA-Alarmkarten und Automationen.

**Einrichten (Alarmanlage → Einstellungen):**
1. **Räume & Sensoren:** Räume anlegen oder „Räume aus HA-Bereichen übernehmen“. Das Icon wählt man per Klick auf das Raum-Symbol (Suche auf Deutsch und Englisch, jedes andere MDI-Icon per Name). Dabei werden Tür-, Fenster-, Bewegungs-, Rauch-, Wasser- und Manipulationssensoren den Bereichen zugeordnet und sinnvoll vorbelegt. Pro Sensor gibt es folgende Einstellungen:
   - **Modi:** In welchen Modi (Zuhause, Nacht, Abwesend) der Sensor überwacht wird.
   - **Typ:**
     - *Sofort:* löst sofort aus.
     - *Verzögert:* startet die Vorwarnung.
     - *Immer:* löst auch unscharf aus, für Rauch, Wasser und Manipulation.
   - **Aktiv nach:** Aktivierungsverzögerung in Sekunden. Der Sensor wird erst so lange nach dem Scharfschalten überwacht, typisch für die Haustür als Ausgangsweg. So ein Sensor darf beim Scharfschalten offen sein. Ist er nach Ablauf noch offen, startet die Vorwarnung.
   - **Alarm nach:** Auslöseverzögerung in Sekunden vom Auslösen bis zum Alarm. Bei „Immer“ dient sie als Bestätigungszeit gegen Fehlalarme.
   - Leere Felder übernehmen den Wert des Modus.
   - **Darf offen sein:** Der Sensor blockiert das Scharfschalten nicht, er wird überbrückt, bis er schließt (z. B. ein gekipptes Fenster).
2. **Modi & Zeiten:** Ausgangs- und Eingangsverzögerung pro Modus, Sirenendauer, ob die Anlage nach einem Alarm wieder scharf wird, Code-Pflicht beim Scharfschalten, und ob Sabotage, Manipulation und Köder bei scharfer Anlage auslösen.
3. **Aktionen:**
   - Sirenen und Lichter werden bei Alarm eingeschaltet.
   - Das Warnsignal läuft während der Verzögerungen.
   - Benachrichtigungen gehen an die Bastion-Benachrichtigungsziele und, falls aktiv, über den Worker. Ein Alarm kommt als kritische Push-Nachricht und durchbricht damit den Stumm-Modus. Vorwarnung und Alarm tragen in der Companion App denselben Tag und einen Link zum Vorfall. Nach dem Unscharfschalten verschwinden sie vom Handy.
4. **Töne:** Lautsprecher (Medienplayer) wählen, Lautstärke für Sirene und Hinweistöne einstellen, pro Ereignis einen Ton zuordnen.
   - Alarm, Vorwarnung und Ausgangsverzögerung wiederholen sich, solange der Zustand dauert. Die Sirene endet mit der Sirenendauer.
   - Scharf und Unscharf spielen einmal. Lautsprecher mit Durchsage-Funktion (z. B. Sonos) spielen sie über laufende Musik, die danach weiterläuft.
   - Danach stellt Bastion die vorherige Lautstärke wieder her.
   - Töne: mitgelieferte (Sirene, Piepen schnell/langsam, Gong) oder eigene Dateien aus „Meine Medien“. „MP3 hochladen“ legt die Datei in den lokalen HA-Medien unter `bastion/` ab.
   - Die Lautsprecher holen die Datei direkt bei HA ab. Dafür muss unter Einstellungen → System → Netzwerk eine interne URL gesetzt sein, die die Lautsprecher erreichen.
5. **Codes:** Codes werden nur als scrypt-Hash gespeichert. Sobald ein Code existiert, verlangt das Unscharfschalten einen Code. Nach 5 falschen Eingaben sperrt die Anlage die Eingabe für 5 Minuten. Während eines Alarms oder einer Vorwarnung verlangt auch jedes Umschalten einen Code, damit niemand die Sirene durch Scharfschalten stummschalten kann.
6. **Cloud-Worker** (optional): siehe unten. Er meldet sich über Pushover, Telegram, ntfy oder einen Webhook bei dir, wenn HA ausfällt, während die Anlage scharf ist, leitet Alarme unabhängig von HA weiter und bewahrt Protokoll und Kamerabilder außer Haus auf. Unter „Protokoll außer Haus“ die Kameras wählen, deren Bilder bei Vorwarnung und Alarm hochgeladen werden.

7. **Personen (Anwesenheit):** Personen im Haushalt anlegen, jeweils mit einem vorhandenen Tracker oder der IP-Adresse des Handys.
   - **Tracker (empfohlen):** z. B. aus der UniFi- oder FRITZ!Box-Integration. Der Router weiß, ob das Handy im WLAN ist. Bastion übernimmt dessen Zustand sofort, `not_home` oder eine andere Zone zählt als weg, `unavailable` lässt den letzten Stand stehen.
   - **IP-Adresse:** Bastion prüft alle 30 Sekunden ohne besondere Rechte (TCP, Ping, ARP-Tabelle). Ein TCP-Reset zählt nur im eigenen Subnetz, weil eine Firewall zwischen den Netzen ihn im Namen des Handys schickt. Die ARP-Prüfung stößt eine Neuprüfung an und wertet erst danach aus, damit ein veralteter Eintrag eines gegangenen Handys nicht als „da“ gilt. Zuhause gilt sofort, weg erst nach der eingestellten Zeit ohne Antwort (Standard 10 Minuten). „Prüfen“ testet eine Adresse sofort.
   - Der letzte Stand bleibt über Neustarts erhalten. Ohne bekannten Stand (neu angelegt) zählt ein stummes Handy beim ersten Durchlauf als weg. Die Sensoren zeigen daher nie „nicht verfügbar“, sondern zuhause oder weg.
   - Pro Person entstehen ein Anwesenheitssensor `binary_sensor.bastion_anwesenheit_<name>` und `device_tracker.bastion_<name>` (lässt sich HA-Personen zuordnen), dazu `binary_sensor.bastion_jemand_zuhause` und das Event `bastion_presence` bei Kommen und Gehen. Erlaubt sind private IP-Adressen und Hostnamen. Damit es zuverlässig klappt: im Router eine feste IP pro Handy vergeben, am iPhone „Private WLAN-Adresse“ für das Heim-WLAN auf „Fest“ oder „Aus“, bei Android „Zufällige MAC“ aus. Das Dashboard zeigt nur Namen und zuhause/weg, keine Adressen.
8. **Fernsteuerung** (Cloud-Worker, unten): „Fernsteuerung erlauben“ schaltet Scharf- und Unscharfschalten aus dem Worker-Dashboard frei, „Auch unscharf schalten erlauben“ zusätzlich das Unscharfschalten. Passkeys koppeln und entfernen geht nur hier (siehe Cloud-Worker → Fernsteuerung).
9. **Erinnerung „niemand zuhause“:** Sind alle gewählten Personen (leer = die Personen aus Punkt 7, sonst alle `person.*`) weg und die Anlage ist unscharf, kommt nach der eingestellten Zeit (Standard 20 Min.) eine Erinnerung aufs Handy und über den Worker. Mit Fernsteuerung öffnet der Link das Dashboard mit „Abwesend scharf schalten?“, bestätigt per Passkey. Eine Erinnerung pro Abwesenheit, sie setzt sich zurück, sobald jemand heimkommt. Im Protokoll steht sie als „Niemand zuhause, nicht scharf“.
10. **Grundriss:** Den Grundriss der Wohnung als JSON-Datei importieren (oder einfügen). Er bleibt in HA und im Worker hinter Access, Bastion liefert keinen mit. Danach die Flächen den Bastion-Räumen zuordnen (leer = automatisch über Name oder Stichwörter) und den Glastüren und der Wohnungstür ihren Sensor. HA schickt den Plan nur, wenn er sich geändert hat (Prüfsumme).
   - Format: `size` [Breite, Höhe], `areas` (id, label, rect [x, y, b, h], outdoor, room, keywords, label_at), `walls` (points, exterior), `glazing` (from, to, panels, door_panels, transom, sensor), `dividers`, `entrance` (from, to, sensor), `boxes` (points, height, bottom, kind furniture/soft/screen/shade, group). Einheiten frei, Wände sind 50 hoch. Höchstens 64 KB.

**Vorfälle:** Vorwarnung und anschließender Alarm bilden einen Vorfall mit eigener ID. Er endet mit dem Unscharf- oder erneuten Scharfschalten. Alle Protokolleinträge und Kamerabilder des Vorfalls tragen diese ID.

**Offene Sensoren:** Ist beim Scharfschalten ein Sensor offen, verweigert Bastion das Scharfschalten und nennt die offenen Sensoren. „Trotzdem scharf schalten“ überbrückt sie, bis sie schließen.

**Neustart:** Der Zustand bleibt erhalten. Eine laufende Ausgangsverzögerung wird fortgesetzt. Ein Neustart während der Vorwarnung, etwa bei einem Stromausfall nach dem Öffnen der Tür, löst den Alarm aus.

## Anomalie-Erkennung

- **Sensoren:** Bastion lernt pro Sensor den üblichen Bereich je Stunde (Werktag/Wochenende), die Nachbarstunden zählen mit. Startwerte kommen aus den Langzeit-Statistiken der letzten 30 Tage (Stundenmittel, -minimum und -maximum, damit kurze Spitzen wie beim Duschen im Bereich liegen). Gemeldet wird eine Abweichung erst, wenn der Wert mehrere Messungen hintereinander außerhalb liegt. Ungewöhnliche Werte lernt Bastion gedämpft mit: Wiederkehrende Spitzen erweitern den Bereich mit der Zeit, ein einzelner Extremwert kaum.
- **Raumklima** ist großzügiger, weil Duschen, Kochen und Lüften normal sind:

  | Sensor | nie ungewöhnlich | Mindestabstand | Dauer |
  |---|---|---|---|
  | Temperatur | 15–27 °C | 3 K | 30 Min. |
  | Luftfeuchte | 25–75 % | 20 % | 30 Min. |
  | CO₂ | bis 1400 ppm | 400 ppm | 30 Min. |
  | VOC, Feinstaub, Helligkeit | – | 60–100 % des Mittels | 30 Min. |

  Andere Sensoren (Strom, Wasser, …) bleiben streng: 15 Minuten außerhalb genügen. Brand (z. B. 45 °C) oder Auskühlen werden weiter erkannt.
- **„Ist normal“:** Im Panel unter Anomalien bei einer Abweichung oder beim Sensor antippen. Nur dieser Wert (und Werte knapp daneben) gilt dann für den Sensor als normal und wird nicht mehr gemeldet, andere Abweichungen im Verlauf bleiben bestehen. Beim Ereignis gilt dessen Wert, beim Sensor die aktuelle Abweichung. Der Sensor zeigt „als normal markiert“ mit den Werten.
- Wiederholte Abweichungen desselben Sensors innerhalb von 6 Stunden sind ein Eintrag.
- **Sabotage:** Fallen innerhalb des Zeitfensters mehrere Tür-, Fenster-, Bewegungs- oder ähnliche Sensoren aus, meldet Bastion Sabotageverdacht. Nicht gezählt werden Bastions eigene Entitäten (Alarmanlage, Köder, Anwesenheit, Sabotageverdacht) und Entitäten einer Integration, die gerade neu geladen oder aktualisiert wird (Zustand mit `restored`). Ein echter Funkausfall zählt weiter.

## Reaktion, Köder, Wochenbericht

**Neue IP:** Ein Konto meldet sich von einer Adresse an, die es noch nicht benutzt hat. IPv6 zählt pro Netz (/64): Handys und Router wechseln die hintere Hälfte ihrer IPv6-Adresse absichtlich alle paar Stunden (Privacy Extensions), das ist keine neue IP. Mit GeoIP merkt sich Bastion zusätzlich die Anbieter (ASN und Land) eines Kontos. Eine neue Adresse bei einem schon benutzten Anbieter (Mobilfunk, Heimanschluss, iCloud Private Relay) steht als „Neue IP · bekannter Anbieter“ im Protokoll, ohne Push. Ein neuer Anbieter oder ein neues Land meldet sich wie bisher.

**Aktionen in Benachrichtigungen:** Benachrichtigungsziele vom Typ `notify.mobile_app_*` bekommen bei Anmeldungen, neuen IPs, neuen Tokens und Benutzern die Buttons „War ich“ und „Sperren“. „Sperren“ hat folgende Wirkung:

- Der betroffene Token wird widerrufen.
- Die IP landet auf der HA-Bannliste (`ip_bans.yaml`). Loopback und Reverse-Proxy-IPs werden nie gesperrt.
- Neu angelegte oder hochgestufte Benutzer werden deaktiviert. Besitzer und du selbst sind geschützt.

Jeder Button gilt 48 Stunden, nur einmal und nur für Admins. Dieselbe Funktion gibt es im Panel und als Aktion `bastion.block`.

**Köder** (Konfigurieren → Köder): Bastion legt den Benutzer `api-backup` an (nur lesen, nur lokal) und dazu einen Long-Lived-Token und einen Webhook. Der Token-Wächter weist jede Benutzung des Tokens ab (HTTP 401), jeder Aufruf des Webhooks löst ebenfalls aus. Folgen eines Auslösers:

- Bastion meldet sofort kritisch mit Absender-IP, Event `bastion_security_event` vom Typ `canary`.
- `binary_sensor.bastion_decoy_triggered` geht für 24 Stunden an.

Token und URL stehen im Panel unter „Anomalien & Köder“. Leg sie dort ab, wo ein Eindringling suchen würde (Notizen, NAS-Freigabe, alte Backups). Ist „Köder ins Git-Repo“ aktiv, liegt zusätzlich `homeassistant/.env` mit diesen Daten unverschlüsselt im Repo. Ein Leck des Repos fällt damit beim ersten Benutzungsversuch auf. Diese Datei wird beim Wiederherstellen nie nach `/config` geschrieben.

**Köder im Worker:** Mit eingerichtetem Cloud-Worker gibt es zwei weitere Köder, die auf den Worker zeigen: einen Token im Format eines HA-Tokens und eine Webhook-URL (`…/api/webhook/<64 Hex>`). Sie stehen im Panel unter „Köder im Worker“ und in der `.env` als `HA_REMOTE_URL`, `HA_REMOTE_TOKEN`, `HA_REMOTE_WEBHOOK`. Der Worker erkennt sie an der Signatur (abgeleitet aus `ALARM_SECRET`, nichts gespeichert), antwortet wie HA (401 bzw. 200), schlägt selbst Alarm (hohe Priorität, je IP höchstens alle 15 Min.) und meldet die Benutzung mit dem nächsten Lebenszeichen an HA. Vorteil: Das funktioniert auch, wenn HA von außen nicht erreichbar oder ausgefallen ist. Ein neues `ALARM_SECRET` erzeugt neue Worker-Köder, alte Kopien an anderen Orten lösen dann nicht mehr aus.

**Token-Nutzung:** HA selbst protokolliert nicht, wann ein Long-Lived-Token per API benutzt wird. Bastion erfasst das ab der Installation selbst, mit Zeit und IP. Darauf beruhen der Befund „ungenutzter Token“ (erst nach genügend Beobachtungszeit) und der Alarm „Token von neuer IP“.

**Wochenbericht** (Konfigurieren → Wochenbericht): standardmäßig montags 08:13 an alle Benachrichtigungsziele, manuell per Button oder Aktion `bastion.send_report`.

**Firmware:** Die Firmware-Versionen von ESPHome-, Tasmota- und WLED-Geräten sowie der Zigbee2MQTT-Bridge aus der Geräteübersicht werden gegen die GitHub-Advisories dieser Projekte geprüft.

## Cloudflare Worker (Totmannschalter, Protokoll, Dashboard, Port-Prüfung)

```bash
cd extras/cloudflare-worker
npx wrangler d1 create bastion                   # ausgegebene database_id in wrangler.toml eintragen
npx wrangler deploy
npx wrangler secret put PROBE_TOKEN              # zufälliger Wert, auch in Bastion → Externe Prüfung
npx wrangler secret put ALARM_SECRET             # Wert aus Alarmanlage → Einstellungen → Cloud-Worker
npx wrangler secret put PUSHOVER_TOKEN           # optional, App-Token (pushover.net → Create an Application)
npx wrangler secret put PUSHOVER_USER            # optional, User-Key (pushover.net → Startseite)
npx wrangler secret put TELEGRAM_BOT_TOKEN       # optional, dazu TELEGRAM_CHAT_ID
npx wrangler secret put NTFY_URL                 # optional, z. B. https://ntfy.sh/<geheimes-topic>
```

Die Tabellen legt der Worker beim ersten Aufruf selbst an. Secrets lassen sich statt mit wrangler auch im Cloudflare-Dashboard setzen: Workers & Pages → bastion-probe → Settings → Variables and Secrets → Add → Typ *Secret*. Tokens dort immer als *Secret* anlegen, nicht als Text-Variable.

Tests: `node --import ./test/register.mjs --test test/worker.test.mjs` (Node ≥ 22, D1 wird mit `node:sqlite` nachgebildet).

**Pushover:** Ein Alarm kommt mit Notfall-Priorität (2). Er wiederholt sich jede Minute, bis jemand ihn bestätigt, höchstens 30 Minuten lang, mit dem Ton `siren` (änderbar über `PUSHOVER_SOUND`). „HA nicht erreichbar“ bei scharfer Anlage kommt ebenfalls als Notfall, Vorwarnungen und falsche Codes mit hoher Priorität, alles andere normal. Mit `PUSHOVER_DEVICE` lässt sich auf ein Gerät beschränken.
- **Quittierung:** Bestätigt jemand den Alarm, ruft Pushover den Worker auf. Der Worker prüft die Bestätigung bei Pushover nach (zusätzlich jede Minute per Cron), meldet „Alarm quittiert von <Gerät>“ an alle Kanäle und gibt sie mit dem nächsten Lebenszeichen an HA. Sie erscheint im Alarm-Protokoll und kann benachrichtigt werden.
- **Entwarnung:** Unscharfschalten bricht die Notfall-Wiederholung auf allen Handys ab.

**Welche Ereignisse gepusht werden,** bestimmt die Auswahl „Benachrichtigen bei“ in Bastion (Aktionen). Gespeichert wird jedes Ereignis.

**Protokoll außer Haus:**
- Jedes Alarmereignis (Scharf, Unscharf, Vorwarnung, Alarm, falscher Code, Scharfschalten fehlgeschlagen, Sensor nicht erreichbar, Quittierung, Funkstille, Neustart) landet in D1.
- HA kann nur anhängen, nicht löschen. Was beim Worker angekommen ist, bleibt erhalten, auch wenn HA zerstört oder übernommen wird.
- Bei Vorwarnung und Alarm schickt HA Bilder der gewählten Kameras (Standard: 3 pro Kamera im Abstand von 5 s, auf 1280 px verkleinert).
- Alarm-Pushs enthalten einen Link `…/i/<vorfall>?t=<token>` auf eine Vorfallseite mit Ablauf und Kamerabildern. Der Token gilt nur für diesen einen Vorfall.
- Aufbewahrung: `LOG_DAYS` (Standard 365) für Ereignisse, `SNAPSHOT_DAYS` (Standard 30) für Bilder.

**Totmannschalter:**
- HA schickt alle 2 Minuten ein signiertes Lebenszeichen, während Vorwarnung oder Alarm alle 15 Sekunden. Es enthält Zustand, offene und nicht erreichbare Sensoren, Startzeit von HA und Host.
- Der Worker prüft jede Minute. Bleibt das Lebenszeichen bei scharfer Anlage länger als `OFFLINE_MINUTES` (Standard 10) aus, meldet er „Home Assistant nicht erreichbar“ mit dem letzten Stand, den letzten Ereignissen und einer Einschätzung:
  - Funkstille während Vorwarnung oder Alarm: Sabotage wahrscheinlich, Link zum Vorfall.
  - Kurz vorher fielen Sensoren aus: Funkstörung, Stromausfall oder Sabotage möglich.
  - Geplanter Neustart: HA meldet das Herunterfahren. Der Worker wartet dann bis `PLANNED_MINUTES` (Standard 20).
- Kommt HA zurück, nennt die Meldung die Dauer und die Ursache: Rechner neu gestartet (Stromausfall), HA neu gestartet oder Netzwerk unterbrochen (HA lief durch).
- Bei unscharfer Anlage werden Ausfälle nur protokolliert (`ALERT_WHEN_DISARMED=1` meldet auch diese).

**Dashboard (hinter Cloudflare Access):**
- Tab „Alarmanlage“: Status mit Modus-Knöpfen (schaltbar mit Fernsteuerung), Systemstatus, Anwesenheit, Zonen (Räume und Sensoren mit bereit/offen/gestört und ob sie gerade überwacht sind; HA meldet Änderungen innerhalb von 15 Sekunden), Ereignisprotokoll, Kennzahlen (Alarme, Vorwarnungen, Scharf-Anteil, Quittierzeit, Funkstille, falsche Codes), Scharf-Zeit pro Tag nach Modus, häufigste Auslöser, Vorfälle mit Kamerabildern und das Protokoll.
- Tagesverlauf (Tab „Alarmanlage“): pro Tag die Zustände der Anlage (scharf nach Modus, Vorwarnung, Alarm), wer zuhause war, Funkstille und Ereignisse wie falsche Codes. Mit den Pfeilen durch die Tage blättern, Hover zeigt Uhrzeit und Dauer. Kommen und Gehen meldet HA mit dem Lebenszeichen, es steht auch im Ereignisprotokoll.
- Tab „Hausansicht“: der Grundriss als 3D-Modell (Kamera schräg von vorn) mit Live-Zustand pro Raum: überwacht, offen, gestört, Vorwarnung und Alarm pulsieren. Offene Glastüren leuchten orange, über der Wohnungstür steht „Tür zu/offen“. Raum antippen zeigt seine Sensoren mit Batterie. Ohne Grundriss erscheinen die Zonen.
- Sensor-Gesundheit (Tab „Hausansicht“): Batterie und letzte Meldung pro Sensor (vom Gerät des Sensors, auch über einen eigenen Batterie-Sensor). Schwach unter 25 %, fast leer unter 10 %, „meldet sich nicht“ nach 48 Stunden ohne Meldung. Schwache Batterien stehen auch im Systemstatus.
- Wandtablet (`#tablet`, Knopf in der Hausansicht): Vollbild mit Uhr, Zustand, Modi, Personen, Hinweisen und Grundriss. Der Bildschirm bleibt an (Wake Lock), der Inhalt wandert jede Minute ein paar Pixel gegen Einbrennen, 22–6 Uhr gedimmt (Antippen hellt eine Minute auf, bei Alarm nie gedimmt). Mit Passkey-Login das Tablet über einen Code koppeln (siehe unten), dann bleibt es lange angemeldet und kann nur anzeigen.
- Tab „Verfügbarkeit“: siehe unten.
- Tab „Sicherheit“: siehe unten.
- Einrichten:
  1. Worker → Settings → Domains & Routes → Custom Domain hinzufügen, z. B. `bastion.example.com`.
  2. Zero Trust → Access → Applications → Self-hosted, Domain wie oben, Policy mit den erlaubten E-Mail-Adressen.
  3. Den „Application Audience (AUD) Tag“ der Anwendung kopieren.
  4. Im Worker die Variablen `DASHBOARD_HOST` (die Domain), `ACCESS_TEAM_DOMAIN` (`<team>.cloudflareaccess.com`) und `ACCESS_AUD` setzen.
- Live: Das Dashboard fragt alle 10 Sekunden einen kleinen Stand ab und lädt nur bei Änderungen neu, ohne dass man neu laden muss. Oben rechts zeigt „LIVE“ mit Uhrzeit, dass die Verbindung steht.
- Als App installierbar (PWA): im Browser „Zum Startbildschirm“ (iPhone: Teilen → Zum Home-Bildschirm, Android/Chrome/Edge: Installieren). Der Service Worker speichert nichts auf dem Gerät, ohne Netz erscheint nur ein Offline-Hinweis. Nach Ablauf der Access-Sitzung öffnet die App den Access-Login und kehrt danach zurück.
- Der Worker prüft das Access-Token selbst (Signatur, Audience, Aussteller, Ablauf). Über die workers.dev-Adresse ist das Dashboard nicht erreichbar. HA spricht weiter über die workers.dev-Adresse, sie liegt nicht hinter Access.

**Fernsteuerung mit Passkey:**
- Voraussetzung: in HA „Fernsteuerung erlauben“ (Alarmanlage → Einstellungen → Cloud-Worker) und speichern. Ohne diese Einstellung zeigt das Dashboard keine Steuerung und der Worker nimmt keine Befehle an.
- Passkey koppeln: In HA „Passkey koppeln“ erzeugt einen 8-stelligen Code (10 Minuten gültig, einmal verwendbar). Im Dashboard unter Fernsteuerung den Code eingeben und den Passkey anlegen (Face ID, Fingerabdruck, Windows Hello, Passwortmanager). Der Worker bekommt nur den Hash des Codes. Nach 5 falschen Codes ist der Code ungültig.
- Schalten: Jeder Befehl verlangt Access und eine Bestätigung mit dem Passkey (mit Benutzerprüfung). HA holt Befehle mit einer signierten Anfrage ab, alle 15 Sekunden und alle 2 Sekunden, solange jemand im Dashboard einen Befehl vorbereitet. Es gibt keinen Weg von außen in HA. Jeder Befehl trägt die Signatur des Workers, gilt 90 Sekunden und läuft nur einmal.
- Unscharf schalten aus der Ferne braucht zusätzlich „Auch unscharf schalten erlauben“. Der Passkey ersetzt dabei den Alarm-Code.
- Offene Sensoren: Das Dashboard nennt sie und bietet „Trotzdem scharf schalten“ (neuer Passkey-Befehl).
- Im Alarm-Protokoll steht als Benutzer „Dashboard (<E-Mail>)“. Dashboard und HA zeigen die letzten Befehle mit Ergebnis.
- Passkeys entfernen: in HA unter Fernsteuerung (einzeln oder alle). Ein neuer Passkey, ein entfernter Passkey und jeder fehlgeschlagene Passkey-Versuch werden gemeldet bzw. als Angriff gezählt.
- Passkeys hängen an der Dashboard-Domain (`DASHBOARD_HOST`). Wechselt die Domain, müssen sie neu gekoppelt werden.

**Passkey-Login (`LOGIN=passkey`):**
- Nach Cloudflare Access verlangt das Dashboard eine Anmeldung mit Passkey. Ohne gültige Anmeldung liefert der Worker nur die Login-Seite, jede API antwortet 401.
- Sitzung: Cookie `__Host-bastion` (Secure, HttpOnly, SameSite=Lax), der Worker speichert nur den SHA-256 des Tokens. Sie gilt nur mit derselben Access-Identität und demselben Gerät (Browser/System), endet nach `LOGIN_IDLE_MINUTES` (Standard 30) ohne geöffnete Seite und spätestens nach `LOGIN_MAX_HOURS` (Standard 12).
- Erster Passkey: auf der Login-Seite „Passkey koppeln“ mit dem Code aus HA (wie bei der Fernsteuerung). Das Koppeln meldet das Gerät gleich an. Vorhandene Passkeys der Fernsteuerung gelten auch für den Login.
- Push bei Anmeldung von neuem Gerät, neuem Netz (/24 bzw. /48), neuem Ort oder Land (`LOGIN_ALERT`: `new` Standard, `all`, `off`). Jede Anmeldung steht im Ereignisprotokoll.
- Sperre: `LOGIN_FAILS` (Standard 5) fehlgeschlagene Anmeldungen eines Kontos oder einer IP in 15 Minuten sperren die Anmeldung für 15 Minuten, mit Push und Eintrag „Anmeldung gesperrt“. Fehlversuche zählen außerdem zur Angriffserkennung.
- Tab „Sicherheit“ → „Sitzungen“: angemeldete Geräte mit Herkunft, einzeln beenden, „Alle anderen beenden“, Abmelden (auch unten in der Seitenleiste).
- Wandtablet koppeln: unter „Sitzungen“ „Wandtablet koppeln“ erzeugt einen 8-stelligen Code (10 Minuten, einmalig). Auf dem Tablet nach Access „Als Wandtablet anmelden“ wählen und den Code eingeben. Das Tablet bleibt `TABLET_DAYS` (Standard 90) angemeldet, ohne Leerlauf-Ende, darf aber nicht schalten, keine Passkeys koppeln und keine Codes erzeugen.
- Läuft die Access-Sitzung ab, lädt das Dashboard die Seite neu und geht über den Access-Login (bei automatischer Weiterleitung zum Identity-Provider meist ohne Eingabe).

**Härtung des Zugriffs:**
- `ALLOWED_EMAILS` (als Secret): nur diese Access-Identitäten, auch wenn die Access-Regel falsch eingestellt ist.
- `ACCESS_MAX_AGE_HOURS` (Standard 168): ältere Access-Anmeldungen (iat) lehnt der Worker ab, auch wenn Access sie noch akzeptiert.
- `API_RATE` (Standard 240): Anfragen pro IP und Minute an Dashboard und API. Mit einem Rate-Limit-Binding `RATE_LIMITER` zählt Cloudflare über alle Instanzen.
- Header: CSP mit Nonce, HSTS, COOP/CORP, Permissions-Policy (Kamera, Mikrofon, Ort aus; Passkeys nur eigene Seite), `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`.
- Empfohlen in Cloudflare (Dashboard → Security → WAF → Custom rules), damit Fremde schon am Rand abprallen:
  - `(http.host eq "<DASHBOARD_HOST>" and ip.src.country ne "DE" and not starts_with(http.request.uri.path, "/pushover/"))` → Block
  - `(http.host eq "<DASHBOARD_HOST>" and (cf.client.bot or ip.src.country eq "T1"))` → Block
  - Rate limiting rule: `http.host eq "<DASHBOARD_HOST>"`, 100 Anfragen in 10 Sekunden pro IP → Block.
- Access: nur ein Identity-Provider mit MFA (kein E-Mail-Code), automatische Weiterleitung, kurze Sitzungsdauer. Liefert der Provider `amr`, zusätzlich „Require → Authentication method → mfa“.

**Prüfkette des Protokolls:**
- Jedes Ereignis bekommt eine HMAC über seinen Inhalt und den Wert des vorigen Ereignisses. Der Schlüssel wird aus `ALARM_SECRET` abgeleitet, liegt also nicht in D1. Wer in D1 einen Eintrag ändert, einfügt oder löscht, bricht die Kette und kann sie ohne das Secret nicht neu berechnen.
- Versiegelt wird mit jedem Lebenszeichen und jede Minute, geprüft jede Minute in Scheiben zu 500 Einträgen, immer wieder von vorn. HA bekommt den neuesten versiegelten Eintrag und schickt ihn mit dem nächsten Lebenszeichen zurück. Fehlt er oder ist er anders, wurde das Protokoll gekürzt.
- Ein Bruch meldet „Protokoll verändert“ über alle Kanäle, steht im Systemstatus und unter Sicherheit → „Protokoll-Prüfkette“.
- Die Aufbewahrung löscht nur vom ältesten Ende und merkt sich den letzten gelöschten Wert als neuen Anfang.

**Verfügbarkeit:**
- Jede Lücke im Lebenszeichen wird als Ausfall gespeichert: geplanter Neustart (HA hat das Herunterfahren gemeldet), Rechner neu gestartet (Stromausfall), Neustart ohne Ankündigung (Absturz), Netzwerk/Internet (HA lief durch) und laufende Funkstille.
- Kurze Lücken ohne Meldung (über 5 Min. bzw. 2,5 Intervalle) zählen als Netzwerkausfall.
- Tab „Verfügbarkeit“: Verfügbarkeit im Zeitraum (gesamt und ohne geplante Neustarts), Ampel pro Tag (ab 90 Tagen pro Woche), Ausfallminuten pro Tag und die Liste aller Ausfälle mit Ursache.
- Ausfälle von vor dieser Version übernimmt der Worker einmalig aus dem Protokoll („Wieder erreichbar“). Gemessen wird ab dem ersten Lebenszeichen, die Dauer ist auf ein Intervall genau.

**Nur bestimmte Länder (`ALLOWED_COUNTRIES`):**
- Variable im Worker, z. B. `DE` oder `DE,AT`. Dann öffnen Dashboard, Vorfallseiten (auch der Link aus dem Push) und App-Dateien nur aus diesen Ländern, alles andere bekommt 403. Unbekanntes Land und Tor zählen als gesperrt. Leer = keine Einschränkung.
- Offen bleiben die signierten Anfragen von HA (Lebenszeichen, Alarme, Bilder, Befehle) und der Pushover-Rückruf. Eine falsche Geolokalisierung des Heimanschlusses darf den Totmannschalter nicht abschalten, die Signatur schützt diese Wege ohnehin.
- Köder werden vor dem Länderfilter erkannt, ihre Benutzung aus dem Ausland wird also weiter gemeldet.
- Auf Reisen: Mobilfunk-Roaming in der EU nutzt meist eine deutsche IP, fremdes WLAN nicht. Dann ist das Dashboard gesperrt, Pushs kommen trotzdem.
- Zusätzlich lässt sich in der Access-Anwendung des Dashboards eine Regel „Require → Country“ setzen, dann sperrt Cloudflare schon vor dem Login.

**Zugriffsprotokoll:**
- Jeder Aufruf des Dashboards wird pro Gerät (Konto + Browser/System) und IP als Sitzung gespeichert, mit Land und Stadt. 30 Minuten ohne Aufruf beenden eine Sitzung.
- Neues Gerät oder neues Land eines Kontos: Meldung mit hoher Priorität und Eintrag im HA-Anmelde-Protokoll (`dashboard_access`). `ACCESS_ALERT=all` meldet jede Sitzung, `off` keine.
- Tab „Sicherheit“ → „Dashboard-Zugriffe“.

**Angriffserkennung am Worker:**
- Gezählt werden abgewiesene Zugriffe: falsche Signatur, falscher Probe-Token, gefälschter Pushover-Rückruf, falscher Vorfall-Link, Zugriffe auf das Dashboard ohne gültiges Access-Token, falsche Kopplungscodes und ungültige Passkeys. Aufrufe unbekannter Pfade (Scanner) zählen nicht.
- Ab `ATTACK_ALERT_AFTER` (Standard 5) abgewiesenen Zugriffen in 20 Minuten kommt eine Meldung über alle Kanäle, höchstens einmal pro Stunde. HA trägt den Angriff ins Anmelde-Protokoll ein und feuert `bastion_security_event` mit dem Typ `worker_attack`.
- Eine IP mit `ATTACK_BLOCK_AFTER` (Standard 10) Fehlversuchen in 20 Minuten wird für `ATTACK_BLOCK_MINUTES` (Standard 60) gesperrt. Die IP des letzten gültigen Lebenszeichens wird nie gesperrt, eine gültige Signatur hebt eine Sperre auf.
- Ein gültig signiertes, aber zu altes Lebenszeichen gilt als Uhrenproblem, nicht als Angriff.
- Schreibzugriffe auf D1 sind pro Worker-Instanz begrenzt, damit eine Flut das Tageskontingent nicht aufbraucht.

**Außenprüfung der öffentlichen Adresse:**
- Bastion übergibt die Adresse aus Alarmanlage → Einstellungen → Cloud-Worker → „Öffentliche Adresse von außen prüfen“, sonst die externe URL aus den HA-Netzwerkeinstellungen. Übergeben werden nur Schema und Host.
- Der Worker prüft alle 6 Stunden und bei jeder Adressänderung:
  - ob Cloudflare Access eine Anmeldung verlangt,
  - ob die HA-Anmeldung (`/auth/providers`) ohne Schutz erreichbar ist,
  - ob die API (`/api/`) ohne Anmeldung antwortet,
  - ob die Adresse auch über `http://` ausliefert, und Zertifikatsfehler.
- Neue Probleme meldet er über die Kanäle, Behebung ebenso. HA übernimmt das Ergebnis als Befunde (Kategorie Erreichbarkeit) in den Sicherheitswert.
- Angezeigt wird, über welches Cloudflare-Rechenzentrum geprüft wurde (z. B. FRA). Access-Regeln mit Länder-Ausnahmen wirken je nach Standort unterschiedlich.
- Grenze: Ein bald ablaufendes Zertifikat erkennt der Worker nicht vorab, erst ein ungültiges.

**Nachliefern:** 30 Sekunden nach dem Start schickt HA das komplette Alarm-Protokoll (bis 300 Einträge) und Anmelde-Protokoll (bis 1000 Einträge) an `/backfill`. Jeder Eintrag trägt eine feste ID, der Worker übernimmt nur, was ihm fehlt, auch Einträge aus der Zeit vor den IDs. Den Score-Verlauf (120 Tage) schickt HA mit dem Sicherheitsüberblick. Das Ergebnis steht unter Cloud-Worker → Protokoll außer Haus.

**Dashboard, Tab „Sicherheit“:** Sicherheitswert mit offenen Befunden, Fehlversuche pro Tag (HA und Worker), häufigste Quellen, gesperrte IPs, Dashboard-Zugriffe, Benutzungen der Worker-Köder und das Anmelde-Protokoll (Anmeldungen, neue IPs, Fehlversuche, Sperren, Konten und Tokens). Dazu Verlauf des Sicherheitswerts und das Ergebnis der Außenprüfung. HA schickt mit dem Lebenszeichen den Überblick (bei Änderung, sonst alle 30 Minuten) und neue Anmeldeereignisse, ältere über das Nachliefern. Interne IDs von Benutzern und Tokens verlassen HA nicht.

**Sicherheit:**
- Jede Meldung von HA trägt eine HMAC-SHA256-Signatur über Zeitstempel und Inhalt, Wiederholungen werden nach 5 Minuten abgewiesen.
- Befehle nimmt der Worker nur mit Access-Login und Passkey an und nur, wenn HA die Fernsteuerung erlaubt. HA prüft Signatur, Alter und Freigabe jedes Befehls noch einmal selbst. Aktionen im Dashboard verlangen zusätzlich dieselbe Herkunft (Origin), Kopplungscodes und Passkey-Challenges sind einmalig.
- Pushover-Rückrufe tragen ein geheimes Pfad-Token und werden zusätzlich bei Pushover gegengeprüft.
- Die Seiten senden eine strikte Content-Security-Policy und `Referrer-Policy: no-referrer`, damit Vorfall-Tokens nicht weitergegeben werden.
- Mit `LOGIN=passkey` verlangt jeder Abruf von Daten zusätzlich eine Passkey-Sitzung; das Wandtablet darf nur lesen.

**Port-Prüfung:**

Danach die Worker-URL (`https://bastion-probe.<account>.workers.dev`) und den Token in Bastion → Externe Prüfung eintragen.

Der Worker baut eine TCP-Verbindung zur IP des Aufrufers auf (`CF-Connecting-IP`), also zur eigenen öffentlichen IP. Fremde Adressen prüft er nie. Geprüfte Ports sind 21, 22, 23, 80, 139, 443, 445, 1880, 1883, 2375/2376, 3000, 3389, 5000/5001, 5900, 6052, 8080, 8086, 8123, 8883, 9000 und 9443. Verlässt HA das Netz über IPv6, prüft der Worker diese IPv6-Adresse, oft direkt den Host ohne NAT.

## Betrieb & Wartung

- **Entities** (IDs je nach Systemsprache, hier Englisch): `sensor.bastion_security_score`, `sensor.bastion_open_findings`, `sensor.bastion_failed_logins_24_h`, `sensor.bastion_git_status`, `sensor.bastion_last_commit`, `binary_sensor.bastion_critical_findings`, `binary_sensor.bastion_sabotage_suspicion`, pro Anomalie-Sensor ein `binary_sensor`, Buttons für Audit, Sicherung und Probe.
- **Events für Automationen:** `bastion_finding`, `bastion_security_event` (Typen: `login`, `new_ip`, `failed_login`, `brute_force`, `ip_banned`, `token_created`, `user_added`, `admin_granted`, `sabotage`, `tamper`, `unusual_action`, `unusual_login_time`, `external_config_change`, `new_destination`, `canary`, `worker_attack`, `dashboard_access`, `passkey_added`), `bastion_alarm` (u. a. `unarmed` für die Erinnerung), `bastion_anomaly`.
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
| Lautsprecher spielen keinen Ton | Log: „Unable to determine Home Assistant URL“ oder der Lautsprecher erreicht HA nicht | Interne URL unter Einstellungen → System → Netzwerk setzen, die im LAN erreichbar ist |
| Kamerabilder fehlen im Vorfall | Log: „snapshot … too large“ oder Kamera-Fehler | Kamera liefert auch verkleinert mehr als ~1 MB. Kleineren Stream bzw. Snapshot-Auflösung wählen |
| Dashboard zeigt 404 | Aufruf über workers.dev, `ACCESS_AUD`/`ACCESS_TEAM_DOMAIN` fehlen oder Domain passt nicht zu `DASHBOARD_HOST` | Über die Access-Domain aufrufen, Variablen prüfen |
| Worker meldet `ALARM_SECRET not set` | Secret fehlt im Worker | Secret setzen, Wert aus Bastion → Cloud-Worker |
| Person gilt als zuhause, obwohl weg | Bei IP-Prüfung: Methode in den Einstellungen ansehen (tcp/ping/arp). Eine andere Gerätschaft hat die IP bekommen, oder das Handy ist über VPN/WLAN-Calling erreichbar | Feste IP im Router, besser den Tracker der UniFi-/FRITZ!Box-Integration verknüpfen |
| Person bleibt „weg“, obwohl zuhause | Handy wechselt die IP (private WLAN-Adresse) oder schläft länger als die eingestellte Zeit | Feste IP im Router, private Adresse fürs Heim-WLAN aus, Zeit erhöhen. „Prüfen“ zeigt, welcher Test antwortet |
| Passkey koppeln: „Kein Kopplungscode aktiv“ | Code abgelaufen (10 Min.), schon benutzt oder nach 5 Fehlversuchen ungültig | In HA neuen Code erzeugen |
| Dashboard zeigt keine Fernsteuerung | „Fernsteuerung erlauben“ in HA aus oder noch nicht gespeichert, HA hat seitdem kein Lebenszeichen geschickt | Einstellung speichern, ein Intervall warten |
| Befehl „Nicht abgeholt“ | HA offline oder Worker-URL/Secret in HA falsch | Cloud-Worker → Testen. Befehle gelten 90 Sekunden |
| HA lehnt Befehle mit „signature“ ab | `ALARM_SECRET` im Worker und in HA verschieden | Secret abgleichen |
| Passkey wird nicht angeboten | Dashboard über andere Domain als bei der Kopplung geöffnet | Über `DASHBOARD_HOST` öffnen oder neu koppeln |
| Login-Seite: „Zu viele Fehlversuche“ | 5 fehlgeschlagene Passkey-Anmeldungen in 15 Min. (Konto oder IP) | 15 Minuten warten. Waren das nicht du: Sicherheit → Sitzungen prüfen, Passkeys in HA kontrollieren |
| Dashboard fragt ständig nach dem Passkey | Leerlauf (`LOGIN_IDLE_MINUTES`) zu kurz, oder Browser/System des Geräts hat sich geändert (Update ändert den Gerätenamen nicht, ein anderer Browser schon) | Leerlauf erhöhen, im selben Browser bleiben |
| Wandtablet zeigt „offline“ | Access-Sitzung abgelaufen und der Identity-Provider verlangt eine Eingabe | Am Tablet einmal anmelden; Sitzungsdauer in Access bzw. beim Provider verlängern |
| Hausansicht ohne Grundriss | Plan in HA nicht gespeichert oder HA noch ohne Lebenszeichen seit dem Speichern | In HA unter Grundriss speichern, ein Intervall warten |
| Raum im Grundriss bleibt grau | Fläche keinem Bastion-Raum zugeordnet | In HA unter Grundriss die Fläche dem Raum zuordnen |
| „Protokoll verändert“ | Prüfkette gebrochen: Daten in D1 geändert oder gelöscht, oder `ALARM_SECRET` gewechselt | Bei gewechseltem Secret ist das erwartbar (alte Einträge gegen neuen Schlüssel); sonst D1-Zugriffe und API-Tokens prüfen |
| Fehlversuche werden nicht gezählt | Logger `homeassistant.components.http.ban` steht in der Logger-Konfiguration auf `error` | Bastion setzt ihn auf `warning`. Diese Einstellung in `logger:` nicht wieder überschreiben |
