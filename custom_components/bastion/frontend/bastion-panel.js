// Bastion sidebar panel. Plain web component, no build step.
// Every dynamic value is escaped before it is put into HTML.

const I18N = {
  de: {
    tabs: { overview: "Übersicht", logins: "Anmeldungen", git: "Git", anomaly: "Anomalien & Köder", external: "Extern" },
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
      tamper: "Manipulation", anomaly: "Anomalie", new_destination: "Neues Verbindungsziel",
      external_config_change: "Extern geändert", deviation: "Abweichung", continuous: "Dauerbetrieb", drift: "Steigende Grundlast",
      token: "Token", webhook: "Webhook",
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
    tabs: { overview: "Overview", logins: "Logins", git: "Git", anomaly: "Anomalies & decoys", external: "External" },
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
      tamper: "Tampering", anomaly: "Anomaly", new_destination: "New destination",
      external_config_change: "Changed outside the UI", deviation: "Deviation", continuous: "Continuous run", drift: "Rising base load",
      token: "Token", webhook: "Webhook",
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
  canary: ["mdi:bird", SEV.critical.color], blocked: ["mdi:block-helper", SEV.critical.color],
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
    this._tab = "overview";
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
    if (first) this._load();
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
    const scroll = this.shadowRoot.querySelector(".content")?.scrollTop || 0;
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <header class="header">
        <ha-menu-button></ha-menu-button>
        ${SHIELD}
        <div class="title">Bastion</div>
        <div class="grow"></div>
        ${this._data ? this._headerScore() : ""}
      </header>
      <nav class="tabs">
        ${Object.keys(t.tabs).map((tab) => `
          <button class="tab ${this._tab === tab ? "active" : ""}" data-tab="${tab}">
            ${icon(TAB_ICON[tab])}<span>${esc(t.tabs[tab])}</span>
          </button>`).join("")}
      </nav>
      <main class="content">${this._data ? this._renderTab() : `<div class="loading">${icon("mdi:shield-sync-outline")}</div>`}</main>
      ${this._toast ? `<div class="toast">${esc(this._toast)}</div>` : ""}
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
    return `<div class="header-score">${icon("mdi:shield-half-full", this._stateColor(state))}<b>${esc(s.score)}</b><span>${esc(this.t.score_label[state])}</span></div>`;
  }

  _renderTab() {
    switch (this._tab) {
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
    return `
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
      <div class="actionbar">
        <button class="btn primary" data-action="audit" ${this._busy || summary.running ? "disabled" : ""}>
          ${icon("mdi:shield-search")}${esc(summary.running || this._busy ? t.running : t.run_audit)}</button>
        <button class="btn" data-action="report">${icon("mdi:file-chart-outline")}${esc(t.send_report)}</button>
        <span class="muted small">${esc(t.last_audit)}: ${esc(this.rel(summary.last_audit))}</span>
      </div>
      ${summary.errors && summary.errors.length ? `<div class="banner">${icon("mdi:alert-outline")}<div>${summary.errors.map(esc).join("<br>")}</div></div>` : ""}
      <div class="filters">
        ${chips.join("")}
        <label class="switch"><input type="checkbox" data-action="toggle-dismissed" ${this._showDismissed ? "checked" : ""}><span>${esc(t.show_dismissed)}</span></label>
      </div>
      ${visible.length === 0
        ? `<div class="empty">${icon("mdi:shield-check", GOOD)}<div>${esc(t.no_findings)}</div></div>`
        : `<div class="findings">${visible.map((f) => this._renderFinding(f)).join("")}</div>`}
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
    return `
      <article class="finding ${f.dismissed ? "dismissed" : ""}" style="--sev:${sev.color}">
        <div class="f-head">
          <span class="chip sev">${icon(sev.icon, sev.color)}${esc(t.severity[f.severity] || f.severity)}</span>
          <span class="chip cat">${icon(CATEGORY_ICON[f.category] || "mdi:shield-outline")}${esc(t.category[f.category] || f.category)}</span>
          <span class="grow"></span>
          <span class="muted small" data-tip="${fmtTime(f.first_seen)}">${esc(t.since)} ${esc(this.rel(f.first_seen))}</span>
        </div>
        <h3>${esc(f.title)}</h3>
        <p class="desc">${esc(f.description)}</p>
        ${f.recommendation ? `<div class="advice">${icon("mdi:lightbulb-on-outline")}<span>${esc(f.recommendation)}</span></div>` : ""}
        <div class="f-actions">
          ${integrity ? `<button class="btn small" data-action="accept" data-domain="${esc(domain)}">${icon("mdi:check-decagram-outline")}${esc(t.accept)}</button>` : ""}
          <button class="btn small ghost" data-action="dismiss" data-id="${esc(f.id)}" data-dismissed="${f.dismissed ? "0" : "1"}">
            ${icon(f.dismissed ? "mdi:eye-outline" : "mdi:eye-off-outline")}${esc(f.dismissed ? t.undismiss : t.dismiss)}</button>
        </div>
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
    if (!this._logins) return `<div class="loading">${icon("mdi:account-lock-outline")}</div>`;
    const { log, tokens, stats } = this._logins;
    const week = Date.now() - 7 * 86400 * 1000;
    const recent = log.filter((e) => (toDate(e.time)?.getTime() || 0) >= week);
    const okCount = recent.filter((e) => e.type === "login").length;
    const blocked = recent.filter((e) => e.type === "blocked" || e.type === "ip_banned").length;
    return `
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
    if (g.status === "disabled") return `<div class="empty">${icon("mdi:source-branch")}<div>${esc(t.git_disabled)}</div></div>`;
    const statusColor = { ok: GOOD, pending: SEV.medium.color, error: SEV.high.color, blocked: SEV.critical.color }[g.status] || "#8a8f98";
    const statusIcon = { ok: "mdi:check-circle", pending: "mdi:progress-upload", error: "mdi:alert", blocked: "mdi:lock-alert" }[g.status] || "mdi:circle";
    const commits = this._git?.commits || [];
    return `
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
        <button class="btn primary" data-action="commit" ${this._busy ? "disabled" : ""}>${icon("mdi:source-commit-local")}${esc(this._busy ? t.running : t.commit_now)}</button>
        <button class="btn" data-action="refresh-git">${icon("mdi:refresh")}${esc(t.refresh)}</button>
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
      <div class="actionbar">
        <button class="btn primary" data-action="probe" ${this._busy ? "disabled" : ""}>${icon("mdi:web-check")}${esc(this._busy ? t.running : t.run_probe)}</button>
        ${probe ? `<span class="muted small">${esc(this.rel(probe.time))}</span>` : ""}
      </div>
      ${!probe ? `<div class="empty">${icon("mdi:web-off")}<div>${esc(t.probe_none)}</div></div>`
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

  // ------------------------------------------------------------------ events
  _bind() {
    const root = this.shadowRoot;
    const on = (sel, fn, type = "click") => root.querySelectorAll(sel).forEach((el) => el.addEventListener(type, (ev) => fn(el, ev)));
    on("[data-tab]", (el) => {
      this._tab = el.dataset.tab;
      this._commit = null;
      this._files = null;
      this._diff = null;
      this._load();
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
    on('[data-action="commit"]', () => this._action(async () => {
      const message = root.getElementById("commit-message")?.value || undefined;
      const result = await this._ws("bastion/git/commit", message ? { message } : {});
      this._notify(result.committed ? `✔ ${result.summary || ""}` : result.push_error ? `${this.t.error}: ${result.push_error}` : "✔");
      this._data = await this._ws("bastion/overview");
      this._git = await this._ws("bastion/git/history", { refresh: false });
    }));
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

const SHIELD = `<svg class="logo" viewBox="18 20 220 220" width="28" height="28" aria-hidden="true">
  <defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2f8cff"/><stop offset="1" stop-color="#103d8c"/></linearGradient></defs>
  <path d="M48 24 H84 V52 H110 V24 H146 V52 H172 V24 H208 V150 C208 192 172 220 128 236 C84 220 48 192 48 150 Z" fill="url(#bg)" stroke="url(#bg)" stroke-width="8" stroke-linejoin="round"/>
  <circle cx="128" cy="122" r="24" fill="#fff"/><path d="M117 134 L110 184 Q109 190 115 190 H141 Q147 190 146 184 L139 134 Z" fill="#fff"/></svg>`;

const STYLE = `
  :host { display:block; min-height:100vh; background: var(--primary-background-color); color: var(--primary-text-color);
    font-family: var(--ha-font-family-body, Roboto, "Noto Sans", sans-serif); --radius: var(--ha-card-border-radius, 12px);
    --surface: var(--card-background-color, #1c1c1c); --line: var(--divider-color, rgba(127,127,127,.2)); --muted: var(--secondary-text-color); }
  ha-icon { --mdc-icon-size: 18px; flex: none; }
  .header { position: sticky; top: 0; z-index: 3; display:flex; align-items:center; gap:10px; height:56px; padding: 0 16px 0 4px;
    background: var(--app-header-background-color, var(--surface)); color: var(--app-header-text-color, var(--primary-text-color));
    border-bottom: 1px solid var(--app-header-border-bottom, var(--line)); }
  .title { font-size:20px; font-weight:500; }
  .grow { flex:1; }
  .header-score { display:flex; align-items:center; gap:6px; padding:4px 10px; border-radius:999px; background: var(--surface); border:1px solid var(--line); font-size:13px; color: var(--primary-text-color); }
  .header-score b { font-size:15px; }
  .tabs { position: sticky; top:56px; z-index:2; display:flex; gap:6px; padding:10px 16px; overflow-x:auto; scrollbar-width:none;
    background: var(--primary-background-color); border-bottom:1px solid var(--line); }
  .tab { display:flex; align-items:center; gap:6px; white-space:nowrap; border:1px solid transparent; background:none; color: var(--muted);
    padding:8px 14px; border-radius:999px; font: inherit; font-size:14px; cursor:pointer; transition: background .15s, color .15s; }
  .tab:hover { background: var(--secondary-background-color, rgba(127,127,127,.1)); color: var(--primary-text-color); }
  .tab.active { background: color-mix(in srgb, var(--primary-color) 16%, transparent); color: var(--primary-color); border-color: color-mix(in srgb, var(--primary-color) 35%, transparent); }
  .content { padding: 20px 16px 48px; max-width: 1180px; margin: 0 auto; box-sizing: border-box; }
  h2 { display:flex; align-items:center; gap:8px; font-size:16px; font-weight:500; margin: 28px 0 10px; }
  .card { background: var(--surface); border-radius: var(--radius); border:1px solid var(--line); padding:16px 18px; box-shadow: var(--ha-card-box-shadow, none); }
  .card + .card { margin-top: 14px; }
  .card-title { display:flex; align-items:center; gap:8px; margin:0 0 10px; font-size:15px; font-weight:500; }
  .muted { color: var(--muted); }
  .small { font-size:12px; }
  .mono { font-family: var(--ha-font-family-code, ui-monospace, SFMono-Regular, Menlo, monospace); }
  .loading, .empty { display:flex; flex-direction:column; align-items:center; gap:10px; padding:40px 16px; color: var(--muted); text-align:center; }
  .loading ha-icon, .empty ha-icon { --mdc-icon-size: 40px; }
  .empty.small { padding:24px 8px; }
  .empty.small ha-icon { --mdc-icon-size: 28px; }

  .hero { display:flex; gap:24px; align-items:center; flex-wrap:wrap; }
  .ring { position:relative; width:128px; flex:none; display:flex; flex-direction:column; align-items:center; }
  .ring-text { position:absolute; top:0; left:0; width:128px; height:128px; display:flex; flex-direction:column; align-items:center; justify-content:center; }
  .ring-value { font-size:36px; font-weight:600; line-height:1; }
  .ring-unit { font-size:12px; color: var(--muted); margin-top:4px; }
  .ring-label { display:flex; align-items:center; gap:4px; margin-top:8px; font-size:13px; color: var(--muted); }
  .ring-label ha-icon { --mdc-icon-size: 10px; }
  .hero-side { flex:1; min-width:260px; display:flex; flex-direction:column; gap:14px; }
  .tiles { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap:10px; }
  .tile { border:1px solid var(--line); border-radius:10px; padding:10px 12px; }
  .tile-head { display:flex; align-items:center; gap:6px; font-size:13px; color: var(--muted); }
  .tile-value { font-size:26px; font-weight:600; margin-top:4px; }
  .tile-sub { font-size:15px; margin-top:6px; }
  .trend svg { display:block; margin-top:4px; overflow:visible; }
  .gridline { stroke: var(--line); stroke-width:1; stroke-dasharray: 3 4; }
  .spark { stroke: var(--primary-color); }
  .spark-dot { fill: var(--primary-color); stroke: var(--surface); stroke-width:2; }
  .bar { fill: ${SEV.high.color}; }

  .actionbar { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin: 16px 0; }
  .actionbar.tight { margin: 10px 0 0; }
  .btn { display:inline-flex; align-items:center; gap:6px; padding:8px 14px; border-radius:10px; border:1px solid var(--line);
    background: var(--surface); color: var(--primary-text-color); font: inherit; font-size:14px; cursor:pointer; transition: filter .15s, background .15s; }
  .btn:hover:not(:disabled) { filter: brightness(1.12); }
  .btn.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: transparent; }
  .btn.danger { background: ${SEV.critical.color}; color:#fff; border-color: transparent; }
  .btn.ghost { background: transparent; }
  .btn.ghost.danger { background: transparent; color: var(--primary-text-color); border-color: color-mix(in srgb, ${SEV.critical.color} 45%, transparent); }
  .btn.small { padding:5px 10px; font-size:12px; border-radius:8px; }
  .btn.small ha-icon { --mdc-icon-size: 16px; }
  .btn:disabled { opacity:.55; cursor:default; }
  .link { display:inline-flex; align-items:center; gap:6px; background:none; border:none; color: var(--primary-text-color); font: inherit; font-size:13px; cursor:pointer; padding:0; text-align:left; min-width:0; }
  .link span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .link:hover { color: var(--primary-color); }
  .input { padding:9px 12px; border-radius:10px; border:1px solid var(--line); background: var(--surface); color: inherit; font: inherit; font-size:14px; min-width:180px; }

  .filters { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin: 6px 0 14px; }
  .chip { display:inline-flex; align-items:center; gap:6px; padding:5px 10px; border-radius:999px; font-size:12px;
    border:1px solid var(--line); background: transparent; color: var(--primary-text-color); font-family: inherit; }
  button.chip { cursor:pointer; }
  .chip.on { background: color-mix(in srgb, var(--primary-color) 16%, transparent); border-color: color-mix(in srgb, var(--primary-color) 45%, transparent); }
  .chip .count { color: var(--muted); }
  .chip.tiny { padding:2px 8px; font-size:11px; background: color-mix(in srgb, var(--c, #8a8f98) 16%, transparent); border-color: transparent; }
  .chip.big { font-size:13px; padding:6px 12px; }
  .chip.alarm { background: color-mix(in srgb, ${SEV.critical.color} 18%, transparent); border-color: ${SEV.critical.color}; }
  .chip.check { cursor:pointer; }
  .chip.check input { margin:0; }
  .switch { display:inline-flex; align-items:center; gap:6px; font-size:13px; color: var(--muted); cursor:pointer; }
  .switch input { accent-color: var(--primary-color); }

  .findings { display:flex; flex-direction:column; gap:12px; }
  .finding { position:relative; background: var(--surface); border:1px solid var(--line); border-radius: var(--radius); padding:14px 18px 12px 22px; overflow:hidden; }
  .finding::before { content:""; position:absolute; left:0; top:0; bottom:0; width:5px; background: var(--sev); }
  .finding.dismissed { opacity:.55; }
  .f-head { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
  .chip.sev { background: color-mix(in srgb, var(--sev) 16%, transparent); border-color: transparent; font-weight:500; }
  .chip.cat ha-icon { color: var(--muted); }
  .finding h3 { font-size:15px; font-weight:600; margin:10px 0 4px; overflow-wrap:anywhere; }
  .desc { margin:0; font-size:14px; line-height:1.5; overflow-wrap:anywhere; }
  .advice { display:flex; gap:8px; align-items:flex-start; margin-top:10px; padding:8px 12px; border-radius:10px; font-size:13px; line-height:1.45;
    background: var(--secondary-background-color, rgba(127,127,127,.08)); color: var(--primary-text-color); overflow-wrap:anywhere; }
  .advice ha-icon { color: ${SEV.medium.color}; margin-top:1px; }
  .f-actions { display:flex; justify-content:flex-end; gap:8px; margin-top:10px; }

  .banner { display:flex; gap:10px; align-items:flex-start; padding:10px 14px; border-radius:10px; margin:10px 0; font-size:13px;
    background: color-mix(in srgb, ${SEV.medium.color} 16%, transparent); border:1px solid color-mix(in srgb, ${SEV.medium.color} 45%, transparent); overflow-wrap:anywhere; }
  details.report summary { display:flex; align-items:center; gap:8px; cursor:pointer; list-style:none; }
  details.report summary::-webkit-details-marker { display:none; }
  .report-title { font-weight:600; margin-top:12px; }
  .report-body { white-space:pre-wrap; font-family: inherit; font-size:13px; line-height:1.55; margin:8px 0 0; }

  .grid3 { display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:14px; }
  .grid3 .card + .card { margin-top:0; }
  .card + .grid3, .grid3 + .card, .findings + .card, .card + .actionbar { margin-top:14px; }
  .stat svg { display:block; margin:10px 0 6px; }
  .list { padding:4px 0; }
  .row { display:flex; align-items:center; gap:12px; padding:10px 16px; border-bottom:1px solid var(--line); }
  .row:last-child { border-bottom:none; }
  .row-main { flex:1; min-width:0; display:flex; flex-direction:column; gap:3px; overflow-wrap:anywhere; font-size:14px; }

  .git-status .git-head, .git-head { display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }
  .facts { display:grid; grid-template-columns: max-content 1fr; gap:8px 18px; margin:14px 0 0; font-size:14px; }
  .facts dt { color: var(--muted); }
  .facts dd { margin:0; display:flex; align-items:center; gap:6px; overflow-wrap:anywhere; min-width:0; }
  .secret { display:flex; align-items:center; gap:8px; margin:6px 0 10px; }
  .secret code { flex:1; min-width:0; padding:9px 12px; border-radius:10px; font-size:12px; overflow-x:auto; white-space:nowrap;
    background: var(--secondary-background-color, rgba(127,127,127,.08)); border:1px solid var(--line); }
  .label { font-size:12px; color: var(--muted); margin-top:12px; }
  .split { display:grid; grid-template-columns: minmax(280px, 2fr) 3fr; gap:14px; align-items:start; }
  .split .card + .card { margin-top:0; }
  @media (max-width: 900px) { .split { grid-template-columns: 1fr; } .tiles { grid-template-columns: repeat(2, minmax(0,1fr)); } }
  .commits { max-height: 70vh; overflow:auto; padding:12px; }
  .commit { display:flex; gap:10px; align-items:flex-start; width:100%; text-align:left; background:none; border:1px solid transparent; color: inherit;
    font: inherit; padding:10px; border-radius:10px; cursor:pointer; }
  .commit:hover { background: var(--secondary-background-color, rgba(127,127,127,.08)); }
  .commit.selected { border-color: color-mix(in srgb, var(--primary-color) 55%, transparent); background: color-mix(in srgb, var(--primary-color) 10%, transparent); }
  .commit-summary { font-size:13px; font-weight:500; }
  .restore { padding:10px 12px; border-radius:10px; border:1px dashed var(--line); margin-bottom:12px; }
  .area-chips { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:8px; }
  .files { display:flex; flex-direction:column; }
  .file { display:flex; align-items:center; gap:8px; padding:6px 4px; border-bottom:1px solid var(--line); }
  .file .link { flex:1; }
  .file.selected .link { color: var(--primary-color); }
  .diff { background: #0d1117; color:#c9d1d9; padding:12px; border-radius:10px; overflow:auto; font-size:12px; max-height:480px; margin-top:12px; }
  .diff .add { color:#7ee787; } .diff .del { color:#ff7b72; } .diff .hunk { color:#79c0ff; }

  .alarm-card { border-color: ${SEV.critical.color}; box-shadow: 0 0 0 1px ${SEV.critical.color} inset; }
  .meter { height:6px; border-radius:999px; background: color-mix(in srgb, var(--primary-color) 18%, transparent); overflow:hidden; margin:4px 0 2px; max-width:320px; }
  .meter div { height:100%; border-radius:999px; background: var(--primary-color); }
  .ports { display:grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap:10px; margin-top:14px; }
  .port { display:flex; align-items:center; gap:10px; padding:10px 12px; border-radius:10px; border:1px solid var(--line); }
  .port > div { flex:1; min-width:0; }
  .port.open { border-color: ${SEV.critical.color}; background: color-mix(in srgb, ${SEV.critical.color} 10%, transparent); }

  .toast { position:fixed; left:50%; bottom:24px; transform:translateX(-50%); z-index:10; max-width:min(560px, calc(100vw - 32px));
    background: var(--primary-text-color); color: var(--primary-background-color); padding:10px 16px; border-radius:10px; font-size:14px;
    box-shadow: 0 6px 24px rgba(0,0,0,.3); }
  .tip { position:fixed; z-index:11; pointer-events:none; background: var(--primary-text-color); color: var(--primary-background-color);
    padding:4px 8px; border-radius:6px; font-size:12px; white-space:nowrap; }
  @media (max-width: 600px) { .content { padding:16px 16px 40px; } .hero { justify-content:center; } .finding { padding-left:18px; } }
`;

customElements.define("bastion-panel", BastionPanel);
