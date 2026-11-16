// Remote control from the dashboard: arm and disarm with a passkey.
//
// Three locks: Cloudflare Access (who), a passkey with user verification for
// every command (this device, this person) and Home Assistant's own settings
// (remote control on, disarm allowed). Passkeys can only be added with a
// one-time code shown in Home Assistant. Home Assistant fetches commands with a
// signed request, there is no way in from outside; every command carries the
// worker's signature and expires after 90 seconds.

import { notify } from "./notify.js";
import * as store from "./store.js";
import { deviceLabel, hmacHex, json, nowS, sha256Hex, timingSafeEqual } from "./util.js";
import { b64url, randomB64url, SUPPORTED_ALGS, verifyAssertion, verifyRegistration } from "./webauthn.js";

const MODES = { home: "Zuhause", night: "Nacht", away: "Abwesend" };
const COMMAND_TTL = 90;
const HOT_SECONDS = 120; // Home Assistant polls every 2 s while someone is about to send a command
const PAIRING_MAX = 900;
const PAIRING_TRIES = 5;

export function dashboardUrl(env) {
  return env.DASHBOARD_HOST ? `https://${env.DASHBOARD_HOST}` : null;
}

export function actionLabel(action, mode) {
  return action === "disarm" ? "Unscharf schalten" : `Scharf schalten (${MODES[mode] || mode})`;
}

export function commandSignature(env, c) {
  return hmacHex(env.ALARM_SECRET, `command.${c.id}.${c.action}.${c.mode || ""}.${c.force ? 1 : 0}.${c.ts}.${c.by || ""}`);
}

function remoteState(hb) {
  const r = (hb && hb.remote) || {};
  return { enabled: Boolean(r.enabled), disarm: Boolean(r.disarm) };
}

// Part of /api/summary.
export async function remoteSummary(env, user, hb) {
  const pairing = await store.getState(env, "pairing");
  return {
    ...remoteState(hb),
    passkeys: await store.passkeysFor(env, user.email),
    pairing: Boolean(pairing && pairing.expires > nowS()),
    commands: await store.commandsSince(env, nowS() - 7 * 86400, 10),
  };
}

const rp = (url) => ({ id: url.hostname, origin: url.origin });

// ------------------------------------------------------------ pairing
async function checkCode(env, code) {
  const pairing = await store.getState(env, "pairing");
  if (!pairing || pairing.expires < nowS()) return { error: "Kein Kopplungscode aktiv. In Home Assistant einen neuen Code erzeugen." };
  const digits = String(code || "").replace(/\D/g, "");
  if (digits.length === 8 && timingSafeEqual(await sha256Hex(digits), pairing.hash)) return { ok: true };
  pairing.tries = (pairing.tries || 0) + 1;
  if (pairing.tries >= PAIRING_TRIES) {
    await store.setState(env, "pairing", null);
    await notify(env, { title: "🔑 Kopplung abgebrochen", message: `${PAIRING_TRIES} falsche Kopplungscodes. Der Code ist ungültig; in Home Assistant einen neuen erzeugen.`, priority: "high" });
    return { error: "Zu viele falsche Codes. Der Kopplungscode ist jetzt ungültig.", attack: true };
  }
  await store.setState(env, "pairing", pairing);
  return { error: "Falscher Code.", attack: true };
}

export async function passkeyBegin(env, url, user, body) {
  const check = await checkCode(env, body.code);
  if (!check.ok) return { response: json({ error: check.error }, 403), attack: check.attack };
  const existing = await store.passkeysFor(env, user.email);
  const challenge = randomB64url(32);
  const id = randomB64url(12);
  await store.addChallenge(env, { id, challenge, email: user.email, purpose: "register", expires: nowS() + 300 });
  const handle = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(user.email))).slice(0, 16);
  return {
    response: json({
      challengeId: id,
      publicKey: {
        challenge,
        rp: { id: rp(url).id, name: "Bastion" },
        user: { id: b64url(handle), name: user.email, displayName: user.email },
        pubKeyCredParams: SUPPORTED_ALGS.map((alg) => ({ type: "public-key", alg })),
        timeout: 120000,
        attestation: "none",
        authenticatorSelection: { residentKey: "preferred", userVerification: "required" },
        excludeCredentials: existing.map((p) => ({ type: "public-key", id: p.id })),
      },
    }),
  };
}

