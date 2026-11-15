// Worker tests: node --import ./test/register.mjs --test test/
// D1 is emulated with node:sqlite, outgoing fetches are recorded.
import assert from "node:assert/strict";
import { createHmac, webcrypto } from "node:crypto";
import { DatabaseSync } from "node:sqlite";
import { test } from "node:test";

const { default: worker, incidentToken } = await import("../src/worker.js");

class Stmt {
  constructor(db, sql, args = []) {
    this.db = db;
    this.sql = sql;
    this.args = args;
  }
  bind(...args) {
    return new Stmt(this.db, this.sql, args);
  }
  async first() {
    const row = this.db.prepare(this.sql).get(...this.args);
    return row ? { ...row } : null;
  }
  async all() {
    return { results: this.db.prepare(this.sql).all(...this.args).map((r) => ({ ...r })) };
  }
  async run() {
    const info = this.db.prepare(this.sql).run(...this.args);
    return { meta: { last_row_id: Number(info.lastInsertRowid), changes: info.changes } };
  }
}

function d1() {
  const db = new DatabaseSync(":memory:");
  return {
    prepare: (sql) => new Stmt(db, sql),
    batch: async (stmts) => {
      const out = [];
      for (const s of stmts) out.push(/^\s*SELECT/i.test(s.sql) ? await s.all() : await s.run());
      return out;
    },
  };
}

const SECRET = "topsecret";
const sent = [];
let receiptN = 0;
let ackDevice = "iphone";
let acked = 1;
let accessJwks = null;

globalThis.fetch = async (input, init = {}) => {
  const url = String(input);
  const body = init.body instanceof URLSearchParams ? init.body.toString() : String(init.body ?? "");
  sent.push({ url, body, headers: init.headers || {} });
  if (url.endsWith("/1/messages.json")) {
    const receipt = body.includes("priority=2") ? `r${String(++receiptN).padStart(29, "0")}` : undefined;
    return Response.json({ status: 1, request: "req", ...(receipt ? { receipt } : {}) });
  }
  if (url.includes("/1/receipts/") && url.includes("/cancel.json")) return Response.json({ status: 1 });
  if (url.includes("/1/receipts/")) {
    return Response.json({ status: 1, acknowledged: acked, acknowledged_at: Math.floor(Date.now() / 1000), acknowledged_by_device: ackDevice, expired: 0 });
  }
  if (url === "https://team.cloudflareaccess.com/cdn-cgi/access/certs") return Response.json(accessJwks);
  return new Response("ok", { status: 200 });
};

function makeEnv(extra = {}) {
  return {
    ALARM_SECRET: SECRET,
    NTFY_URL: "https://ntfy.example/topic",
    TELEGRAM_BOT_TOKEN: "x",
    TELEGRAM_CHAT_ID: "1",
    PUSHOVER_TOKEN: "app",
    PUSHOVER_USER: "usr",
    DB: d1(),
    ...extra,
  };
}

const signed = (path, payload, { secret = SECRET, ts = Math.floor(Date.now() / 1000) } = {}) => {
  const body = JSON.stringify(payload);
  const sig = createHmac("sha256", secret).update(`${ts}.${body}`).digest("hex");
  return new Request(`https://w.example${path}`, { method: "POST", body, headers: { "x-bastion-timestamp": String(ts), "x-bastion-signature": sig } });
};
const ctx = { waitUntil: (p) => p };
const cron = async (env) => {
  let job;
  await worker.scheduled({}, env, { waitUntil: (p) => { job = p; } });
  await job;
};
const decoded = (s) => decodeURIComponent(String(s.body).replace(/\+/g, " "));
const hbState = async (env) => JSON.parse((await env.DB.prepare("SELECT v FROM state WHERE k = 'hb'").first()).v);
const setHb = (env, hb) => env.DB.prepare("UPDATE state SET v = ? WHERE k = 'hb'").bind(JSON.stringify(hb)).run();
const events = async (env) => (await env.DB.prepare("SELECT * FROM events ORDER BY id").all()).results;

const HB = { state: "armed_away", mode: "away", armed: true, interval: 120, instance: "Zuhause", tz: "Europe/Berlin", started: 1000, boot: 500 };

