// Bastion Cloudflare worker.
//
//   POST /probe             Port check of the caller's own public IP (never other hosts).
//   POST /heartbeat         Signed heartbeat of the alarm system (dead man's switch).
//   POST /alert             Signed alarm event: logged in D1, pushed if requested.
//   POST /snapshot          Signed camera image of an incident (stored in D1).
//   POST /pushover/<token>  Pushover callback when an emergency alarm is acknowledged.
//   POST /backfill          Signed resend of Home Assistant's alarm and login log (deduplicated).
//   POST /commands          Signed: Home Assistant fetches remote commands and reports results.
//   POST /remote            Signed: pairing code, passkey list and revocation (managed in HA).
//   GET  /i/<incident>?t=   Incident page (events + camera images), token from the alarm push.
//   GET  /                  Dashboard, only behind Cloudflare Access (installable PWA:
//                           /manifest.webmanifest, /sw.js, icons). Every visit is logged.
//   POST /api/passkey/*     Add a passkey (one-time code from Home Assistant), Access only.
//   POST /api/command/*     Arm/disarm with a passkey, Access only; GET /api/command/<id> = status.
//   any  decoy token/URL    Decoys from Bastion's decoy file: answered like HA, logged, alerted.
//   cron (every minute)     Offline detection with last known state, receipt polling, retention,
//                           outside check of Home Assistant's public address (every 6 hours).
//
// Secrets / variables:
//   PROBE_TOKEN          optional bearer token for /probe
//   ALARM_SECRET         shared secret with Home Assistant (shown in Bastion)
//   PUSHOVER_TOKEN       + PUSHOVER_USER         optional channel (alarm = emergency priority)
//   TELEGRAM_BOT_TOKEN   + TELEGRAM_CHAT_ID      optional channel
//   NTFY_URL             (+ NTFY_TOKEN)           optional channel, e.g. https://ntfy.sh/my-topic
//   WEBHOOK_URL                                   optional channel, receives JSON
//   ACCESS_TEAM_DOMAIN   + ACCESS_AUD            Cloudflare Access for the dashboard
//   DASHBOARD_HOST       optional, serve the dashboard only on this host name
//   OFFLINE_MINUTES      default 10, PLANNED_MINUTES default 20 (after a planned restart)
//   ALERT_WHEN_DISARMED  "1" to also report outages while disarmed
//   LOG_DAYS             default 365, SNAPSHOT_DAYS default 30
//   ATTACK_ALERT_AFTER   default 5 rejected requests in 20 min -> push (at most hourly)
//   ATTACK_BLOCK_AFTER   default 10 rejected requests of one IP in 20 min -> block
//   ATTACK_BLOCK_MINUTES default 60
//   ACCESS_ALERT         "new" (default: push for a new device or country), "all", "off"
// D1 binding: DB

import { connect } from "cloudflare:sockets";
import APP_HTML from "./app.html";
import { accessConfigured, verifyAccess } from "./access.js";
import { canaryResponse, detectCanary } from "./canary.js";
import { EMERGENCY_EXPIRE, notify, pushoverCancel, pushoverEnabled, pushoverReceipt } from "./notify.js";
import { pwaAsset } from "./pwa.js";
import * as remote from "./remote.js";
import { trackAccess } from "./sessions.js";
import * as store from "./store.js";
import * as uptime from "./uptime.js";
import { clientIp, hmacHex, json, nowS, timingSafeEqual, writeBudget } from "./util.js";

const DEFAULT_PORTS = [
  21, 22, 23, 80, 139, 443, 445, 1880, 1883, 2375, 2376, 3000, 3389, 5000,
  5001, 5900, 6052, 8080, 8086, 8123, 8883, 9000, 9443,
];
const MAX_PORTS = 40;
const TIMEOUT_MS = 3000;
const REPLAY_WINDOW = 300;
const MAX_BODY = 64 * 1024;
const MAX_HEARTBEAT = 160 * 1024; // carries the security overview and login events
const MAX_BACKFILL = 512 * 1024;
const EXPOSURE_INTERVAL = 6 * 3600 * 1000;
const MAX_SNAPSHOT = 1_500_000; // base64 characters, D1 allows 2 MB per value
const MODES = { home: "Zuhause", night: "Nacht", away: "Abwesend" };
const LABELS = {
  triggered: "Alarm",
  pending: "Vorwarnung",
  arming: "Wird scharf",
  armed: "Scharf",
  rearmed: "Wieder scharf",
  disarmed: "Unscharf",
  reset: "Zurückgesetzt",
  arm_failed: "Scharfschalten fehlgeschlagen",
  wrong_code: "Falscher Code",
  sensor_unavailable: "Sensor nicht erreichbar",
  acknowledged: "Quittiert",
  offline: "Funkstille",
  online: "Wieder erreichbar",
  restart: "Neustart",
  attack: "Angriffsversuch",
  exposure: "Außenprüfung",
  canary: "Köder benutzt",
  passkey_added: "Passkey gekoppelt",
  passkey_removed: "Passkey entfernt",
  unarmed: "Niemand zuhause, nicht scharf",
};
const ATTACK_LABELS = {
  signature: "falsche Signatur",
  probe_token: "falscher Probe-Token",
  callback: "falscher Pushover-Rückruf",
  link_token: "falscher Vorfall-Link",
  access: "ungültiger Access-Login",
  pairing: "falscher Kopplungscode",
  passkey: "ungültiger Passkey",
};
// Events pushed by older Bastion versions that do not send a push flag.
const LEGACY_PUSH = new Set(["triggered", "pending", "disarmed", "armed", "sensor_unavailable"]);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Link token for an incident page; Bastion computes the same value.
export async function incidentToken(env, incident) {
  return (await hmacHex(env.ALARM_SECRET, `incident.${incident}`)).slice(0, 32);
}

