// Passkey login for the dashboard, on top of Cloudflare Access (LOGIN=passkey).
//
// Access says who may reach the page; the passkey proves it is this person on one
// of their devices. Without a valid login only the login page is served, every
// API answers 401. The session cookie (__Host-, HttpOnly, Secure) holds a random
// token; the worker stores only its SHA-256 and binds it to the Access e-mail and
// the device. Sessions end after LOGIN_IDLE_MINUTES without the page open (default
// 30) and at the latest after LOGIN_MAX_HOURS (default 12).
//
// Wall tablet: a logged-in device creates a one-time code; the tablet enters it
// and gets a long session (TABLET_DAYS, default 90) that may only look, never
// switch. Failed logins are counted per account and IP: after LOGIN_FAILS (5) in
// 15 minutes the login is locked for 15 minutes and a push goes out.

import { notify } from "./notify.js";
import * as store from "./store.js";
import { clientIp, deviceLabel, geo, json, nowS, sha256Hex, timingSafeEqual, writeBudget } from "./util.js";
import { randomB64url, verifyAssertion } from "./webauthn.js";

export const COOKIE = "__Host-bastion";
const FAIL_WINDOW = 900;
const LOCK_SECONDS = 900;
const TABLET_CODE_TTL = 600;
const TABLET_TRIES = 5;
const TOUCH_EVERY = 60;

export const loginEnabled = (env) => String(env.LOGIN || "").toLowerCase() === "passkey";
const idleSeconds = (env) => Math.max(5, Number(env.LOGIN_IDLE_MINUTES) || 30) * 60;
const maxSeconds = (env) => Math.max(1, Number(env.LOGIN_MAX_HOURS) || 12) * 3600;
const tabletSeconds = (env) => Math.max(1, Number(env.TABLET_DAYS) || 90) * 86400;
const failLimit = (env) => Math.max(3, Number(env.LOGIN_FAILS) || 5);
const rp = (url) => ({ id: url.hostname, origin: url.origin });

function readCookie(request, name) {
  for (const part of (request.headers.get("cookie") || "").split(";")) {
    const i = part.indexOf("=");
    if (i > 0 && part.slice(0, i).trim() === name) return part.slice(i + 1).trim();
  }
  return null;
}

export function sessionCookie(token, maxAge) {
  return `${COOKIE}=${token}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=${Math.max(0, Math.floor(maxAge))}`;
}

const clearCookie = () => `${COOKIE}=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0`;

function withCookie(response, cookie) {
  const r = new Response(response.body, response);
  r.headers.append("set-cookie", cookie);
  return r;
}

// Public reference of a session (never the token or its full hash).
const ref = (id) => id.slice(0, 16);

// The valid login of this request, or null.
export async function currentLogin(request, env, user) {
  const token = readCookie(request, COOKIE);
  if (!token || !/^[A-Za-z0-9_-]{32,64}$/.test(token) || !user) return null;
  const row = await store.getLogin(env, await sha256Hex(token));
  if (!row || row.revoked || row.email !== user.email) return null;
  const now = nowS();
  if (row.expires < now) return null;
  if (row.kind !== "tablet" && now - row.last > idleSeconds(env)) return null;
  if (row.label !== deviceLabel(request.headers.get("user-agent"))) return null;
  if (now - row.last >= TOUCH_EVERY && writeBudget()) await store.touchLogin(env, row.id, now);
  return { ...row, ref: ref(row.id) };
}

// Creates a session and returns the Set-Cookie value.
export async function createLogin(env, request, user, { kind = "passkey", passkey = null } = {}) {
  const token = randomB64url(32);
  const now = nowS();
  const label = deviceLabel(request.headers.get("user-agent"));
  const { country, city } = geo(request);
  const ttl = kind === "tablet" ? tabletSeconds(env) : maxSeconds(env);
  const login = { id: await sha256Hex(token), email: user.email, kind, passkey, label, ip: clientIp(request), country, city, created: now, expires: now + ttl };
  const history = await store.loginHistory(env, user.email, now - 180 * 86400);
  await store.addLogin(env, login);
  await store.addEvent(env, { event: "login", user: user.email, detail: { name: label, kind } });
  await alertLogin(env, login, history);
  return sessionCookie(token, ttl);
}

const netOf = (ip) => (ip.includes(":") ? ip.split(":").slice(0, 3).join(":") : ip.split(".").slice(0, 3).join("."));

