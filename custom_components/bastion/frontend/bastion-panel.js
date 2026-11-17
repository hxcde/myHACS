// Bastion sidebar panel. Plain web component, no build step.
// Every dynamic value is escaped before it is put into HTML.

const I18N = {
  de: {
    subtitle: "Sicherheit & Alarm",
    pages: {
      alarm: ["Alarmanlage", "Modi schalten, Räume und Sensoren live im Blick."],
      overview: ["Sicherheitsüberblick", "Ergebnisse des Audits mit konkreten Empfehlungen."],
      logins: ["Anmeldungen & Tokens", "Wer sich wann von wo anmeldet und welche Zugänge aktiv sind."],
      git: ["Konfiguration & Versionen", "Sicherung im privaten Repository, Vergleich und Wiederherstellung."],
      anomaly: ["Anomalien & Köder", "Gelerntes Normalverhalten, Sicherheitsereignisse und Köder."],
      external: ["Erreichbarkeit von außen", "Welche Ports deiner öffentlichen IP aus dem Internet erreichbar sind."],
      settings: ["Einstellungen der Alarmanlage", "Räume, Sensoren, Zeiten, Aktionen, Codes und Cloud-Worker."],
    },
    alarm: {
      tab: "Alarmanlage",
      states: { disarmed: "Aus", arming: "Wird scharf", armed_home: "Scharf · Zuhause", armed_night: "Scharf · Nacht", armed_away: "Scharf · Abwesend", pending: "Vorwarnung", triggered: "ALARM" },
      modes: { off: "Aus", home: "Zuhause", night: "Nacht", away: "Abwesend" },
      mode_hint: { off: "Unscharf", home: "Außenhaut, Bewohner da", night: "Erdgeschoss, schlafen", away: "Alles überwacht" },
      arming_in: "Scharf in {n} s",
      alarm_in: "Alarm in {n} s",
      triggered_by: "Ausgelöst durch",
      since: "seit",
      by: "von",
      settings: "Einstellungen",
      back: "Zurück",
      save: "Speichern",
      saved: "Gespeichert",
      rooms: "Räume",
      no_rooms: "Noch keine Räume. Lege in den Einstellungen Räume an und ordne Sensoren zu.",
      open: "offen",
      closed: "zu",
      unavailable: "nicht erreichbar",
      bypassed: "überbrückt",
      log: "Protokoll",
      no_log: "Noch keine Ereignisse.",
      code: "Code",
      enter_code: "Code eingeben",
      cancel: "Abbrechen",
      ok: "OK",
      open_title: "Offene Sensoren",
      open_text: "Diese Sensoren sind offen. Trotzdem scharf schalten? Sie werden überbrückt, bis sie wieder schließen.",
      force: "Trotzdem scharf schalten",
      sections: { rooms: "Räume & Sensoren", people: "Personen", floorplan: "Grundriss", modes: "Modi & Zeiten", actions: "Aktionen", sounds: "Töne", codes: "Codes", worker: "Cloud-Worker" },
      import_areas: "Räume aus HA-Bereichen übernehmen",
      add_room: "Raum hinzufügen",
      room_name: "Name",
      room_icon: "Icon (mdi:…)",
      choose_icon: "Icon wählen",
      icon_search: "Suchen, z. B. Küche, Bad, bed …",
      icon_custom: "Anderes MDI-Icon",
      icon_apply: "Übernehmen",
      fp_help: "Grundriss der Wohnung für das Worker-Dashboard (3D-Ansicht und Wandtablet). Als JSON-Datei importieren; er bleibt in Home Assistant und im Worker hinter Access und wird nicht mit Bastion veröffentlicht.",
      fp_import: "JSON-Datei wählen",
      fp_paste: "… oder JSON hier einfügen",
      fp_apply: "Übernehmen",
      fp_remove: "Grundriss entfernen",
      fp_invalid: "Kein gültiges JSON",
      fp_areas: "Flächen → Räume",
      fp_doors: "Türen → Sensoren",
      fp_auto: "automatisch",
      fp_none: "kein Sensor",
      fp_entrance: "Wohnungstür",
      fp_saved_hint: "Mit „Speichern“ übernehmen. Das Dashboard zeigt den Grundriss nach dem nächsten Lebenszeichen.",
      people: "Personen",
      people_help: "Personen im Haushalt. Am zuverlässigsten ist ein vorhandener Tracker, z. B. aus der UniFi- oder FRITZ!Box-Integration: Der Router weiß, ob das Handy im WLAN ist. Ohne Tracker prüft Bastion alle 30 Sekunden die IP-Adresse des Handys. Pro Person entstehen ein Anwesenheitssensor und ein device_tracker, dazu „Jemand zuhause“. Die Erinnerung „niemand zuhause“ nutzt diese Personen.",
      people_tracker: "Tracker",
      people_by_ip: "— IP-Adresse prüfen —",
      person_name: "Name",
      people_add: "Person hinzufügen",
      people_new: "neu – speichern",
      people_home: "zuhause",
      people_away: "weg",
      people_unknown: "wird ermittelt",
      people_test: "Prüfen",
      people_seen: "Zuletzt gesehen",
      people_found: "Antwortet",
      people_not_found: "Keine Antwort. Ist das Handy im WLAN und die IP richtig?",
      people_away_minutes: "Als weg nach (Minuten ohne Antwort)",
      people_hint: "Tipps: Im Router für jedes Handy eine feste IP vergeben (DHCP-Reservierung). Am iPhone für das Heim-WLAN „Private WLAN-Adresse“ auf „Fest“ oder „Aus“ stellen, bei Android „Zufällige MAC“ aus, sonst wechselt die Adresse. Handys schlafen: Darum gilt jemand erst nach der eingestellten Zeit ohne Antwort als weg.",
      delete: "Löschen",
      add_sensor: "Sensor hinzufügen …",
      type: { instant: "Sofort", delayed: "Verzögert", always: "Immer (24 h)" },
      type_hint: { instant: "Löst sofort aus", delayed: "Startet die Eingangsverzögerung", always: "Auch wenn die Anlage aus ist (Rauch, Wasser, Sabotage)" },
      may_be_open: "Darf offen sein",
      may_be_open_hint: "Darf beim Scharfschalten offen sein, wird dann überbrückt bis er schließt.",
      sensor_exit: "Aktiv nach",
      watched_in: "Überwacht in",
      sensor_name: "Name des Sensors",
      sensor_name_hint: "Eigener Name für Alarmanlage, Benachrichtigungen und Protokoll. Leer = Name aus Home Assistant.",
      ha_name: "HA",
      type_label: "Typ",
      when_arming: "Beim Scharfschalten",
      remove: "Entfernen",
      sensor_entry: "Alarm nach",
      sensor_exit_hint: "Aktivierungsverzögerung: Sekunden nach dem Scharfschalten, bis der Sensor überwacht wird (leer = Modus). Darf beim Scharfschalten offen sein, z. B. die Haustür.",
      sensor_entry_hint: "Auslöseverzögerung: Sekunden vom Auslösen bis zum Alarm (leer = Modus). Bei „Immer“ eine Bestätigungszeit.",
      mode_default: "auto",
      exit: "Ausgangsverzögerung (s)",
      entry: "Eingangsverzögerung (s)",
      trigger_time: "Sirenendauer (s)",
      rearm: "Nach dem Alarm wieder scharf",
      require_code_arm: "Code auch zum Scharfschalten",
      sabotage_triggers: "Sabotage, Manipulation und Köder lösen Alarm aus (wenn scharf)",
      sirens: "Sirenen (bei Alarm an)",
      lights: "Lichter (bei Alarm an)",
      warning: "Warnsignal während der Verzögerungen",
      add_entity: "Entität hinzufügen …",
      notify_events: "Benachrichtigen bei",
      events: { triggered: "Alarm", pending: "Vorwarnung", armed: "Scharf geschaltet", disarmed: "Unscharf geschaltet", arm_failed: "Scharfschalten fehlgeschlagen", wrong_code: "Falscher Code", sensor_unavailable: "Sensor nicht erreichbar", acknowledged: "Quittiert (Pushover)" },
      sounds_help: "Töne auf Lautsprechern. Sirene und Countdown-Piepen laufen, solange der Zustand dauert. Danach wird die vorherige Lautstärke wiederhergestellt. Kurze Töne laufen auf Lautsprechern mit Durchsage-Funktion über die Musik.",
      players: "Lautsprecher",
      add_player: "Lautsprecher hinzufügen …",
      volume: "Lautstärke Sirene",
      notice_volume: "Lautstärke Hinweistöne",
      sound_for: { triggered: "Alarm", pending: "Vorwarnung", arming: "Ausgangsverzögerung", armed: "Scharf geschaltet", disarmed: "Unscharf geschaltet" },
      sound_hint: { triggered: "Wiederholt bis unscharf oder bis die Sirenendauer vorbei ist", pending: "Wiederholt, solange die Eingangsverzögerung läuft", arming: "Wiederholt, bis die Anlage scharf ist", armed: "Einmal", disarmed: "Einmal" },
      sound_off: "Aus",
      builtin_group: "Bastion",
      builtin: { siren: "Sirene", entry: "Piepen schnell", exit: "Piepen langsam", armed: "Gong aufsteigend", disarmed: "Gong absteigend" },
      my_media: "Meine Medien",
      upload: "MP3 hochladen",
      uploaded: "Hochgeladen: {name}",
      play: "Probehören",
      stop: "Stopp",
      no_players: "Wähle zuerst mindestens einen Lautsprecher.",
      cameras: "Kameras für Beweisbilder",
      cameras_hint: "Bei Vorwarnung und Alarm gehen Bilder dieser Kameras an den Worker. Sie bleiben dort, auch wenn Home Assistant zerstört oder gestohlen wird.",
      add_camera: "Kamera hinzufügen …",
      snapshots: "Bilder pro Kamera und Phase (alle 5 s)",
      remote: "Fernsteuerung (Dashboard)",
      remote_help: "Scharf und unscharf schalten aus dem Worker-Dashboard. Jeder Befehl verlangt Cloudflare Access und einen Passkey (Face ID, Fingerabdruck, PIN). Home Assistant holt Befehle beim Worker ab, es gibt keinen Weg von außen hinein.",
      remote_enabled: "Fernsteuerung erlauben",
      remote_disarm: "Auch unscharf schalten erlauben",
      remote_disarm_hint: "Ohne diese Freigabe kann aus der Ferne nur scharf geschaltet werden.",
      remote_save_first: "Erst speichern, dann Passkeys koppeln.",
      pair: "Passkey koppeln",
      pair_hint: "Code im Dashboard unter Fernsteuerung eingeben. Gültig 10 Minuten, nur einmal.",
      pair_open: "Dashboard öffnen",
      passkeys: "Passkeys",
      no_passkeys: "Noch kein Passkey gekoppelt.",
      revoke: "Entfernen",
      revoke_all: "Alle entfernen",
      revoke_confirm: "Passkey entfernen? Dieses Gerät kann die Alarmanlage dann nicht mehr fernsteuern.",
      last_used: "zuletzt",
      never: "nie",
      commands: "Letzte Befehle",
      cmd_status: { pending: "wartet", delivered: "läuft", done: "ausgeführt", failed: "fehlgeschlagen", expired: "nicht abgeholt" },
      reminder: "Erinnerung: niemand zuhause",
      reminder_help: "Sind alle Personen weg und die Anlage ist unscharf, kommt nach der eingestellten Zeit eine Erinnerung aufs Handy und über den Worker. Mit Fernsteuerung enthält sie einen Link, der nach dem Passkey „Abwesend“ scharf schaltet.",
      reminder_enabled: "Erinnern, wenn niemand zuhause ist",
      reminder_minutes: "Nach Minuten",
      persons: "Personen",
      persons_all: "Leer = Personen aus „Personen“ (Handy-IP), sonst alle Personen von Home Assistant",
      add_person: "Person hinzufügen …",
      extra_events: { unarmed: "Niemand zuhause, nicht scharf" },
      offsite: "Protokoll außer Haus",
      public_url: "Öffentliche Adresse von außen prüfen",
      public_url_hint: "Der Worker prüft alle 6 Stunden, ob diese Adresse geschützt ist (Cloudflare Access), ob die HA-Anmeldung oder die API offen sind und ob sie unverschlüsselt erreichbar ist. Leer = externe URL aus den HA-Einstellungen.",
      exposure_none: "Noch nicht geprüft.",
      exposure_checked: "Geprüft {when} über {colo}",
      backfill: "Nachgeliefert: {alarm} Alarm- und {security} Anmeldeereignisse",
      offsite_hint: "Jedes Alarmereignis wird im Worker gespeichert. Alarm-Pushs enthalten einen Link zum Vorfall mit Kamerabildern. Pushover-Quittierungen erscheinen hier im Protokoll, Unscharfschalten beendet die Notfall-Wiederholung auf allen Handys.",
      critical_push: "Alarm als kritische Push-Nachricht (durchbricht Stumm)",
      codes_help: "Codes werden nur als Hash gespeichert. Ohne Code lässt sich die Anlage ohne Eingabe bedienen.",
      code_name: "Name (z. B. Yann)",
      add_code: "Code hinzufügen",
      no_codes: "Keine Codes. Jeder Admin kann ohne Code unscharf schalten.",
      worker_help: "Der Worker meldet sich bei dir über Pushover, Telegram, ntfy oder Webhook, auch wenn Home Assistant selbst ausfällt (Strom, Internet, Sabotage). Er nennt dann den letzten bekannten Stand, leitet Alarme unabhängig weiter und bewahrt Protokoll und Kamerabilder außer Haus auf.",
      worker_enabled: "Cloud-Worker aktiv",
      worker_url: "Worker-URL",
      interval: "Lebenszeichen alle (s)",
      secret: "Gemeinsames Geheimnis (ALARM_SECRET)",
      regenerate: "Neu erzeugen",
      test: "Testen",
      test_ok: "Worker erreicht. Kanäle: {channels}",
      last_ok: "Zuletzt erreicht",
      steps: ["Datenbank anlegen: wrangler d1 create bastion, database_id in wrangler.toml eintragen", "Worker aus extras/cloudflare-worker deployen (wrangler deploy)", "Geheimnis setzen: wrangler secret put ALARM_SECRET (Wert unten)", "Kanal setzen: PUSHOVER_TOKEN + PUSHOVER_USER, TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID oder NTFY_URL", "URL hier eintragen, speichern, testen"],
    },
    tabs: { alarm: "Alarmanlage", overview: "Übersicht", logins: "Anmeldungen", git: "Git", anomaly: "Anomalien & Köder", external: "Extern" },
    score: "Sicherheitswert",
    score_label: { good: "Gut", warning: "Ausbaufähig", serious: "Riskant", critical: "Kritisch" },
    trend: "Verlauf der letzten 30 Tage",
    no_trend: "Der Verlauf erscheint nach einigen Audits.",
    last_audit: "Letztes Audit",
    run_audit: "Audit ausführen",
    running: "Läuft …",
    send_report: "Wochenbericht senden",
    last_report: "Letzter Wochenbericht",
    all: "Alle",
    show_dismissed: "Ausgeblendete zeigen",
    no_findings: "Keine offenen Befunde. Gut gemacht.",
    dismiss: "Ausblenden",
    undismiss: "Einblenden",
    accept: "Baseline übernehmen",
    since: "erkannt",
    severity: { critical: "Kritisch", high: "Hoch", medium: "Mittel", low: "Niedrig", info: "Info" },
    types: {
      login: "Anmeldung", new_ip: "Neue IP", token_new_ip: "Token von neuer IP", failed_login: "Fehlversuch",
      brute_force: "Brute-Force-Verdacht", ip_banned: "IP gesperrt", token_created: "Token erstellt", token_removed: "Token entfernt",
      user_added: "Benutzer angelegt", user_removed: "Benutzer gelöscht", admin_granted: "Admin-Rechte vergeben",
      user_activated: "Benutzer aktiviert", canary: "Köder ausgelöst", blocked: "Gesperrt", confirmed: "Bestätigt",
      unusual_login_time: "Ungewöhnliche Anmeldezeit", unusual_action: "Ungewöhnliche Aktion", sabotage: "Sabotageverdacht",
      tamper: "Manipulation", anomaly: "Anomalie", new_destination: "Neues Verbindungsziel", worker_attack: "Angriffsversuch am Worker",
      external_config_change: "Extern geändert", deviation: "Abweichung", continuous: "Dauerbetrieb", drift: "Steigende Grundlast",
      token: "Token", webhook: "Webhook",
      dashboard_access: "Dashboard-Zugriff", passkey_added: "Passkey gekoppelt",
    },
    category: {
      access: "Zugang", exposure: "Erreichbarkeit", updates: "Updates", supply_chain: "Integrationen",
      config: "Konfiguration", git: "Git", anomaly: "Anomalie",
    },
    failed_24h: "Fehlversuche (24 h)",
    failed_chart: "Fehlversuche pro Stunde",
    top_sources: "Häufigste Quellen",
    logins_7d: "Anmeldungen (7 Tage)",
    blocked: "Gesperrt",
    tokens: "Tokens und Sitzungen",
    session: "Sitzung",
    llat: "Long-Lived-Token",
    created: "erstellt",
    last_used: "zuletzt",
    never: "nie",
    revoke: "Widerrufen",
    block: "Sperren",
    log: "Protokoll",
    confirm_block: "Wirklich sperren? Token werden widerrufen, die IP wird gesperrt.",
    git_disabled: "Git-Sync ist nicht eingerichtet: Einstellungen → Geräte & Dienste → Bastion → Konfigurieren → Git-Versionierung.",
    git_status: { ok: "Synchron", pending: "Push ausstehend", error: "Fehler", blocked: "Blockiert", disabled: "Aus" },
    repo: "Repository",
    branch: "Branch",
    privacy: "Sichtbarkeit",
    privacy_values: { private: "privat", public: "öffentlich", unknown: "nicht prüfbar" },
    encryption: "Secrets",
    encrypted_on: "verschlüsselt",
    encrypted_off: "nicht gesichert",
    host_key: "Server-Schlüssel",
    last_commit: "Letzter Commit",
    deploy_key: "Deploy-Key",
    deploy_key_help: "Im GitHub-Repo unter Settings → Deploy keys → Add deploy key einfügen und „Allow write access“ aktivieren.",
    copy: "Kopieren",
    copied: "Kopiert",
    show: "Anzeigen",
    hide: "Verbergen",
    commit_message: "Commit-Nachricht (optional)",
    commit_now: "Jetzt sichern",
    refresh: "Aktualisieren",
    history: "Verlauf",
    pick_commit: "Commit auswählen, um Dateien, Unterschiede und Wiederherstellung zu sehen.",
    files: "Dateien",
    only_changed: "Nur geänderte",
    restore_all: "Alles wiederherstellen",
    restore_selected: "Bereiche wiederherstellen",
    restore_file: "Wiederherstellen",
    restart_after: "Danach neu starten (nötig für UI-Konfiguration)",
    confirm_restore: "Stand {sha} wiederherstellen? Der aktuelle Stand wird vorher gesichert.",
    restored: "Wiederhergestellt: {written} geschrieben, {staged} für den Neustart vorbereitet, {skipped} übersprungen.",
    status: { same: "unverändert", changed: "geändert", deleted_locally: "lokal gelöscht", new_locally: "lokal neu", unknown: "unbekannt" },
    encrypted: "verschlüsselt",
    not_pushed: "nicht gepusht",
    changes: "Dateien",
    canary: "Köder",
    canary_off: "Köder sind aus. Aktivieren unter Konfigurieren → Köder.",
    canary_active: "Scharf",
    canary_alarm: "Ausgelöst",
    canary_help: "Diese Zugangsdaten nutzt niemand legitim. Lege sie dort ab, wo ein Eindringling suchen würde. Jede Benutzung wird abgewiesen und meldet Alarm.",
    canary_token: "Köder-Token",
    canary_webhook: "Köder-Webhook",
    canary_triggers: "Auslösungen",
    canary_worker: "Köder im Worker",
    canary_worker_help: "Zeigen auf den Cloud-Worker und schlagen dort Alarm, auch wenn Home Assistant von außen nicht erreichbar oder ausgefallen ist. Stehen auch in der Köderdatei im Git.",
    canary_worker_off: "Mit eingerichtetem Cloud-Worker gibt es zusätzlich Köder, die dort Alarm schlagen.",
    no_triggers: "Noch nie ausgelöst.",
    sabotage: "Sabotageverdacht",
    sensors: "Angelernte Sensoren",
    learned: "gelernt",
    samples: "Messwerte",
    no_sensors: "Keine Sensoren ausgewählt (Konfigurieren → Anomalie-Erkennung).",
    events: "Sicherheitsereignisse",
    no_events: "Keine Ereignisse.",
    outbound: "Neue Verbindungsziele",
    learning_since: "lernt seit",
    probe_none: "Keine externe Prüfung eingerichtet (Konfigurieren → Externe Prüfung).",
    run_probe: "Jetzt prüfen",
    public_ip: "Öffentliche IP",
    open: "offen",
    closed: "geschlossen",
    yes: "ja",
    no: "nein",
    error: "Fehler",
    areas: { config: "YAML", storage: "UI (.storage)", esphome: "ESPHome", zigbee2mqtt: "Zigbee2MQTT", addons: "Add-ons", extra: "Extra", inventory: "Inventar" },
    rel: { now: "gerade eben", m: "vor {n} Min.", h: "vor {n} Std.", d1: "vor 1 Tag", d: "vor {n} Tagen" },
  },
  en: {
    subtitle: "Security & alarm",
    pages: {
      alarm: ["Alarm system", "Switch modes and watch rooms and sensors live."],
      overview: ["Security overview", "Audit results with concrete recommendations."],
      logins: ["Logins & tokens", "Who logs in when and from where, and which credentials are active."],
      git: ["Configuration & versions", "Backup in the private repository, comparison and restore."],
      anomaly: ["Anomalies & decoys", "Learned normal behaviour, security events and decoys."],
      external: ["Exposure", "Which ports of your public IP are reachable from the internet."],
      settings: ["Alarm settings", "Rooms, sensors, timing, actions, codes and cloud worker."],
    },
    alarm: {
      tab: "Alarm",
      states: { disarmed: "Off", arming: "Arming", armed_home: "Armed · Home", armed_night: "Armed · Night", armed_away: "Armed · Away", pending: "Entry warning", triggered: "ALARM" },
      modes: { off: "Off", home: "Home", night: "Night", away: "Away" },
      mode_hint: { off: "Disarmed", home: "Perimeter, people home", night: "Ground floor, sleeping", away: "Everything watched" },
      arming_in: "Armed in {n} s",
      alarm_in: "Alarm in {n} s",
      triggered_by: "Triggered by",
      since: "since",
      by: "by",
      settings: "Settings",
      back: "Back",
      save: "Save",
      saved: "Saved",
      rooms: "Rooms",
      no_rooms: "No rooms yet. Create rooms in the settings and assign sensors.",
      open: "open",
      closed: "closed",
      unavailable: "unavailable",
      bypassed: "bypassed",
      log: "Log",
      no_log: "No events yet.",
      code: "Code",
      enter_code: "Enter code",
      cancel: "Cancel",
      ok: "OK",
      open_title: "Open sensors",
      open_text: "These sensors are open. Arm anyway? They are bypassed until they close again.",
      force: "Arm anyway",
      sections: { rooms: "Rooms & sensors", people: "People", floorplan: "Floor plan", modes: "Modes & timing", actions: "Actions", sounds: "Sounds", codes: "Codes", worker: "Cloud worker" },
      import_areas: "Create rooms from HA areas",
      add_room: "Add room",
      room_name: "Name",
      room_icon: "Icon (mdi:…)",
      choose_icon: "Choose icon",
      icon_search: "Search, e.g. kitchen, bath, bed …",
      icon_custom: "Other MDI icon",
      icon_apply: "Apply",
      fp_help: "Floor plan of the home for the worker dashboard (3D view and wall tablet). Import it as a JSON file; it stays in Home Assistant and in the worker behind Access and is never published with Bastion.",
      fp_import: "Choose JSON file",
      fp_paste: "… or paste JSON here",
      fp_apply: "Apply",
      fp_remove: "Remove floor plan",
      fp_invalid: "Not valid JSON",
      fp_areas: "Areas → rooms",
      fp_doors: "Doors → sensors",
      fp_auto: "automatic",
      fp_none: "no sensor",
      fp_entrance: "Front door",
      fp_saved_hint: "Apply with 'Save'. The dashboard shows the plan after the next heartbeat.",
      people: "People",
      people_help: "People of the household. Most reliable is an existing tracker, e.g. from the UniFi or FRITZ!Box integration: the router knows whether the phone is on the WLAN. Without a tracker Bastion checks the phone's IP address every 30 seconds. Each person gets a presence sensor and a device_tracker, plus 'Someone home'. The 'nobody home' reminder uses these people.",
      people_tracker: "Tracker",
      people_by_ip: "— check IP address —",
      person_name: "Name",
      people_add: "Add person",
      people_new: "new – save",
      people_home: "home",
      people_away: "away",
      people_unknown: "detecting",
      people_test: "Check",
      people_seen: "Last seen",
      people_found: "Answers",
      people_not_found: "No answer. Is the phone on the WLAN and the IP correct?",
      people_away_minutes: "Away after (minutes without answer)",
      people_hint: "Tips: give every phone a fixed IP in the router (DHCP reservation). On iPhone set 'Private Wi-Fi address' for the home network to 'Fixed' or 'Off', on Android turn off 'Randomized MAC', otherwise the address changes. Phones sleep: someone only counts as away after the set time without answer.",
      delete: "Delete",
      add_sensor: "Add sensor …",
      type: { instant: "Instant", delayed: "Delayed", always: "Always (24 h)" },
      type_hint: { instant: "Triggers immediately", delayed: "Starts the entry delay", always: "Also when disarmed (smoke, water, tamper)" },
      may_be_open: "May be open",
      may_be_open_hint: "May be open when arming; it is bypassed until it closes.",
      sensor_exit: "Active after",
      watched_in: "Watched in",
      sensor_name: "Sensor name",
      sensor_name_hint: "Own name for the alarm, notifications and log. Empty = name from Home Assistant.",
      ha_name: "HA",
      type_label: "Type",
      when_arming: "When arming",
      remove: "Remove",
      sensor_entry: "Alarm after",
      sensor_exit_hint: "Activation delay: seconds after arming until the sensor is watched (empty = mode). May be open while arming, e.g. the front door.",
      sensor_entry_hint: "Trigger delay: seconds from opening to the alarm (empty = mode). For 'always' sensors a confirmation time.",
      mode_default: "auto",
      exit: "Exit delay (s)",
      entry: "Entry delay (s)",
      trigger_time: "Siren duration (s)",
      rearm: "Re-arm after an alarm",
      require_code_arm: "Code required for arming",
      sabotage_triggers: "Sabotage, tampering and decoys trigger the alarm (when armed)",
      sirens: "Sirens (on during alarm)",
      lights: "Lights (on during alarm)",
      warning: "Warning signal during delays",
      add_entity: "Add entity …",
      notify_events: "Notify on",
      events: { triggered: "Alarm", pending: "Entry warning", armed: "Armed", disarmed: "Disarmed", arm_failed: "Arming failed", wrong_code: "Wrong code", sensor_unavailable: "Sensor unavailable", acknowledged: "Acknowledged (Pushover)" },
      sounds_help: "Sounds on speakers. Siren and countdown beeps repeat while the state lasts, then the previous volume is restored. Short sounds play over music on speakers that support announcements.",
      players: "Speakers",
      add_player: "Add speaker …",
      volume: "Siren volume",
      notice_volume: "Notice volume",
      sound_for: { triggered: "Alarm", pending: "Entry warning", arming: "Exit delay", armed: "Armed", disarmed: "Disarmed" },
      sound_hint: { triggered: "Repeats until disarmed or the siren time is over", pending: "Repeats during the entry delay", arming: "Repeats until armed", armed: "Once", disarmed: "Once" },
      sound_off: "Off",
      builtin_group: "Bastion",
      builtin: { siren: "Siren", entry: "Fast beeps", exit: "Slow beeps", armed: "Rising chime", disarmed: "Falling chime" },
      my_media: "My media",
      upload: "Upload MP3",
      uploaded: "Uploaded: {name}",
      play: "Preview",
      stop: "Stop",
      no_players: "Choose at least one speaker first.",
      cameras: "Cameras for evidence images",
      cameras_hint: "During entry warnings and alarms, images of these cameras go to the worker. They stay there even if Home Assistant is destroyed or stolen.",
      add_camera: "Add camera …",
      snapshots: "Images per camera and phase (every 5 s)",
      remote: "Remote control (dashboard)",
      remote_help: "Arm and disarm from the worker dashboard. Every command needs Cloudflare Access and a passkey (Face ID, fingerprint, PIN). Home Assistant fetches commands from the worker, there is no way in from outside.",
      remote_enabled: "Allow remote control",
      remote_disarm: "Also allow disarming",
      remote_disarm_hint: "Without this, the alarm can only be armed remotely.",
      remote_save_first: "Save first, then pair passkeys.",
      pair: "Pair a passkey",
      pair_hint: "Enter the code in the dashboard under remote control. Valid for 10 minutes, once.",
      pair_open: "Open dashboard",
      passkeys: "Passkeys",
      no_passkeys: "No passkey paired yet.",
      revoke: "Remove",
      revoke_all: "Remove all",
      revoke_confirm: "Remove this passkey? That device can no longer control the alarm.",
      last_used: "last",
      never: "never",
      commands: "Recent commands",
      cmd_status: { pending: "waiting", delivered: "running", done: "done", failed: "failed", expired: "not fetched" },
      reminder: "Reminder: nobody home",
      reminder_help: "When everybody left and the alarm is disarmed, a reminder goes to the phones and via the worker after the set time. With remote control it links to the dashboard, which arms 'away' after the passkey.",
      reminder_enabled: "Remind when nobody is home",
      reminder_minutes: "After minutes",
      persons: "People",
      persons_all: "Empty = people from 'People' (phone IP), else all Home Assistant persons",
      add_person: "Add person …",
      extra_events: { unarmed: "Nobody home, not armed" },
      offsite: "Off-site log",
      public_url: "Check public address from outside",
      public_url_hint: "Every 6 hours the worker checks whether this address is protected (Cloudflare Access), whether the HA login or API are open and whether it is reachable without encryption. Empty = external URL from the HA settings.",
      exposure_none: "Not checked yet.",
      exposure_checked: "Checked {when} via {colo}",
      backfill: "Resent: {alarm} alarm and {security} login events",
      offsite_hint: "Every alarm event is stored by the worker. Alarm pushes link to the incident with camera images. Pushover acknowledgements show up in the log here, disarming stops the emergency repeat on all phones.",
      critical_push: "Alarm as critical push notification (breaks through silent mode)",
      codes_help: "Codes are stored as hashes only. Without codes the system works without input.",
      code_name: "Name (e.g. Alex)",
      add_code: "Add code",
      no_codes: "No codes. Every admin can disarm without a code.",
      worker_help: "The worker reaches you via Pushover, Telegram, ntfy or webhook even when Home Assistant itself fails (power, internet, sabotage), names the last known state, relays alarms independently and keeps the log and camera images off-site.",
      worker_enabled: "Cloud worker enabled",
      worker_url: "Worker URL",
      interval: "Heartbeat every (s)",
      secret: "Shared secret (ALARM_SECRET)",
      regenerate: "Regenerate",
      test: "Test",
      test_ok: "Worker reached. Channels: {channels}",
      last_ok: "Last reached",
      steps: ["Create the database: wrangler d1 create bastion and put the database_id into wrangler.toml", "Deploy the worker from extras/cloudflare-worker (wrangler deploy)", "Set the secret: wrangler secret put ALARM_SECRET (value below)", "Set a channel: PUSHOVER_TOKEN + PUSHOVER_USER, TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID or NTFY_URL", "Enter the URL here, save, test"],
    },
    tabs: { alarm: "Alarm", overview: "Overview", logins: "Logins", git: "Git", anomaly: "Anomalies & decoys", external: "External" },
    score: "Security score",
    score_label: { good: "Good", warning: "Fair", serious: "At risk", critical: "Critical" },
    trend: "Last 30 days",
    no_trend: "The trend appears after a few audits.",
    last_audit: "Last audit",
    run_audit: "Run audit",
    running: "Running …",
    send_report: "Send weekly report",
    last_report: "Last weekly report",
    all: "All",
    show_dismissed: "Show dismissed",
    no_findings: "No open findings. Well done.",
    dismiss: "Dismiss",
    undismiss: "Restore",
    accept: "Accept baseline",
    since: "found",
    severity: { critical: "Critical", high: "High", medium: "Medium", low: "Low", info: "Info" },
    types: {
      login: "Login", new_ip: "New IP", token_new_ip: "Token from new IP", failed_login: "Failed login",
      brute_force: "Possible brute force", ip_banned: "IP banned", token_created: "Token created", token_removed: "Token removed",
      user_added: "User created", user_removed: "User removed", admin_granted: "Admin rights granted",
      user_activated: "User activated", canary: "Decoy triggered", blocked: "Blocked", confirmed: "Confirmed",
      unusual_login_time: "Unusual login time", unusual_action: "Unusual action", sabotage: "Sabotage suspicion",
      tamper: "Tampering", anomaly: "Anomaly", new_destination: "New destination", worker_attack: "Attack on the worker",
      external_config_change: "Changed outside the UI", deviation: "Deviation", continuous: "Continuous run", drift: "Rising base load",
      token: "Token", webhook: "Webhook",
      dashboard_access: "Dashboard access", passkey_added: "Passkey paired",
    },
    category: {
      access: "Access", exposure: "Exposure", updates: "Updates", supply_chain: "Integrations",
      config: "Configuration", git: "Git", anomaly: "Anomaly",
    },
    failed_24h: "Failed logins (24 h)",
    failed_chart: "Failed logins per hour",
    top_sources: "Top sources",
    logins_7d: "Logins (7 days)",
    blocked: "Blocked",
    tokens: "Tokens and sessions",
    session: "Session",
    llat: "Long-lived token",
    created: "created",
    last_used: "last used",
    never: "never",
    revoke: "Revoke",
    block: "Block",
    log: "Log",
    confirm_block: "Block now? Tokens are revoked and the IP is banned.",
    git_disabled: "Git sync is not configured: Settings → Devices & services → Bastion → Configure → Git versioning.",
    git_status: { ok: "In sync", pending: "Push pending", error: "Error", blocked: "Blocked", disabled: "Off" },
    repo: "Repository",
    branch: "Branch",
    privacy: "Visibility",
    privacy_values: { private: "private", public: "public", unknown: "not verifiable" },
    encryption: "Secrets",
    encrypted_on: "encrypted",
    encrypted_off: "not backed up",
    host_key: "Server key",
    last_commit: "Last commit",
    deploy_key: "Deploy key",
    deploy_key_help: "Add it in the GitHub repository under Settings → Deploy keys → Add deploy key and enable 'Allow write access'.",
    copy: "Copy",
    copied: "Copied",
    show: "Show",
    hide: "Hide",
    commit_message: "Commit message (optional)",
    commit_now: "Back up now",
    refresh: "Refresh",
    history: "History",
    pick_commit: "Pick a commit to see files, differences and restore options.",
    files: "Files",
    only_changed: "Changed only",
    restore_all: "Restore everything",
    restore_selected: "Restore areas",
    restore_file: "Restore",
    restart_after: "Restart afterwards (required for UI configuration)",
    confirm_restore: "Restore state {sha}? The current state is backed up first.",
    restored: "Restored: {written} written, {staged} staged for restart, {skipped} skipped.",
    status: { same: "unchanged", changed: "changed", deleted_locally: "deleted locally", new_locally: "new locally", unknown: "unknown" },
    encrypted: "encrypted",
    not_pushed: "not pushed",
    changes: "files",
    canary: "Decoys",
    canary_off: "Decoys are off. Enable them under Configure → Decoys.",
    canary_active: "Armed",
    canary_alarm: "Triggered",
    canary_help: "Nobody uses these credentials legitimately. Plant them where an intruder would look. Any use is rejected and raises an alarm.",
    canary_token: "Decoy token",
    canary_webhook: "Decoy webhook",
    canary_triggers: "Triggers",
    canary_worker: "Worker decoys",
    canary_worker_help: "Point at the cloud worker and alert from there, even when Home Assistant is down or not reachable from outside. Also part of the decoy file in git.",
    canary_worker_off: "With the cloud worker set up there are extra decoys that alert from there.",
    no_triggers: "Never triggered.",
    sabotage: "Sabotage suspicion",
    sensors: "Learned sensors",
    learned: "learned",
    samples: "samples",
    no_sensors: "No sensors selected (Configure → Anomaly detection).",
    events: "Security events",
    no_events: "No events.",
    outbound: "New outbound destinations",
    learning_since: "learning since",
    probe_none: "No external check configured (Configure → External check).",
    run_probe: "Check now",
    public_ip: "Public IP",
    open: "open",
    closed: "closed",
    yes: "yes",
    no: "no",
    error: "Error",
    areas: { config: "YAML", storage: "UI (.storage)", esphome: "ESPHome", zigbee2mqtt: "Zigbee2MQTT", addons: "Add-ons", extra: "Extra", inventory: "Inventory" },
    rel: { now: "just now", m: "{n} min ago", h: "{n} h ago", d1: "1 day ago", d: "{n} days ago" },
  },
};