test("signature, replay window and methods", async () => {
  const env = makeEnv();
  assert.equal((await worker.fetch(signed("/heartbeat", HB), env)).status, 200);
  assert.equal((await worker.fetch(signed("/heartbeat", HB, { secret: "nope" }), env)).status, 401);
  assert.equal((await worker.fetch(signed("/heartbeat", HB, { ts: 1000 }), env)).status, 401);
  assert.equal((await worker.fetch(new Request("https://w.example/heartbeat"), env)).status, 404);
  assert.equal((await worker.fetch(new Request("https://w.example/heartbeat", { method: "PUT" }), env)).status, 405);
  assert.equal((await worker.fetch(new Request("https://w.example/"), env)).status, 404, "no dashboard without Access");
});

test("alarm is logged, pushed as emergency with incident link and receipt", async () => {
  const env = makeEnv();
  sent.length = 0;
  await worker.fetch(signed("/heartbeat", HB), env);
  const r = await worker.fetch(signed("/alert", { event: "triggered", push: true, incident: "abcdef12", sensor: "Terrassentür", room: "Wohnzimmer", state: "triggered", mode: "away", armed: true }), env);
  const res = await r.json();
  assert.deepEqual(res.channels.sort(), ["ntfy", "pushover", "telegram"]);
  const token = await incidentToken(env, "abcdef12");
  assert.equal(res.view, `https://w.example/i/abcdef12?t=${token}`);
  const po = sent.find((x) => x.url.endsWith("/1/messages.json"));
  assert.ok(po.body.includes("priority=2") && po.body.includes("retry=60") && po.body.includes("sound=siren"));
  assert.ok(decoded(po).includes(`callback=https://w.example/pushover/`), "callback url for acknowledgements");
  assert.ok(decoded(po).includes(res.view), "incident link in the push");
  const ntfy = sent.find((x) => x.url.startsWith("https://ntfy.example"));
  assert.equal(ntfy.headers.Click, res.view);
  const rec = await env.DB.prepare("SELECT * FROM receipts").first();
  assert.equal(rec.kind, "alarm");
  assert.equal(rec.incident, "abcdef12");
  const ev = await events(env);
  assert.equal(ev.at(-1).event, "triggered");
  assert.equal(ev.at(-1).sensor, "Terrassentür");
  assert.equal((await hbState(env)).state, "triggered", "alert keeps the last known state fresh");
});

test("push flag controls notifications, events are always logged", async () => {
  const env = makeEnv();
  sent.length = 0;
  let res = await (await worker.fetch(signed("/alert", { event: "wrong_code", push: false, user: "Gast", state: "armed_away", mode: "away" }), env)).json();
  assert.deepEqual(res.channels, []);
  assert.equal(sent.length, 0);
  res = await (await worker.fetch(signed("/alert", { event: "armed", mode: "away", state: "armed_away" }), env)).json();
  assert.ok(res.channels.length > 0, "legacy clients without push flag still notify");
  assert.deepEqual((await events(env)).map((e) => e.event), ["wrong_code", "armed"]);
});

test("snapshots and incident page with token", async () => {
  const env = makeEnv();
  await worker.fetch(signed("/alert", { event: "pending", push: false, incident: "abcdef12", sensor: "Haustür", state: "pending", mode: "away" }), env);
  const img = Buffer.from("fake-jpeg").toString("base64");
  let r = await worker.fetch(signed("/snapshot", { incident: "abcdef12", camera: "Flur", type: "image/jpeg", data: img }), env);
  const { id } = await r.json();
  assert.ok(id > 0);
  assert.equal((await worker.fetch(signed("/snapshot", { incident: "../x", type: "image/jpeg", data: img }), env)).status, 400);
  assert.equal((await worker.fetch(signed("/snapshot", { incident: "abcdef12", type: "text/html", data: img }), env)).status, 400);

  const token = await incidentToken(env, "abcdef12");
  r = await worker.fetch(new Request(`https://w.example/i/abcdef12?t=${token}`), env);
  assert.equal(r.status, 200);
  const csp = r.headers.get("content-security-policy");
  const nonce = csp.match(/nonce-([a-f0-9]+)/)[1];
  assert.ok((await r.text()).includes(`<script nonce="${nonce}">`));
  assert.equal(r.headers.get("referrer-policy"), "no-referrer");

  r = await worker.fetch(new Request(`https://w.example/api/incident/abcdef12?t=${token}`), env);
  const data = await r.json();
  assert.equal(data.events[0].sensor, "Haustür");
  assert.equal(data.snapshots[0].camera, "Flur");
  assert.equal(data.snapshots[0].data, undefined, "list without image data");
  assert.equal((await worker.fetch(new Request("https://w.example/api/incident/abcdef12?t=wrong"), env)).status, 404);
  assert.equal((await worker.fetch(new Request(`https://w.example/api/incident/abcdef13?t=${token}`), env)).status, 404, "token is bound to the incident");

  r = await worker.fetch(new Request(`https://w.example/api/img/${id}?i=abcdef12&t=${token}`), env);
  assert.equal((await r.json()).data, img);
  assert.equal((await worker.fetch(new Request(`https://w.example/api/img/${id}?i=abcdef12&t=x`), env)).status, 404);
});