// Push for a login from a new device, network, city or country (LOGIN_ALERT: new | all | off).
async function alertLogin(env, login, history) {
  const mode = String(env.LOGIN_ALERT || "new").toLowerCase();
  if (mode === "off") return;
  const reasons = [];
  if (!history.some((h) => h.label === login.label)) reasons.push("neues Gerät");
  if (login.country && !history.some((h) => h.country === login.country)) reasons.push("neues Land");
  else if (login.city && !history.some((h) => h.city === login.city)) reasons.push("neuer Ort");
  if (!history.some((h) => h.ip && netOf(h.ip) === netOf(login.ip))) reasons.push("neues Netz");
  if (mode !== "all" && !reasons.length) return;
  const place = [login.city, login.country].filter(Boolean).join(", ");
  const what = login.kind === "tablet" ? "Wandtablet angemeldet" : "Anmeldung am Dashboard";
  await notify(env, {
    title: `🔐 ${what}${reasons.length ? ` · ${reasons[0]}` : ""}`,
    message: `${login.email}\n${login.label}\n${login.ip}${place ? ` (${place})` : ""}${reasons.length ? `\n\n${reasons.join(", ")}` : ""}\n\n` +
      "Warst du das nicht: im Dashboard unter Sicherheit alle Sitzungen beenden und in Cloudflare Zero Trust die Sitzung widerrufen.",
    priority: reasons.includes("neues Gerät") || reasons.includes("neues Land") ? "high" : "default",
  });
}

// --------------------------------------------------------------- lockout
async function lockState(env, email, ip) {
  const since = nowS() - FAIL_WINDOW;
  const fails = await store.loginFails(env, since, email, ip);
  const limit = failLimit(env);
  const own = fails.filter((f) => f.email === email);
  const fromIp = fails.filter((f) => f.ip === ip);
  const hit = own.length >= limit ? own : fromIp.length >= limit ? fromIp : null;
  if (!hit) return null;
  const until = Math.max(...hit.map((f) => f.ts)) + LOCK_SECONDS;
  return until > nowS() ? until : null;
}

async function failed(env, request, user, reason) {
  const ip = clientIp(request);
  await store.addLoginFail(env, { email: user.email, ip, reason });
  const until = await lockState(env, user.email, ip);
  if (until) {
    const { country, city } = geo(request);
    await store.addEvent(env, { event: "login_locked", user: user.email, detail: { ip, country, until } });
    await notify(env, {
      title: "🔒 Dashboard-Anmeldung gesperrt",
      message: `${failLimit(env)} fehlgeschlagene Passkey-Anmeldungen für ${user.email}.\n${ip}${country ? ` (${[city, country].filter(Boolean).join(", ")})` : ""}\nGesperrt für ${LOCK_SECONDS / 60} Minuten.`,
      priority: "high",
    });
  }
  return until;
}

const lockedResponse = (until) => json({ error: "Zu viele Fehlversuche. Die Anmeldung ist vorübergehend gesperrt.", locked: until }, 429);

// ----------------------------------------------------------------- login
// GET /api/login/state: what the login page shows (Access identity only).
export async function loginState(env, request, user, session) {
  return json({
    email: user.email,
    login: Boolean(session),
    passkeys: (await store.passkeysFor(env, user.email)).length,
    locked: await lockState(env, user.email, clientIp(request)),
  });
}

export async function loginBegin(env, url, user, request) {
  const until = await lockState(env, user.email, clientIp(request));
  if (until) return { response: lockedResponse(until) };
  const keys = await store.passkeysFor(env, user.email);
  if (!keys.length) return { response: json({ error: "Für dieses Konto ist noch kein Passkey gekoppelt.", pair: true }, 409) };
  const challenge = randomB64url(32);
  const id = randomB64url(12);
  await store.addChallenge(env, { id, challenge, email: user.email, purpose: "login", expires: nowS() + 120 });
  return {
    response: json({
      challengeId: id,
      publicKey: { challenge, rpId: rp(url).id, allowCredentials: keys.map((p) => ({ type: "public-key", id: p.id })), userVerification: "required", timeout: 60000 },
    }),
  };
}