async function callbackToken(env) {
  return (await hmacHex(env.ALARM_SECRET, "pushover-callback")).slice(0, 32);
}

// Returns { data } or { response } (with `attack` set for a forged signature).
async function verified(request, env, maxBody = MAX_BODY) {
  if (!env.ALARM_SECRET) return { response: json({ error: "ALARM_SECRET not set" }, 500) };
  if (Number(request.headers.get("content-length") || 0) > maxBody) return { response: json({ error: "too large" }, 413) };
  const ts = request.headers.get("x-bastion-timestamp") || "";
  const sig = request.headers.get("x-bastion-signature") || "";
  const body = await request.text();
  if (body.length > maxBody) return { response: json({ error: "too large" }, 413) };
  const expected = await hmacHex(env.ALARM_SECRET, `${ts}.${body}`);
  if (!timingSafeEqual(sig, expected)) return { response: json({ error: "unauthorized" }, 401), attack: "signature" };
  // A valid signature with an old timestamp is a clock problem (or a replay), not a guess.
  if (Math.abs(Date.now() / 1000 - Number(ts)) > REPLAY_WINDOW) return { response: json({ error: "stale" }, 401) };
  try {
    const data = JSON.parse(body);
    return data && typeof data === "object" ? { data } : { response: json({ error: "invalid json" }, 400) };
  } catch {
    return { response: json({ error: "invalid json" }, 400) };
  }
}

// --------------------------------------------------------- attack detection
const blockedCache = new Map(); // ip -> until (seconds)

async function isBlocked(env, request) {
  const ip = clientIp(request);
  const cached = blockedCache.get(ip);
  if (cached && cached > nowS()) return true;
  if (!env.DB) return false;
  const until = await store.blockedUntil(env, ip);
  if (until) blockedCache.set(ip, until);
  return Boolean(until);
}

function tooMany() {
  return json({ error: "blocked" }, 429);
}

// Counts a rejected request; blocks noisy IPs and pushes a warning (at most hourly).
async function recordAttempt(request, env, kind, url) {
  if (!env.DB || !writeBudget()) return;
  const ip = clientIp(request);
  const country = (request.cf && request.cf.country) || "";
  await store.addAttempt(env, { ip, kind, country, path: url.pathname });
  const recent = await store.recentAttempts(env, 2);
  const hb = await store.getState(env, "hb");
  const own = recent.find((r) => r.ip === ip);
  const blockAfter = Number(env.ATTACK_BLOCK_AFTER || 10);
  if (own && own.n >= blockAfter && ip !== "unknown" && ip !== (hb && hb.ip) && !(await store.blockedUntil(env, ip))) {
    const until = await store.block(env, { ip, minutes: Number(env.ATTACK_BLOCK_MINUTES || 60), reason: own.kinds, n: own.n, country });
    blockedCache.set(ip, until);
  }
  const total = recent.reduce((sum, r) => sum + r.n, 0);
  if (total < Number(env.ATTACK_ALERT_AFTER || 5)) return;
  const last = (await store.getState(env, "attack_alert")) || 0;
  if (Date.now() - last < 3600 * 1000) return;
  await store.setState(env, "attack_alert", Date.now());
  const sources = [];
  for (const r of recent.slice(0, 5)) {
    const blocked = Boolean(await store.blockedUntil(env, r.ip));
    sources.push({ ip: r.ip, country: r.country, n: r.n, kinds: String(r.kinds || "").split(","), blocked });
  }
  const lines = sources.map(
    (r) => `• ${r.ip}${r.country ? ` (${r.country})` : ""}: ${r.n}× ${r.kinds.map((k) => ATTACK_LABELS[k] || k).join(", ")}${r.blocked ? " – gesperrt" : ""}`,
  );
  await notify(env, {
    title: "🛡 Angriffsversuch auf den Bastion-Worker",
    message: `${total} abgewiesene Zugriffe in den letzten 20 Min.\n${lines.join("\n")}\n\nAlles wurde abgewiesen. Häufen sich falsche Signaturen, in Bastion ein neues ALARM_SECRET erzeugen.`,
    priority: "high",
  });
  await store.addEvent(env, { event: "attack", detail: { total, sources } });
  await store.setState(env, "attack_pending", { ts: nowS(), total, sources });
}

async function rejected(request, env, ctx, kind, url) {
  const job = recordAttempt(request, env, kind, url).catch((err) => console.error("bastion attack log", err && err.stack ? err.stack : err));
  if (ctx && typeof ctx.waitUntil === "function") ctx.waitUntil(job);
  else await job;
}

// Signed endpoints: a forged signature is counted, a blocked IP gets 429.
async function signedBody(request, env, ctx, url, maxBody) {
  const res = await verified(request, env, maxBody);
  if (res.data) return res;
  if (res.attack) {
    await rejected(request, env, ctx, res.attack, url);
    if (await isBlocked(env, request)) return { response: tooMany() };
  }
  return res;
}

const list = (v, n = 20) => (Array.isArray(v) ? v.slice(0, n).map((x) => String(x).slice(0, 80)) : []);
const validIncident = (v) => typeof v === "string" && /^[a-f0-9]{8,32}$/.test(v);

