// Bastion sidebar panel. Plain web component, no build step.
// Every dynamic value is escaped before it is put into HTML.

const I18N = {
  de: {
    title: "Bastion",
    tab_overview: "Übersicht",
    tab_logins: "Anmeldungen",
    tab_git: "Git",
    tab_anomaly: "Anomalien",
    tab_external: "Extern",
    score: "Sicherheitswert",
    last_audit: "Letztes Audit",
    run_audit: "Audit ausführen",
    running: "Läuft …",
    no_findings: "Keine offenen Befunde.",
    dismiss: "Ausblenden",
    undismiss: "Einblenden",
    accept: "Baseline übernehmen",
    show_dismissed: "Ausgeblendete anzeigen",
    recommendation: "Empfehlung",
    since: "seit",
    severity: { critical: "Kritisch", high: "Hoch", medium: "Mittel", low: "Niedrig", info: "Info" },
    failed_24h: "Fehlversuche (24 h)",
    top_sources: "Häufigste Quellen",
    log: "Protokoll",
    tokens: "Tokens und Sitzungen",
    time: "Zeit",
    type: "Typ",
    user: "Benutzer",
    ip: "IP",
    client: "Client",
    created: "Erstellt",
    last_used: "Zuletzt genutzt",
    git_disabled: "Git-Sync ist nicht eingerichtet (Einstellungen → Geräte & Dienste → Bastion → Konfigurieren → Git-Versionierung).",
    git_status: "Status",
    repo: "Repository",
    branch: "Branch",
    encryption: "Verschlüsselung",
    privacy: "Sichtbarkeit",
    host_key: "Server-Schlüssel",
    commit_now: "Jetzt sichern",
    commit_message: "Commit-Nachricht (optional)",
    history: "Verlauf",
    refresh: "Aktualisieren",
    files: "Dateien",
    restore_all: "Kompletten Stand wiederherstellen",
    restore_selected: "Ausgewählte Bereiche wiederherstellen",
    restore_file: "Datei wiederherstellen",
    restart_after: "Danach neu starten (nötig für UI-Konfiguration)",
    confirm_restore: "Stand {sha} wiederherstellen? Der aktuelle Stand wird vorher gesichert.",
    restored: "Wiederhergestellt: {written} Dateien geschrieben, {staged} für den Neustart vorbereitet, {skipped} übersprungen.",
    status_same: "unverändert",
    status_changed: "geändert",
    status_deleted_locally: "lokal gelöscht",
    status_new_locally: "lokal neu",
    status_unknown: "unbekannt",
    encrypted: "verschlüsselt",
    not_pushed: "nicht gepusht",
    sensors: "Angelernte Sensoren",
    samples: "Messwerte",
    learned: "gelernte Stunden",
    no_sensors: "Keine Sensoren ausgewählt (Optionen → Anomalie-Erkennung).",
    events: "Ereignisse",
    sabotage: "Sabotageverdacht",
    outbound: "Neue Verbindungsziele",
    learning_since: "Lernt seit",
    probe_none: "Keine externe Prüfstelle eingerichtet (Optionen → Externe Prüfung).",
    run_probe: "Jetzt prüfen",
    port: "Port",
    open: "offen",
    closed: "zu",
    public_ip: "Öffentliche IP",
    error: "Fehler",
    yes: "ja",
    no: "nein",
    areas: { config: "YAML", storage: "UI (.storage)", esphome: "ESPHome", zigbee2mqtt: "Zigbee2MQTT", addons: "Add-ons", extra: "Extra", inventory: "Inventar" },
  },
  en: {
    title: "Bastion",
    tab_overview: "Overview",
    tab_logins: "Logins",
    tab_git: "Git",
    tab_anomaly: "Anomalies",
    tab_external: "External",
    score: "Security score",
    last_audit: "Last audit",
    run_audit: "Run audit",
    running: "Running …",
    no_findings: "No open findings.",
    dismiss: "Dismiss",
    undismiss: "Restore",
    accept: "Accept baseline",
    show_dismissed: "Show dismissed",
    recommendation: "Recommendation",
    since: "since",
    severity: { critical: "Critical", high: "High", medium: "Medium", low: "Low", info: "Info" },
    failed_24h: "Failed logins (24 h)",
    top_sources: "Top sources",
    log: "Log",
    tokens: "Tokens and sessions",
    time: "Time",
    type: "Type",
    user: "User",
    ip: "IP",
    client: "Client",
    created: "Created",
    last_used: "Last used",
    git_disabled: "Git sync is not configured (Settings → Devices & services → Bastion → Configure → Git versioning).",
    git_status: "Status",
    repo: "Repository",
    branch: "Branch",
    encryption: "Encryption",
    privacy: "Visibility",
    host_key: "Server key",
    commit_now: "Back up now",
    commit_message: "Commit message (optional)",
    history: "History",
    refresh: "Refresh",
    files: "Files",
    restore_all: "Restore complete state",
    restore_selected: "Restore selected areas",
    restore_file: "Restore file",
    restart_after: "Restart afterwards (required for UI configuration)",
    confirm_restore: "Restore state {sha}? The current state is backed up first.",
    restored: "Restored: {written} files written, {staged} staged for restart, {skipped} skipped.",
    status_same: "unchanged",
    status_changed: "changed",
    status_deleted_locally: "deleted locally",
    status_new_locally: "new locally",
    status_unknown: "unknown",
    encrypted: "encrypted",
    not_pushed: "not pushed",
    sensors: "Learned sensors",
    samples: "samples",
    learned: "learned hours",
    no_sensors: "No sensors selected (options → anomaly detection).",
    events: "Events",
    sabotage: "Sabotage suspicion",
    outbound: "New outbound destinations",
    learning_since: "Learning since",
    probe_none: "No external probe configured (options → external check).",
    run_probe: "Check now",
    port: "Port",
    open: "open",
    closed: "closed",
    public_ip: "Public IP",
    error: "Error",
    yes: "yes",
    no: "no",
    areas: { config: "YAML", storage: "UI (.storage)", esphome: "ESPHome", zigbee2mqtt: "Zigbee2MQTT", addons: "Add-ons", extra: "Extra", inventory: "Inventory" },
  },
};

