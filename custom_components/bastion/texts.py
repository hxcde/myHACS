"""User facing texts (German and English).

Findings, notifications and commit messages are rendered here instead of in
the frontend translation files, because they carry dynamic content and are
also sent through notify services.
"""

from __future__ import annotations

from typing import Any

# key: (title, description, recommendation)
FINDING_TEXTS: dict[str, dict[str, tuple[str, str, str]]] = {
    # --- access
    "mfa_missing": {
        "de": (
            "Benutzer ohne MFA: {user}",
            "{role} „{user}“ hat keine Zwei-Faktor-Authentifizierung aktiviert.",
            "Profil → Sicherheit → Multi-Faktor-Authentifizierung (TOTP) aktivieren.",
        ),
        "en": (
            "User without MFA: {user}",
            "{role} '{user}' has no multi-factor authentication enabled.",
            "Profile → Security → enable multi-factor authentication (TOTP).",
        ),
    },
    "too_many_admins": {
        "de": (
            "Viele Administratoren ({count})",
            "{count} aktive Benutzer haben Administratorrechte: {users}.",
            "Admin-Rechte nur an Konten vergeben, die sie wirklich brauchen.",
        ),
        "en": (
            "Many administrators ({count})",
            "{count} active users have administrator rights: {users}.",
            "Grant admin rights only to accounts that need them.",
        ),
    },
    "inactive_user": {
        "de": (
            "Ungenutztes Konto: {user}",
            "Das aktive Konto „{user}“ wurde seit {days} Tagen nicht verwendet.",
            "Konto deaktivieren oder löschen, wenn es nicht mehr gebraucht wird.",
        ),
        "en": (
            "Unused account: {user}",
            "The active account '{user}' has not been used for {days} days.",
            "Deactivate or delete the account if it is no longer needed.",
        ),
    },
    "token_old": {
        "de": (
            "Alter Long-Lived-Token: {name}",
            "Token „{name}“ von {user} ist {days} Tage alt.",
            "Token neu erstellen und den alten widerrufen (Profil → Sicherheit).",
        ),
        "en": (
            "Old long-lived token: {name}",
            "Token '{name}' of {user} is {days} days old.",
            "Create a new token and revoke the old one (Profile → Security).",
        ),
    },
    "token_unused": {
        "de": (
            "Ungenutzter Long-Lived-Token: {name}",
            "Token „{name}“ von {user} wurde {when}.",
            "Nicht mehr benötigte Tokens widerrufen.",
        ),
        "en": (
            "Unused long-lived token: {name}",
            "Token '{name}' of {user} was {when}.",
            "Revoke tokens that are no longer needed.",
        ),
    },
    "trusted_networks_wide": {
        "de": (
            "Zu weites trusted_networks: {network}",
            "Der Auth-Provider trusted_networks erlaubt Login ohne Passwort aus {network}.",
            "Nur einzelne Geräte-IPs oder kleine LAN-Bereiche eintragen.",
        ),
        "en": (
            "trusted_networks too wide: {network}",
            "The trusted_networks auth provider allows password-less login from {network}.",
            "Only list single device IPs or small LAN ranges.",
        ),
    },
    "trusted_networks_proxy": {
        "de": (
            "Reverse-Proxy in trusted_networks",
            "Das Netz {network} enthält einen Trusted Proxy. Anfragen über den Proxy können ohne Passwort angemeldet werden.",
            "Proxy-IP aus trusted_networks entfernen.",
        ),
        "en": (
            "Reverse proxy in trusted_networks",
            "Network {network} contains a trusted proxy. Requests through the proxy may log in without a password.",
            "Remove the proxy IP from trusted_networks.",
        ),
    },
    "trusted_networks_bypass": {
        "de": (
            "Login-Umgehung aktiv",
            "trusted_networks mit allow_bypass_login meldet Benutzer ohne Auswahl und Passwort an.",
            "allow_bypass_login deaktivieren.",
        ),
        "en": (
            "Login bypass enabled",
            "trusted_networks with allow_bypass_login logs users in without selection and password.",
            "Disable allow_bypass_login.",
        ),
    },
    # --- http / exposure
    "external_url_http": {
        "de": (
            "Externe URL ohne HTTPS",
            "Die externe URL {url} nutzt unverschlüsseltes HTTP. Passwörter und Tokens gehen im Klartext übers Netz.",
            "HTTPS über Reverse-Proxy, Cloudflare Tunnel oder Nabu Casa nutzen.",
        ),
        "en": (
            "External URL without HTTPS",
            "The external URL {url} uses plain HTTP. Passwords and tokens travel unencrypted.",
            "Use HTTPS via reverse proxy, Cloudflare Tunnel or Nabu Casa.",
        ),
    },
    "ip_ban_disabled": {
        "de": (
            "IP-Sperre deaktiviert",
            "Nach fehlgeschlagenen Logins werden IP-Adressen nicht gesperrt. Brute-Force-Angriffe sind unbegrenzt möglich.",
            "In der HTTP-Konfiguration ip_ban_enabled aktivieren und login_attempts_threshold (z. B. 5) setzen.",
        ),
        "en": (
            "IP ban disabled",
            "IP addresses are not banned after failed logins. Brute force attempts are unlimited.",
            "Enable ip_ban_enabled and set login_attempts_threshold (e.g. 5) in the HTTP configuration.",
        ),
    },
    "login_threshold_high": {
        "de": (
            "Hohe Login-Schwelle ({threshold})",
            "Eine IP wird erst nach {threshold} Fehlversuchen gesperrt.",
            "login_attempts_threshold auf 5 oder weniger setzen.",
        ),
        "en": (
            "High login threshold ({threshold})",
            "An IP is only banned after {threshold} failed attempts.",
            "Set login_attempts_threshold to 5 or less.",
        ),
    },
    "trusted_proxies_wide": {
        "de": (
            "Zu weite trusted_proxies: {network}",
            "Allen Adressen aus {network} wird beim X-Forwarded-For-Header vertraut. Dadurch lassen sich Absender-IPs fälschen und die IP-Sperre umgehen.",
            "Nur die IP des Reverse-Proxys eintragen.",
        ),
        "en": (
            "trusted_proxies too wide: {network}",
            "All addresses in {network} are trusted for X-Forwarded-For. Source IPs can be spoofed and IP bans bypassed.",
            "Only list the reverse proxy IP.",
        ),
    },
    "cors_wildcard": {
        "de": (
            "CORS erlaubt alle Ursprünge",
            "cors_allowed_origins enthält „*“.",
            "Nur benötigte Ursprünge eintragen.",
        ),
        "en": (
            "CORS allows all origins",
            "cors_allowed_origins contains '*'.",
            "Only list required origins.",
        ),
    },
    "webhook_weak_id": {
        "de": (
            "Schwache Webhook-ID: {name}",
            "Webhook „{name}“ ({domain}) hat eine kurze oder erratbare ID ({length} Zeichen){remote}. Webhooks laufen ohne Authentifizierung.",
            "Zufällige ID mit mindestens 32 Zeichen verwenden und „Nur lokal“ aktivieren, wenn möglich.",
        ),
        "en": (
            "Weak webhook ID: {name}",
            "Webhook '{name}' ({domain}) has a short or guessable ID ({length} characters){remote}. Webhooks are unauthenticated.",
            "Use a random ID with at least 32 characters and enable 'local only' where possible.",
        ),
    },
    "webhook_remote": {
        "de": (
            "Webhook aus dem Internet erreichbar: {name}",
            "Automations-Webhook „{name}“ akzeptiert Aufrufe von außerhalb des lokalen Netzes.",
            "„Nur lokal“ aktivieren, falls kein externer Dienst den Webhook braucht.",
        ),
        "en": (
            "Webhook reachable from the internet: {name}",
            "Automation webhook '{name}' accepts calls from outside the local network.",
            "Enable 'local only' unless an external service needs it.",
        ),
    },
    "voice_exposed_sensitive": {
        "de": (
            "Sicherheitskritisch freigegeben: {entity}",
            "{entity} ist für {assistant} freigegeben{pin}. Wer Zugriff auf den Sprachassistenten hat, kann es steuern.",
            "Freigabe entfernen oder PIN für sicherheitsrelevante Geräte setzen.",
        ),
        "en": (
            "Security relevant entity exposed: {entity}",
            "{entity} is exposed to {assistant}{pin}. Anyone with access to the voice assistant can control it.",
            "Remove the exposure or require a PIN for secure devices.",
        ),
    },
    "alarm_no_code": {
        "de": (
            "Alarmanlage ohne Code: {entity}",
            "{entity} lässt sich ohne Code entschärfen.",
            "Code für die Alarmanlage festlegen.",
        ),
        "en": (
            "Alarm panel without code: {entity}",
            "{entity} can be disarmed without a code.",
            "Configure a code for the alarm panel.",
        ),
    },
    # --- updates
    "ha_outdated": {
        "de": (
            "Home Assistant veraltet ({installed})",
            "Installiert: {installed}, aktuell: {latest}.",
            "Container-Image aktualisieren (docker pull + neu erstellen).",
        ),
        "en": (
            "Home Assistant outdated ({installed})",
            "Installed: {installed}, latest: {latest}.",
            "Update the container image (docker pull + recreate).",
        ),
    },
    "advisory": {
        "de": (
            "Sicherheitslücke: {summary}",
            "{component} {installed} ist betroffen von {ghsa}{cve} (Schweregrad {level}). Behoben in: {patched}.",
            "Auf {patched} oder neuer aktualisieren. Details: {url}",
        ),
        "en": (
            "Vulnerability: {summary}",
            "{component} {installed} is affected by {ghsa}{cve} (severity {level}). Fixed in: {patched}.",
            "Update to {patched} or newer. Details: {url}",
        ),
    },
    "esphome_no_encryption": {
        "de": (
            "ESPHome ohne API-Verschlüsselung: {device}",
            "{device} spricht unverschlüsselt mit Home Assistant. Im LAN kann mitgelesen und gesteuert werden.",
            "In der ESPHome-Config api: encryption: key: setzen und Gerät neu einbinden.",
        ),
        "en": (
            "ESPHome without API encryption: {device}",
            "{device} talks to Home Assistant unencrypted. Anyone on the LAN can read and control it.",
            "Set api: encryption: key: in the ESPHome config and re-add the device.",
        ),
    },
    "updates_pending": {
        "de": (
            "{count} Updates seit über {days} Tagen offen",
            "Ausstehend: {entities}.",
            "Updates zeitnah einspielen.",
        ),
        "en": (
            "{count} updates pending for more than {days} days",
            "Pending: {entities}.",
            "Install updates in time.",
        ),
    },
    "firmware_advisory": {
        "de": (
            "Sicherheitslücke in {firmware}-Firmware ({count} Geräte)",
            "{summary} ({ghsa}{cve}, Schweregrad {level}). Betroffen: {devices}. Behoben in: {patched}.",
            "Firmware der Geräte auf {patched} oder neuer aktualisieren. Details: {url}",
        ),
        "en": (
            "Vulnerability in {firmware} firmware ({count} devices)",
            "{summary} ({ghsa}{cve}, severity {level}). Affected: {devices}. Fixed in: {patched}.",
            "Update the device firmware to {patched} or newer. Details: {url}",
        ),
    },
    "mqtt_unencrypted": {
        "de": (
            "MQTT ohne TLS: {broker}",
            "Die Verbindung zum Broker {broker}:{port} ist unverschlüsselt{anon}.",
            "TLS (Port 8883) und Benutzer/Passwort verwenden, besonders bei Brokern außerhalb des Hosts.",
        ),
        "en": (
            "MQTT without TLS: {broker}",
            "The connection to broker {broker}:{port} is unencrypted{anon}.",
            "Use TLS (port 8883) and username/password, especially for brokers outside the host.",
        ),
    },
    # --- supply chain
    "custom_code_changed": {
        "de": (
            "Code geändert ohne Update: {domain}",
            "Dateien von {domain} wurden geändert, die Version ({version}) blieb gleich: {files}.",
            "Prüfen, wer die Dateien geändert hat. Ist die Änderung gewollt, Baseline übernehmen.",
        ),
        "en": (
            "Code changed without update: {domain}",
            "Files of {domain} changed while the version ({version}) stayed the same: {files}.",
            "Check who changed the files. If intended, accept the baseline.",
        ),
    },
    "custom_new": {
        "de": (
            "Neue Custom-Integration: {domain}",
            "{domain} ({version}) wurde neu installiert.",
            "Herkunft prüfen. Ist sie gewollt, Baseline übernehmen.",
        ),
        "en": (
            "New custom integration: {domain}",
            "{domain} ({version}) was newly installed.",
            "Verify where it comes from. If intended, accept the baseline.",
        ),
    },
    "www_changed": {
        "de": (
            "JavaScript in www/ geändert",
            "Geänderte oder neue Dateien: {files}.",
            "Änderung prüfen. Ist sie gewollt, Baseline übernehmen.",
        ),
        "en": (
            "JavaScript in www/ changed",
            "Changed or new files: {files}.",
            "Review the change. If intended, accept the baseline.",
        ),
    },
    "repo_archived": {
        "de": (
            "Archiviertes Repo: {domain}",
            "Das Repository {repo} ist archiviert und bekommt keine Sicherheitsupdates mehr.",
            "Alternative suchen oder Integration entfernen.",
        ),
        "en": (
            "Archived repository: {domain}",
            "Repository {repo} is archived and gets no security updates.",
            "Look for an alternative or remove the integration.",
        ),
    },
    "repo_stale": {
        "de": (
            "Nicht gepflegtes Repo: {domain}",
            "{repo} hatte seit {days} Tagen keine Änderung.",
            "Prüfen, ob die Integration noch gepflegt wird.",
        ),
        "en": (
            "Unmaintained repository: {domain}",
            "{repo} had no change for {days} days.",
            "Check whether the integration is still maintained.",
        ),
    },
    "repo_moved": {
        "de": (
            "Repo übertragen oder umbenannt: {domain}",
            "{old} zeigt jetzt auf {new}. Ein neuer Besitzer kann beliebigen Code ausliefern.",
            "Neuen Besitzer prüfen, bevor das nächste Update installiert wird.",
        ),
        "en": (
            "Repository transferred or renamed: {domain}",
            "{old} now points to {new}. A new owner can ship arbitrary code.",
            "Verify the new owner before installing the next update.",
        ),
    },
    "repo_missing": {
        "de": (
            "Repo nicht mehr vorhanden: {domain}",
            "{repo} ist nicht mehr erreichbar (gelöscht oder privat).",
            "Integration ersetzen oder entfernen.",
        ),
        "en": (
            "Repository gone: {domain}",
            "{repo} is no longer reachable (deleted or private).",
            "Replace or remove the integration.",
        ),
    },
    "repo_new_owner": {
        "de": (
            "Sehr neuer Account: {domain}",
            "Der Besitzer von {repo} existiert erst seit {days} Tagen.",
            "Code und Herkunft genau prüfen (Warnzeichen für Nachahmer-Integrationen).",
        ),
        "en": (
            "Very new account: {domain}",
            "The owner of {repo} has existed for only {days} days.",
            "Review code and origin carefully (warning sign for copycat integrations).",
        ),
    },
    "custom_unused": {
        "de": (
            "Ungenutzte Custom-Integration: {domain}",
            "{domain} ist installiert, aber nicht geladen.",
            "Nicht benötigte Integrationen deinstallieren (weniger Angriffsfläche).",
        ),
        "en": (
            "Unused custom integration: {domain}",
            "{domain} is installed but not loaded.",
            "Uninstall integrations you do not need (smaller attack surface).",
        ),
    },
    "external_resource": {
        "de": (
            "Externe Dashboard-Ressource: {host}",
            "Das Dashboard lädt JavaScript von {url}. Wer diese Quelle kontrolliert, kann Code im Browser jedes Benutzers ausführen.",
            "Ressource lokal ablegen (www/ oder Marketplace) statt von fremden Servern zu laden.",
        ),
        "en": (
            "External dashboard resource: {host}",
            "The dashboard loads JavaScript from {url}. Whoever controls that source can run code in every user's browser.",
            "Host the resource locally (www/ or Marketplace) instead of loading it from third party servers.",
        ),
    },
    # --- config
    "plaintext_secret": {
        "de": (
            "Klartext-Zugangsdaten in {file}",
            "Mögliche Zugangsdaten in Zeile {lines} ({kinds}).",
            "Werte nach secrets.yaml verschieben und mit !secret referenzieren.",
        ),
        "en": (
            "Plain text credentials in {file}",
            "Possible credentials on line {lines} ({kinds}).",
            "Move the values to secrets.yaml and reference them with !secret.",
        ),
    },
    "shell_template": {
        "de": (
            "Template in {kind}: {name}",
            "{kind} „{name}“ setzt Template-Werte in einen Befehl ein{shell}. Manipulierte Zustände oder Webhook-Daten können Befehle einschleusen.",
            "Eingaben im Template validieren oder feste Befehle verwenden.",
        ),
        "en": (
            "Template in {kind}: {name}",
            "{kind} '{name}' inserts template values into a command{shell}. Manipulated states or webhook data can inject commands.",
            "Validate template inputs or use fixed commands.",
        ),
    },
    "python_script_enabled": {
        "de": (
            "{name} aktiv",
            "{name} führt eigenen Python-Code in Home Assistant aus.",
            "Nur nutzen, wenn nötig, und Skripte prüfen.",
        ),
        "en": (
            "{name} enabled",
            "{name} runs custom Python code inside Home Assistant.",
            "Only use when needed and review the scripts.",
        ),
    },
    "debug_console_enabled": {
        "de": (
            "Debug-Konsole aktiv",
            "debug_console gibt Administratoren vollen Zugriff auf alle Interna von Home Assistant.",
            "Nach der Fehlersuche wieder aus configuration.yaml entfernen.",
        ),
        "en": (
            "Debug console enabled",
            "debug_console gives administrators full access to all Home Assistant internals.",
            "Remove it from configuration.yaml after debugging.",
        ),
    },
    "secrets_world_readable": {
        "de": (
            "secrets.yaml für alle lesbar",
            "Die Datei hat die Rechte {mode}.",
            "Rechte auf 600 setzen.",
        ),
        "en": (
            "secrets.yaml world readable",
            "The file has mode {mode}.",
            "Set mode 600.",
        ),
    },
    "backup_unencrypted": {
        "de": (
            "Backups unverschlüsselt",
            "Automatische Backups werden ohne Passwort erstellt{agents}.",
            "Unter Einstellungen → System → Backups die Verschlüsselung aktivieren.",
        ),
        "en": (
            "Backups not encrypted",
            "Automatic backups are created without a password{agents}.",
            "Enable encryption under Settings → System → Backups.",
        ),
    },
    "backup_local_only": {
        "de": (
            "Backups nur lokal",
            "Backups werden nur auf diesem System gespeichert. Bei Defekt oder Ransomware sind sie mit weg.",
            "Ein externes Backup-Ziel (NAS, Cloud) hinzufügen.",
        ),
        "en": (
            "Backups stored locally only",
            "Backups are only stored on this system. They are lost on hardware failure or ransomware.",
            "Add an off-site backup location (NAS, cloud).",
        ),
    },
    "backup_stale": {
        "de": (
            "Kein aktuelles Backup",
            "Letztes erfolgreiches automatisches Backup: {when}.",
            "Automatische Backups einrichten und Fehler prüfen.",
        ),
        "en": (
            "No recent backup",
            "Last successful automatic backup: {when}.",
            "Configure automatic backups and check for errors.",
        ),
    },
    # --- supervisor
    "addon_risky": {
        "de": (
            "Add-on mit weitreichenden Rechten: {name}",
            "{name}: {flags}.",
            "Nur vertrauenswürdige Add-ons mit diesen Rechten betreiben, Protection Mode aktiv lassen.",
        ),
        "en": (
            "Add-on with broad privileges: {name}",
            "{name}: {flags}.",
            "Only run trusted add-ons with these privileges, keep protection mode enabled.",
        ),
    },
    "addon_port_exposed": {
        "de": (
            "Add-on-Port freigegeben: {name}",
            "{name} veröffentlicht die Ports {ports} am Host.",
            "Nicht benötigte Port-Mappings in der Add-on-Konfiguration entfernen.",
        ),
        "en": (
            "Add-on port exposed: {name}",
            "{name} publishes ports {ports} on the host.",
            "Remove unneeded port mappings in the add-on configuration.",
        ),
    },
    # --- external probe
    "port_open": {
        "de": (
            "Port {port} aus dem Internet erreichbar ({service})",
            "Die öffentliche Adresse {ip} nimmt Verbindungen auf Port {port} ({service}) an.",
            "{advice}",
        ),
        "en": (
            "Port {port} reachable from the internet ({service})",
            "The public address {ip} accepts connections on port {port} ({service}).",
            "{advice}",
        ),
    },
    "probe_failed": {
        "de": (
            "Externe Prüfung fehlgeschlagen",
            "Die externe Prüfstelle ist nicht erreichbar: {error}.",
            "URL und Token der Prüfstelle prüfen.",
        ),
        "en": (
            "External probe failed",
            "The external probe could not be reached: {error}.",
            "Check probe URL and token.",
        ),
    },
    # --- git
    "git_repo_public": {
        "de": (
            "Git-Repo ist öffentlich",
            "{repo} ist ohne Anmeldung lesbar. Bastion pusht nicht in öffentliche Repositories.",
            "Repository auf privat stellen.",
        ),
        "en": (
            "Git repository is public",
            "{repo} is readable without authentication. Bastion does not push to public repositories.",
            "Make the repository private.",
        ),
    },
    "git_repo_unverified": {
        "de": (
            "Git-Repo: privat nicht überprüfbar",
            "Für {repo} konnte nicht geprüft werden, ob es privat ist. Push ist gesperrt.",
            "In den Git-Optionen bestätigen, dass das Repo privat ist.",
        ),
        "en": (
            "Git repository: privacy not verifiable",
            "Bastion could not verify that {repo} is private. Push is blocked.",
            "Confirm in the git options that the repository is private.",
        ),
    },
    "git_push_failed": {
        "de": (
            "Git-Push fehlgeschlagen",
            "Der letzte Push ist fehlgeschlagen: {error}. Commits bleiben lokal und werden erneut versucht.",
            "Deploy-Key/Token, Netzwerk und Schreibrechte prüfen.",
        ),
        "en": (
            "Git push failed",
            "The last push failed: {error}. Commits stay local and will be retried.",
            "Check deploy key/token, network and write access.",
        ),
    },
    "git_host_key_changed": {
        "de": (
            "SSH-Hostkey des Git-Servers geändert",
            "{host} hat einen anderen Hostkey geliefert als hinterlegt. Mögliche Man-in-the-Middle-Attacke. Sync gestoppt.",
            "Fingerprint beim Anbieter prüfen und in den Git-Optionen neu bestätigen.",
        ),
        "en": (
            "SSH host key of git server changed",
            "{host} presented a different host key than stored. Possible man-in-the-middle attack. Sync stopped.",
            "Verify the fingerprint with the provider and confirm it again in the git options.",
        ),
    },
    "git_secrets_skipped": {
        "de": (
            "Dateien mit Secrets nicht gesichert",
            "Ohne Passphrase werden diese Dateien nicht übertragen: {files}.",
            "In den Git-Optionen eine Passphrase für die Verschlüsselung setzen.",
        ),
        "en": (
            "Files with secrets not backed up",
            "Without a passphrase these files are not pushed: {files}.",
            "Set an encryption passphrase in the git options.",
        ),
    },
    "restore_pending": {
        "de": (
            "Wiederherstellung wartet auf Neustart",
            "Es liegen vorbereitete Dateien aus Commit {commit} bereit. Sie werden beim nächsten Neustart eingespielt.",
            "Home Assistant neu starten.",
        ),
        "en": (
            "Restore waiting for restart",
            "Staged files from commit {commit} will be applied on the next restart.",
            "Restart Home Assistant.",
        ),
    },
}

