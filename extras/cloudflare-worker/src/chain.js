// Tamper-evident event log: every event gets an HMAC over its content and the
// previous event's value (key derived from ALARM_SECRET, which D1 does not hold).
// Whoever changes or deletes a row in D1 breaks the chain from there on and cannot
// recompute it without the secret.
//
// Sealing runs with the heartbeat and the cron job, in id order. Verification runs
// in slices of 500 rows per minute and walks the whole log over and over; the
// result is in state "chain_check". Home Assistant echoes the newest sealed event
// it was told about; if that row is gone or different, the log was cut back.
// Retention deletes only from the oldest end and keeps the last deleted value as
// the new start ("chain_base").

import { notify } from "./notify.js";
import * as store from "./store.js";
import { hmacHex, nowS } from "./util.js";

const SLICE = 500;
const GENESIS = "bastion";
const FIELDS = ["id", "ts", "event", "state", "mode", "incident", "sensor", "room", "user", "detail", "uid"];

const key = (env) => `chain|${env.ALARM_SECRET}`;
const canonical = (row) => FIELDS.map((f) => (row[f] == null ? "" : String(row[f]))).join("\u001f");
const link = (env, prev, row) => hmacHex(key(env), `${prev}\u001e${canonical(row)}`);

async function base(env) {
  return (await store.getState(env, "chain_base")) || { id: 0, hash: GENESIS };
}

export async function seal(env) {
  if (!env.ALARM_SECRET) return 0;
  const rows = await store.unsealedEvents(env, SLICE);
  if (!rows.length) return 0;
  const last = await store.lastSealed(env);
  let prev = last && last.id < rows[0].id ? last.chain : (await base(env)).hash;
  const sealed = [];
  for (const row of rows) {
    prev = await link(env, prev, row);
    sealed.push({ id: row.id, chain: prev });
  }
  await store.sealEvents(env, sealed);
  const head = sealed[sealed.length - 1];
  await store.setState(env, "chain_head", { id: head.id, hash: head.chain });
  return sealed.length;
}

async function broken(env, check, id, what, source = "walk") {
  check.ok = false;
  check.pass_broken = true;
  if (check.broken && check.broken.id === id && check.broken.what === what) return;
  check.broken = { id, what, at: nowS(), source };
  await store.addEvent(env, { event: "tamper", detail: { id, what } });
  await notify(env, {
    title: "⚠️ Protokoll verändert",
    message: `Die Prüfkette des Ereignisprotokolls ist ab Eintrag ${id} gebrochen (${what}). Jemand hat Daten in der Datenbank geändert oder gelöscht.`,
    priority: "high",
  });
}

// One slice of the endless verification walk.
export async function verifySlice(env) {
  if (!env.ALARM_SECRET) return null;
  const check = (await store.getState(env, "chain_check")) || { ok: true, cursor: 0, prev: null, checked: 0, full: null, broken: null };
  const b = await base(env);
  if (check.cursor < b.id || check.prev == null) Object.assign(check, { cursor: b.id, prev: b.hash });
  const rows = (await store.eventsAfter(env, check.cursor, SLICE)).filter((r) => r.chain != null);
  let prev = check.prev;
  for (const row of rows) {
    const want = await link(env, prev, row);
    if (want !== row.chain) {
      await broken(env, check, row.id, "Eintrag geändert, eingefügt oder gelöscht");
      // Continue from the stored value so later breaks are found too.
    }
    prev = row.chain;
    check.cursor = row.id;
  }
  check.prev = prev;
  check.checked = (check.checked || 0) + rows.length;
  if (rows.length < SLICE) {
    // End of the log reached: one full pass done, start again from the base.
    const head = await store.getState(env, "chain_head");
    if (head && head.id > check.cursor) await broken(env, check, head.id, "neueste Einträge fehlen");
    check.full = nowS();
    // A cut-back log (reported by Home Assistant) stays visible for a week; the walk itself decides the rest.
    const echo = check.broken && check.broken.source === "echo" && nowS() - check.broken.at < 7 * 86400;
    check.ok = !check.pass_broken && !echo;
    Object.assign(check, { cursor: b.id, prev: b.hash, pass_broken: false });
  }
  check.at = nowS();
  await store.setState(env, "chain_check", check);
  return check;
}

// Home Assistant remembers the newest sealed event it was told about and sends it back.
export async function checkEcho(env, seen) {
  if (!seen || !Number.isInteger(seen.id) || typeof seen.hash !== "string") return;
  const b = await base(env);
  if (seen.id <= b.id) return;
  const row = await store.eventChain(env, seen.id);
  if (row && row.chain === seen.hash) return;
  const check = (await store.getState(env, "chain_check")) || { ok: true, cursor: b.id, prev: b.hash, checked: 0 };
  await broken(env, check, seen.id, row ? "Eintrag geändert" : "Einträge gelöscht", "echo");
  await store.setState(env, "chain_check", check);
}

// Retention: delete old events from the start, keep the chain anchored.
export async function prune(env, cutoff) {
  await seal(env);
  const last = await store.pruneEvents(env, cutoff);
  if (last) await store.setState(env, "chain_base", { id: last.id, hash: last.chain });
}

export async function status(env) {
  const check = await store.getState(env, "chain_check");
  const head = await store.getState(env, "chain_head");
  return {
    ok: check ? check.ok !== false : null,
    full: check ? check.full : null,
    checked: check ? check.checked : 0,
    broken: check ? check.broken : null,
    head: head ? { id: head.id, hash: head.hash.slice(0, 12) } : null,
  };
}

export async function head(env) {
  return store.getState(env, "chain_head");
}