const SEV_COLORS = {
  critical: "var(--error-color, #db4437)",
  high: "#e8710a",
  medium: "var(--warning-color, #f4b400)",
  low: "var(--info-color, #4285f4)",
  info: "var(--secondary-text-color, #888)",
};

function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function fmtTime(value) {
  if (!value) return "—";
  const date = typeof value === "number" ? new Date(value * 1000) : new Date(value);
  if (Number.isNaN(date.getTime())) return esc(value);
  return esc(date.toLocaleString());
}

class BastionPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tab = "overview";
    this._data = null;
    this._logins = null;
    this._git = null;
    this._commit = null;
    this._files = null;
    this._diff = null;
    this._showDismissed = false;
    this._busy = false;
    this._message = "";
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
    const lang = (this._hass?.language || "en").startsWith("de") ? "de" : "en";
    return I18N[lang];
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
      this._message = `${this.t.error}: ${err.message || err.code || err}`;
    }
    this._render();
  }

  async _action(fn) {
    if (this._busy) return;
    this._busy = true;
    this._message = "";
    this._render();
    try {
      await fn();
    } catch (err) {
      this._message = `${this.t.error}: ${err.message || err.code || err}`;
    }
    this._busy = false;
    this._render();
  }

  _render() {
    const t = this.t;
    const tabs = ["overview", "logins", "git", "anomaly", "external"];
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div class="toolbar">
        <ha-menu-button></ha-menu-button>
        <div class="title">${esc(t.title)}</div>
      </div>
      <div class="tabs">
        ${tabs.map((tab) => `<button class="tab ${this._tab === tab ? "active" : ""}" data-tab="${tab}">${esc(t["tab_" + tab])}</button>`).join("")}
      </div>
      ${this._message ? `<div class="message">${esc(this._message)}</div>` : ""}
      <div class="content">${this._data ? this._renderTab() : "…"}</div>
    `;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) {
      menu.hass = this._hass;
      menu.narrow = this._narrow;
    }
    this.shadowRoot.querySelectorAll("[data-tab]").forEach((el) =>
      el.addEventListener("click", () => {
        this._tab = el.dataset.tab;
        this._commit = null;
        this._files = null;
        this._diff = null;
        this._load();
      })
    );
    this._bind();
  }

  _renderTab() {
    switch (this._tab) {
      case "logins":
        return this._renderLogins();
      case "git":
        return this._renderGit();
      case "anomaly":
        return this._renderAnomaly();
      case "external":
        return this._renderExternal();
      default:
        return this._renderOverview();
    }
  }

  _sevBadge(sev) {
    return `<span class="badge" style="background:${SEV_COLORS[sev] || SEV_COLORS.info}">${esc(this.t.severity[sev] || sev)}</span>`;
  }

  _renderOverview() {
    const t = this.t;
    const { summary, findings } = this._data;
    const visible = findings.filter((f) => this._showDismissed || !f.dismissed);
    const counts = summary.counts;
    const scoreColor = summary.score >= 90 ? "var(--success-color, #0f9d58)" : summary.score >= 60 ? SEV_COLORS.medium : SEV_COLORS.critical;
    return `
      <div class="cards">
        <div class="card score">
          <div class="big" style="color:${scoreColor}">${summary.last_audit ? esc(summary.score) : "—"}</div>
          <div>${esc(t.score)}</div>
        </div>
        ${["critical", "high", "medium", "low"].map((s) => `
          <div class="card"><div class="big" style="color:${SEV_COLORS[s]}">${esc(counts[s] || 0)}</div><div>${esc(t.severity[s])}</div></div>`).join("")}
      </div>
      <div class="row">
        <button class="primary" data-action="audit" ${this._busy || summary.running ? "disabled" : ""}>${esc(summary.running || this._busy ? t.running : t.run_audit)}</button>
        <span class="muted">${esc(t.last_audit)}: ${fmtTime(summary.last_audit)}</span>
        <label class="muted"><input type="checkbox" data-action="toggle-dismissed" ${this._showDismissed ? "checked" : ""}> ${esc(t.show_dismissed)}</label>
      </div>
      ${summary.errors && summary.errors.length ? `<div class="message">${summary.errors.map(esc).join("<br>")}</div>` : ""}
      ${visible.length === 0 ? `<p>${esc(t.no_findings)}</p>` : visible.map((f) => this._renderFinding(f)).join("")}
    `;
  }

  _renderFinding(f) {
    const t = this.t;
    const integrity = ["custom_code_changed", "custom_new", "www_changed"].includes(f.check);
    const domain = f.check === "www_changed" ? "www" : f.data?.domain || "";
    return `
      <div class="finding ${f.dismissed ? "dismissed" : ""}">
        <div class="finding-head">
          ${this._sevBadge(f.severity)}
          <span class="finding-title">${esc(f.title)}</span>
        </div>
        <div>${esc(f.description)}</div>
        <div class="muted">${esc(t.recommendation)}: ${esc(f.recommendation)}</div>
        <div class="row small">
          <span class="muted">${esc(t.since)} ${fmtTime(f.first_seen)}</span>
          ${integrity ? `<button data-action="accept" data-domain="${esc(domain)}">${esc(t.accept)}</button>` : ""}
          <button data-action="dismiss" data-id="${esc(f.id)}" data-dismissed="${f.dismissed ? "0" : "1"}">${esc(f.dismissed ? t.undismiss : t.dismiss)}</button>
        </div>
      </div>`;
  }

  _renderLogins() {
    const t = this.t;
    if (!this._logins) return "…";
    const { log, tokens, stats } = this._logins;
    const max = Math.max(1, ...stats.failed_per_hour);
    return `
      <div class="cards">
        <div class="card"><div class="big">${esc(stats.failed_24h)}</div><div>${esc(t.failed_24h)}</div></div>
        <div class="card wide">
          <div class="bars">${stats.failed_per_hour.map((v) => `<div class="bar" style="height:${Math.round((v / max) * 100)}%" title="${esc(v)}"></div>`).join("")}</div>
          <div class="muted">${esc(t.top_sources)}: ${stats.top_sources.map(([ip, c]) => `${esc(ip)} (${esc(c)})`).join(", ") || "—"}</div>
        </div>
      </div>
      <h3>${esc(t.tokens)}</h3>
      <div class="table-wrap"><table>
        <tr><th>${esc(t.user)}</th><th>${esc(t.type)}</th><th>${esc(t.client)}</th><th>${esc(t.created)}</th><th>${esc(t.last_used)}</th><th>${esc(t.ip)}</th></tr>
        ${tokens.map((tk) => `<tr><td>${esc(tk.user)}</td><td>${esc(tk.type === "long_lived_access_token" ? "LLAT" : "Session")}</td><td>${esc(tk.name)}</td><td>${fmtTime(tk.created_at)}</td><td>${fmtTime(tk.last_used_at)}</td><td>${esc(tk.last_used_ip || "—")}</td></tr>`).join("")}
      </table></div>
      <h3>${esc(t.log)}</h3>
      <div class="table-wrap"><table>
        <tr><th>${esc(t.time)}</th><th>${esc(t.type)}</th><th>${esc(t.user)}</th><th>${esc(t.ip)}</th><th>${esc(t.client)}</th></tr>
        ${log.map((e) => `<tr class="${e.type === "failed_login" || e.type === "brute_force" || e.type === "ip_banned" ? "warn" : ""}"><td>${fmtTime(e.time)}</td><td>${esc(e.type)}</td><td>${esc(e.user || "")}</td><td>${esc(e.ip || "")}${e.geo ? " (" + esc(e.geo) + ")" : ""}</td><td>${esc(e.client || e.name || e.user_agent || "")}</td></tr>`).join("")}
      </table></div>
    `;
  }

  _renderGit() {
    const t = this.t;
    const status = this._data.git;
    if (status.status === "disabled") return `<p>${esc(t.git_disabled)}</p>`;
    const commits = this._git?.commits || [];
    return `
      <div class="card info">
        <div><b>${esc(t.git_status)}:</b> ${esc(status.status)} ${status.last_error ? `<span class="error">(${esc(status.last_error)})</span>` : ""}</div>
        <div><b>${esc(t.repo)}:</b> ${esc(status.url)} · <b>${esc(t.branch)}:</b> ${esc(status.branch)}</div>
        <div><b>${esc(t.privacy)}:</b> ${esc(status.privacy || "—")} · <b>${esc(t.encryption)}:</b> ${esc(status.encryption ? t.yes : t.no)}</div>
        <div><b>${esc(t.host_key)}:</b> <code>${esc(status.host_key_fp || "—")}</code></div>
      </div>
      <div class="row">
        <input class="grow" id="commit-message" placeholder="${esc(t.commit_message)}">
        <button class="primary" data-action="commit" ${this._busy ? "disabled" : ""}>${esc(this._busy ? t.running : t.commit_now)}</button>
        <button data-action="refresh-git">${esc(t.refresh)}</button>
      </div>
      <div class="split">
        <div class="list">
          <h3>${esc(t.history)}</h3>
          ${this._git?.error ? `<div class="message">${esc(this._git.error)}</div>` : ""}
          ${commits.map((c) => `
            <div class="commit ${this._commit === c.sha ? "selected" : ""}" data-action="select-commit" data-sha="${esc(c.sha)}">
              <div><code>${esc(c.short)}</code> ${esc(c.summary)}</div>
              <div class="muted small">${fmtTime(c.time)} · ${esc(c.changes)} · ${esc(c.author)} ${c.pushed ? "" : `· <span class="error">${esc(t.not_pushed)}</span>`}</div>
            </div>`).join("")}
        </div>
        <div class="detail">${this._commit ? this._renderCommit() : ""}</div>
      </div>
    `;
  }

  _renderCommit() {
    const t = this.t;
    if (!this._files) return "…";
    const areas = [...new Set(this._files.map((f) => f.area).filter((a) => a && a !== "inventory"))];
    return `
      <h3>${esc(t.files)} <code>${esc(this._commit.slice(0, 8))}</code></h3>
      <div class="row wrap">
        ${areas.map((a) => `<label><input type="checkbox" class="area" value="${esc(a)}"> ${esc(t.areas[a] || a)}</label>`).join("")}
      </div>
      <label><input type="checkbox" id="restart"> ${esc(t.restart_after)}</label>
      <div class="row wrap">
        <button class="danger" data-action="restore-all">${esc(t.restore_all)}</button>
        <button data-action="restore-areas">${esc(t.restore_selected)}</button>
      </div>
      <div class="table-wrap"><table>
        ${this._files.map((f) => `
          <tr class="${f.status === "same" ? "muted" : ""}">
            <td><a href="#" data-action="diff" data-path="${esc(f.path)}">${esc(f.path)}</a> ${f.encrypted ? `<span class="badge" style="background:#666">${esc(t.encrypted)}</span>` : ""}</td>
            <td>${esc(t["status_" + f.status] || f.status)}</td>
            <td>${f.status !== "new_locally" && f.area !== "inventory" ? `<button class="small" data-action="restore-file" data-path="${esc(f.path)}">${esc(t.restore_file)}</button>` : ""}</td>
          </tr>`).join("")}
      </table></div>
      ${this._diff ? `<pre class="diff">${this._diff}</pre>` : ""}
    `;
  }

  _renderAnomaly() {
    const t = this.t;
    const a = this._data.anomaly;
    return `
      <div class="cards">
        <div class="card"><div class="big" style="color:${a.sabotage ? SEV_COLORS.critical : "inherit"}">${esc(a.sabotage ? t.yes : t.no)}</div><div>${esc(t.sabotage)}</div></div>
        <div class="card"><div>${esc(t.learning_since)}</div><div>${fmtTime(a.learning_since)}</div></div>
      </div>
      <h3>${esc(t.sensors)}</h3>
      ${a.sensors.length === 0 ? `<p>${esc(t.no_sensors)}</p>` : `<div class="table-wrap"><table>
        ${a.sensors.map((s) => `<tr><td>${esc(s.name)}</td><td>${esc(s.samples)} ${esc(t.samples)}</td><td>${esc(s.learned_buckets)}/48 ${esc(t.learned)}</td><td>${s.active.map((x) => `<span class="badge" style="background:${SEV_COLORS.high}">${esc(x.type)}</span>`).join(" ")}</td></tr>`).join("")}
      </table></div>`}
      <h3>${esc(t.events)}</h3>
      <div class="table-wrap"><table>
        ${a.events.map((e) => `<tr><td>${fmtTime(e.time)}</td><td>${esc(e.type)}</td><td>${esc(e.name || e.actor || e.user || e.entity || e.target || "")}</td><td>${esc(e.detail || e.reason || e.entities || "")}</td></tr>`).join("")}
      </table></div>
      ${a.outbound.enabled ? `<h3>${esc(t.outbound)}</h3>
        <div class="table-wrap"><table>${a.outbound.new.map((o) => `<tr><td>${fmtTime(o.time)}</td><td>${esc(o.host || "")}</td><td>${esc(o.ip)}</td><td>${esc(o.network)}</td></tr>`).join("")}</table></div>` : ""}
    `;
  }

  _renderExternal() {
    const t = this.t;
    const probe = this._data.probe;
    return `
      <div class="row">
        <button class="primary" data-action="probe" ${this._busy ? "disabled" : ""}>${esc(this._busy ? t.running : t.run_probe)}</button>
        <span class="muted">${probe ? fmtTime(probe.time) : ""}</span>
      </div>
      ${!probe ? `<p>${esc(t.probe_none)}</p>` : probe.error ? `<div class="message">${esc(probe.error)}</div>` : `
        <p><b>${esc(t.public_ip)}:</b> ${esc(probe.ip)}</p>
        <div class="table-wrap"><table>
          ${(probe.results || []).map((r) => `<tr class="${r.open ? "warn" : "muted"}"><td>${esc(t.port)} ${esc(r.port)}</td><td>${esc(r.open ? t.open : t.closed)}</td><td>${esc(r.ms ?? "")} ms</td></tr>`).join("")}
        </table></div>`}
    `;
  }

  _bind() {
    const root = this.shadowRoot;
    const on = (sel, fn) => root.querySelectorAll(sel).forEach((el) => el.addEventListener("click", (ev) => fn(el, ev)));
    on('[data-action="audit"]', () =>
      this._action(async () => {
        this._data = await this._ws("bastion/audit/run");
      })
    );
    on('[data-action="toggle-dismissed"]', (el) => {
      this._showDismissed = el.checked;
      this._render();
    });
    on('[data-action="dismiss"]', (el) =>
      this._action(async () => {
        this._data = await this._ws("bastion/finding/dismiss", { finding_id: el.dataset.id, dismissed: el.dataset.dismissed === "1" });
      })
    );
    on('[data-action="accept"]', (el) =>
      this._action(async () => {
        const extra = el.dataset.domain ? { domain: el.dataset.domain } : {};
        this._data = await this._ws("bastion/integrity/accept", extra);
      })
    );
    on('[data-action="commit"]', () =>
      this._action(async () => {
        const message = root.getElementById("commit-message")?.value || undefined;
        const result = await this._ws("bastion/git/commit", message ? { message } : {});
        this._message = result.committed ? `✔ ${result.summary || ""}` : result.push_error ? `${this.t.error}: ${result.push_error}` : "✔";
        this._data = await this._ws("bastion/overview");
        this._git = await this._ws("bastion/git/history", { refresh: false });
      })
    );
    on('[data-action="refresh-git"]', () =>
      this._action(async () => {
        this._git = await this._ws("bastion/git/history", { refresh: true });
      })
    );
    on('[data-action="select-commit"]', (el) =>
      this._action(async () => {
        this._commit = el.dataset.sha;
        this._files = null;
        this._diff = null;
        this._render();
        this._files = (await this._ws("bastion/git/files", { commit: this._commit })).files;
      })
    );
    on('[data-action="diff"]', (el, ev) => {
      ev.preventDefault();
      this._action(async () => {
        const result = await this._ws("bastion/git/diff", { commit: this._commit, path: el.dataset.path });
        if (result.diff) {
          this._diff = result.diff
            .split("\n")
            .map((line) => {
              const cls = line.startsWith("+") ? "add" : line.startsWith("-") ? "del" : line.startsWith("@@") ? "hunk" : "";
              return `<span class="${cls}">${esc(line)}</span>`;
            })
            .join("\n");
        } else {
          this._diff = esc(this.t["status_" + result.status] || result.status);
        }
      });
    });
    const restore = (extra) =>
      this._action(async () => {
        if (!confirm(this.t.confirm_restore.replace("{sha}", this._commit.slice(0, 8)))) return;
        const restart = root.getElementById("restart")?.checked || false;
        const result = await this._ws("bastion/git/restore", { commit: this._commit, restart, ...extra });
        this._message = this.t.restored
          .replace("{written}", result.written.length)
          .replace("{staged}", result.staged.length)
          .replace("{skipped}", result.skipped.length);
      });
    on('[data-action="restore-all"]', () => restore({}));
    on('[data-action="restore-areas"]', () => {
      const areas = [...root.querySelectorAll("input.area:checked")].map((el) => el.value);
      if (areas.length) restore({ areas });
    });
    on('[data-action="restore-file"]', (el) => restore({ paths: [el.dataset.path] }));
    on('[data-action="probe"]', () =>
      this._action(async () => {
        this._data = await this._ws("bastion/probe/run");
      })
    );
  }
}

const STYLE = `
  :host { display:block; background: var(--primary-background-color); color: var(--primary-text-color); min-height:100vh; font-family: var(--paper-font-body1_-_font-family, sans-serif); }
  .toolbar { display:flex; align-items:center; height:56px; padding:0 12px; background: var(--app-header-background-color, var(--primary-color)); color: var(--app-header-text-color, #fff); }
  .title { font-size:20px; margin-left:8px; }
  .tabs { display:flex; gap:4px; padding:8px 16px 0; flex-wrap:wrap; border-bottom:1px solid var(--divider-color); }
  .tab { background:none; border:none; padding:10px 14px; cursor:pointer; color: var(--secondary-text-color); border-bottom:2px solid transparent; font-size:14px; }
  .tab.active { color: var(--primary-color); border-bottom-color: var(--primary-color); }
  .content { padding:16px; max-width:1200px; }
  .cards { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:16px; }
  .card { background: var(--card-background-color); border-radius:12px; padding:14px 18px; min-width:110px; box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.15)); }
  .card.wide { flex:1; min-width:260px; }
  .card.info { margin-bottom:12px; line-height:1.7; }
  .big { font-size:32px; font-weight:600; }
  .row { display:flex; gap:10px; align-items:center; margin:10px 0; flex-wrap:wrap; }
  .row.wrap label { margin-right:8px; }
  .grow { flex:1; min-width:180px; padding:8px; border-radius:6px; border:1px solid var(--divider-color); background: var(--card-background-color); color: inherit; }
  button { padding:7px 14px; border-radius:6px; border:1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); cursor:pointer; }
  button.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); border:none; }
  button.danger { background: var(--error-color, #db4437); color:#fff; border:none; }
  button.small, .small { font-size:12px; }
  button:disabled { opacity:.6; cursor:default; }
  .finding { background: var(--card-background-color); border-radius:12px; padding:12px 16px; margin-bottom:10px; box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.15)); }
  .finding.dismissed { opacity:.55; }
  .finding-head { display:flex; gap:8px; align-items:center; margin-bottom:4px; }
  .finding-title { font-weight:600; }
  .badge { color:#fff; border-radius:10px; padding:2px 8px; font-size:12px; white-space:nowrap; }
  .muted { color: var(--secondary-text-color); }
  .message { background: var(--warning-color, #f4b400); color:#000; padding:8px 12px; border-radius:8px; margin:8px 16px; }
  .error { color: var(--error-color, #db4437); }
  .table-wrap { overflow-x:auto; }
  table { border-collapse:collapse; width:100%; font-size:13px; background: var(--card-background-color); border-radius:8px; }
  th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--divider-color); vertical-align:top; }
  tr.warn td { color: var(--error-color, #db4437); }
  tr.muted td { color: var(--secondary-text-color); }
  .bars { display:flex; align-items:flex-end; gap:2px; height:60px; margin-bottom:6px; }
  .bar { flex:1; background: var(--error-color, #db4437); min-height:1px; border-radius:2px 2px 0 0; }
  .split { display:grid; grid-template-columns: minmax(260px, 1fr) 2fr; gap:16px; }
  @media (max-width: 900px) { .split { grid-template-columns: 1fr; } }
  .commit { padding:8px 10px; border-radius:8px; cursor:pointer; margin-bottom:4px; background: var(--card-background-color); }
  .commit.selected { outline:2px solid var(--primary-color); }
  .diff { background:#111; color:#ddd; padding:10px; border-radius:8px; overflow:auto; font-size:12px; max-height:480px; }
  .diff .add { color:#7ee787; } .diff .del { color:#ff7b72; } .diff .hunk { color:#79c0ff; }
  code { font-size:12px; }
  a { color: var(--primary-color); }
`;

customElements.define("bastion-panel", BastionPanel);