ROLE = {"de": {"admin": "Administrator", "user": "Benutzer"}, "en": {"admin": "Administrator", "user": "User"}}

EVENT_TEXTS: dict[str, dict[str, tuple[str, str]]] = {
    "login": {
        "de": ("Neue Anmeldung: {user}", "{user} hat sich von {ip}{geo} angemeldet ({client})."),
        "en": ("New login: {user}", "{user} logged in from {ip}{geo} ({client})."),
    },
    "new_ip": {
        "de": ("Neue IP für {user}", "{user} nutzt Home Assistant zum ersten Mal von {ip}{geo} ({client})."),
        "en": ("New IP for {user}", "{user} uses Home Assistant from {ip}{geo} for the first time ({client})."),
    },
    "failed_login": {
        "de": ("Fehlgeschlagene Anmeldung", "Fehlversuch von {ip} ({host})."),
        "en": ("Failed login", "Failed attempt from {ip} ({host})."),
    },
    "brute_force": {
        "de": ("Brute-Force-Verdacht", "{count} Fehlversuche in {minutes} Minuten, zuletzt von {ip}."),
        "en": ("Possible brute force", "{count} failed attempts in {minutes} minutes, last from {ip}."),
    },
    "ip_banned": {
        "de": ("IP gesperrt", "{ip} wurde nach zu vielen Fehlversuchen gesperrt."),
        "en": ("IP banned", "{ip} was banned after too many failed attempts."),
    },
    "token_created": {
        "de": ("Neuer Long-Lived-Token", "Für {user} wurde der Token „{name}“ erstellt."),
        "en": ("New long-lived token", "Token '{name}' was created for {user}."),
    },
    "token_removed": {
        "de": ("Long-Lived-Token entfernt", "Token „{name}“ von {user} wurde widerrufen."),
        "en": ("Long-lived token removed", "Token '{name}' of {user} was revoked."),
    },
    "user_added": {
        "de": ("Neuer Benutzer", "Benutzer „{user}“ wurde angelegt{admin}."),
        "en": ("New user", "User '{user}' was created{admin}."),
    },
    "user_removed": {
        "de": ("Benutzer gelöscht", "Benutzer „{user}“ wurde gelöscht."),
        "en": ("User removed", "User '{user}' was removed."),
    },
    "admin_granted": {
        "de": ("Admin-Rechte vergeben", "„{user}“ ist jetzt Administrator."),
        "en": ("Admin rights granted", "'{user}' is now an administrator."),
    },
    "user_activated": {
        "de": ("Benutzer aktiviert", "„{user}“ wurde aktiviert."),
        "en": ("User activated", "'{user}' was activated."),
    },
    "unusual_login_time": {
        "de": ("Anmeldung zu ungewöhnlicher Zeit", "{user} hat sich um {hour} Uhr angemeldet, das ist untypisch."),
        "en": ("Login at unusual time", "{user} logged in at {hour}:00, which is unusual."),
    },
    "unusual_action": {
        "de": ("Ungewöhnliche Aktion", "{actor} hat {service} für {entities} ausgeführt ({reason})."),
        "en": ("Unusual action", "{actor} called {service} for {entities} ({reason})."),
    },
    "sabotage": {
        "de": ("Sabotageverdacht", "{count} sicherheitsrelevante Geräte gleichzeitig nicht erreichbar: {entities}."),
        "en": ("Possible sabotage", "{count} security devices became unavailable at once: {entities}."),
    },
    "tamper": {
        "de": ("Manipulationsalarm", "{entity} meldet Manipulation."),
        "en": ("Tamper alarm", "{entity} reports tampering."),
    },
    "external_config_change": {
        "de": ("Konfiguration außerhalb der UI geändert", "Geändert ohne Aktion in Home Assistant: {files}."),
        "en": ("Configuration changed outside the UI", "Changed without an action in Home Assistant: {files}."),
    },
    "new_destination": {
        "de": ("Neues Verbindungsziel", "Home Assistant verbindet sich erstmals mit {target}."),
        "en": ("New outbound destination", "Home Assistant connects to {target} for the first time."),
    },
    "canary": {
        "de": (
            "⚠ Köder ausgelöst – möglicher Einbruch",
            "Der Köder ({via}) wurde von {ip} benutzt ({agent}). Diese Zugangsdaten nutzt niemand legitim: Jemand hat sie gefunden.",
        ),
        "en": (
            "⚠ Decoy triggered – possible intrusion",
            "The decoy ({via}) was used from {ip} ({agent}). Nobody uses these credentials legitimately: someone found them.",
        ),
    },
    "token_new_ip": {
        "de": (
            "Token von neuer IP: {name}",
            "Der Long-Lived-Token „{name}“ von {user} wird erstmals von {ip}{geo} benutzt.",
        ),
        "en": (
            "Token used from new IP: {name}",
            "Long-lived token '{name}' of {user} is used from {ip}{geo} for the first time.",
        ),
    },
    "anomaly": {
        "de": ("Anomalie: {name}", "{name}: {detail}"),
        "en": ("Anomaly: {name}", "{name}: {detail}"),
    },
    "new_finding": {
        "de": ("Bastion: {title}", "{description}\n\nEmpfehlung: {recommendation}"),
        "en": ("Bastion: {title}", "{description}\n\nRecommendation: {recommendation}"),
    },
    "git_error": {
        "de": ("Bastion Git-Sync", "{error}"),
        "en": ("Bastion git sync", "{error}"),
    },
}