function formatTime(ts, tz) {
  try {
    return new Date(ts * 1000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: tz || "Europe/Berlin" });
  } catch {
    return new Date(ts * 1000).toISOString().slice(11, 16);
  }
}

function stateText(record) {
  const mode = MODES[record.mode] || "";
  switch (record.state) {
    case "triggered":
      return `ALARM (${mode})`;
    case "pending":
      return `Vorwarnung (${mode})`;
    case "arming":
      return `wird scharf (${mode})`;
    case "disarmed":
    case undefined:
      return "aus";
    default:
      return `scharf (${mode})`;
  }
}

// ------------------------------------------------------------------ probe
async function probe(ip, port) {
  const started = Date.now();
  let socket;
  try {
    socket = connect({ hostname: ip, port });
    const open = await Promise.race([socket.opened.then(() => true), sleep(TIMEOUT_MS).then(() => false)]);
    return { port, open, ms: Date.now() - started };
  } catch (err) {
    return { port, open: false, error: String(err).slice(0, 80) };
  } finally {
    try {
      if (socket) await socket.close();
    } catch {
      /* ignore */
    }
  }
}

async function handleProbe(request, env, ctx, url) {
  if (await isBlocked(env, request)) return tooMany();
  if (env.PROBE_TOKEN) {
    const auth = request.headers.get("authorization") || "";
    if (!timingSafeEqual(auth, `Bearer ${env.PROBE_TOKEN}`)) {
      await rejected(request, env, ctx, "probe_token", url);
      return json({ error: "unauthorized" }, 401);
    }
  }
  const ip = request.headers.get("cf-connecting-ip");
  if (!ip) return json({ error: "no client ip" }, 400);
  let ports = DEFAULT_PORTS;
  try {
    const body = await request.json();
    if (Array.isArray(body.ports) && body.ports.length) {
      ports = [...new Set(body.ports.map(Number))]
        .filter((p) => Number.isInteger(p) && p > 0 && p < 65536 && p !== 25)
        .slice(0, MAX_PORTS);
    }
  } catch {
    /* defaults */
  }
  const results = await Promise.all(ports.map((port) => probe(ip, port)));
  return json({ ip, results, checked_at: new Date().toISOString() });
}

// ------------------------------------------------------------ alarm events
function eventText(data) {
  const mode = MODES[data.mode] || data.mode || "";
  const where = [data.sensor, data.room].filter(Boolean).join(" · ");
  const by = data.user ? ` von ${data.user}` : "";
  switch (data.event) {
    case "triggered":
      return [`🚨 ALARM ${data.instance || ""}`.trim(), `${where || data.reason || "Alarm"} (Modus ${mode})`, "urgent"];
    case "pending":
      return ["⏳ Vorwarnung", `${where} – Alarm folgt, falls nicht unscharf geschaltet wird.`, "high"];
    case "disarmed":
      return ["✅ Alarmanlage aus", `Unscharf geschaltet${by}.`, "default"];
    case "armed":
    case "arming":
    case "rearmed":
      return ["🛡 Alarmanlage scharf", `Modus ${mode}${by}`, "default"];
    case "sensor_unavailable":
      return ["⚠️ Sensor nicht erreichbar", where, "high"];
    case "wrong_code":
      return ["🔑 Falscher Alarm-Code", `Ein falscher Code wurde eingegeben${by}.`, "high"];
    case "arm_failed":
      return ["Scharfschalten fehlgeschlagen", `Offen: ${list(data.sensors).join(", ")}`, "default"];
    case "unarmed": {
      const minutes = data.detail && data.detail.minutes;
      return ["🏠 Niemand zuhause – Alarmanlage aus", `Alle sind${minutes ? ` seit ${minutes} Min.` : ""} weg, die Alarmanlage ist unscharf.`, "high"];
    }
    case "test":
      return ["🧪 Bastion Test", "Die Verbindung zwischen Home Assistant und dem Worker funktioniert.", "default"];
    default:
      return [`Bastion: ${LABELS[data.event] || data.event}`, where, "default"];
  }
}

async function cancelOpen(env, kind) {
  for (const r of await store.openReceipts(env, kind)) {
    await pushoverCancel(env, r.receipt);
    await store.markCancelled(env, r.receipt);
  }
}

function securityOverview(sec) {
  const counts = sec.counts && typeof sec.counts === "object" ? sec.counts : {};
  return {
    score: Math.max(0, Math.min(100, Number(sec.score) || 0)),
    counts: Object.fromEntries(["critical", "high", "medium", "low", "info"].map((k) => [k, Number(counts[k]) || 0])),
    open: Number(sec.open) || 0,
    last_audit: typeof sec.last_audit === "string" ? sec.last_audit.slice(0, 40) : null,
    failed_24h: Number(sec.failed_24h) || 0,
    findings: (Array.isArray(sec.findings) ? sec.findings : []).slice(0, 40).map((f) => ({
      id: String(f.id || "").slice(0, 40),
      severity: String(f.severity || "info").slice(0, 10),
      category: String(f.category || "").slice(0, 20),
      title: String(f.title || "").slice(0, 200),
      since: typeof f.since === "string" ? f.since.slice(0, 40) : null,
    })),
    git: sec.git && typeof sec.git === "object" ? { status: String(sec.git.status || "").slice(0, 20), last: String(sec.git.last || "").slice(0, 40) } : null,
    history: (Array.isArray(sec.history) ? sec.history : []).slice(-400).map((h) => ({
      date: String(h.date || "").slice(0, 10),
      score: Math.max(0, Math.min(100, Number(h.score) || 0)),
    })),
    received: nowS(),
  };
}