export async function passkeyFinish(env, url, user, body, agent) {
  const ch = await store.takeChallenge(env, body.challengeId);
  if (!ch || ch.purpose !== "register" || ch.email !== user.email) return { response: json({ error: "Die Anfrage ist abgelaufen. Bitte erneut versuchen." }, 400) };
  const pairing = await store.getState(env, "pairing");
  if (!pairing || pairing.expires < nowS()) return { response: json({ error: "Der Kopplungscode ist abgelaufen." }, 403) };
  let key;
  try {
    key = await verifyRegistration(body.credential, { challenge: ch.challenge, origin: rp(url).origin, rpId: rp(url).id });
  } catch (err) {
    return { response: json({ error: `Passkey ungültig: ${err.message}` }, 403), attack: true };
  }
  if (await store.getPasskey(env, key.id)) return { response: json({ error: "Dieser Passkey ist schon gekoppelt." }, 409) };
  const name = deviceLabel(agent);
  await store.addPasskey(env, { ...key, email: user.email, name });
  await store.setState(env, "pairing", null);
  await store.addEvent(env, { event: "passkey_added", user: user.email, detail: { name } });
  await store.addNotice(env, "passkey_added", { email: user.email, name });
  await notify(env, { title: "🔑 Neuer Passkey für die Fernsteuerung", message: `${name} (${user.email}) kann die Alarmanlage jetzt aus dem Dashboard schalten.`, priority: "high" });
  return { response: json({ ok: true, name }) };
}

// ------------------------------------------------------------ commands
function parseCommand(body) {
  const action = body.action === "disarm" ? "disarm" : body.action === "arm" ? "arm" : null;
  if (!action) return null;
  const mode = action === "arm" ? (MODES[body.mode] ? body.mode : null) : null;
  if (action === "arm" && !mode) return null;
  return { action, mode, force: action === "arm" && body.force === true };
}

export async function commandBegin(env, url, user, body) {
  const cmd = parseCommand(body);
  if (!cmd) return { response: json({ error: "Unbekannter Befehl." }, 400) };
  const hb = await store.getState(env, "hb");
  const remote = remoteState(hb);
  if (!remote.enabled) return { response: json({ error: "Die Fernsteuerung ist in Home Assistant ausgeschaltet." }, 403) };
  if (cmd.action === "disarm" && !remote.disarm) return { response: json({ error: "Unscharf schalten aus der Ferne ist in Home Assistant nicht erlaubt." }, 403) };
  if (!hb || hb.offline) return { response: json({ error: "Home Assistant ist nicht erreichbar." }, 409) };
  const keys = await store.passkeysFor(env, user.email);
  if (!keys.length) return { response: json({ error: "Für dieses Konto ist kein Passkey gekoppelt." }, 403) };
  const challenge = randomB64url(32);
  const id = randomB64url(12);
  await store.addChallenge(env, { id, challenge, email: user.email, purpose: "command", data: cmd, expires: nowS() + 120 });
  await store.setState(env, "remote_hot", nowS() + HOT_SECONDS);
  return {
    response: json({
      challengeId: id,
      label: actionLabel(cmd.action, cmd.mode),
      publicKey: {
        challenge,
        rpId: rp(url).id,
        allowCredentials: keys.map((p) => ({ type: "public-key", id: p.id })),
        userVerification: "required",
        timeout: 60000,
      },
    }),
  };
}

