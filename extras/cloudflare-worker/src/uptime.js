// Availability of Home Assistant from the worker's point of view.
//
// Every gap in the heartbeat becomes an outage row: detected by the cron job
// (offline), a restart between two heartbeats, or a short network gap. The kind
// says what happened, as far as the heartbeat tells:
//   planned  Home Assistant announced its shutdown (restart, update)
//   reboot   the host restarted (boot time changed): power cut or host restart
//   restart  Home Assistant restarted without notice (crash, manual restart)
//   network  Home Assistant kept running: internet or network was down
//   open     still down (no heartbeat yet)

import * as store from "./store.js";
import { nowS } from "./util.js";

export const CAUSES = {
  planned: "Home Assistant wurde geplant neu gestartet.",
  reboot: "Der Rechner wurde neu gestartet – vermutlich Stromausfall oder Neustart des Hosts.",
  restart: "Home Assistant wurde neu gestartet (Absturz oder Neustart).",
  network: "Home Assistant lief durch – Internet oder Netzwerk war unterbrochen.",
};

export function restarted(prev, cur) {
  return Boolean((prev.started && cur.started && prev.started !== cur.started) || (prev.boot && cur.boot && Math.abs(cur.boot - prev.boot) > 300));
}

export function classify(prev, cur) {
  if (prev.boot && cur.boot && Math.abs(cur.boot - prev.boot) > 300) return "reboot";
  if (prev.started && cur.started && prev.started !== cur.started) return prev.stopping ? "planned" : "restart";
  return "network";
}

export function recoveryCause(prev, cur) {
  return CAUSES[classify(prev, cur)];
}

// Heartbeats missing for longer than this (without restart) count as a network gap.
const gapLimit = (interval) => Math.max(300, 2.5 * (interval || 120));

// Called for every heartbeat before the new record is stored.
export async function onHeartbeat(env, prev, cur) {
  if (!prev) return null;
  const now = nowS();
  const start = Math.floor(prev.received / 1000);
  const kind = classify(prev, cur);
  if (prev.offline) {
    if (prev.outage_id) await store.endOutage(env, prev.outage_id, { end: now, kind, cause: CAUSES[kind] });
    else await store.addOutage(env, { start, end: now, kind, cause: CAUSES[kind], armed: prev.armed, notified: prev.offline_notified });
    return kind;
  }
  if (restarted(prev, cur) || now - start > gapLimit(prev.interval)) {
    await store.addOutage(env, { start, end: now, kind, cause: CAUSES[kind], armed: prev.armed });
    return kind;
  }
  return null;
}

// Called by the cron job when the heartbeat stops; returns the outage id.
export function onOffline(env, record, notified) {
  return store.addOutage(env, {
    start: Math.floor(record.received / 1000),
    end: null,
    kind: record.stopping ? "planned" : "open",
    armed: record.armed,
    notified,
  });
}

const KIND_FROM_TEXT = [
  [/Rechner/, "reboot"],
  [/geplant/, "planned"],
  [/neu gestartet/, "restart"],
];

// Outages from before this table existed, taken from the event log (runs once).
export async function ensureHistory(env) {
  if (await store.getState(env, "uptime_since")) return;
  const events = await store.eventsSince(env, 0, 10000);
  const own = events.filter((e) => ["offline", "online", "restart", "attack", "exposure"].includes(e.event));
  const hb = await store.getState(env, "hb");
  const first = Math.min(nowS(), ...own.map((e) => e.ts), hb ? Math.floor(hb.received / 1000) : nowS());
  const { n } = await store.outageTotal(env);
  if (!n) {
    for (const e of events) {
      if (e.event !== "online" && e.event !== "restart") continue;
      const cause = (e.detail && e.detail.cause) || "";
      const kind = (KIND_FROM_TEXT.find(([re]) => re.test(cause)) || [null, "network"])[1];
      const minutes = (e.detail && Number(e.detail.minutes)) || 0;
      await store.addOutage(env, { start: e.ts - minutes * 60, end: e.ts, kind: e.event === "restart" && kind === "network" ? "restart" : kind, cause });
    }
    if (hb && hb.offline && !hb.outage_id) {
      hb.outage_id = await onOffline(env, hb, hb.offline_notified);
      await store.setState(env, "hb", hb);
    }
  }
  await store.setState(env, "uptime_since", first);
}