// Public addresses of Home Assistant to check from outside (scheme + host only).
function checkUrls(list) {
  const out = [];
  for (const raw of Array.isArray(list) ? list.slice(0, 3) : []) {
    try {
      const u = new URL(String(raw));
      if ((u.protocol === "https:" || u.protocol === "http:") && !u.username && !u.password) out.push(`${u.protocol}//${u.host}`);
    } catch {
      /* ignore */
    }
  }
  return [...new Set(out)];
}

async function handleHeartbeat(request, env, url, ctx) {
  const { data, response } = await signedBody(request, env, ctx, url, MAX_HEARTBEAT);
  if (response) return response;
  const prev = await store.getState(env, "hb");
  const seen = list(data.acks_seen);
  const record = {
    ts: Number(data.ts) || nowS(),
    state: String(data.state || ""),
    mode: data.mode || null,
    armed: Boolean(data.armed),
    incident: validIncident(data.incident) ? data.incident : null,
    interval: Number(data.interval) || 120,
    instance: String(data.instance || "").slice(0, 80),
    tz: String(data.tz || "").slice(0, 60),
    open: list(data.open),
    unavailable: list(data.unavailable),
    started: Number(data.started) || null,
    boot: Number(data.boot) || null,
    version: String(data.version || "").slice(0, 20),
    stopping: Boolean(data.stopping),
    received: Date.now(),
    origin: url.origin,
    ip: clientIp(request),
    check_urls: checkUrls(data.check_urls),
    remote: data.remote && typeof data.remote === "object" ? { enabled: Boolean(data.remote.enabled), disarm: Boolean(data.remote.disarm) } : null,
    offline: false,
    offline_notified: false,
  };
  await uptime.onHeartbeat(env, prev, record);
  if (prev && prev.offline) {
    const minutes = Math.round((Date.now() - prev.received) / 60000);
    const cause = uptime.recoveryCause(prev, record);
    await store.addEvent(env, { event: "online", state: record.state, mode: record.mode, detail: { minutes, cause } });
    if (prev.offline_notified) {
      await cancelOpen(env, "offline");
      await notify(env, {
        title: "✅ Home Assistant wieder erreichbar",
        message: `Nach ${minutes} Min. Funkstille. ${cause}\nAlarmanlage: ${stateText(record)}.`,
      });
    }
  } else if (prev && !prev.stopping && uptime.restarted(prev, record)) {
    await store.addEvent(env, { event: "restart", state: record.state, mode: record.mode, detail: { cause: uptime.recoveryCause(prev, record) } });
  }
  await store.setState(env, "hb", record);
  if (seen.length) await store.markSeen(env, seen);
  const noticesSeen = (Array.isArray(data.notices_seen) ? data.notices_seen : []).map(Number).filter((n) => Number.isInteger(n) && n > 0).slice(0, 50);
  if (noticesSeen.length) await store.markNoticesSeen(env, noticesSeen);
  // A valid signature lifts a block of this IP (e.g. HA behind a new address).
  if (await store.blockedUntil(env, record.ip)) await store.unblock(env, record.ip);
  blockedCache.delete(record.ip);
  if (data.security && typeof data.security === "object") await store.setState(env, "security", securityOverview(data.security));
  if (Array.isArray(data.security_events)) {
    await store.addSecEvents(env, data.security_events.slice(0, 60).filter((e) => e && typeof e === "object" && e.uid && e.type));
  }
  const attack = await store.getState(env, "attack_pending");
  if (attack) await store.setState(env, "attack_pending", null);
  return json({
    ok: true,
    acks: await store.unseenAcks(env),
    attack: attack || null,
    exposure: await store.getState(env, "exposure"),
    notices: await store.unseenNotices(env),
    dashboard: remote.dashboardUrl(env),
  });
}

async function handleAlert(request, env, url, ctx) {
  const { data, response } = await signedBody(request, env, ctx, url);
  if (response) return response;
  const incident = validIncident(data.incident) ? data.incident : null;
  if (data.event !== "test") {
    await store.addEvent(env, {
      ts: data.ts,
      event: data.event,
      state: data.state,
      mode: data.mode,
      incident,
      sensor: data.sensor,
      room: data.room,
      user: data.user,
      detail: data.detail && typeof data.detail === "object" ? data.detail : null,
      uid: data.uid,
    });
    // An alert is also a sign of life and the freshest state for the offline report.
    const hb = await store.getState(env, "hb");
    if (hb && !hb.offline) {
      Object.assign(hb, { state: String(data.state || hb.state), mode: data.mode ?? hb.mode, armed: Boolean(data.armed), incident, received: Date.now() });
      await store.setState(env, "hb", hb);
    }
  }
  if (data.event === "disarmed") await cancelOpen(env, "alarm");
  let view = incident ? `${url.origin}/i/${incident}?t=${await incidentToken(env, incident)}` : null;
  let urlTitle = "Ereignis und Kamerabilder";
  if (data.event === "unarmed" && remote.dashboardUrl(env)) {
    const hb = await store.getState(env, "hb");
    const allowed = hb && hb.remote && hb.remote.enabled;
    view = `${remote.dashboardUrl(env)}/${allowed ? "?do=arm_away" : ""}`;
    urlTitle = allowed ? "Jetzt scharf schalten" : "Dashboard öffnen";
  }
  const push = data.event === "test" || (typeof data.push === "boolean" ? data.push : LEGACY_PUSH.has(data.event));
  let channels = [];
  if (push) {
    const [title, message, priority] = eventText(data);
    const callback = pushoverEnabled(env) ? `${url.origin}/pushover/${await callbackToken(env)}` : null;
    const res = await notify(env, { title, message, priority, url: view, urlTitle, callback });
    channels = res.sent;
    if (res.receipt && priority === "urgent") {
      await store.addReceipt(env, { receipt: res.receipt, kind: "alarm", incident, expires: nowS() + EMERGENCY_EXPIRE });
    }
  }
  return json({ ok: true, channels, view });
}