test("pushover acknowledgement reaches Home Assistant once", async () => {
  const env = makeEnv();
  await worker.fetch(signed("/heartbeat", HB), env);
  await worker.fetch(signed("/alert", { event: "triggered", push: true, incident: "abcdef12", sensor: "Haustür", state: "triggered", mode: "away" }), env);
  const rec = await env.DB.prepare("SELECT receipt FROM receipts").first();
  const po = sent.findLast((x) => x.url.endsWith("/1/messages.json") && x.body.includes("priority=2"));
  const cb = decoded(po).match(/callback=(\S+?)(&|$)/)[1];
  // forged token
  let r = await worker.fetch(new Request("https://w.example/pushover/forged", { method: "POST", body: new URLSearchParams({ receipt: rec.receipt }) }), env);
  assert.equal(r.status, 401);
  sent.length = 0;
  r = await worker.fetch(new Request(cb, { method: "POST", body: new URLSearchParams({ receipt: rec.receipt, acknowledged: "1" }) }), env);
  assert.equal(r.status, 200);
  assert.ok(sent.some((x) => x.url.includes(`/1/receipts/${rec.receipt}.json`)), "receipt confirmed with Pushover");
  assert.ok(sent.some((x) => decoded(x).includes("Quittiert von iphone")));
  let hb = await (await worker.fetch(signed("/heartbeat", HB), env)).json();
  assert.equal(hb.acks.length, 1);
  assert.equal(hb.acks[0].by, "iphone");
  assert.equal(hb.acks[0].incident, "abcdef12");
  hb = await (await worker.fetch(signed("/heartbeat", { ...HB, acks_seen: [rec.receipt] }), env)).json();
  assert.equal(hb.acks.length, 0, "seen acknowledgements are not repeated");
  assert.ok((await events(env)).some((e) => e.event === "acknowledged" && e.user === "iphone"));
});

test("disarm cancels the repeating emergency push", async () => {
  const env = makeEnv();
  await worker.fetch(signed("/alert", { event: "triggered", push: true, incident: "abcdef12", state: "triggered", mode: "away" }), env);
  const rec = await env.DB.prepare("SELECT receipt FROM receipts").first();
  sent.length = 0;
  await worker.fetch(signed("/alert", { event: "disarmed", push: true, incident: "abcdef12", user: "Yann", state: "disarmed" }), env);
  assert.ok(sent.some((x) => x.url.endsWith(`/1/receipts/${rec.receipt}/cancel.json`)));
  assert.equal((await env.DB.prepare("SELECT cancelled FROM receipts").first()).cancelled, 1);
});

test("offline report names the last known state and events", async () => {
  const env = makeEnv();
  acked = 0;
  await worker.fetch(signed("/heartbeat", { ...HB, open: ["Fenster Bad"], unavailable: [] }), env);
  await worker.fetch(signed("/alert", { event: "pending", push: false, incident: "abcdef12", sensor: "Haustür", room: "Flur", state: "pending", mode: "away", armed: true }), env);
  const hb = await hbState(env);
  hb.received = Date.now() - 15 * 60000;
  await setHb(env, hb);
  sent.length = 0;
  await cron(env);
  const po = sent.find((x) => x.url.endsWith("/1/messages.json"));
  const text = decoded(po);
  assert.ok(text.includes("Funkstille während Alarm"), text);
  assert.ok(text.includes("Sabotage wahrscheinlich"));
  assert.ok(text.includes("Vorwarnung – Haustür, Flur"));
  assert.ok(text.includes("Offen: Fenster Bad"));
  assert.ok(text.includes("priority=2"));
  assert.ok(text.includes("/i/abcdef12?t="), "link to the running incident");
  assert.equal((await env.DB.prepare("SELECT kind FROM receipts").first()).kind, "offline");
  sent.length = 0;
  await cron(env);
  assert.equal(sent.filter((x) => x.url.endsWith("/1/messages.json")).length, 0, "reported once");

  // back after a host reboot
  await worker.fetch(signed("/heartbeat", { ...HB, boot: 99999, started: 2000 }), env);
  const back = decoded(sent.find((x) => x.url.endsWith("/1/messages.json")));
  assert.ok(back.includes("wieder erreichbar") && back.includes("Rechner wurde neu gestartet"), back);
  assert.ok(sent.some((x) => x.url.includes("/cancel.json")), "open offline emergency is cancelled");
  const ev = await events(env);
  assert.deepEqual(ev.slice(-2).map((e) => e.event), ["offline", "online"]);
  assert.ok(JSON.parse(ev.at(-1).detail).minutes >= 15);
  acked = 1;
});

