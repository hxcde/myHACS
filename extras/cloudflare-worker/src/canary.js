// Worker decoys: a token that looks like a Home Assistant long-lived access token
// and a webhook URL. Both are derived from ALARM_SECRET, so Bastion can write them
// into its decoy file and the worker recognises them without storing anything.
//
//   token    JWT  {"alg":"HS256","typ":"JWT"}.{"iss":<id>,"iat":..,"exp":..}
//            signed with HMAC(key = hex(HMAC(ALARM_SECRET, "canary-token")))
//   webhook  /api/webhook/<id 32 hex><hex(HMAC(ALARM_SECRET, "canary-webhook.<id>"))[:32]>
//
// Nobody uses them legitimately: any use means the place they were planted in
// (git backup, password manager, notes) is in someone else's hands.

import { notify } from "./notify.js";
import * as store from "./store.js";
import { clientIp, geo, hmacBytes, hmacHex, later, nowS, timingSafeEqual, writeBudget } from "./util.js";
import { b64url } from "./webauthn.js";

const JWT = /^[A-Za-z0-9_-]{10,200}\.[A-Za-z0-9_-]{10,400}\.[A-Za-z0-9_-]{20,100}$/;
const ALERT_EVERY = 900; // seconds per IP
const KIND = { token: "den Köder-Token", webhook: "die Köder-Webhook-URL" };

function bearer(request, url) {
  const m = (request.headers.get("authorization") || "").match(/^Bearer\s+(\S+)$/i);
  return m ? m[1] : url.searchParams.get("access_token");
}

export async function detectCanary(request, env, url) {
  if (!env.ALARM_SECRET) return null;
  const token = bearer(request, url);
  if (token && JWT.test(token)) {
    const [header, payload, sig] = token.split(".");
    const key = await hmacHex(env.ALARM_SECRET, "canary-token");
    if (timingSafeEqual(sig, b64url(await hmacBytes(key, `${header}.${payload}`)))) return "token";
  }
  const m = url.pathname.match(/^\/api\/webhook\/([a-f0-9]{32})([a-f0-9]{32})$/);
  if (m && timingSafeEqual(m[2], (await hmacHex(env.ALARM_SECRET, `canary-webhook.${m[1]}`)).slice(0, 32))) return "webhook";
  return null;
}

// Answers like Home Assistant would, logs the use and alerts.
export async function canaryResponse(request, env, ctx, url, kind) {
  const ip = clientIp(request);
  const { country, city } = geo(request);
  const agent = (request.headers.get("user-agent") || "").slice(0, 200);
  const path = url.pathname.replace(/^(\/api\/webhook\/[a-f0-9]{8})[a-f0-9]+$/, "$1…").slice(0, 200);
  await later(ctx, async () => {
    if (!env.DB || !writeBudget()) return;
    await store.addCanaryHit(env, { kind, ip, country, agent, method: request.method, path });
    await store.addEvent(env, { event: "canary", detail: { kind, ip, country, path } });
    await store.addNotice(env, "canary", { kind, ip, country, agent: agent.slice(0, 120), path });
    const alerts = (await store.getState(env, "canary_alert")) || {};
    if (nowS() - (alerts[ip] || 0) < ALERT_EVERY) return;
    alerts[ip] = nowS();
    for (const [k, v] of Object.entries(alerts)) if (nowS() - v > 86400) delete alerts[k];
    await store.setState(env, "canary_alert", alerts);
    await notify(env, {
      title: "🐦 Köder benutzt – Zugangsdaten in fremden Händen",
      message:
        `Jemand hat ${KIND[kind]} aus der Bastion-Köderdatei benutzt.\n` +
        `Von: ${ip}${country ? ` (${[city, country].filter(Boolean).join(", ")})` : ""}\n` +
        `Anfrage: ${request.method} ${path}\nGerät: ${agent || "–"}\n\n` +
        "Diese Zugangsdaten nutzt niemand legitim. Der Ort, an dem sie lagen (Git-Backup, Passwortmanager, Notizen), gilt als kompromittiert.",
      priority: "high",
    });
  }, "canary");
  if (kind === "webhook") return new Response("", { status: 200 });
  return new Response("401: Unauthorized", { status: 401, headers: { "content-type": "text/plain; charset=utf-8" } });
}