async function handleSnapshot(request, env, url, ctx) {
  const { data, response } = await signedBody(request, env, ctx, url, MAX_SNAPSHOT + 4096);
  if (response) return response;
  if (!validIncident(data.incident)) return json({ error: "invalid incident" }, 400);
  const type = String(data.type || "image/jpeg");
  if (!/^image\/(jpeg|png|webp|gif)$/.test(type)) return json({ error: "invalid type" }, 400);
  if (typeof data.data !== "string" || !data.data || data.data.length > MAX_SNAPSHOT || !/^[A-Za-z0-9+/=]+$/.test(data.data)) {
    return json({ error: "invalid image" }, 400);
  }
  const id = await store.addSnapshot(env, { ts: data.ts, incident: data.incident, camera: data.camera, type, data: data.data });
  return json({ ok: true, id });
}

async function handleBackfill(request, env, url, ctx) {
  const { data, response } = await signedBody(request, env, ctx, url, MAX_BACKFILL);
  if (response) return response;
  const alarm = (Array.isArray(data.alarm_events) ? data.alarm_events : [])
    .slice(0, 300)
    .filter((e) => e && typeof e === "object" && e.event && e.uid)
    .map((e) => ({ ...e, incident: validIncident(e.incident) ? e.incident : null }));
  const security = (Array.isArray(data.security_events) ? data.security_events : [])
    .slice(0, 300)
    .filter((e) => e && typeof e === "object" && e.uid && e.type);
  return json({ ok: true, alarm: await store.addEventsBackfill(env, alarm), security: await store.addSecEvents(env, security) });
}

// ---------------------------------------------------- outside check (exposure)
const FAILING = new Set(["warning", "critical"]);

async function outsideFetch(url) {
  const started = Date.now();
  try {
    const res = await fetch(url, { redirect: "manual", headers: { "user-agent": "Bastion-Aussenpruefung/1" }, signal: AbortSignal.timeout(8000) });
    return { res, ms: Date.now() - started };
  } catch (err) {
    return { error: String((err && err.message) || err).slice(0, 120), ms: Date.now() - started };
  }
}