test("planned restart while disarmed is only logged", async () => {
  const env = makeEnv();
  await worker.fetch(signed("/heartbeat", { ...HB, state: "disarmed", mode: null, armed: false, stopping: true }), env);
  const hb = await hbState(env);
  hb.received = Date.now() - 30 * 60000;
  await setHb(env, hb);
  sent.length = 0;
  await cron(env);
  assert.equal(sent.length, 0);
  assert.equal((await events(env)).at(-1).event, "offline");
  await worker.fetch(signed("/heartbeat", { ...HB, state: "disarmed", armed: false, started: 3000 }), env);
  assert.equal(sent.length, 0, "no recovery push when nothing was pushed");
  assert.match(JSON.parse((await events(env)).at(-1).detail).cause, /geplant neu gestartet/);
});

async function accessSetup() {
  const keys = await webcrypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
    true,
    ["sign", "verify"],
  );
  const jwk = await webcrypto.subtle.exportKey("jwk", keys.publicKey);
  accessJwks = { keys: [{ ...jwk, kid: "k1", alg: "RS256" }] };
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
  return async (payload, kid = "k1") => {
    const head = `${b64({ alg: "RS256", kid })}.${b64(payload)}`;
    const sig = await webcrypto.subtle.sign("RSASSA-PKCS1-v1_5", keys.privateKey, new TextEncoder().encode(head));
    return `${head}.${Buffer.from(sig).toString("base64url")}`;
  };
}

test("dashboard only behind a valid Access token on the dashboard host", async () => {
  const jwt = await accessSetup();
  const env = makeEnv({ ACCESS_TEAM_DOMAIN: "team.cloudflareaccess.com", ACCESS_AUD: "aud123", DASHBOARD_HOST: "bastion.example.com" });
  await worker.fetch(signed("/heartbeat", HB), env);
  await worker.fetch(signed("/alert", { event: "armed", push: false, state: "armed_away", mode: "away" }), env);
  const exp = Math.floor(Date.now() / 1000) + 600;
  const good = await jwt({ aud: ["aud123"], iss: "https://team.cloudflareaccess.com", exp, email: "owner@example.com" });
  const get = (host, path, token) => worker.fetch(new Request(`https://${host}${path}`, { headers: token ? { "cf-access-jwt-assertion": token } : {} }), env);

  assert.equal((await get("bastion.example.com", "/", null)).status, 404);
  assert.equal((await get("w.example", "/", good)).status, 404, "workers.dev host never serves the dashboard");
  assert.equal((await get("bastion.example.com", "/", good)).status, 200);
  const sum = await (await get("bastion.example.com", "/api/summary?days=7", good)).json();
  assert.equal(sum.user, "owner@example.com");
  assert.equal(sum.hb.state, "armed_away");
  assert.equal(sum.events.at(-1).event, "armed");

  const wrongAud = await jwt({ aud: ["other"], iss: "https://team.cloudflareaccess.com", exp });
  const expired = await jwt({ aud: ["aud123"], iss: "https://team.cloudflareaccess.com", exp: 1000 });
  const wrongIss = await jwt({ aud: ["aud123"], iss: "https://evil.cloudflareaccess.com", exp });
  for (const t of [wrongAud, expired, wrongIss, `${good.slice(0, -4)}AAAA`, "garbage"]) {
    assert.equal((await get("bastion.example.com", "/api/summary", t)).status, 404);
  }
  // dashboard login also opens incident data without link token
  await worker.fetch(signed("/alert", { event: "pending", push: false, incident: "abcdef99", state: "pending", mode: "away" }), env);
  assert.equal((await get("bastion.example.com", "/api/incident/abcdef99", good)).status, 200);
  assert.equal((await get("bastion.example.com", "/api/incident/abcdef99", null)).status, 404);
});
