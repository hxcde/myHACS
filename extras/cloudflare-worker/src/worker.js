// Bastion Cloudflare worker.
//
//   POST /probe      Port check of the caller's own public IP (never other hosts).
//   POST /heartbeat  Signed heartbeat of the alarm system (dead man's switch).
//   POST /alert      Signed alarm event, relayed to Telegram / ntfy / webhook.
//   cron             Alerts when heartbeats stop while the alarm is armed.
//
// Secrets / variables (wrangler secret put …):
//   PROBE_TOKEN          optional bearer token for /probe
//   ALARM_SECRET         shared secret for /heartbeat and /alert (shown in Bastion)
//   PUSHOVER_TOKEN       + PUSHOVER_USER         optional channel (alarm = emergency priority)
//   TELEGRAM_BOT_TOKEN   + TELEGRAM_CHAT_ID      optional channel
//   NTFY_URL             (+ NTFY_TOKEN)           optional channel, e.g. https://ntfy.sh/my-topic
//   WEBHOOK_URL                                   optional channel, receives JSON
//   OFFLINE_MINUTES      default 10
//   ALERT_WHEN_DISARMED  "1" to also report outages while disarmed
// KV binding: BASTION_KV

import { connect } from "cloudflare:sockets";

const DEFAULT_PORTS = [
  21, 22, 23, 80, 139, 443, 445, 1880, 1883, 2375, 2376, 3000, 3389, 5000,
  5001, 5900, 6052, 8080, 8086, 8123, 8883, 9000, 9443,
];
const MAX_PORTS = 40;
const TIMEOUT_MS = 3000;
const REPLAY_WINDOW = 300;
const MODES = { home: "Zuhause", night: "Nacht", away: "Abwesend" };

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

function timingSafeEqual(a, b) {
  const enc = new TextEncoder();
  const x = enc.encode(a);
  const y = enc.encode(b);
  if (x.length !== y.length) return false;
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function hmacHex(secret, message) {
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Returns the parsed body or a Response with the error.
async function verified(request, env) {
  if (!env.ALARM_SECRET) return json({ error: "ALARM_SECRET not set" }, 500);
  const ts = request.headers.get("x-bastion-timestamp") || "";
  const sig = request.headers.get("x-bastion-signature") || "";
  const body = await request.text();
  if (Math.abs(Date.now() / 1000 - Number(ts)) > REPLAY_WINDOW) return json({ error: "stale" }, 401);
  const expected = await hmacHex(env.ALARM_SECRET, `${ts}.${body}`);
  if (!timingSafeEqual(sig, expected)) return json({ error: "unauthorized" }, 401);
  try {
    return JSON.parse(body);
  } catch {
    return json({ error: "invalid json" }, 400);
  }
}

// Pushover priorities: 2 = emergency (repeats until acknowledged), 1 = high, 0 = normal.
const PUSHOVER_PRIORITY = { urgent: 2, high: 1, default: 0 };

async function notify(env, title, message, priority = "default") {
  const sent = [];
  const tasks = [];
  if (env.PUSHOVER_TOKEN && env.PUSHOVER_USER) {
    const level = PUSHOVER_PRIORITY[priority] ?? 0;
    const form = new URLSearchParams({
      token: env.PUSHOVER_TOKEN,
      user: env.PUSHOVER_USER,
      title: title.slice(0, 250),
      message: message.slice(0, 1024) || title,
      priority: String(level),
    });
    if (level === 2) {
      form.set("retry", "60");
      form.set("expire", "1800");
      form.set("sound", env.PUSHOVER_SOUND || "siren");
    }
    if (env.PUSHOVER_DEVICE) form.set("device", env.PUSHOVER_DEVICE);
    tasks.push(
      fetch("https://api.pushover.net/1/messages.json", { method: "POST", body: form }).then(
        (r) => r.ok && sent.push("pushover"),
      ),
    );
  }
  if (env.TELEGRAM_BOT_TOKEN && env.TELEGRAM_CHAT_ID) {
    tasks.push(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text: `${title}\n${message}` }),
      }).then((r) => r.ok && sent.push("telegram")),
    );
  }
  if (env.NTFY_URL) {
    const headers = { Title: encodeURIComponent(title), Priority: priority === "urgent" ? "5" : "3", Tags: "rotating_light" };
    if (env.NTFY_TOKEN) headers.Authorization = `Bearer ${env.NTFY_TOKEN}`;
    tasks.push(fetch(env.NTFY_URL, { method: "POST", headers, body: message }).then((r) => r.ok && sent.push("ntfy")));
  }
  if (env.WEBHOOK_URL) {
    tasks.push(
      fetch(env.WEBHOOK_URL, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title, message, priority }),
      }).then((r) => r.ok && sent.push("webhook")),
    );
  }
  await Promise.allSettled(tasks);
  return sent;
}

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