ANOMALY_DETAIL = {
    "deviation": {
        "de": "Wert {value} liegt außerhalb des üblichen Bereichs {low} – {high}.",
        "en": "Value {value} is outside the usual range {low} – {high}.",
    },
    "continuous": {
        "de": "Läuft seit {hours} h ohne Pause (üblich höchstens {usual} h).",
        "en": "Running for {hours} h without pause (usually at most {usual} h).",
    },
    "drift": {
        "de": "Grundlast der letzten 7 Tage {recent} liegt {percent} % über dem Mittel ({baseline}).",
        "en": "Base load of the last 7 days {recent} is {percent} % above average ({baseline}).",
    },
}

MISC = {
    "de": {
        "never_used": "noch nie verwendet",
        "unused_days": "seit {days} Tagen nicht verwendet",
        "remote_yes": ", aus dem Internet erreichbar",
        "remote_no": "",
        "pin_none": " ohne PIN",
        "pin_set": " (PIN gesetzt)",
        "anon": ", ohne Anmeldung",
        "shell_yes": " und führt ihn in einer Shell aus",
        "never": "noch nie",
        "commit_auto": "automatisch",
        "commit_manual": "manuell",
        "commit_daily": "täglich",
        "commit_pre_restore": "vor Wiederherstellung",
        "commit_initial": "erste Sicherung",
        "commit_title": "Bastion: Konfiguration gesichert ({counts})",
        "commit_counts": "{m} geändert, {a} neu, {d} gelöscht",
        "commit_trigger": "Auslöser",
        "commit_users": "Benutzer",
        "commit_external": "Außerhalb der UI geändert",
        "commit_encrypted": "Automatisch verschlüsselt (Secrets erkannt)",
        "commit_skipped": "Nicht gesichert (Secrets, keine Passphrase)",
        "admin_suffix": " (Administrator)",
    },
    "en": {
        "never_used": "never used",
        "unused_days": "not used for {days} days",
        "remote_yes": ", reachable from the internet",
        "remote_no": "",
        "pin_none": " without PIN",
        "pin_set": " (PIN set)",
        "anon": ", without authentication",
        "shell_yes": " and runs it in a shell",
        "never": "never",
        "commit_auto": "automatic",
        "commit_manual": "manual",
        "commit_daily": "daily",
        "commit_pre_restore": "before restore",
        "commit_initial": "initial backup",
        "commit_title": "Bastion: configuration saved ({counts})",
        "commit_counts": "{m} modified, {a} added, {d} deleted",
        "commit_trigger": "Trigger",
        "commit_users": "Users",
        "commit_external": "Changed outside the UI",
        "commit_encrypted": "Encrypted automatically (secrets detected)",
        "commit_skipped": "Not backed up (secrets, no passphrase)",
        "admin_suffix": " (administrator)",
    },
}