export async function commandFinish(env, url, user, body) {
  const ch = await store.takeChallenge(env, body.challengeId);
  if (!ch || ch.purpose !== "command" || ch.email !== user.email) return { response: json({ error: "Die Anfrage ist abgelaufen. Bitte erneut versuchen." }, 400) };
  const credential = body.credential;
  const passkey = credential && typeof credential.id === "string" ? await store.getPasskey(env, credential.id.slice(0, 400)) : null;
  if (!passkey || passkey.email !== user.email) return { response: json({ error: "Unbekannter Passkey." }, 403), attack: true };
  let counter;
  try {
    ({ counter } = await verifyAssertion(credential, passkey, { challenge: ch.challenge, origin: rp(url).origin, rpId: rp(url).id }));
  } catch (err) {
    return { response: json({ error: `Passkey-Prüfung fehlgeschlagen: ${err.message}` }, 403), attack: true };
  }
  await store.usePasskey(env, passkey.id, counter);
  const hex = [...crypto.getRandomValues(new Uint8Array(8))].map((b) => b.toString(16).padStart(2, "0")).join("");
  const command = { id: hex, ts: nowS(), ...ch.data, by: user.email, passkey: passkey.name, expires: nowS() + COMMAND_TTL };
  await store.addCommand(env, command);
  await store.setState(env, "remote_hot", nowS() + HOT_SECONDS);
  return { response: json({ ok: true, id: command.id, label: actionLabel(command.action, command.mode) }) };
}

export async function commandStatus(env, id) {
  const c = await store.getCommand(env, id);
  if (!c) return json({ error: "not found" }, 404);
  if (["pending", "delivered"].includes(c.status) && c.expires < nowS()) c.status = "expired";
  return json({ id: c.id, status: c.status, result: c.result, action: c.action, mode: c.mode, label: actionLabel(c.action, c.mode) });
}

// ------------------------------------------------- Home Assistant side
// POST /commands (signed): results of executed commands in, pending commands out.
export async function haCommands(env, data) {
  for (const d of (Array.isArray(data.done) ? data.done : []).slice(0, 10)) {
    if (!d || typeof d.id !== "string") continue;
    const result = { error: d.error ? String(d.error).slice(0, 60) : null, detail: Array.isArray(d.detail) ? d.detail.slice(0, 20).map((x) => String(x).slice(0, 60)) : d.detail ? String(d.detail).slice(0, 200) : null };
    await store.finishCommand(env, d.id, d.ok ? "done" : "failed", result);
  }
  const open = await store.openCommands(env);
  const fresh = open.filter((c) => c.status === "pending").map((c) => c.id);
  if (fresh.length) await store.markDelivered(env, fresh);
  const commands = [];
  for (const c of open) {
    const cmd = { id: c.id, ts: c.ts, action: c.action, mode: c.mode, force: Boolean(c.force), by: c.by || "" };
    commands.push({ ...cmd, sig: await commandSignature(env, cmd) });
  }
  const hot = (await store.getState(env, "remote_hot")) || 0;
  return json({ ok: true, commands, fast: hot > nowS() });
}

// POST /remote (signed): pairing code, passkey list and revocation, managed in Home Assistant.
export async function haRemote(env, data) {
  if (data.op === "pair") {
    if (typeof data.code_hash !== "string" || !/^[a-f0-9]{64}$/.test(data.code_hash)) return json({ error: "invalid" }, 400);
    const expires = Math.min(Number(data.expires) || 0, nowS() + PAIRING_MAX);
    await store.setState(env, "pairing", { hash: data.code_hash, expires, tries: 0 });
  } else if (data.op === "unpair") {
    await store.setState(env, "pairing", null);
  } else if (data.op === "revoke") {
    const id = typeof data.id === "string" ? data.id.slice(0, 400) : null;
    const before = id ? await store.getPasskey(env, id) : null;
    const removed = await store.deletePasskeys(env, data.all === true ? null : id || "-");
    if (removed) {
      const what = before ? `${before.name} (${before.email})` : `${removed} Passkeys`;
      await store.addEvent(env, { event: "passkey_removed", user: before ? before.email : null, detail: { name: what } });
      await notify(env, { title: "🔑 Passkey entfernt", message: `${what} kann die Alarmanlage nicht mehr fernsteuern.` });
    }
  } else if (data.op !== "list") {
    return json({ error: "unknown op" }, 400);
  }
  const pairing = await store.getState(env, "pairing");
  return json({
    ok: true,
    dashboard: dashboardUrl(env),
    pairing: pairing && pairing.expires > nowS() ? { expires: pairing.expires } : null,
    passkeys: await store.allPasskeys(env),
    commands: await store.commandsSince(env, nowS() - 30 * 86400, 20),
  });
}