async function handleProbe(request, env) {
  if (env.PROBE_TOKEN) {
    const auth = request.headers.get("authorization") || "";
    if (!timingSafeEqual(auth, `Bearer ${env.PROBE_TOKEN}`)) return json({ error: "unauthorized" }, 401);
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

function eventText(data) {
  const mode = MODES[data.mode] || data.mode || "";
  const where = [data.sensor, data.room].filter(Boolean).join(" · ");
  switch (data.event) {
    case "triggered":
      return [`🚨 ALARM ${data.instance || ""}`.trim(), `${where || data.reason || "Alarm"} (Modus ${mode})`, "urgent"];
    case "pending":
      return ["⏳ Vorwarnung", `${where} – Alarm folgt, falls nicht unscharf geschaltet wird.`, "high"];
    case "disarmed":
      return ["✅ Alarmanlage aus", data.user ? `Unscharf geschaltet von ${data.user}` : "Unscharf geschaltet", "default"];
    case "armed":
      return ["🛡 Alarmanlage scharf", `Modus ${mode}`, "default"];
    case "sensor_unavailable":
      return ["⚠️ Sensor nicht erreichbar", where, "high"];
    case "test":
      return ["🧪 Bastion Test", "Die Verbindung zwischen Home Assistant und dem Worker funktioniert.", "default"];
    default:
      return [`Bastion: ${data.event}`, where, "default"];
  }
}

async function handleHeartbeat(request, env) {
  const data = await verified(request, env);
  if (data instanceof Response) return data;
  const previous = JSON.parse((await env.BASTION_KV.get("hb")) || "null");
  const record = { ...data, received: Date.now() };
  await env.BASTION_KV.put("hb", JSON.stringify(record));
  if (previous && previous.offline_alerted) {
    await notify(env, "✅ Home Assistant wieder erreichbar", `Alarmanlage: ${data.state}`);
  }
  return json({ ok: true });
}

async function handleAlert(request, env) {
  const data = await verified(request, env);
  if (data instanceof Response) return data;
  const [title, message, priority] = eventText(data);
  const channels = await notify(env, title, message, priority);
  return json({ ok: true, channels });
}

async function checkHeartbeat(env) {
  const record = JSON.parse((await env.BASTION_KV.get("hb")) || "null");
  if (!record) return;
  const minutes = Math.max(Number(env.OFFLINE_MINUTES || 10), Math.ceil((3 * (record.interval || 120)) / 60));
  const silentFor = (Date.now() - record.received) / 60000;
  const relevant = record.armed || env.ALERT_WHEN_DISARMED === "1";
  if (silentFor > minutes && relevant && !record.offline_alerted) {
    const mode = MODES[record.mode] || record.mode || "aus";
    await notify(
      env,
      "⚠️ Home Assistant nicht erreichbar",
      `Seit ${Math.round(silentFor)} Min. kein Lebenszeichen von ${record.instance || "Home Assistant"}. ` +
        `Alarmanlage war ${record.armed ? `scharf (${mode})` : "aus"}. Möglich: Stromausfall, Internetausfall oder Sabotage.`,
      "urgent",
    );
    record.offline_alerted = true;
    await env.BASTION_KV.put("hb", JSON.stringify(record));
  }
}

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (request.method !== "POST") return json({ error: "method not allowed" }, 405);
    if (pathname === "/probe") return handleProbe(request, env);
    if (pathname === "/heartbeat") return handleHeartbeat(request, env);
    if (pathname === "/alert") return handleAlert(request, env);
    return json({ error: "not found" }, 404);
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil(checkHeartbeat(env));
  },
};