README = {
    "de": """# Home Assistant Konfiguration (Bastion)

Dieses Repository wird von der Integration **Bastion** automatisch gepflegt.

| Pfad | Inhalt |
|---|---|
| `homeassistant/` | YAML-Konfiguration aus `/config` |
| `homeassistant/.storage/` | UI-Konfiguration (Dashboards, Helfer, Bereiche, Registries) |
| `esphome/` | ESPHome-Gerätekonfigurationen |
| `zigbee2mqtt/` | Zigbee2MQTT-Konfiguration und Gerätedatenbank |
| `extra/` | Zusätzlich konfigurierte Pfade |
| `addons/` | Add-on-Optionen (nur mit Supervisor, immer verschlüsselt) |
| `bastion/` | Inventar und Manifest |

Dateien mit der Endung `.bastion.enc` sind mit AES-256-GCM verschlüsselt
(Schlüssel aus der Passphrase per scrypt). Ohne Passphrase sind sie wertlos.

**Wiederherstellen:** In Home Assistant → Bastion → Git → Stand auswählen →
Wiederherstellen. Auf einer neuen Instanz: Bastion installieren, dasselbe
Repository, denselben Schlüssel und dieselbe Passphrase eintragen.

Dateien außerhalb der oben genannten Ordner werden von Bastion nicht verändert.
""",
    "en": """# Home Assistant configuration (Bastion)

This repository is maintained automatically by the **Bastion** integration.

| Path | Content |
|---|---|
| `homeassistant/` | YAML configuration from `/config` |
| `homeassistant/.storage/` | UI configuration (dashboards, helpers, areas, registries) |
| `esphome/` | ESPHome device configurations |
| `zigbee2mqtt/` | Zigbee2MQTT configuration and device database |
| `extra/` | Additionally configured paths |
| `addons/` | Add-on options (Supervisor only, always encrypted) |
| `bastion/` | Inventory and manifest |

Files ending in `.bastion.enc` are encrypted with AES-256-GCM (key derived
from the passphrase with scrypt). They are useless without the passphrase.

**Restore:** Home Assistant → Bastion → Git → pick a commit → restore. On a new
instance: install Bastion and enter the same repository, key and passphrase.

Files outside the folders above are never touched by Bastion.
""",
}