export async function loginFinish(env, url, user, body, request) {
  const until = await lockState(env, user.email, clientIp(request));
  if (until) return { response: lockedResponse(until) };
  const ch = await store.takeChallenge(env, body.challengeId);
  if (!ch || ch.purpose !== "login" || ch.email !== user.email) return { response: json({ error: "Die Anfrage ist abgelaufen. Bitte erneut versuchen." }, 400) };
  const credential = body.credential;
  const passkey = credential && typeof credential.id === "string" ? await store.getPasskey(env, credential.id.slice(0, 400)) : null;
  if (!passkey || passkey.email !== user.email) {
    const locked = await failed(env, request, user, "unknown passkey");
    return { response: locked ? lockedResponse(locked) : json({ error: "Unbekannter Passkey." }, 403), attack: true };
  }
  let counter;
  try {
    ({ counter } = await verifyAssertion(credential, passkey, { challenge: ch.challenge, origin: rp(url).origin, rpId: rp(url).id }));
  } catch (err) {
    const locked = await failed(env, request, user, String(err.message).slice(0, 60));
    return { response: locked ? lockedResponse(locked) : json({ error: `Passkey-Prüfung fehlgeschlagen: ${err.message}` }, 403), attack: true };
  }
  await store.usePasskey(env, passkey.id, counter);
  const cookie = await createLogin(env, request, user, { kind: "passkey", passkey: passkey.name });
  return { response: withCookie(json({ ok: true }), cookie) };
}

export async function logout(env, request, login) {
  if (login) await store.revokeLogins(env, { id: login.id });
  return { response: withCookie(json({ ok: true }), clearCookie()) };
}

// End one session (by reference) or all others of this account.
export async function revoke(env, user, login, body) {
  let n = 0;
  if (body.all === true) n = await store.revokeLogins(env, { email: user.email, except: login.id });
  else if (typeof body.ref === "string" && /^[a-f0-9]{16}$/.test(body.ref)) n = await store.revokeLogins(env, { email: user.email, prefix: body.ref });
  if (n) await store.addEvent(env, { event: "logout", user: user.email, detail: { name: body.all ? "alle anderen Sitzungen" : "eine Sitzung", count: n } });
  return { response: json({ ok: true, revoked: n }) };
}

export async function loginList(env, user, login) {
  const rows = await store.activeLogins(env, user.email, nowS());
  const idle = idleSeconds(env);
  return rows
    .filter((r) => r.kind === "tablet" || nowS() - r.last <= idle)
    .map((r) => ({ ref: ref(r.id), kind: r.kind, label: r.label, passkey: r.passkey, ip: r.ip, country: r.country, city: r.city, created: r.created, last: r.last, expires: r.expires, current: r.id === login.id }));
}

// ------------------------------------------------------------ wall tablet
export async function tabletCode(env, user) {
  const digits = [...crypto.getRandomValues(new Uint32Array(8))].map((n) => n % 10).join("");
  await store.setState(env, "tablet_pairing", { hash: await sha256Hex(digits), email: user.email, expires: nowS() + TABLET_CODE_TTL, tries: 0 });
  return { response: json({ code: digits, expires: nowS() + TABLET_CODE_TTL }) };
}

export async function tabletFinish(env, user, body, request) {
  const until = await lockState(env, user.email, clientIp(request));
  if (until) return { response: lockedResponse(until) };
  const pairing = await store.getState(env, "tablet_pairing");
  if (!pairing || pairing.expires < nowS() || pairing.email !== user.email) {
    return { response: json({ error: "Kein Tablet-Code aktiv. Auf einem angemeldeten Gerät unter Sicherheit einen Code erzeugen." }, 403) };
  }
  const digits = String(body.code || "").replace(/\D/g, "");
  if (digits.length !== 8 || !timingSafeEqual(await sha256Hex(digits), pairing.hash)) {
    pairing.tries = (pairing.tries || 0) + 1;
    await store.setState(env, "tablet_pairing", pairing.tries >= TABLET_TRIES ? null : pairing);
    const locked = await failed(env, request, user, "tablet code");
    return { response: locked ? lockedResponse(locked) : json({ error: pairing.tries >= TABLET_TRIES ? "Zu viele falsche Codes, der Code ist ungültig." : "Falscher Code." }, 403), attack: true };
  }
  await store.setState(env, "tablet_pairing", null);
  const cookie = await createLogin(env, request, user, { kind: "tablet" });
  return { response: withCookie(json({ ok: true }), cookie) };
}

export { withCookie };