// Status palette (fixed): critical / serious / warning / good. "low" is informational.
const SEV = {
  critical: { color: "#d03b3b", icon: "mdi:alert-octagon" },
  high: { color: "#ec835a", icon: "mdi:alert" },
  medium: { color: "#fab219", icon: "mdi:alert-circle-outline" },
  low: { color: "#5b8bd0", icon: "mdi:information-outline" },
  info: { color: "#8a8f98", icon: "mdi:information-outline" },
};
const GOOD = "#0ca30c";
const CATEGORY_ICON = {
  access: "mdi:account-key", exposure: "mdi:web", updates: "mdi:update", supply_chain: "mdi:package-variant-closed",
  config: "mdi:cog-outline", git: "mdi:source-branch", anomaly: "mdi:chart-bell-curve",
};
const TAB_ICON = {
  alarm: "mdi:shield-home",
  overview: "mdi:shield-check-outline", logins: "mdi:account-lock-outline", git: "mdi:source-branch",
  anomaly: "mdi:radar", external: "mdi:web-check",
};
const LOG_ICON = {
  login: ["mdi:login", GOOD], new_ip: ["mdi:map-marker-alert-outline", SEV.medium.color],
  token_new_ip: ["mdi:key-alert-outline", SEV.medium.color], failed_login: ["mdi:account-cancel-outline", SEV.high.color],
  brute_force: ["mdi:shield-alert-outline", SEV.critical.color], ip_banned: ["mdi:cancel", SEV.critical.color],
  token_created: ["mdi:key-plus", SEV.medium.color], token_removed: ["mdi:key-remove", "#8a8f98"],
  user_added: ["mdi:account-plus-outline", SEV.medium.color], user_removed: ["mdi:account-remove-outline", "#8a8f98"],
  admin_granted: ["mdi:shield-account-outline", SEV.high.color], user_activated: ["mdi:account-check-outline", SEV.medium.color],
  canary: ["mdi:bird", SEV.critical.color], blocked: ["mdi:block-helper", SEV.critical.color], worker_attack: ["mdi:shield-bug-outline", SEV.high.color],
  confirmed: ["mdi:check-circle-outline", GOOD],
};
const PORT_NAMES = {
  21: "FTP", 22: "SSH", 23: "Telnet", 80: "HTTP", 139: "NetBIOS", 443: "HTTPS", 445: "SMB", 1880: "Node-RED",
  1883: "MQTT", 2375: "Docker API", 2376: "Docker TLS", 3000: "Grafana", 3389: "RDP", 5000: "Synology", 5001: "Synology",
  5900: "VNC", 6052: "ESPHome", 8080: "Web", 8086: "InfluxDB", 8123: "Home Assistant", 8883: "MQTT TLS",
  9000: "Portainer", 9443: "Portainer",
};

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
const icon = (name, color) => `<ha-icon icon="${esc(name)}"${color ? ` style="color:${color}"` : ""}></ha-icon>`;

// Icons for rooms, with German and English search words.
const ROOM_ICONS = [
  ["door", "tür flur eingang door hall"], ["door-open", "tür offen eingang"], ["door-sliding", "schiebetür terrasse"], ["door-closed-lock", "haustür abgeschlossen"],
  ["home", "haus home"], ["home-outline", "haus"], ["home-floor-0", "erdgeschoss eg"], ["home-floor-1", "obergeschoss og"], ["home-floor-2", "dachgeschoss"],
  ["home-floor-b", "keller basement"], ["home-roof", "dach dachboden"], ["stairs", "treppe stairs"], ["stairs-up", "treppenhaus"], ["elevator", "aufzug"],
  ["sofa", "wohnzimmer sofa couch living"], ["sofa-outline", "wohnzimmer"], ["television", "fernseher tv wohnzimmer"], ["fireplace", "kamin"],
  ["bed", "schlafzimmer bett bedroom"], ["bed-king-outline", "schlafzimmer"], ["bed-single", "gästezimmer gast"], ["bunk-bed", "kinderzimmer"],
  ["teddy-bear", "kinderzimmer kinder kids"], ["human-child", "kind kinder"], ["baby-carriage", "baby"],
  ["stove", "küche herd kitchen"], ["fridge", "küche kühlschrank"], ["silverware-fork-knife", "esszimmer essen dining"], ["chef-hat", "küche kochen"],
  ["coffee", "kaffee küche"], ["countertop", "küche"], ["dishwasher", "spülmaschine"], ["washing-machine", "waschküche wäsche laundry"], ["tumble-dryer", "trockner wäsche"],
  ["shower", "bad dusche bathroom"], ["bathtub", "bad badewanne"], ["toilet", "wc toilette gäste"], ["paper-roll", "wc"],
  ["desk", "büro arbeitszimmer office"], ["laptop", "büro"], ["monitor", "büro computer"], ["bookshelf", "bibliothek bücher"], ["library", "bibliothek"],
  ["briefcase", "arbeit büro"], ["printer", "drucker"], ["gamepad-variant", "spielzimmer gaming"], ["music", "musik"], ["guitar-acoustic", "musikzimmer"],
  ["dumbbell", "fitness sport gym"], ["yoga", "sport yoga"], ["window-closed-variant", "fenster"], ["window-open-variant", "fenster offen"],
  ["window-shutter", "rollladen"], ["curtains", "vorhang"], ["wardrobe-outline", "ankleide schrank"], ["hanger", "garderobe"], ["tshirt-crew", "ankleide kleidung"],
  ["shoe-formal", "garderobe schuhe"], ["garage", "garage"], ["garage-variant", "garage"], ["gate", "tor einfahrt"], ["car", "auto carport"], ["car-side", "carport"],
  ["bicycle", "fahrrad keller"], ["motorbike", "motorrad"], ["tools", "werkstatt werkzeug"], ["hammer-wrench", "werkstatt"], ["toolbox", "werkstatt"],
  ["package-variant", "abstellraum lager"], ["warehouse", "lager halle"], ["archive", "abstellraum archiv"], ["server", "technik serverraum"],
  ["router-wireless", "technik netzwerk"], ["water", "hauswirtschaft wasser"], ["radiator", "heizung heizungsraum"], ["solar-panel", "solar"],
  ["flower", "garten blumen garden"], ["tree", "garten baum"], ["pine-tree", "garten"], ["grass", "garten rasen"], ["balcony", "balkon"],
  ["greenhouse", "gewächshaus"], ["barn", "scheune schuppen"], ["fence", "zaun grundstück"], ["grill", "terrasse grill"], ["umbrella-beach", "terrasse"],
  ["pool", "pool schwimmbad"], ["hot-tub", "whirlpool wellness"], ["mailbox", "briefkasten"], ["cctv", "kamera überwachung"], ["shield-home", "sicherheit"],
  ["lightbulb", "licht"], ["lamp", "lampe"], ["ceiling-light", "deckenlicht"], ["floor-lamp", "stehlampe"],
  ["paw", "haustier tiere"], ["dog", "hund"], ["cat", "katze"], ["fish", "aquarium fisch"], ["account", "person zimmer"], ["account-group", "familie"],
].map(([name, words]) => [`mdi:${name}`, `${name.replace(/-/g, " ")} ${words}`]);

function toDate(value) {
  if (!value) return null;
  const d = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}
function fmtTime(value) {
  const d = toDate(value);
  return d ? esc(d.toLocaleString()) : "—";
}

class BastionPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tab = "alarm";
    this._alarmView = "status";
    this._section = "rooms";
    this._filter = "all";
    this._showDismissed = false;
    this._onlyChanged = true;
    this._busy = false;
    this._toast = "";
    this._reveal = false;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._load();
      return;
    }
    // Live view of the alarm: re-render when the alarm or one of its sensors changes.
    if (this._tab === "alarm" && this._alarmView === "status" && this._alarm && !this._modal) {
      const sig = this._alarmSignature();
      if (sig !== this._alarmSig) {
        const alarmChanged = sig.split("|")[0] !== (this._alarmSig || "").split("|")[0];
        this._alarmSig = sig;
        if (alarmChanged) this._refreshAlarm();
        else this._render();
      }
    }
  }

  _alarmEntity() {
    return Object.values(this._hass.states).find(
      (st) => st.entity_id.startsWith("alarm_control_panel.") && "target_mode" in (st.attributes || {})
    );
  }

  _alarmSignature() {
    const entity = this._alarmEntity();
    const sensors = (this._alarm?.config.rooms || []).flatMap((r) => r.sensors);
    return [entity ? `${entity.state}:${entity.last_changed}` : "", ...sensors.map((e) => this._hass.states[e]?.state)].join("|");
  }

  async _refreshAlarm() {
    try {
      this._alarm = await this._ws("bastion/alarm/get");
    } catch (err) {
      this._notify(`${this.t.error}: ${err.message || err}`);
    }
    this._render();
  }

  set narrow(value) {
    this._narrow = value;
  }

  get t() {
    return I18N[(this._hass?.language || "en").startsWith("de") ? "de" : "en"];
  }

  rel(value) {
    const d = toDate(value);
    if (!d) return "—";
    const s = (Date.now() - d.getTime()) / 1000;
    const r = this.t.rel;
    if (s < 60) return r.now;
    if (s < 3600) return r.m.replace("{n}", Math.round(s / 60));
    if (s < 86400) return r.h.replace("{n}", Math.round(s / 3600));
    const days = Math.round(s / 86400);
    return days === 1 ? r.d1 : r.d.replace("{n}", days);
  }

  async _ws(type, extra = {}) {
    return this._hass.connection.sendMessagePromise({ type, ...extra });
  }

  async _load() {
    try {
      this._data = await this._ws("bastion/overview");
      if (this._tab === "alarm") {
        this._alarm = await this._ws("bastion/alarm/get");
        this._alarmSig = this._alarmSignature();
      }
      if (this._tab === "logins") this._logins = await this._ws("bastion/logins");
      if (this._tab === "git" && this._data.git.status !== "disabled") {
        this._git = await this._ws("bastion/git/history", { refresh: !this._git });
      }
    } catch (err) {
      this._notify(`${this.t.error}: ${err.message || err.code || err}`);
    }
    this._render();
  }

  _notify(text) {
    this._toast = text;
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      this._toast = "";
      this._render();
    }, 6000);
  }

  async _action(fn) {
    if (this._busy) return;
    this._busy = true;
    this._render();
    try {
      await fn();
    } catch (err) {
      this._notify(`${this.t.error}: ${err.message || err.code || err}`);
    }
    this._busy = false;
    this._render();
  }

  // ------------------------------------------------------------------ layout
  _render() {
    const t = this.t;
    const scroller = this.shadowRoot.querySelector(".content");
    const scroll = scroller ? scroller.scrollTop : 0;
    if (this._data && !this._expanded) {
      this._expanded = new Set(this._data.findings.filter((f) => ["critical", "high"].includes(f.severity)).map((f) => f.id));
    }
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div class="app">
        <header class="appbar">
          <div class="appbar-row">
            <ha-menu-button></ha-menu-button>
            <div class="brand">${SHIELD}<div class="brand-text"><div class="brand-name">Bastion</div><div class="brand-sub">${esc(t.subtitle)}</div></div></div>
            <div class="grow"></div>
            <div class="pills">${this._alarmPill()}${this._data ? this._headerScore() : ""}</div>
          </div>
          <nav class="tabs" role="tablist">
            ${Object.keys(t.tabs).map((tab) => `
              <button class="tab ${this._tab === tab ? "active" : ""}" data-tab="${tab}" role="tab" aria-selected="${this._tab === tab}">
                ${icon(TAB_ICON[tab])}<span>${esc(t.tabs[tab])}</span>
              </button>`).join("")}
          </nav>
        </header>
        <main class="content"><div class="container">${this._data ? this._renderTab() : `<div class="loading"><span class="spinner"></span></div>`}</div></main>
      </div>
      ${this._modal ? this._renderModal() : ""}
      ${this._toast ? `<div class="toast">${icon("mdi:information-outline")}<span>${esc(this._toast)}</span></div>` : ""}
      <div class="tip" hidden></div>
    `;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) {
      menu.hass = this._hass;
      menu.narrow = this._narrow;
    }
    const content = this.shadowRoot.querySelector(".content");
    if (content) content.scrollTop = scroll;
    this._bind();
    this._bindAlarm();
    this._tickCountdown();
  }

  _head(page, actions = "", extra = "") {
    const [title, desc] = this.t.pages[page];
    return `
      <div class="page-head">
        <div class="page-title"><h1>${esc(title)}</h1><p>${esc(desc)}${extra ? ` <span class="sep">·</span> ${extra}` : ""}</p></div>
        ${actions ? `<div class="page-actions">${actions}</div>` : ""}
      </div>`;
  }

  _alarmPill() {
    const entity = this._hass && this._alarmEntity();
    if (!entity) return "";
    const st = entity.state;
    const a = this.t.alarm;
    const color = this._alarmColor(st);
    return `<button class="pill alarm-pill" data-tab="alarm" style="--c:${color}"><span class="pill-dot"></span>${esc(a.states[st] || st)}</button>`;
  }

  _tickCountdown() {
    clearInterval(this._countdown);
    const until = this._alarm?.status?.until;
    const st = this._alarm?.status?.state;
    if (this._tab !== "alarm" || !until || !["arming", "pending", "triggered"].includes(st)) return;
    const el = this.shadowRoot.querySelector(".countdown");
    const bar = this.shadowRoot.querySelector(".countdown-bar > div");
    const total = Math.max(1, (new Date(until) - new Date(this._alarm.status.since)) / 1000);
    const update = () => {
      const left = Math.max(0, Math.round((new Date(until) - Date.now()) / 1000));
      if (el && st !== "triggered") el.textContent = (st === "arming" ? this.t.alarm.arming_in : this.t.alarm.alarm_in).replace("{n}", left);
      if (bar) bar.style.width = `${Math.max(0, Math.min(100, (left / total) * 100))}%`;
      if (left <= 0) {
        clearInterval(this._countdown);
        setTimeout(() => this._refreshAlarm(), 800);
      }
    };
    update();
    this._countdown = setInterval(update, 1000);
  }

  _scoreState(score) {
    if (score >= 90) return "good";
    if (score >= 70) return "warning";
    if (score >= 50) return "serious";
    return "critical";
  }

  _stateColor(state) {
    return { good: GOOD, warning: SEV.medium.color, serious: SEV.high.color, critical: SEV.critical.color }[state];
  }

  _headerScore() {
    const s = this._data.summary;
    if (!s.last_audit) return "";
    const state = this._scoreState(s.score);
    return `<button class="pill" data-tab="overview" style="--c:${this._stateColor(state)}"><span class="pill-dot"></span><b class="num">${esc(s.score)}</b><span class="pill-label">${esc(this.t.score_label[state])}</span></button>`;
  }

  _renderTab() {
    switch (this._tab) {
      case "alarm": return this._renderAlarm();
      case "logins": return this._renderLogins();
      case "git": return this._renderGit();
      case "anomaly": return this._renderAnomaly();
      case "external": return this._renderExternal();
      default: return this._renderOverview();
    }
  }

  // ---------------------------------------------------------------- overview
  _ring(score, hasAudit) {
    const t = this.t;
    const state = this._scoreState(score);
    const color = this._stateColor(state);
    const r = 52;
    const c = 2 * Math.PI * r;
    const fill = hasAudit ? (Math.max(0, Math.min(100, score)) / 100) * c : 0;
    return `
      <div class="ring" data-tip="${esc(t.score)}: ${esc(hasAudit ? score : "—")}">
        <svg viewBox="0 0 128 128" width="128" height="128" aria-hidden="true">
          <circle cx="64" cy="64" r="${r}" fill="none" stroke="${color}" stroke-opacity="0.18" stroke-width="12"/>
          <circle cx="64" cy="64" r="${r}" fill="none" stroke="${color}" stroke-width="12" stroke-linecap="round"
            stroke-dasharray="${fill} ${c}" transform="rotate(-90 64 64)"/>
        </svg>
        <div class="ring-text"><div class="ring-value">${hasAudit ? esc(score) : "—"}</div><div class="ring-unit">/ 100</div></div>
        <div class="ring-label">${hasAudit ? `${icon("mdi:circle", color)}${esc(t.score_label[state])}` : ""}</div>
      </div>`;
  }

  _sparkline(history) {
    const t = this.t;
    if (!history || history.length < 2) return `<div class="muted small">${esc(t.no_trend)}</div>`;
    const w = 280;
    const h = 56;
    const pad = 6;
    const xs = (i) => pad + (i * (w - 2 * pad)) / (history.length - 1);
    const lo = Math.max(0, Math.min(...history.map((p) => p.score)) - 10);
    const hi = Math.min(100, Math.max(...history.map((p) => p.score)) + 5);
    const ys = (v) => pad + (1 - (v - lo) / Math.max(1, hi - lo)) * (h - 2 * pad);
    const points = history.map((p, i) => `${xs(i).toFixed(1)},${ys(p.score).toFixed(1)}`).join(" ");
    const last = history[history.length - 1];
    const hits = history
      .map((p, i) => `<rect x="${(xs(i) - (w - 2 * pad) / (history.length - 1) / 2).toFixed(1)}" y="0" width="${((w - 2 * pad) / (history.length - 1)).toFixed(1)}" height="${h}" fill="transparent" data-tip="${esc(p.date)}: ${esc(p.score)}"></rect>`)
      .join("");
    return `
      <div class="trend">
        <div class="muted small">${esc(t.trend)}</div>
        <svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none" role="img" aria-label="${esc(t.trend)}">
          ${hi >= 90 && lo <= 90 ? `<line x1="${pad}" x2="${w - pad}" y1="${ys(90)}" y2="${ys(90)}" class="gridline"/>` : ""}
          <polyline points="${points}" fill="none" class="spark" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
          <circle cx="${xs(history.length - 1)}" cy="${ys(last.score)}" r="4" class="spark-dot"/>
          ${hits}
        </svg>
      </div>`;
  }

  _renderOverview() {
    const t = this.t;
    const { summary, findings, history, report } = this._data;
    const active = findings.filter((f) => !f.dismissed);
    const visible = findings.filter(
      (f) => (this._showDismissed || !f.dismissed) && (this._filter === "all" || f.severity === this._filter)
    );
    const counts = summary.counts;
    const chips = ["all", "critical", "high", "medium", "low"].map((key) => {
      const n = key === "all" ? active.length : counts[key] || 0;
      const label = key === "all" ? t.all : t.severity[key];
      return `<button class="chip ${this._filter === key ? "on" : ""}" data-filter="${key}">
        ${key === "all" ? "" : icon(SEV[key].icon, SEV[key].color)}${esc(label)} <span class="count">${esc(n)}</span></button>`;
    });
    const actions = `
      <button class="btn" data-action="report">${icon("mdi:file-chart-outline")}<span>${esc(t.send_report)}</span></button>
      <button class="btn primary" data-action="audit" ${this._busy || summary.running ? "disabled" : ""}>
        ${icon("mdi:shield-search")}<span>${esc(summary.running || this._busy ? t.running : t.run_audit)}</span></button>`;
    return `
      ${this._head("overview", actions, `${esc(t.last_audit)} ${esc(this.rel(summary.last_audit))}`)}
      <section class="card hero">
        ${this._ring(summary.score, !!summary.last_audit)}
        <div class="hero-side">
          <div class="tiles">
            ${["critical", "high", "medium", "low"].map((key) => `
              <div class="tile">
                <div class="tile-head">${icon(SEV[key].icon, SEV[key].color)}<span>${esc(t.severity[key])}</span></div>
                <div class="tile-value">${esc(counts[key] || 0)}</div>
              </div>`).join("")}
          </div>
          ${this._sparkline(history)}
        </div>
      </section>
      ${summary.errors && summary.errors.length ? `<div class="banner">${icon("mdi:alert-outline")}<div>${summary.errors.map(esc).join("<br>")}</div></div>` : ""}
      <div class="filters">
        ${chips.join("")}
        <label class="switch"><input type="checkbox" data-action="toggle-dismissed" ${this._showDismissed ? "checked" : ""}><span>${esc(t.show_dismissed)}</span></label>
      </div>
      ${visible.length === 0
        ? `<div class="card empty">${icon("mdi:shield-check", GOOD)}<div>${esc(t.no_findings)}</div></div>`
        : `<div class="card findings">${visible.map((f) => this._renderFinding(f)).join("")}</div>`}
      ${report ? `
        <details class="card report">
          <summary>${icon("mdi:file-chart-outline")}<b>${esc(t.last_report)}</b><span class="muted small">${esc(this.rel(report.time))}</span></summary>
          <div class="report-title">${esc(report.title)}</div>
          <pre class="report-body">${esc(report.message)}</pre>
        </details>` : ""}
    `;
  }

  _renderFinding(f) {
    const t = this.t;
    const sev = SEV[f.severity] || SEV.info;
    const integrity = ["custom_code_changed", "custom_new", "www_changed"].includes(f.check);
    const domain = f.check === "www_changed" ? "www" : f.data?.domain || "";
    const open = this._expanded.has(f.id);
    return `
      <article class="finding ${open ? "open" : ""} ${f.dismissed ? "dismissed" : ""}" style="--sev:${sev.color}">
        <button class="f-row" data-toggle="${esc(f.id)}" aria-expanded="${open}">
          <span class="sev-badge">${icon(sev.icon)}</span>
          <span class="f-main">
            <span class="f-title">${esc(f.title)}</span>
            <span class="f-meta"><span class="sev-label">${esc(t.severity[f.severity] || f.severity)}</span>
              <span class="sep">·</span>${icon(CATEGORY_ICON[f.category] || "mdi:shield-outline")}${esc(t.category[f.category] || f.category)}
              <span class="sep">·</span><span data-tip="${fmtTime(f.first_seen)}">${esc(t.since)} ${esc(this.rel(f.first_seen))}</span></span>
          </span>
          <ha-icon class="chevron" icon="mdi:chevron-down"></ha-icon>
        </button>
        ${open ? `
          <div class="f-body">
            <p class="desc">${esc(f.description)}</p>
            ${f.recommendation ? `<div class="advice">${icon("mdi:lightbulb-on-outline")}<span>${esc(f.recommendation)}</span></div>` : ""}
            <div class="f-actions">
              ${integrity ? `<button class="btn small" data-action="accept" data-domain="${esc(domain)}">${icon("mdi:check-decagram-outline")}<span>${esc(t.accept)}</span></button>` : ""}
              <button class="btn small ghost" data-action="dismiss" data-id="${esc(f.id)}" data-dismissed="${f.dismissed ? "0" : "1"}">
                ${icon(f.dismissed ? "mdi:eye-outline" : "mdi:eye-off-outline")}<span>${esc(f.dismissed ? t.undismiss : t.dismiss)}</span></button>
            </div>
          </div>` : ""}
      </article>`;
  }

  // ------------------------------------------------------------------ logins
  _bars(values) {
    const t = this.t;
    const max = Math.max(1, ...values);
    const w = 288;
    const h = 64;
    const bw = w / values.length;
    return `
      <svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" preserveAspectRatio="none" role="img" aria-label="${esc(t.failed_chart)}">
        <line x1="0" x2="${w}" y1="${h - 0.5}" y2="${h - 0.5}" class="gridline"/>
        ${values.map((v, i) => {
          const bh = v ? Math.max(3, (v / max) * (h - 4)) : 0;
          const hoursAgo = values.length - 1 - i;
          return `<g data-tip="-${hoursAgo} h: ${esc(v)}">
            <rect x="${i * bw}" y="0" width="${bw}" height="${h}" fill="transparent"></rect>
            ${bh ? `<path d="${barPath(i * bw + 1, h, bw - 2, bh)}" class="bar"></path>` : ""}
          </g>`;
        }).join("")}
      </svg>`;
  }

  _renderLogins() {
    const t = this.t;
    if (!this._logins) return `<div class="loading"><span class="spinner"></span></div>`;
    const { log, tokens, stats } = this._logins;
    const week = Date.now() - 7 * 86400 * 1000;
    const recent = log.filter((e) => (toDate(e.time)?.getTime() || 0) >= week);
    const okCount = recent.filter((e) => e.type === "login").length;
    const blocked = recent.filter((e) => e.type === "blocked" || e.type === "ip_banned").length;
    return `
      ${this._head("logins")}
      <div class="grid3">
        <section class="card stat">
          <div class="tile-head">${icon("mdi:account-cancel-outline", SEV.high.color)}<span>${esc(t.failed_24h)}</span></div>
          <div class="tile-value">${esc(stats.failed_24h)}</div>
          ${this._bars(stats.failed_per_hour)}
          <div class="muted small">${esc(t.top_sources)}: ${stats.top_sources.map(([ip, c]) => `${esc(ip)} (${esc(c)})`).join(", ") || "—"}</div>
        </section>
        <section class="card stat">
          <div class="tile-head">${icon("mdi:login", GOOD)}<span>${esc(t.logins_7d)}</span></div>
          <div class="tile-value">${esc(okCount)}</div>
        </section>
        <section class="card stat">
          <div class="tile-head">${icon("mdi:block-helper", SEV.critical.color)}<span>${esc(t.blocked)}</span></div>
          <div class="tile-value">${esc(blocked)}</div>
        </section>
      </div>
      <h2>${icon("mdi:key-chain-variant")}${esc(t.tokens)}</h2>
      <div class="list card">
        ${tokens.map((tk) => `
          <div class="row">
            ${icon(tk.type === "long_lived_access_token" ? "mdi:key-variant" : "mdi:cellphone-key")}
            <div class="row-main">
              <div><b>${esc(tk.name || "—")}</b> <span class="chip tiny">${esc(tk.type === "long_lived_access_token" ? t.llat : t.session)}</span></div>
              <div class="muted small">${esc(tk.user)} · ${esc(t.created)} ${esc(this.rel(tk.created_at))} · ${esc(t.last_used)} ${tk.last_used_at ? esc(this.rel(tk.last_used_at)) : esc(t.never)}${tk.last_used_ip ? ` · ${esc(tk.last_used_ip)}` : ""}</div>
            </div>
            <button class="btn small ghost danger" data-action="block" data-token="${esc(tk.id)}">${icon("mdi:key-remove")}${esc(t.revoke)}</button>
          </div>`).join("") || `<div class="row muted">—</div>`}
      </div>
      <h2>${icon("mdi:timeline-text-outline")}${esc(t.log)}</h2>
      <div class="list card timeline">
        ${log.slice(0, 200).map((e) => {
          const [ic, color] = LOG_ICON[e.type] || ["mdi:circle-small", "#8a8f98"];
          const who = e.user || e.name || "";
          const detail = e.client || e.result || e.user_agent || e.agent || "";
          const canBlock = (e.ip && e.ip !== "?") || e.token_id;
          return `
            <div class="row">
              ${icon(ic, color)}
              <div class="row-main">
                <div><b>${esc(t.types[e.type] || e.type)}</b> ${who ? `· ${esc(who)}` : ""} ${e.ip ? `<span class="chip tiny mono">${esc(e.ip)}${e.geo ? ` · ${esc(e.geo)}` : ""}</span>` : ""}</div>
                <div class="muted small" data-tip="${fmtTime(e.time)}">${esc(this.rel(e.time))}${detail ? ` · ${esc(detail)}` : ""}</div>
              </div>
              ${canBlock && !["blocked", "confirmed", "token_removed"].includes(e.type)
                ? `<button class="btn small ghost danger" data-action="block" data-ip="${esc(e.ip && e.ip !== "?" ? e.ip : "")}" data-token="${esc(e.token_id || "")}">${icon("mdi:block-helper")}${esc(t.block)}</button>`
                : ""}
            </div>`;
        }).join("") || `<div class="row muted">—</div>`}
      </div>
    `;
  }

  // --------------------------------------------------------------------- git
  _renderGit() {
    const t = this.t;
    const g = this._data.git;
    if (g.status === "disabled") return `${this._head("git")}<div class="card empty">${icon("mdi:source-branch")}<div>${esc(t.git_disabled)}</div></div>`;
    const statusColor = { ok: GOOD, pending: SEV.medium.color, error: SEV.high.color, blocked: SEV.critical.color }[g.status] || "#8a8f98";
    const statusIcon = { ok: "mdi:check-circle", pending: "mdi:progress-upload", error: "mdi:alert", blocked: "mdi:lock-alert" }[g.status] || "mdi:circle";
    const commits = this._git?.commits || [];
    return `
      ${this._head("git", `<button class="btn" data-action="refresh-git">${icon("mdi:refresh")}<span>${esc(t.refresh)}</span></button>`)}
      <section class="card git-status">
        <div class="git-head">
          <span class="chip big">${icon(statusIcon, statusColor)}${esc(t.git_status[g.status] || g.status)}</span>
          <span class="muted small">${esc(t.last_commit)}: ${esc(this.rel(g.last_commit_time))}</span>
        </div>
        ${g.last_error ? `<div class="banner">${icon("mdi:alert-outline")}<div>${esc(g.last_error)}</div></div>` : ""}
        <dl class="facts">
          <dt>${esc(t.repo)}</dt><dd class="mono">${esc(g.url)}</dd>
          <dt>${esc(t.branch)}</dt><dd class="mono">${esc(g.branch)}</dd>
          <dt>${esc(t.privacy)}</dt><dd>${icon(g.privacy === "private" ? "mdi:lock" : "mdi:lock-open-alert", g.privacy === "private" ? GOOD : SEV.high.color)}${esc(t.privacy_values[g.privacy] || g.privacy || "—")}</dd>
          <dt>${esc(t.encryption)}</dt><dd>${icon(g.encryption ? "mdi:shield-key" : "mdi:shield-off-outline", g.encryption ? GOOD : SEV.high.color)}${esc(g.encryption ? t.encrypted_on : t.encrypted_off)}</dd>
          <dt>${esc(t.host_key)}</dt><dd class="mono small">${esc(g.host_key_fp || "—")}</dd>
        </dl>
      </section>
      ${g.public_key ? `
        <section class="card">
          <h3 class="card-title">${icon("mdi:key-chain")}${esc(t.deploy_key)}</h3>
          <div class="secret"><code>${esc(g.public_key)}</code><button class="btn small" data-copy="${esc(g.public_key)}">${icon("mdi:content-copy")}${esc(t.copy)}</button></div>
          <div class="muted small">${esc(t.deploy_key_help)}</div>
        </section>` : ""}
      <div class="actionbar">
        <input class="input grow" id="commit-message" placeholder="${esc(t.commit_message)}">
        <button class="btn primary" data-action="commit" ${this._busy ? "disabled" : ""}>${icon("mdi:source-commit-local")}<span>${esc(this._busy ? t.running : t.commit_now)}</span></button>
      </div>
      <div class="split">
        <section class="card list commits">
          <h3 class="card-title">${icon("mdi:history")}${esc(t.history)}</h3>
          ${this._git?.error ? `<div class="banner">${icon("mdi:alert-outline")}<div>${esc(this._git.error)}</div></div>` : ""}
          ${commits.map((c) => `
            <button class="commit ${this._commit === c.sha ? "selected" : ""}" data-action="select-commit" data-sha="${esc(c.sha)}">
              ${icon(c.pushed ? "mdi:source-commit" : "mdi:source-commit-local", c.pushed ? "var(--primary-color)" : SEV.medium.color)}
              <div class="row-main">
                <div class="commit-summary">${esc(c.summary)}</div>
                <div class="muted small"><span class="mono">${esc(c.short)}</span> · ${esc(this.rel(c.time))} · ${esc(c.changes)} ${esc(t.changes)}${c.pushed ? "" : ` · ${esc(t.not_pushed)}`}</div>
              </div>
            </button>`).join("")}
        </section>
        <section class="card detail">${this._commit ? this._renderCommit() : `<div class="empty small">${icon("mdi:cursor-default-click-outline")}<div>${esc(t.pick_commit)}</div></div>`}</section>
      </div>
    `;
  }

  _renderCommit() {
    const t = this.t;
    if (!this._files) return `<div class="loading">${icon("mdi:file-search-outline")}</div>`;
    const areas = [...new Set(this._files.map((f) => f.area).filter((a) => a && a !== "inventory"))];
    const files = this._onlyChanged ? this._files.filter((f) => f.status !== "same") : this._files;
    const statusColor = { same: "#8a8f98", changed: SEV.medium.color, deleted_locally: SEV.high.color, new_locally: "var(--primary-color)", unknown: "#8a8f98" };
    return `
      <h3 class="card-title">${icon("mdi:file-tree-outline")}${esc(t.files)} <span class="mono">${esc(this._commit.slice(0, 8))}</span></h3>
      <div class="restore">
        <div class="area-chips">
          ${areas.map((a) => `<label class="chip check"><input type="checkbox" class="area" value="${esc(a)}"><span>${esc(t.areas[a] || a)}</span></label>`).join("")}
        </div>
        <label class="switch"><input type="checkbox" id="restart"><span>${esc(t.restart_after)}</span></label>
        <div class="actionbar tight">
          <button class="btn danger" data-action="restore-all">${icon("mdi:backup-restore")}${esc(t.restore_all)}</button>
          <button class="btn" data-action="restore-areas">${icon("mdi:folder-refresh-outline")}${esc(t.restore_selected)}</button>
          <span class="grow"></span>
          <label class="switch"><input type="checkbox" data-action="only-changed" ${this._onlyChanged ? "checked" : ""}><span>${esc(t.only_changed)}</span></label>
        </div>
      </div>
      <div class="files">
        ${files.map((f) => `
          <div class="file ${this._diffPath === f.path ? "selected" : ""}">
            <button class="link" data-action="diff" data-path="${esc(f.path)}">${icon(f.encrypted ? "mdi:file-lock-outline" : "mdi:file-document-outline")}<span class="mono">${esc(f.path)}</span></button>
            <span class="chip tiny" style="--c:${statusColor[f.status] || "#8a8f98"}">${esc(t.status[f.status] || f.status)}</span>
            ${f.status !== "new_locally" && f.area !== "inventory" ? `<button class="btn small ghost" data-action="restore-file" data-path="${esc(f.path)}">${icon("mdi:restore")}${esc(t.restore_file)}</button>` : ""}
          </div>`).join("") || `<div class="muted small">—</div>`}
      </div>
      ${this._diff ? `<pre class="diff">${this._diff}</pre>` : ""}
    `;
  }

  // ------------------------------------------------------------ anomalies
  _renderCanary(c) {
    const t = this.t;
    if (!c || !c.enabled) return `<section class="card">${`<h3 class="card-title">${icon("mdi:bird")}${esc(t.canary)}</h3>`}<div class="muted">${esc(t.canary_off)}</div></section>`;
    const state = c.alarm
      ? `<span class="chip big alarm">${icon("mdi:alarm-light", SEV.critical.color)}${esc(t.canary_alarm)}</span>`
      : `<span class="chip big">${icon("mdi:shield-check", GOOD)}${esc(t.canary_active)}</span>`;
    const masked = (value) => (this._reveal ? value : `${value.slice(0, 12)}••••••••••••${value.slice(-6)}`);
    return `
      <section class="card ${c.alarm ? "alarm-card" : ""}">
        <div class="git-head"><h3 class="card-title">${icon("mdi:bird")}${esc(t.canary)}</h3>${state}</div>
        <div class="muted small">${esc(t.canary_help)}</div>
        ${c.token ? `
          <div class="label">${esc(t.canary_token)}</div>
          <div class="secret"><code>${esc(masked(c.token))}</code>
            <button class="btn small ghost" data-action="reveal">${icon(this._reveal ? "mdi:eye-off-outline" : "mdi:eye-outline")}${esc(this._reveal ? t.hide : t.show)}</button>
            <button class="btn small" data-copy="${esc(c.token)}">${icon("mdi:content-copy")}${esc(t.copy)}</button></div>` : ""}
        ${c.webhook_url ? `
          <div class="label">${esc(t.canary_webhook)}</div>
          <div class="secret"><code>${esc(c.webhook_url)}</code><button class="btn small" data-copy="${esc(c.webhook_url)}">${icon("mdi:content-copy")}${esc(t.copy)}</button></div>` : ""}
        <div class="label">${esc(t.canary_worker)}</div>
        ${c.worker ? `<div class="muted small">${esc(t.canary_worker_help)}</div>
          <div class="secret"><code>${esc(masked(c.worker.token))}</code>
            <button class="btn small" data-copy="${esc(c.worker.token)}">${icon("mdi:content-copy")}${esc(t.copy)}</button></div>
          <div class="secret"><code>${esc(c.worker.webhook)}</code><button class="btn small" data-copy="${esc(c.worker.webhook)}">${icon("mdi:content-copy")}${esc(t.copy)}</button></div>`
          : `<div class="muted small">${esc(t.canary_worker_off)}</div>`}
        <div class="label">${esc(t.canary_triggers)}</div>
        ${c.triggers.length ? c.triggers.map((tr) => `
          <div class="row">${icon("mdi:alarm-light-outline", SEV.critical.color)}
            <div class="row-main"><div><b>${esc(t.types[tr.via] || tr.via)}</b> <span class="chip tiny mono">${esc(tr.ip)}</span></div>
            <div class="muted small" data-tip="${fmtTime(tr.time)}">${esc(this.rel(tr.time))} · ${esc(tr.agent || "")}</div></div>
            ${tr.ip && tr.ip !== "?" ? `<button class="btn small ghost danger" data-action="block" data-ip="${esc(tr.ip)}">${icon("mdi:block-helper")}${esc(t.block)}</button>` : ""}
          </div>`).join("") : `<div class="muted small">${esc(t.no_triggers)}</div>`}
      </section>`;
  }

  _renderAnomaly() {
    const t = this.t;
    const a = this._data.anomaly;
    return `
      ${this._head("anomaly")}
      ${this._renderCanary(this._data.canary)}
      <div class="grid3">
        <section class="card stat">
          <div class="tile-head">${icon("mdi:shield-alert-outline", a.sabotage ? SEV.critical.color : GOOD)}<span>${esc(t.sabotage)}</span></div>
          <div class="tile-value">${esc(a.sabotage ? t.yes : t.no)}</div>
        </section>
        <section class="card stat">
          <div class="tile-head">${icon("mdi:school-outline")}<span>${esc(t.learning_since)}</span></div>
          <div class="tile-sub">${esc(this.rel(a.learning_since))}</div>
        </section>
      </div>
      <h2>${icon("mdi:chart-bell-curve")}${esc(t.sensors)}</h2>
      <div class="list card">
        ${a.sensors.length === 0 ? `<div class="row muted">${esc(t.no_sensors)}</div>` : a.sensors.map((s) => `
          <div class="row">
            ${icon(s.active.length ? "mdi:alert-decagram" : "mdi:check-decagram-outline", s.active.length ? SEV.high.color : GOOD)}
            <div class="row-main">
              <div><b>${esc(s.name)}</b> ${s.active.map((x) => `<span class="chip tiny" style="--c:${SEV.high.color}">${esc(t.types[x.type] || x.type)}</span>`).join(" ")}</div>
              <div class="meter" data-tip="${esc(s.learned_buckets)}/48 ${esc(t.learned)}"><div style="width:${Math.round((s.learned_buckets / 48) * 100)}%"></div></div>
              <div class="muted small">${esc(s.samples)} ${esc(t.samples)} · ${esc(s.learned_buckets)}/48 ${esc(t.learned)}</div>
            </div>
          </div>`).join("")}
      </div>
      <h2>${icon("mdi:timeline-alert-outline")}${esc(t.events)}</h2>
      <div class="list card timeline">
        ${a.events.length === 0 ? `<div class="row muted">${esc(t.no_events)}</div>` : a.events.map((e) => {
          const [ic, color] = LOG_ICON[e.type] || ["mdi:alert-circle-outline", SEV.medium.color];
          return `<div class="row">${icon(ic, color)}
            <div class="row-main"><div><b>${esc(t.types[e.type] || e.type)}</b> ${esc(e.name || e.actor || e.user || e.entity || e.target || "")}</div>
            <div class="muted small" data-tip="${fmtTime(e.time)}">${esc(this.rel(e.time))} · ${esc(e.detail || e.reason || e.entities || "")}</div></div></div>`;
        }).join("")}
      </div>
      ${a.outbound.enabled ? `
        <h2>${icon("mdi:transit-connection-variant")}${esc(t.outbound)}</h2>
        <div class="list card">${a.outbound.new.map((o) => `
          <div class="row">${icon("mdi:server-network")}<div class="row-main"><div><b>${esc(o.host || o.ip)}</b> <span class="chip tiny mono">${esc(o.network)}</span></div>
          <div class="muted small">${esc(this.rel(o.time))}</div></div></div>`).join("") || `<div class="row muted">—</div>`}</div>` : ""}
    `;
  }

  // ------------------------------------------------------------- external
  _renderExternal() {
    const t = this.t;
    const probe = this._data.probe;
    return `
      ${this._head("external", `<button class="btn primary" data-action="probe" ${this._busy ? "disabled" : ""}>${icon("mdi:web-check")}<span>${esc(this._busy ? t.running : t.run_probe)}</span></button>`, probe ? esc(this.rel(probe.time)) : "")}
      ${!probe ? `<div class="card empty">${icon("mdi:web-off")}<div>${esc(t.probe_none)}</div></div>`
        : probe.error ? `<div class="banner">${icon("mdi:alert-outline")}<div>${esc(probe.error)}</div></div>`
        : `<section class="card">
            <div class="git-head"><span class="muted">${esc(t.public_ip)}</span><span class="chip big mono">${esc(probe.ip)}</span></div>
            <div class="ports">
              ${(probe.results || []).map((r) => `
                <div class="port ${r.open ? "open" : ""}" data-tip="${esc(r.ms ?? "")} ms">
                  ${icon(r.open ? "mdi:lock-open-alert" : "mdi:lock", r.open ? SEV.critical.color : GOOD)}
                  <div><b>${esc(r.port)}</b><div class="muted small">${esc(PORT_NAMES[r.port] || "")}</div></div>
                  <span class="small">${esc(r.open ? t.open : t.closed)}</span>
                </div>`).join("")}
            </div>
          </section>`}
    `;
  }


  // ------------------------------------------------------------------- alarm
  _alarmColor(state) {
    if (state === "triggered") return SEV.critical.color;
    if (state === "pending" || state === "arming") return SEV.medium.color;
    if (state && state.startsWith("armed_")) return "var(--primary-color)";
    return GOOD;
  }

  _sensorState(entityId) {
    const st = this._hass.states[entityId];
    if (!st || ["unavailable", "unknown"].includes(st.state)) return "unavailable";
    return ["on", "open", "opening", "unlocked", "detected", "wet", "home"].includes(st.state) ? "open" : "closed";
  }

  _renderAlarm() {
    if (!this._alarm) return `<div class="loading"><span class="spinner"></span></div>`;
    return this._alarmView === "settings" ? this._renderAlarmSettings() : this._renderAlarmStatus();
  }

  _renderAlarmStatus() {
    const a = this.t.alarm;
    const { status, config, log } = this._alarm;
    const st = status.state;
    const color = this._alarmColor(st);
    const stateIcon = {
      disarmed: "mdi:shield-off-outline", arming: "mdi:shield-sync-outline", armed_home: "mdi:home-lock",
      armed_night: "mdi:weather-night", armed_away: "mdi:shield-lock", pending: "mdi:timer-sand", triggered: "mdi:alarm-light",
    }[st] || "mdi:shield";
    const activeMode = st === "disarmed" ? "off" : status.target || status.mode;
    const lastBy = [...log].find((e) => e.user);
    const trig = status.triggered_by;
    const modes = [
      ["off", "mdi:shield-off-outline"], ["home", "mdi:home-lock"], ["night", "mdi:weather-night"], ["away", "mdi:shield-lock"],
    ];
    const rooms = config.rooms || [];
    return `
      ${this._head("alarm", `<button class="btn" data-action="alarm-settings">${icon("mdi:cog-outline")}<span>${esc(a.settings)}</span></button>`)}
      <section class="card alarm-hero ${st === "triggered" ? "pulse" : ""}" style="--state:${color}">
        <div class="alarm-badge">${icon(stateIcon)}</div>
        <div class="alarm-main">
          <div class="alarm-state">${esc(a.states[st] || st)}</div>
          <div class="muted">${esc(a.since)} ${esc(this.rel(status.since))}${lastBy ? ` · ${esc(a.by)} ${esc(lastBy.user)}` : ""}</div>
          ${["arming", "pending", "triggered"].includes(st) && status.until ? `
            <div class="countdown-wrap"><div class="countdown">${st === "triggered" ? "" : "…"}</div>
            <div class="countdown-bar"><div></div></div></div>` : ""}
          ${trig && (st === "pending" || st === "triggered") ? `
            <div class="trigger-info">${icon("mdi:map-marker-alert-outline")}<span>${esc(a.triggered_by)}: <b>${esc(trig.name || trig.reason)}</b>${trig.room ? ` · ${esc(trig.room)}` : ""}</span></div>` : ""}
          ${status.locked ? `<div class="banner">${icon("mdi:lock-clock")}<div>${esc(this.t.alarm.code)}: ${esc(status.locked)} s</div></div>` : ""}
        </div>
      </section>
      <div class="mode-grid">
        ${modes.map(([key, ic]) => `
          <button class="mode ${activeMode === key ? "active" : ""}" data-mode="${key}" style="--mc:${key === "off" ? GOOD : st === "triggered" ? SEV.critical.color : "var(--primary-color)"}" ${this._busy ? "disabled" : ""}>
            ${icon(ic)}<span class="mode-name">${esc(a.modes[key])}</span><span class="mode-hint">${esc(a.mode_hint[key])}</span>
          </button>`).join("")}
      </div>
      ${(this._alarm.household || []).length ? `
      <h2>${icon("mdi:account-group")}${esc(a.people)}</h2>
      <div class="people-strip">${this._alarm.household.map((p) => `<span class="chip big" ${p.home ? `style="--c:${GOOD}"` : ""}>${icon(p.home ? "mdi:home-account" : p.home === false ? "mdi:home-export-outline" : "mdi:help-circle-outline", p.home ? GOOD : undefined)}${esc(p.name)}<span class="muted small">${esc(p.home ? a.people_home : p.home === false ? a.people_away : a.people_unknown)}</span></span>`).join("")}</div>` : ""}
      <h2>${icon("mdi:floor-plan")}${esc(a.rooms)}</h2>
      ${rooms.length === 0 ? `<div class="card empty">${icon("mdi:floor-plan")}<div>${esc(a.no_rooms)}</div></div>` : `
      <div class="room-grid">
        ${rooms.map((room) => {
          const states = room.sensors.map((e) => this._sensorState(e));
          const openCount = states.filter((x) => x === "open").length;
          const unavailable = states.filter((x) => x === "unavailable").length;
          return `
            <section class="card room ${openCount ? "has-open" : ""}">
              <div class="room-head">
                <span class="room-icon">${icon(room.icon || "mdi:door")}</span>
                <b>${esc(room.name)}</b>
                <span class="grow"></span>
                ${openCount ? `<span class="chip tiny" style="--c:${SEV.medium.color}">${esc(openCount)} ${esc(a.open)}</span>` : `<span class="chip tiny" style="--c:${GOOD}">${esc(a.closed)}</span>`}
                ${unavailable ? `<span class="chip tiny" style="--c:#8a8f98">${esc(unavailable)} ${esc(a.unavailable)}</span>` : ""}
              </div>
              ${room.sensors.map((e) => {
                const cfg = { modes: ["home", "night", "away"], type: "delayed", bypass: false, ...(config.sensors[e] || {}) };
                const sst = this._sensorState(e);
                const dot = sst === "open" ? SEV.medium.color : sst === "unavailable" ? "#8a8f98" : GOOD;
                const name = cfg.name || this._hass.states[e]?.attributes?.friendly_name || e;
                const bypassed = status.bypassed.includes(e);
                return `
                  <div class="sensor">
                    <span class="dot" style="background:${dot}"></span>
                    <span class="sensor-name" data-tip="${esc(e)}">${esc(name)}</span>
                    ${bypassed ? `<span class="chip tiny" style="--c:${SEV.medium.color}">${esc(a.bypassed)}</span>` : ""}
                    <span class="grow"></span>
                    ${cfg.type === "always"
                      ? `<span class="mini always" data-tip="${esc(a.type.always)}">24h</span>`
                      : ["home", "night", "away"].map((m) => `<span class="mini ${cfg.modes.includes(m) ? "on" : ""}" data-tip="${esc(a.modes[m])}">${esc(a.modes[m][0])}</span>`).join("")}
                    ${cfg.exit_delay != null || cfg.entry_delay != null ? `<span class="chip tiny" data-tip="${esc(a.sensor_exit)} ${esc(cfg.exit_delay ?? a.mode_default)} s · ${esc(a.sensor_entry)} ${esc(cfg.entry_delay ?? a.mode_default)} s">${icon("mdi:timer-cog-outline")}</span>` : ""}
                    <span class="type-icon" data-tip="${esc(a.type[cfg.type])}">${icon(cfg.type === "instant" ? "mdi:flash" : cfg.type === "always" ? "mdi:hours-24" : "mdi:timer-outline")}</span>
                  </div>`;
              }).join("")}
            </section>`;
        }).join("")}
      </div>`}
      <h2>${icon("mdi:timeline-clock-outline")}${esc(a.log)}</h2>
      <div class="list card timeline">
        ${log.length === 0 ? `<div class="row muted">${esc(a.no_log)}</div>` : log.slice(0, 40).map((e) => {
          const ic = { triggered: ["mdi:alarm-light", SEV.critical.color], pending: ["mdi:timer-sand", SEV.medium.color], armed: ["mdi:shield-lock", "var(--primary-color)"],
            arming: ["mdi:shield-sync-outline", "var(--primary-color)"], rearmed: ["mdi:shield-refresh", "var(--primary-color)"], disarmed: ["mdi:shield-off-outline", GOOD],
            arm_failed: ["mdi:shield-alert-outline", SEV.high.color], wrong_code: ["mdi:form-textbox-password", SEV.high.color],
            sensor_unavailable: ["mdi:lan-disconnect", "#8a8f98"], acknowledged: ["mdi:hand-back-right-outline", GOOD], unarmed: ["mdi:home-export-outline", SEV.medium.color] }[e.type] || ["mdi:circle-small", "#8a8f98"];
          const label = a.events[e.type] || (a.extra_events || {})[e.type] || a.states[e.type] || e.type;
          const detail = [e.target ? a.modes[e.target] : "", e.name, e.room, e.user ? `${a.by} ${e.user}` : "", (e.sensors || []).join(", "), (e.persons || []).join(", ")].filter(Boolean).join(" · ");
          return `<div class="row">${icon(ic[0], ic[1])}<div class="row-main"><div><b>${esc(label)}</b> ${detail ? `· ${esc(detail)}` : ""}</div>
            <div class="muted small" data-tip="${fmtTime(e.time)}">${esc(this.rel(e.time))}</div></div></div>`;
        }).join("")}
      </div>`;
  }

  _renderModal() {
    const a = this.t.alarm;
    const m = this._modal;
    if (m.type === "open") {
      return `<div class="overlay"><div class="modal">
        <h3 class="card-title">${icon("mdi:door-open", SEV.medium.color)}${esc(a.open_title)}</h3>
        <p class="muted">${esc(a.open_text)}</p>
        <ul class="open-list">${m.sensors.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
        <div class="actionbar tight"><span class="grow"></span>
          <button class="btn" data-modal="cancel">${esc(a.cancel)}</button>
          <button class="btn primary" data-modal="force">${esc(a.force)}</button></div>
      </div></div>`;
    }
    const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "clear", "0", "back"];
    return `<div class="overlay"><div class="modal keypad-modal">
      <h3 class="card-title">${icon("mdi:dialpad")}${esc(a.enter_code)}</h3>
      <div class="code-display">${m.code ? "●".repeat(m.code.length) : `<span class="muted">${esc(a.code)}</span>`}</div>
      ${this._alarm.status.numeric_codes
        ? `<div class="keypad">${keys.map((k) => `<button class="key" data-key="${k}">${k === "clear" ? icon("mdi:close") : k === "back" ? icon("mdi:backspace-outline") : k}</button>`).join("")}</div>`
        : `<input class="input" type="password" id="code-input" autocomplete="off" value="${esc(m.code)}">`}
      <div class="actionbar tight"><span class="grow"></span>
        <button class="btn" data-modal="cancel">${esc(a.cancel)}</button>
        <button class="btn primary" data-modal="ok">${esc(a.ok)}</button></div>
    </div></div>`;
  }

  async _alarmCommand(kind, mode, code, force = false) {
    const payload = kind === "disarm" ? {} : { mode, force };
    if (code) payload.code = code;
    try {
      this._alarm = await this._ws(kind === "disarm" ? "bastion/alarm/disarm" : "bastion/alarm/arm", payload);
      this._modal = null;
    } catch (err) {
      if (err.code === "open_sensors") {
        const sensors = String(err.message).split(": ").slice(1).join(": ").split(", ");
        this._modal = { type: "open", sensors, mode, code };
      } else {
        this._notify(err.message || err.code);
        if (this._modal) this._modal.code = "";
      }
    }
    this._render();
  }

  _modeClicked(key) {
    const status = this._alarm.status;
    const kind = key === "off" ? "disarm" : "arm";
    const needsCode = status.has_codes && (kind === "disarm" || status.require_code_arm || ["triggered", "pending"].includes(status.state));
    if (needsCode) {
      this._modal = { type: "code", kind, mode: key, code: "" };
      this._render();
      return;
    }
    this._action(() => this._alarmCommand(kind, key, null));
  }

  // -------------------------------------------------------- alarm settings
  _renderAlarmSettings() {
    const a = this.t.alarm;
    const d = this._draft;
    const sections = Object.keys(a.sections);
    let body = "";
    if (this._section === "rooms") body = this._settingsRooms(d);
    else if (this._section === "people") body = this._settingsPeople(d);
    else if (this._section === "floorplan") body = this._settingsFloorplan(d);
    else if (this._section === "modes") body = this._settingsModes(d);
    else if (this._section === "actions") body = this._settingsActions(d);
    else if (this._section === "sounds") body = this._settingsSounds(d);
    else if (this._section === "codes") body = this._settingsCodes();
    else body = this._settingsWorker(d);
    const saveable = this._section !== "codes";
    const actions = `
      <button class="btn ghost" data-action="alarm-back">${icon("mdi:arrow-left")}<span>${esc(a.back)}</span></button>
      ${saveable ? `<button class="btn primary" data-action="alarm-save" ${this._busy ? "disabled" : ""}>${icon("mdi:content-save-outline")}<span>${esc(a.save)}</span></button>` : ""}`;
    return `
      ${this._head("settings", actions)}
      <div class="segmented">${sections.map((key) => `<button class="seg-item ${this._section === key ? "on" : ""}" data-section="${key}">${esc(a.sections[key])}</button>`).join("")}</div>
      ${body}`;
  }

  _iconPanel(current) {
    const a = this.t.alarm;
    return `
      <div class="icon-panel">
        <input class="input" data-icon-search placeholder="${esc(a.icon_search)}" autocomplete="off">
        <div class="icon-grid">${ROOM_ICONS.map(([name, words]) => `<button class="icon-opt ${name === current ? "on" : ""}" data-icon-set="${name}" data-words="${esc(words)}" title="${esc(name)}">${icon(name)}</button>`).join("")}</div>
        <div class="icon-custom">
          <span class="label">${esc(a.icon_custom)}</span>
          <input class="input mono" data-icon-custom value="${esc(current)}" placeholder="mdi:…">
          <button class="btn small" data-icon-apply>${esc(a.icon_apply)}</button>
        </div>
      </div>`;
  }

  _sensorNames() {
    const names = [];
    for (const room of this._draft.rooms) {
      for (const e of room.sensors) {
        const own = (this._draft.sensors[e] || {}).name;
        names.push(own || this._hass.states[e]?.attributes?.friendly_name || e);
      }
    }
    return [...new Set(names)].sort((x, y) => x.localeCompare(y));
  }

  _planSvg(plan) {
    const [w, h] = plan.size;
    const pts = (list) => list.map(([x, y]) => `${x},${y}`).join(" ");
    const areas = (plan.areas || []).map((a) => {
      const [x, y, aw, ah] = a.rect;
      const [lx, ly] = a.label_at || [x + aw / 2, y + ah / 2];
      return `<rect x="${x}" y="${y}" width="${aw}" height="${ah}" class="fp-area ${a.outdoor ? "out" : ""}"/>
        <text x="${lx}" y="${ly}" class="fp-label">${esc(a.label)}</text>`;
    }).join("");
    const walls = (plan.walls || []).map((wl) => `<polyline points="${pts(wl.points)}" class="fp-wall ${wl.exterior ? "ext" : ""}"/>`).join("");
    const glass = (plan.glazing || []).map((g) => `<line x1="${g.from[0]}" y1="${g.from[1]}" x2="${g.to[0]}" y2="${g.to[1]}" class="fp-glass"/>`).join("");
    const div = (plan.dividers || []).map((dv) => `<polyline points="${pts(dv)}" class="fp-div"/>`).join("");
    const boxes = (plan.boxes || []).map((b) => `<polygon points="${pts(b.points)}" class="fp-box"/>`).join("");
    const e = plan.entrance ? `<line x1="${plan.entrance.from[0]}" y1="${plan.entrance.from[1]}" x2="${plan.entrance.to[0]}" y2="${plan.entrance.to[1]}" class="fp-door"/>` : "";
    return `<svg class="fp-svg" viewBox="-20 -20 ${w + 40} ${h + 40}" role="img">${areas}${boxes}${div}${walls}${glass}${e}</svg>`;
  }

  _settingsFloorplan(d) {
    const a = this.t.alarm;
    const plan = d.floorplan;
    const importer = `
      <div class="actionbar tight">
        <label class="btn small upload">${icon("mdi:file-upload-outline")}<span>${esc(a.fp_import)}</span><input type="file" accept="application/json,.json" data-fp-file></label>
        ${plan ? `<button class="btn small ghost danger" data-action="fp-remove">${icon("mdi:delete-outline")}${esc(a.fp_remove)}</button>` : ""}
      </div>
      ${plan ? "" : `<textarea class="input fp-text" data-fp-text placeholder="${esc(a.fp_paste)}" spellcheck="false"></textarea>
        <div class="actionbar tight"><button class="btn small" data-action="fp-apply">${esc(a.fp_apply)}</button></div>`}`;
    if (!plan) return `<section class="card"><div class="muted small">${esc(a.fp_help)}</div>${importer}</section>`;
    const rooms = d.rooms.map((r) => r.name);
    const sensors = this._sensorNames();
    // A stored name that no longer exists stays visible instead of silently switching to "automatic".
    const select = (attr, value, options, empty = a.fp_auto) => `<select class="input" ${attr}><option value="">${esc(empty)}</option>
      ${(value && !options.includes(value) ? [value, ...options] : options).map((o) => `<option value="${esc(o)}" ${o === value ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
    return `
      <section class="card">
        <div class="muted small">${esc(a.fp_help)}</div>
        ${importer}
        <div class="fp-wrap">${this._planSvg(plan)}</div>
        <div class="muted small">${esc(a.fp_saved_hint)}</div>
      </section>
      <section class="card">
        <h3 class="card-title">${icon("mdi:floor-plan")}${esc(a.fp_areas)}</h3>
        ${plan.areas.map((ar, i) => `<div class="fp-row"><span>${esc(ar.label)}</span>${select(`data-fp-room="${i}"`, ar.room || "", rooms)}</div>`).join("")}
        ${(plan.glazing || []).length || plan.entrance ? `<h3 class="card-title" style="margin-top:14px">${icon("mdi:door")}${esc(a.fp_doors)}</h3>` : ""}
        ${(plan.glazing || []).map((g, i) => `<div class="fp-row"><span>${esc(g.label || g.id)}</span>${select(`data-fp-glass="${i}"`, g.sensor || "", sensors, a.fp_none)}</div>`).join("")}
        ${plan.entrance ? `<div class="fp-row"><span>${esc(a.fp_entrance)}</span>${select("data-fp-entrance", plan.entrance.sensor || "", sensors, a.fp_none)}</div>` : ""}
      </section>`;
  }

  _settingsPeople(d) {
    const a = this.t.alarm;
    const live = Object.fromEntries((this._alarm.household || []).map((p) => [p.id, p]));
    const chip = (p) => {
      const st = p.id ? live[p.id] : null;
      if (!st) return `<span class="chip tiny">${esc(a.people_new)}</span>`;
      if (st.home === true) return `<span class="chip tiny" style="--c:${GOOD}">${icon("mdi:home-account", GOOD)}${esc(a.people_home)}</span>`;
      if (st.home === false) return `<span class="chip tiny">${icon("mdi:home-export-outline")}${esc(a.people_away)}</span>`;
      return `<span class="chip tiny">${esc(a.people_unknown)}</span>`;
    };
    return `
      <section class="card">
        <div class="muted small">${esc(a.people_help)}</div>
        <div class="people">${d.people.map((p, i) => {
          const st = p.id ? live[p.id] : null;
          const probe = this._probe && this._probe.i === i ? `<div class="person-seen ${this._probe.ok ? "" : "warn-text"}">${esc(this._probe.text)}</div>` : "";
          return `<div class="person-row">
            <span class="room-icon">${icon("mdi:account")}</span>
            <input class="input" data-person-name="${i}" value="${esc(p.name)}" placeholder="${esc(a.person_name)}">
            <div class="person-src">
              <select class="input" data-person-tracker="${i}" title="${esc(a.people_tracker)}">
                <option value="">${esc(a.people_by_ip)}</option>
                ${(this._alarm.trackers || []).map((tr) => `<option value="${esc(tr.entity_id)}" ${p.tracker === tr.entity_id ? "selected" : ""}>${esc(tr.name)} (${esc(tr.state === "home" ? a.people_home : tr.state === "not_home" ? a.people_away : tr.state)})</option>`).join("")}
              </select>
              ${p.tracker ? "" : `<input class="input mono" data-person-ip="${i}" value="${esc(p.ip || "")}" placeholder="192.168.1.20" autocomplete="off">`}
            </div>
            ${chip(p)}
            ${p.tracker ? "<span></span>" : `<button class="btn small" data-person-test="${i}">${icon("mdi:radar")}${esc(a.people_test)}</button>`}
            <button class="btn small ghost danger" data-person-delete="${i}" aria-label="${esc(a.delete)}">${icon("mdi:delete-outline")}</button>
            ${st && st.last_seen ? `<div class="person-seen muted">${esc(a.people_seen)} ${esc(this.rel(st.last_seen))}${st.method ? ` · ${esc(st.method)}` : ""}</div>` : ""}
            ${probe}
          </div>`;
        }).join("")}</div>
        <div class="actionbar"><button class="btn" data-action="person-add">${icon("mdi:account-plus")}${esc(a.people_add)}</button></div>
        <label class="field"><span>${esc(a.people_away_minutes)}</span><input class="input" type="number" min="2" max="60" data-presence-minutes value="${esc(d.presence.away_minutes)}"></label>
        <div class="muted small">${esc(a.people_hint)}</div>
      </section>`;
  }

  _candidateOptions(exclude) {
    const groups = {};
    for (const c of this._alarm.candidates) {
      if (exclude.has(c.entity_id)) continue;
      (groups[c.area || "—"] ||= []).push(c);
    }
    return Object.entries(groups).map(([area, items]) => `<optgroup label="${esc(area)}">${items.map((c) => `<option value="${esc(c.entity_id)}">${esc(c.name)}${c.device_class ? ` (${esc(c.device_class)})` : ""}</option>`).join("")}</optgroup>`).join("");
  }

  _settingsRooms(d) {
    const a = this.t.alarm;
    const used = new Set(d.rooms.flatMap((r) => r.sensors));
    return `
      <div class="actionbar">
        <button class="btn" data-action="room-add">${icon("mdi:plus")}${esc(a.add_room)}</button>
        <button class="btn ghost" data-action="room-import">${icon("mdi:import")}${esc(a.import_areas)}</button>
      </div>
      ${d.rooms.length === 0 ? `<div class="card empty">${icon("mdi:floor-plan")}<div>${esc(a.no_rooms)}</div></div>` : ""}
      ${d.rooms.map((room, ri) => `
        <section class="card edit-room">
          <div class="room-edit-head">
            <button class="room-icon icon-pick ${this._iconFor === ri ? "on" : ""}" data-icon-pick="${ri}" title="${esc(a.choose_icon)}" aria-label="${esc(a.choose_icon)}">${icon(room.icon || "mdi:door")}<span class="pick-caret">${icon("mdi:chevron-down")}</span></button>
            <input class="input grow" data-room-name="${ri}" value="${esc(room.name)}" placeholder="${esc(a.room_name)}">
            <button class="btn small ghost danger" data-room-delete="${ri}">${icon("mdi:delete-outline")}${esc(a.delete)}</button>
          </div>
          ${this._iconFor === ri ? this._iconPanel(room.icon || "mdi:door") : ""}
          ${room.sensors.map((e) => {
            const cfg = { modes: ["home", "night", "away"], type: "delayed", bypass: false, ...(d.sensors[e] || {}) };
            const haName = this._hass.states[e]?.attributes?.friendly_name || e;
            const sst = this._sensorState(e);
            const dot = { open: SEV.medium.color, unavailable: "#8a8f98" }[sst] || GOOD;
            const delayField = (kind, label, hint, ic) => `
              <div class="fld" title="${esc(hint)}">
                <span class="fld-label">${icon(ic)}${esc(label)}</span>
                <div class="suffix"><input type="number" inputmode="numeric" min="0" max="900" placeholder="${esc(a.mode_default)}"
                  data-sensor-delay="${esc(e)}" data-delay-kind="${kind}" value="${cfg[kind] ?? ""}"><span>s</span></div>
              </div>`;
            return `
              <div class="sensor-card">
                <div class="sensor-card-head">
                  <span class="dot" style="background:${dot}" data-tip="${esc(a[sst] || sst)}"></span>
                  <div class="sensor-ident">
                    <input class="name-input" data-sensor-name="${esc(e)}" value="${esc(cfg.name || "")}" placeholder="${esc(haName)}" maxlength="60" aria-label="${esc(a.sensor_name)}" title="${esc(a.sensor_name_hint)}">
                    <div class="mono muted small sensor-id">${esc(e)}${cfg.name ? ` · ${esc(a.ha_name)}: ${esc(haName)}` : ""}</div>
                  </div>
                  <button class="icon-btn" data-sensor-remove="${esc(e)}" data-room="${ri}" title="${esc(a.remove)}" aria-label="${esc(a.remove)}">${icon("mdi:close")}</button>
                </div>
                <div class="sensor-fields">
                  <div class="fld">
                    <span class="fld-label">${icon("mdi:shield-half-full")}${esc(a.watched_in)}</span>
                    <div class="seg">${["home", "night", "away"].map((m) => `<button class="seg-btn ${cfg.modes.includes(m) || cfg.type === "always" ? "on" : ""}" data-sensor-mode="${esc(e)}" data-mode-key="${m}" ${cfg.type === "always" ? "disabled" : ""}>${esc(a.modes[m])}</button>`).join("")}</div>
                  </div>
                  <div class="fld" title="${esc(a.type_hint[cfg.type])}">
                    <span class="fld-label">${icon("mdi:tune-variant")}${esc(a.type_label)}</span>
                    <select class="input type-select" data-sensor-type="${esc(e)}">
                      ${["delayed", "instant", "always"].map((tp) => `<option value="${tp}" ${cfg.type === tp ? "selected" : ""}>${esc(a.type[tp])}</option>`).join("")}
                    </select>
                  </div>
                  ${cfg.type === "always" ? "" : delayField("exit_delay", a.sensor_exit, a.sensor_exit_hint, "mdi:timer-play-outline")}
                  ${cfg.type === "instant" ? "" : delayField("entry_delay", a.sensor_entry, a.sensor_entry_hint, "mdi:timer-alert-outline")}
                  ${cfg.type === "always" ? "" : `
                    <div class="fld" title="${esc(a.may_be_open_hint)}">
                      <span class="fld-label">${icon("mdi:door-open")}${esc(a.when_arming)}</span>
                      <label class="switch"><input type="checkbox" data-sensor-bypass="${esc(e)}" ${cfg.bypass ? "checked" : ""}><span>${esc(a.may_be_open)}</span></label>
                    </div>`}
                </div>
              </div>`;
          }).join("")}
          <select class="input add-sensor" data-room-add-sensor="${ri}"><option value="">${esc(a.add_sensor)}</option>${this._candidateOptions(used)}</select>
        </section>`).join("")}`;
  }

  _settingsModes(d) {
    const a = this.t.alarm;
    return `
      <section class="card">
        <div class="mode-table">
          <div></div><div class="muted small">${esc(a.exit)}</div><div class="muted small">${esc(a.entry)}</div>
          ${["home", "night", "away"].map((m) => `
            <div><b>${esc(a.modes[m])}</b><div class="muted small">${esc(a.mode_hint[m])}</div></div>
            <input class="input" type="number" min="0" max="900" data-delay="${m}" data-kind="exit" value="${esc(d.modes[m]?.exit ?? 0)}">
            <input class="input" type="number" min="0" max="900" data-delay="${m}" data-kind="entry" value="${esc(d.modes[m]?.entry ?? 0)}">`).join("")}
        </div>
      </section>
      <section class="card">
        <label class="field"><span>${esc(a.trigger_time)}</span><input class="input" type="number" min="0" max="3600" data-field="trigger_time" value="${esc(d.trigger_time)}"></label>
        <label class="switch block"><input type="checkbox" data-flag="rearm" ${d.rearm ? "checked" : ""}><span>${esc(a.rearm)}</span></label>
        <label class="switch block"><input type="checkbox" data-flag="require_code_arm" ${d.require_code_arm ? "checked" : ""}><span>${esc(a.require_code_arm)}</span></label>
        <label class="switch block"><input type="checkbox" data-flag="sabotage_triggers" ${d.sabotage_triggers ? "checked" : ""}><span>${esc(a.sabotage_triggers)}</span></label>
      </section>`;
  }

  _entityList(d, key, label) {
    const a = this.t.alarm;
    const chosen = d.actions[key] || [];
    const nameOf = (e) => this._alarm.actors.find((x) => x.entity_id === e)?.name || e;
    return `
      <div class="field-block">
        <div class="label">${esc(label)}</div>
        <div class="area-chips">${chosen.map((e) => `<span class="chip">${esc(nameOf(e))}<button class="chip-x" data-action-remove="${key}" data-entity="${esc(e)}">${icon("mdi:close")}</button></span>`).join("")}</div>
        <select class="input add-sensor" data-action-add="${key}"><option value="">${esc(a.add_entity)}</option>
          ${this._alarm.actors.filter((x) => !chosen.includes(x.entity_id)).map((x) => `<option value="${esc(x.entity_id)}">${esc(x.name)} (${esc(x.entity_id)})</option>`).join("")}</select>
      </div>`;
  }

  _settingsActions(d) {
    const a = this.t.alarm;
    return `
      <section class="card">
        ${this._entityList(d, "sirens", a.sirens)}
        ${this._entityList(d, "lights", a.lights)}
        ${this._entityList(d, "warning", a.warning)}
      </section>
      <section class="card">
        <div class="label">${esc(a.notify_events)}</div>
        <div class="area-chips">${Object.keys(a.events).map((ev) => `<label class="chip check"><input type="checkbox" data-notify-event="${ev}" ${d.actions.notify_events.includes(ev) ? "checked" : ""}><span>${esc(a.events[ev])}</span></label>`).join("")}</div>
        <label class="switch block"><input type="checkbox" data-critical ${d.actions.critical_push ? "checked" : ""}><span>${esc(a.critical_push)}</span></label>
      </section>`;
  }

  _settingsCodes() {
    const a = this.t.alarm;
    const codes = this._alarm.config.codes;
    return `
      <section class="card">
        <div class="muted small">${esc(a.codes_help)}</div>
        <div class="list">${codes.length === 0 ? `<div class="row muted">${esc(a.no_codes)}</div>` : codes.map((c) => `
          <div class="row">${icon("mdi:account-key-outline")}<div class="row-main"><b>${esc(c.name)}</b></div>
          <button class="btn small ghost danger" data-code-delete="${esc(c.id)}">${icon("mdi:delete-outline")}${esc(a.delete)}</button></div>`).join("")}</div>
        <div class="actionbar">
          <input class="input" id="code-name" placeholder="${esc(a.code_name)}">
          <input class="input" id="code-value" type="password" inputmode="numeric" autocomplete="new-password" placeholder="${esc(a.code)}">
          <button class="btn primary" data-action="code-add">${icon("mdi:plus")}${esc(a.add_code)}</button>
        </div>
      </section>`;
  }

  _settingsWorker(d) {
    const a = this.t.alarm;
    const relay = this._alarm.relay;
    const secret = this._alarm.config.worker.secret || "";
    return `
      <section class="card">
        <div class="muted small">${esc(a.worker_help)}</div>
        <ol class="steps">${a.steps.map((x) => `<li>${esc(x)}</li>`).join("")}</ol>
        <label class="switch block"><input type="checkbox" data-worker="enabled" ${d.worker.enabled ? "checked" : ""}><span>${esc(a.worker_enabled)}</span></label>
        <label class="field"><span>${esc(a.worker_url)}</span><input class="input" data-worker="url" placeholder="https://bastion-probe.<account>.workers.dev" value="${esc(d.worker.url || "")}"></label>
        <label class="field"><span>${esc(a.interval)}</span><input class="input" type="number" min="30" max="3600" data-worker="interval" value="${esc(d.worker.interval)}"></label>
        <div class="label">${esc(a.secret)}</div>
        <div class="secret"><code>${esc(this._reveal ? secret : `${secret.slice(0, 6)}••••••••••••`)}</code>
          <button class="btn small ghost" data-action="reveal">${icon(this._reveal ? "mdi:eye-off-outline" : "mdi:eye-outline")}${esc(this._reveal ? this.t.hide : this.t.show)}</button>
          <button class="btn small" data-copy="${esc(secret)}">${icon("mdi:content-copy")}${esc(this.t.copy)}</button>
          <button class="btn small ghost" data-action="worker-secret">${icon("mdi:refresh")}${esc(a.regenerate)}</button></div>
        <div class="actionbar tight">
          <button class="btn" data-action="worker-test">${icon("mdi:lan-connect")}${esc(a.test)}</button>
          <span class="muted small">${esc(a.last_ok)}: ${esc(this.rel(relay.last_ok))}</span>
          ${relay.last_error ? `<span class="chip tiny" style="--c:${SEV.high.color}">${esc(relay.last_error)}</span>` : ""}
        </div>
      </section>
      <section class="card">
        <h3 class="card-title">${icon("mdi:cloud-lock-outline")}${esc(a.offsite)}</h3>
        <div class="muted small">${esc(a.offsite_hint)}</div>
        ${this._pickList(a.cameras, d.worker.cameras, this._alarm.cameras || [], "camera", a.add_camera)}
        <div class="muted small" style="margin-top:6px">${esc(a.cameras_hint)}</div>
        <label class="field"><span>${esc(a.snapshots)}</span>
          <select class="input type-select" data-worker="snapshots">${[0, 1, 2, 3, 4, 5].map((n) => `<option value="${n}" ${Number(d.worker.snapshots) === n ? "selected" : ""}>${n}</option>`).join("")}</select></label>
        ${relay.backfill && !relay.backfill.error ? `<div class="muted small">${esc(a.backfill.replace("{alarm}", relay.backfill.alarm).replace("{security}", relay.backfill.security))}</div>` : ""}
      </section>
      <section class="card">
        <h3 class="card-title">${icon("mdi:web-check")}${esc(a.public_url)}</h3>
        <div class="muted small">${esc(a.public_url_hint)}</div>
        <label class="field"><span>URL</span><input class="input" data-worker="public_url" placeholder="${esc(this._alarm.external_url || "https://ha.example.com")}" value="${esc(d.worker.public_url || "")}"></label>
        ${this._exposureList()}
      </section>
      ${this._settingsRemote(d)}`;
  }

  _loadRemote() {
    this._remoteLoading = true;
    this._ws("bastion/alarm/remote", { action: "list" })
      .then((r) => { this._remote = r; })
      .catch((err) => { this._remote = { ok: false, error: err.message || String(err) }; })
      .finally(() => { this._remoteLoading = false; this._render(); });
  }

  _settingsRemote(d) {
    const a = this.t.alarm;
    const r = d.remote;
    const saved = this._alarm.config.remote || {};
    const ready = Boolean(saved.enabled && this._alarm.relay.enabled);
    if (ready && this._remote === undefined && !this._remoteLoading) this._loadRemote();
    const info = this._remote || {};
    const dash = info.dashboard || this._alarm.relay.dashboard;
    const keys = info.passkeys || [];
    const ago = (ts) => this.rel(new Date(ts * 1000).toISOString());
    const cmdLabel = (c) => (c.action === "disarm" ? this.t.alarm.states.disarmed || "disarm" : `${a.modes[c.mode] || c.mode}`);
    const passkeys = !ready ? `<div class="muted small">${esc(a.remote_save_first)}</div>` : `
      <div class="label">${esc(a.passkeys)}</div>
      ${info.error ? `<div class="chip tiny" style="--c:${SEV.high.color}">${esc(info.error)}</div>` : ""}
      ${keys.length ? keys.map((k) => `<div class="row">${icon("mdi:key-variant")}
          <div class="row-main"><div><b>${esc(k.name || "Passkey")}</b> <span class="muted small">${esc(k.email || "")}</span></div>
          <div class="muted small">${esc(a.last_used)}: ${esc(k.last_used ? ago(k.last_used) : a.never)}</div></div>
          <button class="btn small ghost danger" data-passkey-revoke="${esc(k.id)}">${icon("mdi:delete-outline")}${esc(a.revoke)}</button></div>`).join("")
        : `<div class="muted small">${esc(this._remoteLoading ? "…" : a.no_passkeys)}</div>`}
      ${this._pairing ? `<div class="secret"><code style="font-size:20px;letter-spacing:.12em">${esc(this._pairing.code)}</code></div><div class="muted small">${esc(a.pair_hint)}</div>` : ""}
      <div class="actionbar tight">
        <button class="btn" data-action="remote-pair">${icon("mdi:key-plus")}${esc(a.pair)}</button>
        ${dash ? `<a class="btn ghost" href="${esc(dash)}/" target="_blank" rel="noopener noreferrer">${icon("mdi:open-in-new")}${esc(a.pair_open)}</a>` : ""}
        ${keys.length > 1 ? `<button class="btn ghost danger" data-action="remote-revoke-all">${esc(a.revoke_all)}</button>` : ""}
      </div>
      ${(info.commands || []).length ? `<div class="label">${esc(a.commands)}</div>${info.commands.slice(0, 8).map((c) => `<div class="row">${icon(c.action === "disarm" ? "mdi:shield-off-outline" : "mdi:shield-lock", c.status === "done" ? GOOD : c.status === "failed" || c.status === "expired" ? SEV.high.color : "#8a8f98")}
          <div class="row-main"><div><b>${esc(cmdLabel(c))}</b> · ${esc((a.cmd_status || {})[c.status] || c.status)}${c.result && c.result.error ? ` (${esc(c.result.error)})` : ""}</div>
          <div class="muted small">${esc(ago(c.ts))} · ${esc(c.passkey || c.by || "")}</div></div></div>`).join("")}` : ""}`;
    return `
      <section class="card">
        <h3 class="card-title">${icon("mdi:cellphone-key")}${esc(a.remote)}</h3>
        <div class="muted small">${esc(a.remote_help)}</div>
        <label class="switch block"><input type="checkbox" data-remote-flag="enabled" ${r.enabled ? "checked" : ""}><span>${esc(a.remote_enabled)}</span></label>
        <label class="switch block"><input type="checkbox" data-remote-flag="disarm" ${r.disarm ? "checked" : ""}><span>${esc(a.remote_disarm)}</span></label>
        <div class="muted small">${esc(a.remote_disarm_hint)}</div>
        ${passkeys}
      </section>
      <section class="card">
        <h3 class="card-title">${icon("mdi:home-export-outline")}${esc(a.reminder)}</h3>
        <div class="muted small">${esc(a.reminder_help)}</div>
        <label class="switch block"><input type="checkbox" data-remote-flag="reminder" ${r.reminder ? "checked" : ""}><span>${esc(a.reminder_enabled)}</span></label>
        <label class="field"><span>${esc(a.reminder_minutes)}</span><input class="input" type="number" min="5" max="240" data-remote-minutes value="${esc(r.reminder_minutes)}"></label>
        ${this._pickList(a.persons, r.persons, this._alarm.persons || [], "person", a.add_person)}
        <div class="muted small">${esc(a.persons_all)}</div>
      </section>`;
  }

  _exposureList() {
    const a = this.t.alarm;
    const ex = this._alarm.exposure;
    if (!ex || !ex.results || !ex.results.length) return `<div class="muted small">${esc(a.exposure_none)}</div>`;
    const color = { ok: GOOD, info: "#8a8f98", warning: SEV.medium.color, critical: SEV.critical.color };
    return ex.results.map((r) => `
      <div class="exposure">
        <div class="exposure-head"><span class="mono">${esc(r.url)}</span><span class="grow"></span>
          <span class="muted small">${esc(a.exposure_checked.replace("{when}", this.rel(new Date(ex.checked).toISOString())).replace("{colo}", r.colo || "?"))}</span></div>
        ${r.checks.map((c) => `<div class="exposure-row">${icon(c.level === "ok" ? "mdi:check-circle-outline" : c.level === "critical" ? "mdi:alert-octagon-outline" : "mdi:alert-outline", color[c.level] || color.info)}<span>${esc(c.text)}</span></div>`).join("")}
      </div>`).join("");
  }

  _pickList(label, chosen, options, kind, addLabel) {
    const nameOf = (e) => options.find((x) => x.entity_id === e)?.name || e;
    return `
      <div class="field-block">
        <div class="label">${esc(label)}</div>
        <div class="area-chips">${chosen.map((e) => `<span class="chip">${esc(nameOf(e))}<button class="chip-x" data-${kind}-remove="${esc(e)}" aria-label="${esc(this.t.alarm.remove)}">${icon("mdi:close")}</button></span>`).join("")}</div>
        <select class="input add-sensor" data-${kind}-add><option value="">${esc(addLabel)}</option>
          ${options.filter((x) => !chosen.includes(x.entity_id)).map((x) => `<option value="${esc(x.entity_id)}">${esc(x.name)} (${esc(x.entity_id)})</option>`).join("")}</select>
      </div>`;
  }

  _settingsSounds(d) {
    const a = this.t.alarm;
    const s = d.sounds;
    const media = this._media || [];
    const opt = (value, label, cur) => `<option value="${esc(value)}" ${value === cur ? "selected" : ""}>${esc(label)}</option>`;
    const select = (key) => {
      const cur = s[key] || "";
      const known = cur === "" || cur.startsWith("bastion:") || media.some((m) => m.id === cur);
      return `<select class="input type-select sound-select" data-sound="${key}">
        ${opt("", a.sound_off, cur)}
        <optgroup label="${esc(a.builtin_group)}">${(this._alarm.sounds_builtin || []).map((n) => opt(`bastion:${n}`, a.builtin[n] || n, cur)).join("")}</optgroup>
        ${media.length ? `<optgroup label="${esc(a.my_media)}">${media.map((m) => opt(m.id, m.title.split(" / ").slice(1).join(" / ") || m.title, cur)).join("")}</optgroup>` : ""}
        ${known ? "" : opt(cur, decodeURIComponent(cur.split("/").pop()), cur)}
      </select>`;
    };
    const slider = (key, label) => `
      <div class="fld vol">
        <span class="fld-label">${icon(key === "volume" ? "mdi:volume-high" : "mdi:volume-medium")}${esc(label)}</span>
        <div class="range-row"><input type="range" min="5" max="100" step="5" data-volume="${key}" value="${Math.round((s[key] || 0) * 100)}"><b data-volume-label="${key}">${Math.round((s[key] || 0) * 100)} %</b></div>
      </div>`;
    return `
      <section class="card">
        <div class="muted small">${esc(a.sounds_help)}</div>
        ${this._pickList(a.players, s.players, this._alarm.players || [], "player", a.add_player)}
        <div class="sensor-fields" style="padding-left:0;margin-top:18px">${slider("volume", a.volume)}${slider("notice_volume", a.notice_volume)}</div>
      </section>
      <section class="card sound-list">
        ${["triggered", "pending", "arming", "armed", "disarmed"].map((key) => `
          <div class="sound-row">
            <div class="sound-ident"><div class="sound-title">${esc(a.sound_for[key])}</div><div class="muted small">${esc(a.sound_hint[key])}</div></div>
            ${select(key)}
            <button class="icon-btn play" data-sound-play="${key}" title="${esc(a.play)}" aria-label="${esc(a.play)}" ${s[key] ? "" : "disabled"}>${icon("mdi:play")}</button>
          </div>`).join("")}
        <div class="actionbar tight">
          <button class="btn small" data-action="sound-stop">${icon("mdi:stop")}<span>${esc(a.stop)}</span></button>
          <span class="grow"></span>
          <label class="btn small upload">${icon("mdi:upload")}<span>${esc(a.upload)}</span><input type="file" accept="audio/*" data-sound-upload></label>
        </div>
      </section>`;
  }

  _openSettings() {
    const cfg = this._alarm.config;
    this._draft = JSON.parse(JSON.stringify({
      rooms: cfg.rooms, sensors: cfg.sensors, modes: cfg.modes, trigger_time: cfg.trigger_time, rearm: cfg.rearm,
      require_code_arm: cfg.require_code_arm, sabotage_triggers: cfg.sabotage_triggers, actions: cfg.actions,
      worker: { url: cfg.worker.url, interval: cfg.worker.interval, enabled: cfg.worker.enabled, cameras: cfg.worker.cameras || [], snapshots: cfg.worker.snapshots ?? 3, public_url: cfg.worker.public_url || "" },
      remote: { enabled: false, disarm: false, reminder: false, reminder_minutes: 20, persons: [], ...(cfg.remote || {}) },
      people: (cfg.people || []).map((x) => ({ ...x })),
      floorplan: cfg.floorplan ? JSON.parse(JSON.stringify(cfg.floorplan)) : null,
      presence: { away_minutes: 10, ...(cfg.presence || {}) },
      sounds: { players: [], volume: 0.9, notice_volume: 0.5, triggered: "", pending: "", arming: "", armed: "", disarmed: "", ...(cfg.sounds || {}) },
    }));
    this._alarmView = "settings";
    this._render();
  }

  _importAreas() {
    const d = this._draft;
    const security = new Set(["door", "window", "opening", "garage_door", "motion", "occupancy", "presence", "smoke", "gas", "moisture", "tamper", "vibration", "safety", "lock"]);
    const used = new Set(d.rooms.flatMap((r) => r.sensors));
    const byArea = {};
    for (const c of this._alarm.candidates) {
      if (!c.area || used.has(c.entity_id)) continue;
      if (!(security.has(c.device_class) || c.entity_id.startsWith("lock."))) continue;
      (byArea[c.area] ||= { icon: c.area_icon, sensors: [] }).sensors.push(c);
    }
    for (const [area, info] of Object.entries(byArea)) {
      let room = d.rooms.find((r) => r.name === area);
      if (!room) {
        room = { name: area, icon: info.icon || "mdi:door", sensors: [] };
        d.rooms.push(room);
      }
      for (const c of info.sensors) {
        room.sensors.push(c.entity_id);
        const always = ["smoke", "gas", "moisture", "tamper", "safety"].includes(c.device_class);
        const motion = ["motion", "occupancy", "presence"].includes(c.device_class);
        d.sensors[c.entity_id] = {
          type: always ? "always" : motion ? "instant" : "delayed",
          modes: motion ? ["away"] : ["home", "night", "away"],
          bypass: c.device_class === "window",
        };
      }
    }
  }

  _bindAlarm() {
    const root = this.shadowRoot;
    const on = (sel, fn, type = "click") => root.querySelectorAll(sel).forEach((el) => el.addEventListener(type, (ev) => fn(el, ev)));
    on("[data-mode]", (el) => this._modeClicked(el.dataset.mode));
    on('[data-action="alarm-settings"]', () => this._openSettings());
    on('[data-action="alarm-back"]', () => { this._alarmView = "status"; this._refreshAlarm(); });
    on("[data-section]", (el) => {
      this._section = el.dataset.section;
      if (this._section === "worker") this._remote = undefined;
      this._render();
      if (this._section === "sounds" && !this._media) {
        this._media = [];
        this._ws("bastion/alarm/media").then((r) => { this._media = r.files || []; this._render(); }).catch(() => {});
      }
    });
    // keypad
    on("[data-key]", (el) => {
      const k = el.dataset.key;
      if (k === "clear") this._modal.code = "";
      else if (k === "back") this._modal.code = this._modal.code.slice(0, -1);
      else if (this._modal.code.length < 32) this._modal.code += k;
      this._render();
    });
    on("#code-input", (el) => { this._modal.code = el.value; }, "input");
    on('[data-modal="cancel"]', () => { this._modal = null; this._render(); });
    on('[data-modal="ok"]', () => {
      const m = this._modal;
      this._action(() => this._alarmCommand(m.kind, m.mode, m.code));
    });
    on('[data-modal="force"]', () => {
      const m = this._modal;
      this._action(() => this._alarmCommand("arm", m.mode, m.code, true));
    });
    if (this._modal && this._modal.type === "code") {
      const input = root.getElementById("code-input");
      if (input) input.focus();
    }
    const d = this._draft;
    if (!d || this._alarmView !== "settings") return;
    // rooms
    on('[data-action="room-add"]', () => { d.rooms.push({ name: `${this.t.alarm.rooms} ${d.rooms.length + 1}`, icon: "mdi:door", sensors: [] }); this._render(); });
    on('[data-action="room-import"]', () => { this._importAreas(); this._render(); });
    on("[data-room-name]", (el) => { d.rooms[+el.dataset.roomName].name = el.value; }, "input");
    // icon picker
    on("[data-icon-pick]", (el) => {
      const ri = +el.dataset.iconPick;
      this._iconFor = this._iconFor === ri ? null : ri;
      this._render();
      const search = this.shadowRoot.querySelector("[data-icon-search]");
      if (search) search.focus();
    });
    on("[data-icon-search]", (el) => {
      const q = el.value.trim().toLowerCase();
      root.querySelectorAll("[data-icon-set]").forEach((b) => { b.hidden = Boolean(q) && !b.dataset.words.includes(q); });
    }, "input");
    on("[data-icon-search]", (el, ev) => { if (ev.key === "Escape") { this._iconFor = null; this._render(); } }, "keydown");
    on("[data-icon-set]", (el) => { if (this._iconFor != null) { d.rooms[this._iconFor].icon = el.dataset.iconSet; this._iconFor = null; this._render(); } });
    on("[data-icon-apply]", () => {
      const value = (root.querySelector("[data-icon-custom]")?.value || "").trim();
      if (this._iconFor != null && /^mdi:[a-z0-9-]+$/.test(value)) { d.rooms[this._iconFor].icon = value; this._iconFor = null; this._render(); }
    });
    // floor plan
    // Optional lists may be missing (the backend fills them in too); the preview must render
    // before the draft takes the plan, so a broken file never replaces a working one.
    const takePlan = (text) => {
      let plan;
      try {
        plan = JSON.parse(text);
        if (!plan || typeof plan !== "object" || !Array.isArray(plan.size) || !Array.isArray(plan.areas) || !plan.areas.length) throw new Error("plan");
        for (const key of ["walls", "glazing", "dividers", "boxes"]) if (!Array.isArray(plan[key])) plan[key] = [];
        this._planSvg(plan);
      } catch {
        this._notify(this.t.alarm.fp_invalid);
        return;
      }
      d.floorplan = plan;
      this._render();
    };
    on("[data-fp-file]", (el) => {
      const file = el.files && el.files[0];
      if (file) file.text().then(takePlan);
    }, "change");
    on('[data-action="fp-apply"]', () => takePlan(root.querySelector("[data-fp-text]")?.value || ""));
    on('[data-action="fp-remove"]', () => { d.floorplan = null; this._render(); });
    on("[data-fp-room]", (el) => { const ar = d.floorplan.areas[+el.dataset.fpRoom]; if (el.value) ar.room = el.value; else delete ar.room; }, "change");
    on("[data-fp-glass]", (el) => { const g = d.floorplan.glazing[+el.dataset.fpGlass]; if (el.value) g.sensor = el.value; else delete g.sensor; }, "change");
    on("[data-fp-entrance]", (el) => { if (el.value) d.floorplan.entrance.sensor = el.value; else delete d.floorplan.entrance.sensor; }, "change");
    // people
    on("[data-person-name]", (el) => { d.people[+el.dataset.personName].name = el.value; }, "input");
    on("[data-person-ip]", (el) => { d.people[+el.dataset.personIp].ip = el.value.trim(); }, "input");
    on("[data-person-tracker]", (el) => { d.people[+el.dataset.personTracker].tracker = el.value || null; this._render(); }, "change");
    on('[data-action="person-add"]', () => { d.people.push({ name: "", ip: "" }); this._render(); });
    on("[data-person-delete]", (el) => { d.people.splice(+el.dataset.personDelete, 1); this._probe = null; this._render(); });
    on("[data-presence-minutes]", (el) => { d.presence.away_minutes = Math.max(2, Math.min(60, Number(el.value) || 10)); }, "input");
    on("[data-person-test]", (el) => this._action(async () => {
      const i = +el.dataset.personTest;
      const a = this.t.alarm;
      const r = await this._ws("bastion/alarm/presence_test", { address: d.people[i].ip || "" });
      this._probe = { i, ok: r.found, text: r.found ? `${a.people_found} (${r.method})` : a.people_not_found };
    }));
    on("[data-room-delete]", (el) => {
      const room = d.rooms.splice(+el.dataset.roomDelete, 1)[0];
      room.sensors.forEach((e) => delete d.sensors[e]);
      this._render();
    });
    on("[data-room-add-sensor]", (el) => {
      if (!el.value) return;
      d.rooms[+el.dataset.roomAddSensor].sensors.push(el.value);
      d.sensors[el.value] ||= { modes: ["home", "night", "away"], type: "delayed", bypass: false };
      this._render();
    }, "change");
    on("[data-sensor-remove]", (el) => {
      const room = d.rooms[+el.dataset.room];
      room.sensors = room.sensors.filter((e) => e !== el.dataset.sensorRemove);
      delete d.sensors[el.dataset.sensorRemove];
      this._render();
    });
    const sensorCfg = (e) => (d.sensors[e] ||= { modes: ["home", "night", "away"], type: "delayed", bypass: false });
    on("[data-sensor-mode]", (el) => {
      const cfg = sensorCfg(el.dataset.sensorMode);
      const m = el.dataset.modeKey;
      cfg.modes = cfg.modes.includes(m) ? cfg.modes.filter((x) => x !== m) : [...cfg.modes, m];
      this._render();
    });
    on("[data-sensor-type]", (el) => { sensorCfg(el.dataset.sensorType).type = el.value; this._render(); }, "change");
    on("[data-sensor-bypass]", (el) => { sensorCfg(el.dataset.sensorBypass).bypass = el.checked; }, "change");
    on("[data-sensor-name]", (el) => { sensorCfg(el.dataset.sensorName).name = el.value.trim() || null; }, "input");
    on("[data-sensor-name]", () => this._render(), "change");
    on("[data-sensor-delay]", (el) => {
      const value = el.value.trim();
      sensorCfg(el.dataset.sensorDelay)[el.dataset.delayKind] = value === "" ? null : Math.max(0, Math.min(900, Number(value) || 0));
    }, "input");
    // modes
    on("[data-delay]", (el) => { (d.modes[el.dataset.delay] ||= {})[el.dataset.kind] = Number(el.value) || 0; }, "input");
    on('[data-field="trigger_time"]', (el) => { d.trigger_time = Number(el.value) || 0; }, "input");
    on("[data-flag]", (el) => { d[el.dataset.flag] = el.checked; }, "change");
    // actions
    on("[data-action-add]", (el) => { if (el.value) { (d.actions[el.dataset.actionAdd] ||= []).push(el.value); this._render(); } }, "change");
    on("[data-action-remove]", (el) => { const k = el.dataset.actionRemove; d.actions[k] = d.actions[k].filter((x) => x !== el.dataset.entity); this._render(); });
    on("[data-notify-event]", (el) => {
      const ev = el.dataset.notifyEvent;
      d.actions.notify_events = el.checked ? [...new Set([...d.actions.notify_events, ev])] : d.actions.notify_events.filter((x) => x !== ev);
    }, "change");
    on("[data-critical]", (el) => { d.actions.critical_push = el.checked; }, "change");
    // sounds
    on("[data-player-add]", (el) => { if (el.value) { d.sounds.players = [...new Set([...d.sounds.players, el.value])]; this._render(); } }, "change");
    on("[data-player-remove]", (el) => { d.sounds.players = d.sounds.players.filter((x) => x !== el.dataset.playerRemove); this._render(); });
    on("[data-volume]", (el) => {
      d.sounds[el.dataset.volume] = Number(el.value) / 100;
      const label = root.querySelector(`[data-volume-label="${el.dataset.volume}"]`);
      if (label) label.textContent = `${el.value} %`;
    }, "input");
    on("[data-sound]", (el) => { d.sounds[el.dataset.sound] = el.value; }, "change");
    on("[data-sound-play]", (el) => this._action(async () => {
      const key = el.dataset.soundPlay;
      if (!d.sounds.players.length) throw new Error(this.t.alarm.no_players);
      if (!d.sounds[key]) return;
      await this._ws("bastion/alarm/sound", { action: "play", sound: d.sounds[key], players: d.sounds.players, volume: key === "triggered" ? d.sounds.volume : d.sounds.notice_volume });
    }));
    on('[data-action="sound-stop"]', () => this._action(async () => { await this._ws("bastion/alarm/sound", { action: "stop" }); }));
    on("[data-sound-upload]", (el) => this._action(async () => {
      const file = el.files && el.files[0];
      if (!file) return;
      const form = new FormData();
      form.append("media_content_id", "media-source://media_source/local/bastion");
      form.append("file", file);
      const resp = await this.hass.fetchWithAuth("/api/media_source/local_source/upload", { method: "POST", body: form });
      if (!resp.ok) throw new Error(`Upload ${resp.status}`);
      const { media_content_id: id } = await resp.json();
      this._media = (await this._ws("bastion/alarm/media")).files || [];
      if (!this._media.some((m) => m.id === id)) this._media.push({ id, title: file.name });
      this._notify(this.t.alarm.uploaded.replace("{name}", file.name));
    }), "change");
    // worker
    on("[data-camera-add]", (el) => { if (el.value) { d.worker.cameras = [...new Set([...d.worker.cameras, el.value])]; this._render(); } }, "change");
    // remote control and reminder
    on("[data-remote-flag]", (el) => { d.remote[el.dataset.remoteFlag] = el.checked; }, "change");
    on("[data-remote-minutes]", (el) => { d.remote.reminder_minutes = Math.max(5, Math.min(240, Number(el.value) || 20)); }, "input");
    on("[data-person-add]", (el) => { if (el.value) { d.remote.persons = [...new Set([...d.remote.persons, el.value])]; this._render(); } }, "change");
    on("[data-person-remove]", (el) => { d.remote.persons = d.remote.persons.filter((x) => x !== el.dataset.personRemove); this._render(); });
    on('[data-action="remote-pair"]', () => this._action(async () => {
      const r = await this._ws("bastion/alarm/remote", { action: "pair" });
      if (!r.ok) throw new Error(r.error || "Worker");
      this._pairing = { code: r.code };
      this._remote = r;
      clearTimeout(this._pairTimer);
      this._pairTimer = setTimeout(() => { this._pairing = null; this._render(); }, 600000);
    }));
    on("[data-passkey-revoke]", (el) => {
      if (!confirm(this.t.alarm.revoke_confirm)) return;
      this._action(async () => { this._remote = await this._ws("bastion/alarm/remote", { action: "revoke", passkey: el.dataset.passkeyRevoke }); });
    });
    on('[data-action="remote-revoke-all"]', () => {
      if (!confirm(this.t.alarm.revoke_confirm)) return;
      this._action(async () => { this._remote = await this._ws("bastion/alarm/remote", { action: "revoke_all" }); });
    });
    on("[data-camera-remove]", (el) => { d.worker.cameras = d.worker.cameras.filter((x) => x !== el.dataset.cameraRemove); this._render(); });
    on('[data-worker="snapshots"]', (el) => { d.worker.snapshots = Number(el.value); }, "change");
    on('[data-worker="public_url"]', (el) => { d.worker.public_url = el.value.trim(); }, "input");
    on('[data-worker="enabled"]', (el) => { d.worker.enabled = el.checked; }, "change");
    on('[data-worker="url"]', (el) => { d.worker.url = el.value.trim(); }, "input");
    on('[data-worker="interval"]', (el) => { d.worker.interval = Number(el.value) || 120; }, "input");
    on('[data-action="worker-secret"]', () => this._action(async () => { this._alarm = await this._ws("bastion/alarm/worker", { action: "secret" }); }));
    on('[data-action="worker-test"]', () => this._action(async () => {
      const result = await this._ws("bastion/alarm/worker", { action: "test" });
      this._alarm = result;
      this._notify(result.result.ok ? this.t.alarm.test_ok.replace("{channels}", (result.result.channels || []).join(", ") || "—") : `${this.t.error}: ${result.result.error}`);
    }));
    // codes
    // Read inputs before _action: it re-renders and the fields start empty again.
    on('[data-action="code-add"]', () => {
      const name = root.getElementById("code-name").value;
      const code = root.getElementById("code-value").value;
      this._action(async () => {
        this._alarm = await this._ws("bastion/alarm/code", { name, code });
        this._notify(this.t.alarm.saved);
      });
    });
    on("[data-code-delete]", (el) => this._action(async () => { this._alarm = await this._ws("bastion/alarm/code", { delete: el.dataset.codeDelete }); }));
    // save
    on('[data-action="alarm-save"]', () => this._action(async () => {
      d.people = d.people.filter((x) => x.name.trim() && ((x.ip || "").trim() || x.tracker)).map((x) => ({ ...x, ip: x.tracker ? "" : (x.ip || "").trim(), tracker: x.tracker || null }));
      this._alarm = await this._ws("bastion/alarm/save", { config: d });
      this._notify(this.t.alarm.saved);
    }));
  }

  // ------------------------------------------------------------------ events
  _bind() {
    const root = this.shadowRoot;
    const on = (sel, fn, type = "click") => root.querySelectorAll(sel).forEach((el) => el.addEventListener(type, (ev) => fn(el, ev)));
    on("[data-tab]", (el) => {
      this._tab = el.dataset.tab;
      this._alarmView = "status";
      this._modal = null;
      this._commit = null;
      this._files = null;
      this._diff = null;
      this._load();
    });
    on("[data-toggle]", (el) => {
      const id = el.dataset.toggle;
      if (this._expanded.has(id)) this._expanded.delete(id);
      else this._expanded.add(id);
      this._render();
    });
    on("[data-filter]", (el) => {
      this._filter = el.dataset.filter;
      this._render();
    });
    on('[data-action="toggle-dismissed"]', (el) => {
      this._showDismissed = el.checked;
      this._render();
    }, "change");
    on('[data-action="only-changed"]', (el) => {
      this._onlyChanged = el.checked;
      this._render();
    }, "change");
    on('[data-action="reveal"]', () => {
      this._reveal = !this._reveal;
      this._render();
    });
    on("[data-copy]", async (el) => {
      try {
        await navigator.clipboard.writeText(el.dataset.copy);
      } catch {
        const area = document.createElement("textarea");
        area.value = el.dataset.copy;
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        area.remove();
      }
      this._notify(this.t.copied);
      this._render();
    });
    on('[data-action="audit"]', () => this._action(async () => { this._data = await this._ws("bastion/audit/run"); }));
    on('[data-action="report"]', () => this._action(async () => { this._data = await this._ws("bastion/report/send"); }));
    on('[data-action="dismiss"]', (el) => this._action(async () => {
      this._data = await this._ws("bastion/finding/dismiss", { finding_id: el.dataset.id, dismissed: el.dataset.dismissed === "1" });
    }));
    on('[data-action="accept"]', (el) => this._action(async () => {
      this._data = await this._ws("bastion/integrity/accept", el.dataset.domain ? { domain: el.dataset.domain } : {});
    }));
    on('[data-action="block"]', (el) => this._action(async () => {
      if (!confirm(this.t.confirm_block)) return;
      const payload = {};
      if (el.dataset.ip) payload.ip = el.dataset.ip;
      if (el.dataset.token) payload.token_id = el.dataset.token;
      const result = await this._ws("bastion/security/block", payload);
      this._notify(result.result.join(" · "));
      this._logins = await this._ws("bastion/logins");
      this._data = await this._ws("bastion/overview");
    }));
    on('[data-action="commit"]', () => {
      const message = root.getElementById("commit-message")?.value || undefined;
      this._action(async () => {
        const result = await this._ws("bastion/git/commit", message ? { message } : {});
        this._notify(result.committed ? `✔ ${result.summary || ""}` : result.push_error ? `${this.t.error}: ${result.push_error}` : "✔");
        this._data = await this._ws("bastion/overview");
        this._git = await this._ws("bastion/git/history", { refresh: false });
      });
    });
    on('[data-action="refresh-git"]', () => this._action(async () => { this._git = await this._ws("bastion/git/history", { refresh: true }); }));
    on('[data-action="select-commit"]', (el) => this._action(async () => {
      this._commit = el.dataset.sha;
      this._files = null;
      this._diff = null;
      this._diffPath = null;
      this._render();
      this._files = (await this._ws("bastion/git/files", { commit: this._commit })).files;
    }));
    on('[data-action="diff"]', (el) => this._action(async () => {
      const result = await this._ws("bastion/git/diff", { commit: this._commit, path: el.dataset.path });
      this._diffPath = el.dataset.path;
      this._diff = result.diff
        ? result.diff.split("\n").map((line) => {
            const cls = line.startsWith("+") ? "add" : line.startsWith("-") ? "del" : line.startsWith("@@") ? "hunk" : "";
            return `<span class="${cls}">${esc(line)}</span>`;
          }).join("\n")
        : esc(this.t.status[result.status] || result.status);
    }));
    const restore = (extra) => this._action(async () => {
      if (!confirm(this.t.confirm_restore.replace("{sha}", this._commit.slice(0, 8)))) return;
      const restart = root.getElementById("restart")?.checked || false;
      const result = await this._ws("bastion/git/restore", { commit: this._commit, restart, ...extra });
      this._notify(this.t.restored
        .replace("{written}", result.written.length)
        .replace("{staged}", result.staged.length)
        .replace("{skipped}", result.skipped.length));
      this._files = (await this._ws("bastion/git/files", { commit: this._commit })).files;
    });
    on('[data-action="restore-all"]', () => restore({}));
    on('[data-action="restore-areas"]', () => {
      const areas = [...root.querySelectorAll("input.area:checked")].map((el) => el.value);
      if (areas.length) restore({ areas });
    });
    on('[data-action="restore-file"]', (el) => restore({ paths: [el.dataset.path] }));
    on('[data-action="probe"]', () => this._action(async () => { this._data = await this._ws("bastion/probe/run"); }));

    // Tooltips for charts and timestamps.
    const tip = root.querySelector(".tip");
    root.querySelectorAll("[data-tip]").forEach((el) => {
      el.addEventListener("mousemove", (ev) => {
        tip.textContent = el.dataset.tip;
        tip.hidden = false;
        tip.style.left = `${ev.clientX + 12}px`;
        tip.style.top = `${ev.clientY + 12}px`;
      });
      el.addEventListener("mouseleave", () => { tip.hidden = true; });
    });
  }
}

// Bar with rounded data end (top) anchored to the baseline.
function barPath(x, base, w, h) {
  const r = Math.min(4, w / 2, h);
  const y = base - h;
  return `M${x},${base} V${y + r} Q${x},${y} ${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${base} Z`;
}

const SHIELD = `<svg class="logo" viewBox="18 20 220 220" width="34" height="34" aria-hidden="true">
  <defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2f8cff"/><stop offset="1" stop-color="#103d8c"/></linearGradient></defs>
  <path d="M48 24 H84 V52 H110 V24 H146 V52 H172 V24 H208 V150 C208 192 172 220 128 236 C84 220 48 192 48 150 Z" fill="url(#bg)" stroke="url(#bg)" stroke-width="8" stroke-linejoin="round"/>
  <circle cx="128" cy="122" r="24" fill="#fff"/><path d="M117 134 L110 184 Q109 190 115 190 H141 Q147 190 146 184 L139 134 Z" fill="#fff"/></svg>`;

const STYLE = `
  :host {
    --bg: var(--primary-background-color);
    --surface: var(--card-background-color, #1c1c1c);
    --surface-2: color-mix(in srgb, var(--primary-text-color) 4%, var(--surface));
    --surface-3: color-mix(in srgb, var(--primary-text-color) 7%, var(--surface));
    --line: color-mix(in srgb, var(--primary-text-color) 9%, transparent);
    --line-strong: color-mix(in srgb, var(--primary-text-color) 16%, transparent);
    --text: var(--primary-text-color);
    --muted: var(--secondary-text-color);
    --accent: var(--primary-color);
    --on-accent: var(--text-primary-color, #fff);
    --radius-sm: 10px; --radius: 14px; --radius-lg: 18px;
    --shadow: 0 1px 2px rgba(0,0,0,.04), 0 6px 20px -10px rgba(0,0,0,.18);
    --shadow-lg: 0 24px 60px -20px rgba(0,0,0,.45);
    --font: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, Roboto, system-ui, -apple-system, "Segoe UI", sans-serif));
    --mono: var(--ha-font-family-code, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace);
    display:block; height:100%; background: var(--bg); color: var(--text); font-family: var(--font);
    -webkit-font-smoothing: antialiased; font-size:14px; line-height:1.45;
  }
  * { box-sizing: border-box; }
  ha-icon { --mdc-icon-size: 18px; flex: none; display:inline-flex; }
  .grow { flex:1; }
  .muted { color: var(--muted); }
  .small { font-size:12px; }
  .mono { font-family: var(--mono); font-size:.92em; }
  .num, .tile-value, .ring-value, .alarm-state { font-variant-numeric: tabular-nums; }
  .sep { color: var(--line-strong); margin: 0 2px; }

  /* ------------------------------------------------------------- shell */
  .app { display:flex; flex-direction:column; height:100vh; }
  .appbar { position:relative; z-index:3; background: color-mix(in srgb, var(--surface) 92%, transparent);
    backdrop-filter: saturate(1.4) blur(12px); border-bottom:1px solid var(--line); }
  .appbar-row { display:flex; align-items:center; gap:12px; height:60px; padding: 0 20px 0 4px; }
  .brand { display:flex; align-items:center; gap:10px; }
  .brand .logo { filter: drop-shadow(0 2px 6px rgba(47,140,255,.35)); }
  .brand-name { font-size:17px; font-weight:650; letter-spacing:-.01em; line-height:1.1; }
  .brand-sub { font-size:12px; color: var(--muted); }
  .pills { display:flex; gap:8px; align-items:center; }
  .pill { display:inline-flex; align-items:center; gap:8px; height:32px; padding:0 12px; border-radius:999px; cursor:pointer; white-space:nowrap;
    border:1px solid var(--line); background: var(--surface); color: var(--text); font: inherit; font-size:13px; transition: background .15s, border-color .15s; }
  .pill:hover { border-color: var(--line-strong); background: var(--surface-2); }
  .pill-dot { width:8px; height:8px; border-radius:50%; background: var(--c); box-shadow: 0 0 0 3px color-mix(in srgb, var(--c) 22%, transparent); }
  .pill b { font-size:14px; }
  .pill-label { color: var(--muted); }
  .tabs { display:flex; gap:2px; padding:0 16px; overflow-x:auto; scrollbar-width:none; }
  .tabs::-webkit-scrollbar { display:none; }
  .tab { position:relative; display:flex; align-items:center; gap:8px; white-space:nowrap; border:none; background:none; color: var(--muted);
    padding:12px 14px 13px; font: inherit; font-size:14px; font-weight:500; cursor:pointer; border-radius:10px 10px 0 0; transition: color .15s, background .15s; }
  .tab:hover { color: var(--text); background: var(--surface-2); }
  .tab.active { color: var(--text); }
  .tab.active::after { content:""; position:absolute; left:12px; right:12px; bottom:-1px; height:2px; border-radius:2px; background: var(--accent); }
  .tab.active ha-icon { color: var(--accent); }
  .content { flex:1; overflow:auto; scroll-behavior:smooth; }
  .container { max-width: 1200px; margin: 0 auto; padding: 28px 24px 64px; }
  .page-head { display:flex; align-items:flex-end; justify-content:space-between; gap:16px; flex-wrap:wrap; margin-bottom:20px; }
  .page-title h1 { margin:0; font-size:24px; font-weight:650; letter-spacing:-.02em; line-height:1.2; }
  .page-title p { margin:6px 0 0; color: var(--muted); font-size:14px; }
  .page-actions { display:flex; gap:8px; flex-wrap:wrap; }
  h2 { display:flex; align-items:center; gap:8px; font-size:13px; font-weight:600; text-transform:uppercase; letter-spacing:.06em;
    color: var(--muted); margin: 32px 0 12px; }
  h2 ha-icon { --mdc-icon-size: 16px; }

  /* ------------------------------------------------------------- cards */
  .card { background: var(--surface); border:1px solid var(--line); border-radius: var(--radius-lg); padding:20px; box-shadow: var(--shadow); }
  .card + .card, .card + .grid3, .grid3 + .card, .card + .actionbar, .card + .segmented { margin-top:16px; }
  .card-title { display:flex; align-items:center; gap:10px; margin:0 0 14px; font-size:15px; font-weight:600; }
  .card-title ha-icon { color: var(--accent); }
  .label { font-size:12px; font-weight:600; text-transform:uppercase; letter-spacing:.05em; color: var(--muted); margin:18px 0 8px; }
  .loading { display:flex; justify-content:center; padding:80px 0; }
  .spinner { width:28px; height:28px; border-radius:50%; border:3px solid var(--line-strong); border-top-color: var(--accent); animation: spin .8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .empty { display:flex; flex-direction:column; align-items:center; gap:12px; padding:40px 24px; color: var(--muted); text-align:center; }
  .empty > ha-icon { --mdc-icon-size: 28px; width:56px; height:56px; border-radius:50%; align-items:center; justify-content:center;
    background: color-mix(in srgb, currentColor 12%, transparent); color: var(--accent); }
  .empty.small { padding:28px 12px; box-shadow:none; border:none; }

  /* ------------------------------------------------------------- hero / tiles */
  .hero { display:flex; gap:28px; align-items:center; flex-wrap:wrap; padding:24px; }
  .ring { position:relative; width:136px; flex:none; display:flex; flex-direction:column; align-items:center; }
  .ring svg { width:136px; height:136px; }
  .ring-text { position:absolute; top:0; left:0; width:136px; height:136px; display:flex; flex-direction:column; align-items:center; justify-content:center; }
  .ring-value { font-size:40px; font-weight:700; line-height:1; letter-spacing:-.02em; }
  .ring-unit { font-size:12px; color: var(--muted); margin-top:4px; }
  .ring-label { display:flex; align-items:center; gap:6px; margin-top:10px; font-size:13px; font-weight:500; }
  .ring-label ha-icon { --mdc-icon-size: 10px; }
  .hero-side { flex:1; min-width:260px; display:flex; flex-direction:column; gap:18px; }
  .tiles { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:12px; }
  .tile { background: var(--surface-2); border-radius: var(--radius); padding:14px; }
  .tile-head { display:flex; align-items:center; gap:10px; font-size:13px; color: var(--muted); font-weight:500; }
  .tile-head ha-icon { width:32px; height:32px; border-radius:10px; align-items:center; justify-content:center;
    background: color-mix(in srgb, currentColor 14%, transparent); }
  .tile-value { font-size:28px; font-weight:700; margin-top:10px; letter-spacing:-.02em; line-height:1; }
  .tile-sub { font-size:15px; margin-top:12px; font-weight:500; }
  .trend svg { display:block; margin-top:6px; overflow:visible; }
  .gridline { stroke: var(--line-strong); stroke-width:1; stroke-dasharray: 3 4; }
  .spark { stroke: var(--accent); }
  .spark-dot { fill: var(--accent); stroke: var(--surface); stroke-width:2; }
  .bar { fill: ${SEV.high.color}; }
  .grid3 { display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap:16px; align-items:start; }
  .grid3 .card + .card { margin-top:0; }
  .stat svg { display:block; margin:14px 0 8px; }

  /* ------------------------------------------------------------- controls */
  .actionbar { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin: 16px 0; }
  .actionbar.tight { margin: 12px 0 0; }
  .btn { display:inline-flex; align-items:center; justify-content:center; gap:8px; height:38px; padding:0 16px; border-radius: var(--radius-sm);
    border:1px solid var(--line); background: var(--surface); color: var(--text); font: inherit; font-size:14px; font-weight:500; cursor:pointer;
    transition: background .15s, border-color .15s, transform .05s, box-shadow .15s; white-space:nowrap; }
  .btn:hover:not(:disabled) { background: var(--surface-2); border-color: var(--line-strong); }
  .btn:active:not(:disabled) { transform: translateY(1px); }
  .btn:focus-visible, .tab:focus-visible, .chip:focus-visible, .mode:focus-visible, .key:focus-visible, .f-row:focus-visible, .seg-item:focus-visible {
    outline:none; box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 35%, transparent); }
  .btn.primary { background: var(--accent); color: var(--on-accent); border-color: transparent; box-shadow: 0 4px 14px -6px var(--accent); }
  .btn.primary:hover:not(:disabled) { background: color-mix(in srgb, var(--accent) 88%, #000); }
  .btn.danger { background: ${SEV.critical.color}; color:#fff; border-color: transparent; }
  .btn.danger:hover:not(:disabled) { background: color-mix(in srgb, ${SEV.critical.color} 88%, #000); }
  .btn.ghost { background: transparent; border-color: transparent; color: var(--muted); }
  .btn.ghost:hover:not(:disabled) { background: var(--surface-2); color: var(--text); }
  .btn.ghost.danger { color: ${SEV.critical.color}; background: transparent; }
  .btn.ghost.danger:hover:not(:disabled) { background: color-mix(in srgb, ${SEV.critical.color} 10%, transparent); }
  .btn.small { height:30px; padding:0 10px; font-size:13px; border-radius:8px; gap:6px; }
  .btn.small ha-icon { --mdc-icon-size: 16px; }
  .btn:disabled { opacity:.5; cursor:default; box-shadow:none; }
  .link { display:inline-flex; align-items:center; gap:8px; background:none; border:none; color: var(--text); font: inherit; font-size:13px; cursor:pointer; padding:0; text-align:left; min-width:0; }
  .link span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .link:hover { color: var(--accent); }
  .input { height:38px; padding:0 12px; border-radius: var(--radius-sm); border:1px solid var(--line); background: var(--surface-2); color: inherit;
    font: inherit; font-size:14px; min-width:0; transition: border-color .15s, box-shadow .15s, background .15s; }
  .input:focus { outline:none; border-color: var(--accent); background: var(--surface); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 20%, transparent); }
  select.input { padding-right:28px; }
  .actionbar .input.grow, .input.grow { flex:1; min-width:200px; }
  .filters { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin: 24px 0 12px; }
  .chip { display:inline-flex; align-items:center; gap:6px; height:30px; padding:0 12px; border-radius:999px; font-size:13px; font-weight:500;
    border:1px solid var(--line); background: var(--surface); color: var(--text); font-family: inherit; }
  button.chip { cursor:pointer; transition: background .15s, border-color .15s; }
  button.chip:hover { border-color: var(--line-strong); }
  .chip.on { background: var(--text); color: var(--bg); border-color: transparent; }
  .chip.on .count { color: color-mix(in srgb, var(--bg) 70%, transparent); }
  .chip.on ha-icon { color: inherit !important; }
  .chip .count { color: var(--muted); font-variant-numeric: tabular-nums; }
  .chip ha-icon { --mdc-icon-size: 16px; }
  .chip.tiny { height:22px; padding:0 8px; font-size:11px; font-weight:600; background: color-mix(in srgb, var(--c, #8a8f98) 15%, transparent);
    color: var(--text); border-color: transparent; }
  .chip.tiny ha-icon { --mdc-icon-size: 13px; }
  .chip.big { height:34px; font-size:14px; padding:0 14px; }
  .chip.alarm { background: color-mix(in srgb, ${SEV.critical.color} 16%, transparent); border-color: ${SEV.critical.color}; }
  .chip.check { cursor:pointer; }
  .chip.check input { accent-color: var(--accent); margin:0; width:16px; height:16px; }
  .switch input[type=checkbox] { appearance:none; -webkit-appearance:none; flex:none; margin:0; width:36px; height:20px; border-radius:999px;
    background: var(--line-strong); position:relative; cursor:pointer; transition: background .15s; }
  .switch input[type=checkbox]::after { content:""; position:absolute; top:2px; left:2px; width:16px; height:16px; border-radius:50%; background:#fff;
    box-shadow: 0 1px 3px rgba(0,0,0,.3); transition: transform .15s; }
  .switch input[type=checkbox]:checked { background: var(--accent); }
  .switch input[type=checkbox]:checked::after { transform: translateX(16px); }
  .switch input[type=checkbox]:focus-visible { outline:none; box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 30%, transparent); }
  .switch { display:inline-flex; align-items:center; gap:8px; font-size:13px; color: var(--muted); cursor:pointer; }
  .switch.block { display:flex; margin:12px 0; color: var(--text); font-size:14px; }
  .segmented { display:inline-flex; flex-wrap:wrap; gap:4px; padding:4px; border-radius:12px; background: var(--surface-2); border:1px solid var(--line); margin-bottom:16px; }
  .seg-item { height:32px; padding:0 14px; border:none; border-radius:9px; background:none; color: var(--muted); font: inherit; font-size:13px; font-weight:500; cursor:pointer; }
  .seg-item:hover { color: var(--text); }
  .seg-item.on { background: var(--surface); color: var(--text); box-shadow: 0 1px 3px rgba(0,0,0,.15); }

  /* ------------------------------------------------------------- findings */
  .findings { padding:4px; }
  .finding { border-radius: var(--radius); transition: background .15s; }
  .finding + .finding { border-top:1px solid var(--line); border-radius:0; }
  .finding.open { background: var(--surface-2); border-radius: var(--radius); }
  .finding.open + .finding { border-top-color: transparent; }
  .finding.dismissed { opacity:.5; }
  .f-row { display:flex; align-items:center; gap:14px; width:100%; padding:14px 14px; background:none; border:none; color: inherit; font: inherit; text-align:left; cursor:pointer; border-radius: var(--radius); }
  .f-row:hover { background: var(--surface-2); }
  .sev-badge { width:36px; height:36px; border-radius:10px; flex:none; display:flex; align-items:center; justify-content:center;
    background: color-mix(in srgb, var(--sev) 16%, transparent); color: var(--sev); }
  .f-main { flex:1; min-width:0; display:flex; flex-direction:column; gap:3px; }
  .f-title { font-size:15px; font-weight:600; overflow-wrap:anywhere; }
  .f-meta { display:flex; align-items:center; gap:4px; flex-wrap:wrap; font-size:12px; color: var(--muted); }
  .f-meta ha-icon { --mdc-icon-size: 14px; }
  .sev-label { display:inline-flex; align-items:center; gap:6px; color: var(--text); font-weight:600; }
  .sev-label::before { content:""; width:7px; height:7px; border-radius:50%; background: var(--sev); }
  .chevron { color: var(--muted); transition: transform .2s; }
  .finding.open .chevron { transform: rotate(180deg); }
  .f-body { padding: 0 16px 16px 64px; }
  .desc { margin:0; font-size:14px; line-height:1.55; overflow-wrap:anywhere; }
  .advice { display:flex; gap:10px; align-items:flex-start; margin-top:12px; padding:12px 14px; border-radius: var(--radius-sm); font-size:13px; line-height:1.5;
    background: var(--surface); border:1px solid var(--line); overflow-wrap:anywhere; }
  .advice ha-icon { color: ${SEV.medium.color}; }
  .f-actions { display:flex; justify-content:flex-end; gap:8px; margin-top:12px; }
  @media (max-width: 600px) { .f-body { padding-left:16px; } }

  .banner { display:flex; gap:10px; align-items:flex-start; padding:12px 14px; border-radius: var(--radius); margin:12px 0; font-size:13px;
    background: color-mix(in srgb, ${SEV.medium.color} 12%, var(--surface)); border:1px solid color-mix(in srgb, ${SEV.medium.color} 40%, transparent); overflow-wrap:anywhere; }
  details.report { margin-top:16px; }
  details.report summary { display:flex; align-items:center; gap:10px; cursor:pointer; list-style:none; font-size:15px; }
  details.report summary ha-icon { color: var(--accent); }
  details.report summary::-webkit-details-marker { display:none; }
  .report-title { font-weight:600; margin-top:14px; }
  .report-body { white-space:pre-wrap; font-family: inherit; font-size:14px; line-height:1.6; margin:8px 0 0; }

  /* ------------------------------------------------------------- lists */
  .list { padding:6px; }
  .row { display:flex; align-items:center; gap:14px; padding:12px; border-radius: var(--radius-sm); }
  .row + .row { border-top:1px solid var(--line); }
  .list .row:hover { background: var(--surface-2); }
  .row > ha-icon:first-child { width:34px; height:34px; border-radius:10px; align-items:center; justify-content:center;
    background: color-mix(in srgb, currentColor 13%, transparent); }
  .row-main { flex:1; min-width:0; display:flex; flex-direction:column; gap:3px; overflow-wrap:anywhere; font-size:14px; }
  .row-main b { font-weight:600; }

  /* ------------------------------------------------------------- git */
  .git-head { display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }
  .facts { display:grid; grid-template-columns: max-content 1fr; gap:10px 24px; margin:18px 0 0; font-size:14px; }
  .facts dt { color: var(--muted); }
  .facts dd { margin:0; display:flex; align-items:center; gap:8px; overflow-wrap:anywhere; min-width:0; }
  .secret { display:flex; align-items:center; gap:8px; margin:6px 0 10px; flex-wrap:wrap; }
  .secret code { flex:1; min-width:200px; padding:10px 12px; border-radius: var(--radius-sm); font-family: var(--mono); font-size:12px; overflow-x:auto; white-space:nowrap;
    background: var(--surface-2); border:1px solid var(--line); }
  .split { display:grid; grid-template-columns: minmax(280px, 2fr) 3fr; gap:16px; align-items:start; margin-top:16px; }
  .split .card + .card { margin-top:0; }
  .commits { max-height: 72vh; overflow:auto; padding:14px; }
  .commit { display:flex; gap:12px; align-items:flex-start; width:100%; text-align:left; background:none; border:1px solid transparent; color: inherit;
    font: inherit; padding:10px; border-radius: var(--radius-sm); cursor:pointer; }
  .commit:hover { background: var(--surface-2); }
  .commit.selected { border-color: color-mix(in srgb, var(--accent) 50%, transparent); background: color-mix(in srgb, var(--accent) 9%, transparent); }
  .commit-summary { font-size:13px; font-weight:600; }
  .restore { padding:14px; border-radius: var(--radius); background: var(--surface-2); margin-bottom:14px; }
  .area-chips { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:10px; }
  .files { display:flex; flex-direction:column; }
  .file { display:flex; align-items:center; gap:10px; padding:8px 6px; border-bottom:1px solid var(--line); }
  .file .link { flex:1; }
  .file.selected .link { color: var(--accent); }
  .diff { background: #0d1117; color:#c9d1d9; padding:14px; border-radius: var(--radius); overflow:auto; font-family: var(--mono); font-size:12px; line-height:1.5; max-height:520px; margin-top:14px; }
  .diff .add { color:#7ee787; } .diff .del { color:#ff7b72; } .diff .hunk { color:#79c0ff; }

  /* ------------------------------------------------------------- anomalies / external */
  .alarm-card { border-color: ${SEV.critical.color}; box-shadow: 0 0 0 1px ${SEV.critical.color} inset, var(--shadow); }
  .meter { height:6px; border-radius:999px; background: color-mix(in srgb, var(--accent) 16%, transparent); overflow:hidden; margin:6px 0 2px; max-width:340px; }
  .meter div { height:100%; border-radius:999px; background: var(--accent); }
  .ports { display:grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap:10px; margin-top:16px; }
  .port { display:flex; align-items:center; gap:12px; padding:12px 14px; border-radius: var(--radius); background: var(--surface-2); border:1px solid transparent; }
  .port > div { flex:1; min-width:0; }
  .port.open { border-color: color-mix(in srgb, ${SEV.critical.color} 55%, transparent); background: color-mix(in srgb, ${SEV.critical.color} 10%, var(--surface)); }

  /* ------------------------------------------------------------- alarm */
  .alarm-hero { display:flex; gap:28px; align-items:center; padding:28px; position:relative; overflow:hidden;
    border-color: color-mix(in srgb, var(--state) 35%, var(--line)); }
  .alarm-hero::before { content:""; position:absolute; inset:0; pointer-events:none;
    background: radial-gradient(600px 220px at 0% 0%, color-mix(in srgb, var(--state) 18%, transparent), transparent 70%); }
  .alarm-badge { position:relative; width:104px; height:104px; border-radius:50%; flex:none; display:flex; align-items:center; justify-content:center;
    background: color-mix(in srgb, var(--state) 16%, var(--surface)); color: var(--state);
    box-shadow: 0 0 0 8px color-mix(in srgb, var(--state) 7%, transparent), inset 0 0 0 1px color-mix(in srgb, var(--state) 35%, transparent); }
  .alarm-badge ha-icon { --mdc-icon-size: 50px; }
  .alarm-main { position:relative; flex:1; min-width:0; display:flex; flex-direction:column; gap:8px; }
  .alarm-state { font-size:32px; font-weight:700; letter-spacing:-.02em; line-height:1.1; }
  .pulse .alarm-badge { animation: pulse 1.2s ease-in-out infinite; }
  @keyframes pulse { 0%,100% { box-shadow: 0 0 0 8px color-mix(in srgb, var(--state) 18%, transparent); } 50% { box-shadow: 0 0 0 22px color-mix(in srgb, var(--state) 3%, transparent); } }
  .countdown-wrap { display:flex; flex-direction:column; gap:8px; max-width:380px; margin-top:4px; }
  .countdown { font-size:16px; font-weight:600; font-variant-numeric: tabular-nums; }
  .countdown-bar { height:8px; border-radius:999px; background: color-mix(in srgb, var(--state) 16%, transparent); overflow:hidden; }
  .countdown-bar > div { height:100%; width:100%; border-radius:999px; background: var(--state); transition: width 1s linear; }
  .trigger-info { display:flex; align-items:center; gap:8px; font-size:14px; }
  .mode-grid { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:12px; margin:16px 0 0; }
  .mode { position:relative; display:flex; flex-direction:column; align-items:flex-start; gap:2px; padding:18px; border-radius: var(--radius-lg); border:1px solid var(--line);
    background: var(--surface); color: var(--text); font: inherit; cursor:pointer; text-align:left; box-shadow: var(--shadow);
    transition: transform .12s, border-color .15s, background .15s, box-shadow .15s; }
  .mode:hover:not(:disabled) { transform: translateY(-2px); border-color: color-mix(in srgb, var(--mc) 45%, var(--line)); }
  .mode ha-icon { --mdc-icon-size: 24px; width:44px; height:44px; border-radius:12px; align-items:center; justify-content:center; margin-bottom:12px;
    color: var(--mc); background: color-mix(in srgb, var(--mc) 14%, transparent); }
  .mode.active { border-color: var(--mc); background: color-mix(in srgb, var(--mc) 9%, var(--surface)); box-shadow: 0 0 0 1px var(--mc) inset, var(--shadow); }
  .mode.active::after { content:""; position:absolute; top:16px; right:16px; width:10px; height:10px; border-radius:50%; background: var(--mc);
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--mc) 22%, transparent); }
  .mode-name { font-size:16px; font-weight:650; }
  .mode-hint { font-size:12px; color: var(--muted); }
  .mode:disabled { opacity:.55; cursor:default; }
  @media (max-width: 760px) {
    .mode-grid { grid-template-columns: repeat(2, minmax(0,1fr)); }
    .alarm-hero { flex-direction:column; text-align:center; }
    .countdown-wrap { margin: 4px auto 0; width:100%; }
    .trigger-info { justify-content:center; }
  }
  .room-grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap:16px; }
  .room-grid .card + .card { margin-top:0; }
  .room { padding:16px 18px; }
  .room.has-open { border-color: color-mix(in srgb, ${SEV.medium.color} 55%, var(--line)); }
  .room-head { display:flex; align-items:center; gap:10px; margin-bottom:8px; font-size:15px; }
  .room-icon { width:38px; height:38px; border-radius:12px; display:inline-flex; align-items:center; justify-content:center; flex:none;
    background: color-mix(in srgb, var(--accent) 13%, transparent); color: var(--accent); }
  .sensor { display:flex; align-items:center; gap:8px; padding:9px 0; border-top:1px solid var(--line); font-size:14px; }
  .sensor-name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; }
  .dot { width:9px; height:9px; border-radius:50%; flex:none; box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 0%, transparent); }
  .mini { width:22px; height:22px; border-radius:7px; font-size:11px; font-weight:700; display:inline-flex; align-items:center; justify-content:center;
    color: var(--muted); background: var(--surface-2); }
  .mini.on { color: var(--on-accent); background: var(--accent); }
  .mini.always { width:auto; padding:0 7px; color:#fff; background: ${SEV.critical.color}; }
  .type-icon { color: var(--muted); display:inline-flex; }
  .type-icon ha-icon { --mdc-icon-size: 16px; }

  .overlay { position:fixed; inset:0; z-index:20; background: rgba(8,10,14,.55); backdrop-filter: blur(4px); display:flex; align-items:center; justify-content:center; padding:16px;
    animation: fade .15s ease-out; }
  @keyframes fade { from { opacity:0; } }
  .modal { width:min(420px, 100%); background: var(--surface); border-radius:22px; padding:24px; border:1px solid var(--line); box-shadow: var(--shadow-lg);
    animation: rise .18s ease-out; }
  @keyframes rise { from { transform: translateY(8px); opacity:0; } }
  .code-display { font-size:28px; letter-spacing:.35em; text-align:center; padding:16px; border-radius: var(--radius); background: var(--surface-2); margin-bottom:16px; min-height:40px; }
  .keypad { display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; margin-bottom:6px; }
  .key { height:60px; border-radius:16px; border:1px solid var(--line); background: var(--surface-2); color: var(--text); font: inherit; font-size:22px; font-weight:500;
    cursor:pointer; display:flex; align-items:center; justify-content:center; transition: background .12s, transform .05s; }
  .key:hover { background: var(--surface-3); }
  .key:active { transform: scale(.97); background: color-mix(in srgb, var(--accent) 18%, var(--surface-2)); }
  .open-list { margin:10px 0 0 18px; padding:0; line-height:1.8; }

  .edit-room { padding:18px; }
  .room-edit-head { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:4px; }
  .room-edit-head .input { height:40px; font-size:15px; }
  .icon-pick { position:relative; border:1px solid transparent; cursor:pointer; padding:0; font:inherit; }
  .icon-pick:hover, .icon-pick.on { border-color: var(--accent); }
  .icon-pick .pick-caret { position:absolute; right:-5px; bottom:-5px; width:16px; height:16px; border-radius:50%; display:grid; place-items:center;
    background: var(--surface); border:1px solid var(--line); color: var(--secondary-text-color); --mdc-icon-size:12px; }
  .icon-panel { margin:10px 0 6px; padding:12px; border:1px solid var(--line); border-radius: var(--radius-sm); background: var(--surface-2); }
  .icon-panel > .input { width:100%; }
  .icon-grid { display:grid; grid-template-columns: repeat(auto-fill, minmax(42px, 1fr)); gap:4px; max-height:232px; overflow:auto; margin:10px 0; }
  .icon-opt { height:42px; border-radius:10px; border:1px solid transparent; background:transparent; color: var(--primary-text-color); cursor:pointer; display:grid; place-items:center; }
  .icon-opt:hover { background: var(--surface); border-color: var(--line); }
  .icon-opt.on { border-color: var(--accent); color: var(--accent); background: color-mix(in srgb, var(--accent) 12%, transparent); }
  .icon-opt[hidden] { display:none; }
  .icon-custom { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
  .icon-custom .input { width:200px; }
  .fp-wrap { margin:12px 0 6px; padding:12px; border-radius: var(--radius-sm); background: var(--surface-2); border:1px solid var(--line); }
  .fp-svg { display:block; width:100%; max-height:460px; }
  .fp-area { fill: color-mix(in srgb, var(--accent) 7%, transparent); stroke:none; }
  .fp-area.out { fill: transparent; stroke: var(--line); stroke-dasharray: 6 6; }
  .fp-label { fill: var(--secondary-text-color); font-size:18px; text-anchor:middle; dominant-baseline:middle; font-family: inherit; }
  .fp-wall { fill:none; stroke: var(--primary-text-color); stroke-width:8; stroke-linecap:square; stroke-linejoin:miter; opacity:.75; }
  .fp-wall.ext { stroke-width:12; }
  .fp-glass { stroke:#6ab7ff; stroke-width:6; }
  .fp-div { fill:none; stroke: var(--secondary-text-color); stroke-width:2; stroke-dasharray:4 8; }
  .fp-box { fill: color-mix(in srgb, var(--primary-text-color) 12%, transparent); stroke:none; }
  .fp-door { stroke: ${SEV.medium.color}; stroke-width:6; stroke-linecap:round; }
  .fp-text { width:100%; height:auto; min-height:140px; font-family: var(--mono); font-size:12px; padding:10px; margin-top:8px; }
  .fp-row { display:grid; grid-template-columns: minmax(120px, 1fr) minmax(160px, 260px); gap:10px; align-items:center; padding:6px 0; border-top:1px solid var(--line); }
  .person-row { display:grid; grid-template-columns: 38px minmax(120px, 1fr) minmax(200px, 300px) 104px 96px 36px; gap:10px; align-items:center; padding:10px 0; border-top:1px solid var(--line); }
  .person-src { display:flex; flex-direction:column; gap:6px; min-width:0; }
  .person-src .input { width:100%; }
  .person-row > .chip { justify-self:start; }
  .person-row:first-child { border-top:0; }
  .person-seen { grid-column: 2 / -1; font-size:12px; margin-top:-4px; }
  .warn-text { color: ${SEV.medium.color}; }
  .people-strip { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:6px; }
  .people-strip .chip .muted { margin-left:4px; }
  @media (max-width: 640px) {
    .person-row { grid-template-columns: 38px minmax(0, 1fr); }
    .person-row > .input, .person-row > .person-src, .person-row > .chip, .person-row > .btn { grid-column: 2; justify-self: start; }
    .person-row > .person-src { justify-self: stretch; }
    .person-row > .input { justify-self: stretch; }
  }
  .room-edit-head .input:first-of-type { font-weight:600; }
  .exposure { margin-top:14px; padding:12px 14px; border-radius: var(--radius); background: var(--surface-2); }
  .exposure-head { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:6px; }
  .exposure-row { display:flex; align-items:flex-start; gap:8px; padding:4px 0; font-size:14px; }
  .exposure-row ha-icon { --mdc-icon-size: 18px; flex:none; }
  .sound-list { padding:6px 20px 16px; }
  .sound-row { display:flex; align-items:center; gap:14px; padding:12px 0; border-bottom:1px solid var(--line); }
  .sound-ident { flex:1; min-width:0; }
  .sound-title { font-weight:600; }
  .sound-select { width:240px; flex:none; }
  .icon-btn.play { border:1px solid var(--line); background: var(--surface); color: var(--accent); }
  .icon-btn.play:hover { background: color-mix(in srgb, var(--accent) 12%, transparent); color: var(--accent); }
  .icon-btn.play:disabled { opacity:.4; cursor:default; }
  .upload { position:relative; overflow:hidden; cursor:pointer; }
  .upload input { position:absolute; inset:0; opacity:0; cursor:pointer; }
  .fld.vol { flex:1 1 220px; }
  .range-row { display:flex; align-items:center; gap:12px; height:36px; }
  .range-row input[type=range] { flex:1; accent-color: var(--accent); }
  .range-row b { min-width:48px; text-align:right; font-variant-numeric: tabular-nums; font-weight:600; }
  @media (max-width: 600px) { .sound-row { flex-wrap:wrap; } .sound-select { width:auto; flex:1; } }
  .sensor-card { background: var(--surface-2); border-radius: var(--radius); padding:14px 16px 16px; margin-top:10px; }
  .sensor-card-head { display:flex; align-items:center; gap:12px; }
  .sensor-card-head .dot { box-shadow: 0 0 0 4px color-mix(in srgb, var(--surface) 70%, transparent); }
  .sensor-ident { flex:1; min-width:0; }
  .sensor-title { font-size:15px; font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .name-input { display:block; width:100%; max-width:420px; margin:-4px 0 0 -9px; padding:4px 8px; border-radius:8px; border:1px solid transparent;
    background:transparent; color: var(--text); font: inherit; font-size:15px; font-weight:600; outline:none; transition: border-color .15s, background .15s; }
  .name-input::placeholder { color: var(--text); opacity:1; }
  .name-input:hover { border-color: var(--line); background: var(--surface); }
  .name-input:focus { border-color: var(--accent); background: var(--surface); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 20%, transparent); }
  .name-input:focus::placeholder { color: var(--muted); }
  .sensor-id { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-top:2px; }
  .icon-btn { width:32px; height:32px; flex:none; border-radius:9px; border:none; background:none; color: var(--muted); cursor:pointer;
    display:inline-flex; align-items:center; justify-content:center; transition: background .15s, color .15s; }
  .icon-btn:hover { background: color-mix(in srgb, ${SEV.critical.color} 12%, transparent); color: ${SEV.critical.color}; }
  .sensor-fields { display:flex; flex-wrap:wrap; align-items:flex-end; gap:14px 24px; margin-top:14px; padding-left:21px; }
  .fld { display:flex; flex-direction:column; gap:7px; min-width:0; }
  .fld-label { display:inline-flex; align-items:center; gap:6px; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.05em; color: var(--muted); white-space:nowrap; }
  .fld-label ha-icon { --mdc-icon-size: 14px; }
  .type-select { height:36px; min-width:150px; background: var(--surface); }
  .suffix { display:inline-flex; align-items:center; height:36px; border-radius: var(--radius-sm); border:1px solid var(--line); background: var(--surface);
    transition: border-color .15s, box-shadow .15s; }
  .suffix:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 20%, transparent); }
  .suffix input { width:70px; height:100%; border:none; background:none; color: inherit; font: inherit; font-size:14px; text-align:right; padding:0 6px 0 12px; outline:none;
    font-variant-numeric: tabular-nums; -moz-appearance: textfield; appearance: textfield; }
  .suffix input::placeholder { color: var(--muted); font-size:13px; }
  .suffix span { padding-right:12px; color: var(--muted); font-size:13px; }
  input[type=number]::-webkit-inner-spin-button, input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin:0; }
  input[type=number] { -moz-appearance: textfield; appearance: textfield; }
  .sensor-fields .seg { background: var(--surface); border:1px solid var(--line); }
  .sensor-fields .switch { height:36px; color: var(--text); }
  @media (max-width: 600px) {
    .sensor-card { padding:12px 12px 14px; }
    .sensor-fields { padding-left:0; gap:14px 12px; }
    .sensor-fields .fld { flex:1 1 120px; }
    .sensor-fields .fld:first-child, .sensor-fields .fld:has(.switch), .sensor-fields .fld:has(.type-select) { flex-basis:100%; }
    .sensor-fields .seg { display:flex; }
    .sensor-fields .seg-btn { flex:1; }
    .type-select { min-width:0; width:100%; }
    .suffix input { flex:1; width:0; min-width:0; }
  }
  .seg { display:inline-flex; padding:3px; gap:2px; border-radius:10px; background: var(--surface-2); }
  .seg-btn { height:28px; padding:0 10px; border:none; border-radius:8px; background:none; color: var(--muted); font: inherit; font-size:12px; font-weight:500; cursor:pointer; }
  .seg-btn.on { background: var(--accent); color: var(--on-accent); }
  .seg-btn:disabled { opacity:.35; cursor:default; }
  .delay { display:inline-flex; align-items:center; gap:6px; font-size:12px; color: var(--muted); white-space:nowrap; }
  .delay ha-icon { --mdc-icon-size: 16px; }
  .tiny-input { width:64px; height:34px; padding:0 8px; font-size:13px; text-align:right; }
  .tiny-input::placeholder { font-size:12px; }
  .add-sensor { width:100%; margin-top:12px; height:42px; border-style:dashed; border-color: var(--line-strong); background: transparent; color: var(--muted); cursor:pointer; }
  .add-sensor:hover { border-color: var(--accent); color: var(--text); }
  .mode-table { display:grid; grid-template-columns: 1fr 170px 170px; gap:14px 18px; align-items:center; }
  @media (max-width: 600px) { .mode-table { grid-template-columns: 1fr 92px 92px; } }
  .field { display:flex; align-items:center; justify-content:space-between; gap:14px; margin:12px 0; font-size:14px; }
  .field .input { max-width:340px; flex:1; }
  .field-block { margin-bottom:18px; }
  .chip-x { background:none; border:none; padding:0; margin-left:2px; color: var(--muted); cursor:pointer; display:inline-flex; }
  .chip-x ha-icon { --mdc-icon-size: 14px; }
  .steps { margin:12px 0 8px 18px; padding:0; font-size:13px; line-height:1.8; color: var(--muted); }

  .toast { position:fixed; left:50%; bottom:28px; transform:translateX(-50%); z-index:30; display:flex; align-items:center; gap:10px;
    max-width:min(560px, calc(100vw - 32px)); background: var(--text); color: var(--bg); padding:12px 18px; border-radius:14px; font-size:14px;
    box-shadow: var(--shadow-lg); animation: rise .18s ease-out; }
  .tip { position:fixed; z-index:31; pointer-events:none; background: var(--text); color: var(--bg); padding:5px 9px; border-radius:8px; font-size:12px; white-space:nowrap; }
  @media (max-width: 900px) { .split { grid-template-columns: 1fr; } .tiles { grid-template-columns: repeat(2, minmax(0,1fr)); } }
  @media (max-width: 600px) {
    .container { padding:20px 16px 48px; }
    .appbar-row { padding-right:12px; }
    .brand-sub, .pill-label, .alarm-pill { display:none; }
    .page-title h1 { font-size:21px; }
    .hero { justify-content:center; }
    .card { padding:16px; }
  }
`;

customElements.define("bastion-panel", BastionPanel);