def lang(language: str | None) -> str:
    """Return supported language code."""
    return "de" if (language or "").lower().startswith("de") else "en"


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def fmt(template: str, data: dict[str, Any]) -> str:
    """Format with missing keys left visible."""
    return template.format_map(_SafeDict({k: v for k, v in data.items()}))


def finding_text(key: str, language: str, data: dict[str, Any]) -> tuple[str, str, str]:
    """Render (title, description, recommendation)."""
    texts = FINDING_TEXTS.get(key)
    if texts is None:
        return key, "", ""
    title, desc, rec = texts[lang(language)]
    return fmt(title, data), fmt(desc, data), fmt(rec, data)


def event_text(key: str, language: str, data: dict[str, Any]) -> tuple[str, str]:
    """Render (title, message) for a security event."""
    texts = EVENT_TEXTS.get(key)
    if texts is None:
        return key, ""
    title, msg = texts[lang(language)]
    return fmt(title, data), fmt(msg, data)


def misc(key: str, language: str, **data: Any) -> str:
    """Small text snippets."""
    return fmt(MISC[lang(language)].get(key, key), data)


ACTION_TEXTS = {
    "de": {
        "ok": "War ich",
        "block": "Sperren",
        "expired": "Die Aktion ist abgelaufen oder wurde schon ausgeführt.",
        "confirmed": "Bestätigt: {what}",
        "token_revoked": "Token „{name}“ widerrufen",
        "own_token": "Eigener Token wird nicht widerrufen",
        "ip_banned": "IP {ip} gesperrt",
        "ban_invalid": "Ungültige IP {ip}",
        "ban_protected": "IP {ip} ist geschützt (Loopback oder Reverse-Proxy) und wird nicht gesperrt",
        "ban_unavailable": "IP {ip} nicht gesperrt: IP-Sperre ist in der HTTP-Konfiguration deaktiviert",
        "user_deactivated": "Benutzer „{user}“ deaktiviert",
        "user_protected": "Benutzer „{user}“ ist geschützt (Besitzer oder du selbst)",
        "nothing": "Nichts zu tun",
    },
    "en": {
        "ok": "That was me",
        "block": "Block",
        "expired": "The action expired or was already executed.",
        "confirmed": "Confirmed: {what}",
        "token_revoked": "Token '{name}' revoked",
        "own_token": "Your own token is not revoked",
        "ip_banned": "IP {ip} banned",
        "ban_invalid": "Invalid IP {ip}",
        "ban_protected": "IP {ip} is protected (loopback or reverse proxy) and is not banned",
        "ban_unavailable": "IP {ip} not banned: IP banning is disabled in the HTTP configuration",
        "user_deactivated": "User '{user}' deactivated",
        "user_protected": "User '{user}' is protected (owner or yourself)",
        "nothing": "Nothing to do",
    },
}