async function bodyJson(res) {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

// One address: reachable? protected by Access? login or API open? plain http?
export async function probeAddress(base) {
  const host = new URL(base).host;
  const checks = [];
  const main = await outsideFetch(`${base}/`);
  if (main.error) {
    const tls = /ssl|tls|certificate|handshake/i.test(main.error);
    checks.push({ id: tls ? "tls_invalid" : "unreachable", level: tls ? "critical" : "warning", text: `${tls ? "TLS-Fehler" : "Nicht erreichbar"}: ${main.error}` });
    return { url: base, colo: "", ms: main.ms, checks };
  }
  const res = main.res;
  const colo = (res.headers.get("cf-ray") || "").split("-")[1] || "";
  if (res.status === 525 || res.status === 526) {
    checks.push({ id: "tls_invalid", level: "critical", text: `Zertifikat am Ursprung ungültig (Cloudflare ${res.status})` });
  }
  const location = res.headers.get("location") || "";
  const access = /^https:\/\/[^/]+\.cloudflareaccess\.com\//.test(location);
  if (access) {
    checks.push({ id: "access", level: "ok", text: "Cloudflare Access verlangt eine Anmeldung" });
  } else {
    const providers = await outsideFetch(`${base}/auth/providers`);
    const list = providers.res && providers.res.status === 200 ? await bodyJson(providers.res) : null;
    const loginOpen = Array.isArray(list) || Array.isArray(list && list.providers);
    checks.push(
      loginOpen
        ? { id: "login_open", level: "warning", text: "Die Home-Assistant-Anmeldung ist ohne vorgeschalteten Schutz öffentlich erreichbar" }
        : { id: "reachable", level: "ok", text: `Erreichbar (HTTP ${res.status})` },
    );
    const api = await outsideFetch(`${base}/api/`);
    if (api.res && api.res.status === 200) checks.push({ id: "api_open", level: "critical", text: "Die HA-API antwortet ohne Anmeldung" });
  }
  if (base.startsWith("https://")) {
    const plain = await outsideFetch(`http://${host}/`);
    if (plain.res && plain.res.status >= 200 && plain.res.status < 300) {
      checks.push({ id: "http_plain", level: "warning", text: "Auch unverschlüsselt über http:// erreichbar" });
    }
  } else {
    checks.push({ id: "http_plain", level: "warning", text: "Adresse ohne HTTPS: Anmeldedaten gehen unverschlüsselt übers Netz" });
  }
  return { url: base, status: res.status, colo, ms: main.ms, checks };
}

function problemKeys(state) {
  return new Set(((state && state.results) || []).flatMap((r) => r.checks.filter((c) => FAILING.has(c.level)).map((c) => `${r.url}|${c.id}`)));
}

async function checkExposure(env, force = false) {
  const hb = await store.getState(env, "hb");
  const urls = (hb && hb.check_urls) || [];
  const prev = await store.getState(env, "exposure");
  const sameUrls = prev && JSON.stringify(prev.urls) === JSON.stringify(urls);
  if (!urls.length) {
    if (prev && prev.urls && prev.urls.length) await store.setState(env, "exposure", { urls: [], checked: Date.now(), results: [] });
    return;
  }
  if (!force && sameUrls && Date.now() - prev.checked < EXPOSURE_INTERVAL) return;
  const results = [];
  for (const base of urls) results.push(await probeAddress(base));
  const state = { urls, checked: Date.now(), results };
  await store.setState(env, "exposure", state);
  const before = sameUrls ? problemKeys(prev) : new Set();
  const now = problemKeys(state);
  const fresh = results.flatMap((r) => r.checks.filter((c) => FAILING.has(c.level) && !before.has(`${r.url}|${c.id}`)).map((c) => ({ url: r.url, colo: r.colo, ...c })));
  if (fresh.length) {
    await notify(env, {
      title: "🌐 Außenprüfung: neues Problem",
      message: fresh.map((p) => `• ${new URL(p.url).host}: ${p.text}${p.colo ? ` (geprüft über ${p.colo})` : ""}`).join("\n"),
      priority: fresh.some((p) => p.level === "critical") ? "high" : "default",
    });
    await store.addEvent(env, { event: "exposure", detail: { problems: fresh.map((p) => ({ url: p.url, id: p.id, level: p.level, text: p.text })) } });
  } else if (sameUrls && before.size && !now.size) {
    await notify(env, { title: "✅ Außenprüfung in Ordnung", message: "Die zuvor gemeldeten Probleme sind behoben." });
    await store.addEvent(env, { event: "exposure", detail: { problems: [] } });
  }
}

// ------------------------------------------------------ acknowledgements
async function checkReceipt(env, rec) {
  const info = await pushoverReceipt(env, rec.receipt);
  if (!info) return;
  if (Number(info.acknowledged) === 1) {
    const by = String(info.acknowledged_by_device || "").trim() || "Pushover";
    const at = Number(info.acknowledged_at) || nowS();
    await store.markAcked(env, rec.receipt, at, by);
    await store.addEvent(env, { ts: at, event: "acknowledged", incident: rec.incident, user: by, detail: { kind: rec.kind, receipt: rec.receipt } });
    await notify(env, { title: "✋ Alarm quittiert", message: `Quittiert von ${by}. Die Wiederholung ist für alle beendet.` });
  } else if (Number(info.expired) === 1) {
    await store.markCancelled(env, rec.receipt);
  }
}

async function handlePushoverCallback(request, env, token, ctx, url) {
  if (!env.ALARM_SECRET || !pushoverEnabled(env)) return json({ error: "not found" }, 404);
  if (await isBlocked(env, request)) return tooMany();
  if (!timingSafeEqual(token, await callbackToken(env))) {
    await rejected(request, env, ctx, "callback", url);
    return json({ error: "unauthorized" }, 401);
  }
  let receipt = "";
  try {
    receipt = String((await request.formData()).get("receipt") || "");
  } catch {
    return json({ error: "invalid" }, 400);
  }
  if (!/^[A-Za-z0-9]{10,40}$/.test(receipt)) return json({ error: "invalid" }, 400);
  const rec = await store.getReceipt(env, receipt);
  // The callback itself is not trusted: the receipt is confirmed with Pushover.
  if (rec && !rec.acked_at) await checkReceipt(env, rec);
  return json({ ok: true });
}

// ---------------------------------------------------------- offline check
function offlineReport(record, events, silent) {
  const active = ["pending", "triggered"].includes(record.state);
  const recentUnavailable = events.some((e) => e.event === "sensor_unavailable") || record.unavailable.length > 0;
  let verdict;
  let priority = record.armed || active ? "urgent" : "high";
  if (active) verdict = "Funkstille während eines laufenden Alarms – Sabotage wahrscheinlich.";
  else if (record.stopping) {
    verdict = "Home Assistant wurde geplant beendet (Neustart oder Update) und ist nicht zurückgekehrt.";
  } else if (recentUnavailable) verdict = "Kurz vorher fielen Sensoren aus – Funkstörung, Stromausfall oder Sabotage möglich.";
  else verdict = "Möglich: Strom- oder Internetausfall, Absturz oder Sabotage.";
  if (!record.armed && !active) priority = "high";
  const lines = [`Seit ${Math.round(silent)} Min. kein Lebenszeichen von ${record.instance || "Home Assistant"}.`, verdict, "", `Letzter Stand: ${stateText(record)}`];
  if (events.length) {
    lines.push("Zuletzt:");
    for (const e of [...events].reverse()) {
      const where = [e.sensor, e.room].filter(Boolean).join(", ");
      lines.push(`• ${formatTime(e.ts, record.tz)} ${LABELS[e.event] || e.event}${where ? ` – ${where}` : ""}${e.user && e.event !== "acknowledged" ? ` (${e.user})` : ""}`);
    }
  }
  if (record.open.length) lines.push(`Offen: ${record.open.join(", ")}`);
  if (record.unavailable.length) lines.push(`Nicht erreichbar: ${record.unavailable.join(", ")}`);
  return { title: active ? "🚨 Funkstille während Alarm" : "⚠️ Home Assistant nicht erreichbar", message: lines.join("\n"), priority, verdict };
}

async function checkHeartbeat(env) {
  const record = await store.getState(env, "hb");
  if (!record || record.offline) return;
  let minutes = Math.max(Number(env.OFFLINE_MINUTES || 10), Math.ceil((3 * (record.interval || 120)) / 60));
  if (record.stopping) minutes = Math.max(minutes, Number(env.PLANNED_MINUTES || 20));
  const silent = (Date.now() - record.received) / 60000;
  if (silent <= minutes) return;
  const active = ["pending", "triggered"].includes(record.state);
  const relevant = record.armed || active || env.ALERT_WHEN_DISARMED === "1";
  const events = await store.recentEvents(env, Math.floor(record.received / 1000) - 1800, 5);
  const report = offlineReport({ ...record, open: record.open || [], unavailable: record.unavailable || [] }, events, silent);
  record.offline = true;
  record.outage_id = await uptime.onOffline(env, record, relevant);
  if (relevant) {
    const view = active && record.incident && record.origin
      ? `${record.origin}/i/${record.incident}?t=${await incidentToken(env, record.incident)}`
      : null;
    const callback = pushoverEnabled(env) && record.origin ? `${record.origin}/pushover/${await callbackToken(env)}` : null;
    const res = await notify(env, { title: report.title, message: report.message, priority: report.priority, url: view, urlTitle: "Ereignis und Kamerabilder", callback });
    if (res.receipt && report.priority === "urgent") {
      await store.addReceipt(env, { receipt: res.receipt, kind: "offline", incident: record.incident, expires: nowS() + EMERGENCY_EXPIRE });
    }
    record.offline_notified = true;
  }
  await store.addEvent(env, {
    event: "offline",
    state: record.state,
    mode: record.mode,
    incident: active ? record.incident : null,
    detail: { verdict: report.verdict, since: Math.floor(record.received / 1000), notified: record.offline_notified },
  });
  await store.setState(env, "hb", record);
}

async function pollReceipts(env) {
  if (!pushoverEnabled(env)) return;
  for (const rec of await store.openReceipts(env, null, 5)) await checkReceipt(env, rec);
}

async function retention(env) {
  const last = (await store.getState(env, "cleanup")) || 0;
  if (Date.now() - last < 3600 * 1000) return;
  await store.cleanup(env, { logDays: Number(env.LOG_DAYS || 365), snapshotDays: Number(env.SNAPSHOT_DAYS || 30) });
  await store.setState(env, "cleanup", Date.now());
}

// ------------------------------------------------------------- web pages
function page(env) {
  const nonce = crypto.randomUUID().replace(/-/g, "");
  return new Response(APP_HTML.replace(/<script>/g, `<script nonce="${nonce}">`), {
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "content-security-policy": `default-src 'none'; script-src 'nonce-${nonce}'; style-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; worker-src 'self'; manifest-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'`,
      "referrer-policy": "no-referrer",
      "x-content-type-options": "nosniff",
      "x-frame-options": "DENY",
    },
  });
}