REPORT_TEXTS = {
    "de": {
        "title": "Bastion Wochenbericht (KW {week})",
        "score": "Sicherheitswert: **{score}**",
        "score_trend": "Sicherheitswert: **{score}** (Vorwoche {previous}, {diff})",
        "open": "Offene Befunde: {critical} kritisch, {high} hoch, {medium} mittel, {low} niedrig",
        "new_findings": "Neu in den letzten 7 Tagen ({count}):",
        "resolved_findings": "Behoben ({count}):",
        "logins": "Anmeldungen: {ok} erfolgreich, {failed} fehlgeschlagen, {new_ip} neue IPs, {banned} gesperrt",
        "canary_hit": "⚠ Köder {count}× ausgelöst",
        "canary_quiet": "Köder: nicht ausgelöst",
        "anomalies": "Anomalien und Sicherheitsereignisse: {count}",
        "git": "Git: {commits} Commits, Status {status}, letzter Push {last}",
        "ports": "Offene Ports von außen: {ports}",
    },
    "en": {
        "title": "Bastion weekly report (week {week})",
        "score": "Security score: **{score}**",
        "score_trend": "Security score: **{score}** (last week {previous}, {diff})",
        "open": "Open findings: {critical} critical, {high} high, {medium} medium, {low} low",
        "new_findings": "New in the last 7 days ({count}):",
        "resolved_findings": "Resolved ({count}):",
        "logins": "Logins: {ok} successful, {failed} failed, {new_ip} new IPs, {banned} blocked",
        "canary_hit": "⚠ Decoy triggered {count} times",
        "canary_quiet": "Decoy: not triggered",
        "anomalies": "Anomalies and security events: {count}",
        "git": "Git: {commits} commits, status {status}, last push {last}",
        "ports": "Ports open from outside: {ports}",
    },
}


def action_text(key: str, language: str, **data: Any) -> str:
    """Texts of notification actions and their results."""
    return fmt(ACTION_TEXTS[lang(language)].get(key, key), data)


def report_text(key: str, language: str, **data: Any) -> str:
    """Texts of the weekly report."""
    return fmt(REPORT_TEXTS[lang(language)].get(key, key), data)