function onDashboardHost(env, url) {
  return !env.DASHBOARD_HOST || url.hostname === env.DASHBOARD_HOST;
}

// Access identity for dashboard requests, null otherwise.
async function dashboardUser(request, env, url) {
  if (!accessConfigured(env) || !onDashboardHost(env, url)) return null;
  return verifyAccess(request, env);
}

// Incident data needs either the link token or a dashboard login.
async function incidentAllowed(request, env, url, incident) {
  const token = url.searchParams.get("t") || "";
  if (env.ALARM_SECRET && token && timingSafeEqual(token, await incidentToken(env, incident))) return true;
  return Boolean(await dashboardUser(request, env, url));
}

async function apiIncident(request, env, url, incident, ctx) {
  if (!validIncident(incident) || !(await incidentAllowed(request, env, url, incident))) {
    await rejected(request, env, ctx, onDashboardHost(env, url) && accessConfigured(env) ? "access" : "link_token", url);
    return json({ error: "not found" }, 404);
  }
  const hb = await store.getState(env, "hb");
  return json({
    incident,
    tz: hb?.tz || "Europe/Berlin",
    instance: hb?.instance || "",
    events: await store.incidentEvents(env, incident),
    snapshots: await store.snapshotList(env, incident),
  });
}

async function apiImage(request, env, url, id, ctx) {
  const incident = url.searchParams.get("i") || "";
  if (!/^\d+$/.test(id) || !validIncident(incident) || !(await incidentAllowed(request, env, url, incident))) {
    await rejected(request, env, ctx, onDashboardHost(env, url) && accessConfigured(env) ? "access" : "link_token", url);
    return json({ error: "not found" }, 404);
  }
  const row = await store.getSnapshot(env, Number(id));
  if (!row || row.incident !== incident) return json({ error: "not found" }, 404);
  return json({ id: row.id, ts: row.ts, camera: row.camera, type: row.type, data: row.data });
}

async function apiSummary(env, url, user) {
  await uptime.ensureHistory(env);
  const days = Math.min(Math.max(Number(url.searchParams.get("days")) || 30, 1), 365);
  const since = nowS() - days * 86400;
  const hb = await store.getState(env, "hb");
  return json({
    now: nowS(),
    days,
    user: user.email,
    hb: hb && {
      state: hb.state, mode: hb.mode, armed: hb.armed, incident: hb.incident, instance: hb.instance, tz: hb.tz,
      open: hb.open, unavailable: hb.unavailable, received: Math.floor(hb.received / 1000), offline: hb.offline,
      interval: hb.interval, version: hb.version,
    },
    before: await store.lastEventBefore(env, since),
    events: await store.eventsSince(env, since),
    receipts: await store.receiptsSince(env, since),
    snapshots: await store.snapshotCounts(env, since),
    security: await store.getState(env, "security"),
    secevents: await store.secEventsSince(env, since),
    attempts: await store.attemptsSince(env, since),
    blocked: await store.blockedList(env, since),
    exposure: await store.getState(env, "exposure"),
    outages: await store.outagesSince(env, since),
    uptime_since: await store.getState(env, "uptime_since"),
    sessions: await store.sessionsSince(env, since),
    canary: await store.canaryHitsSince(env, since),
    remote: await remote.remoteSummary(env, user, hb),
  });
}

async function handleGet(request, env, url, ctx) {
  const path = url.pathname;
  // Manifest, service worker and icons hold no data (behind Access on the dashboard host anyway).
  const asset = pwaAsset(path);
  if (asset) return asset;
  const known = path === "/" || path.startsWith("/i/") || path.startsWith("/api/");
  if (known && (await isBlocked(env, request))) return tooMany();
  if (path.startsWith("/i/")) return validIncident(path.slice(3)) ? page(env) : json({ error: "not found" }, 404);
  let m = path.match(/^\/api\/incident\/([a-f0-9]{8,32})$/);
  if (m) return apiIncident(request, env, url, m[1], ctx);
  m = path.match(/^\/api\/img\/(\d+)$/);
  if (m) return apiImage(request, env, url, m[1], ctx);
  m = path.match(/^\/api\/command\/([a-f0-9]{16})$/);
  if (path === "/" || path === "/api/summary" || m) {
    const user = await dashboardUser(request, env, url);
    if (!user) {
      // Behind Access every request carries a valid token; anything else is a bypass attempt.
      if (accessConfigured(env) && onDashboardHost(env, url) && env.DASHBOARD_HOST) await rejected(request, env, ctx, "access", url);
      return json({ error: "not found" }, 404);
    }
    if (!m) await trackAccess(request, env, ctx, user);
    if (m) return remote.commandStatus(env, m[1]);
    return path === "/" ? page(env) : apiSummary(env, url, user);
  }
  return json({ error: "not found" }, 404);
}

// Dashboard actions (passkeys, commands): Access, same origin, JSON.
const DASHBOARD_POST = {
  "/api/passkey/begin": (env, url, user, body) => remote.passkeyBegin(env, url, user, body),
  "/api/passkey/finish": (env, url, user, body, request) => remote.passkeyFinish(env, url, user, body, request.headers.get("user-agent")),
  "/api/command/begin": (env, url, user, body) => remote.commandBegin(env, url, user, body),
  "/api/command/finish": (env, url, user, body) => remote.commandFinish(env, url, user, body),
};

async function handleDashboardPost(request, env, url, ctx) {
  const handler = DASHBOARD_POST[url.pathname];
  if (!handler) return json({ error: "not found" }, 404);
  if (await isBlocked(env, request)) return tooMany();
  const user = await dashboardUser(request, env, url);
  if (!user) {
    if (accessConfigured(env) && onDashboardHost(env, url) && env.DASHBOARD_HOST) await rejected(request, env, ctx, "access", url);
    return json({ error: "not found" }, 404);
  }
  if (request.headers.get("origin") !== url.origin) return json({ error: "forbidden" }, 403);
  if (Number(request.headers.get("content-length") || 0) > 32768) return json({ error: "too large" }, 413);
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "invalid json" }, 400);
  }
  if (!body || typeof body !== "object") return json({ error: "invalid json" }, 400);
  await trackAccess(request, env, ctx, user);
  const res = await handler(env, url, user, body, request);
  if (res.attack) await rejected(request, env, ctx, url.pathname.startsWith("/api/passkey/begin") ? "pairing" : "passkey", url);
  return res.response;
}

async function handleSigned(request, env, url, ctx, fn) {
  const { data, response } = await signedBody(request, env, ctx, url);
  return response || fn(env, data);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    try {
      // Decoys first: whatever the path, a decoy token or URL is never legitimate.
      const decoy = await detectCanary(request, env, url);
      if (decoy) return await canaryResponse(request, env, ctx, url, decoy);
      if (request.method === "GET" || request.method === "HEAD") return await handleGet(request, env, url, ctx);
      if (request.method !== "POST") return json({ error: "method not allowed" }, 405);
      if (path.startsWith("/api/")) return await handleDashboardPost(request, env, url, ctx);
      if (path === "/commands") return await handleSigned(request, env, url, ctx, remote.haCommands);
      if (path === "/remote") return await handleSigned(request, env, url, ctx, remote.haRemote);
      if (path === "/probe") return await handleProbe(request, env, ctx, url);
      if (path === "/heartbeat") return await handleHeartbeat(request, env, url, ctx);
      if (path === "/alert") return await handleAlert(request, env, url, ctx);
      if (path === "/snapshot") return await handleSnapshot(request, env, url, ctx);
      if (path === "/backfill") return await handleBackfill(request, env, url, ctx);
      if (path.startsWith("/pushover/")) return await handlePushoverCallback(request, env, path.slice(10), ctx, url);
      return json({ error: "not found" }, 404);
    } catch (err) {
      console.error("bastion worker", err && err.stack ? err.stack : err);
      return json({ error: "internal error" }, 500);
    }
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil(
      (async () => {
        for (const job of [uptime.ensureHistory, checkHeartbeat, pollReceipts, retention, checkExposure]) {
          try {
            await job(env);
          } catch (err) {
            console.error("bastion cron", job.name, err && err.stack ? err.stack : err);
          }
        }
      })(),
    );
  },
};
