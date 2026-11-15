// D1 storage: alarm events, camera snapshots, Pushover receipts and small state.
//
// Home Assistant can only append (signed requests); nothing here deletes data
// except the retention cleanup of the cron job. An intruder who takes over the
// house cannot erase what already reached the worker.

const SCHEMA = [
  `CREATE TABLE IF NOT EXISTS events (
     id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, event TEXT NOT NULL,
     state TEXT, mode TEXT, incident TEXT, sensor TEXT, room TEXT, user TEXT, detail TEXT)`,
  `CREATE INDEX IF NOT EXISTS events_ts ON events(ts)`,
  `CREATE INDEX IF NOT EXISTS events_incident ON events(incident)`,
  `CREATE TABLE IF NOT EXISTS snapshots (
     id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, incident TEXT NOT NULL,
     camera TEXT, type TEXT, data TEXT NOT NULL)`,
  `CREATE INDEX IF NOT EXISTS snapshots_incident ON snapshots(incident)`,
  `CREATE INDEX IF NOT EXISTS snapshots_ts ON snapshots(ts)`,
  `CREATE TABLE IF NOT EXISTS receipts (
     receipt TEXT PRIMARY KEY, ts INTEGER NOT NULL, kind TEXT, incident TEXT, expires INTEGER,
     acked_at INTEGER, acked_by TEXT, cancelled INTEGER NOT NULL DEFAULT 0, ha_seen INTEGER NOT NULL DEFAULT 0)`,
  `CREATE TABLE IF NOT EXISTS state (k TEXT PRIMARY KEY, v TEXT NOT NULL)`,
];

const ready = new WeakMap();

export async function database(env) {
  if (!env.DB) throw new Error("D1 binding DB missing");
  if (!ready.has(env.DB)) {
    ready.set(
      env.DB,
      env.DB.batch(SCHEMA.map((sql) => env.DB.prepare(sql))).catch((err) => {
        ready.delete(env.DB);
        throw err;
      }),
    );
  }
  await ready.get(env.DB);
  return env.DB;
}

const nowS = () => Math.floor(Date.now() / 1000);
const str = (v, max = 120) => (v == null || v === "" ? null : String(v).slice(0, max));

// ------------------------------------------------------------------ state
export async function getState(env, key) {
  const db = await database(env);
  const row = await db.prepare("SELECT v FROM state WHERE k = ?").bind(key).first();
  return row ? JSON.parse(row.v) : null;
}

export async function setState(env, key, value) {
  const db = await database(env);
  await db
    .prepare("INSERT INTO state (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v")
    .bind(key, JSON.stringify(value))
    .run();
}

// ----------------------------------------------------------------- events
export async function addEvent(env, e) {
  const db = await database(env);
  const detail = e.detail && Object.keys(e.detail).length ? JSON.stringify(e.detail).slice(0, 2000) : null;
  await db
    .prepare(
      "INSERT INTO events (ts, event, state, mode, incident, sensor, room, user, detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
    )
    .bind(
      Math.floor(Number(e.ts) || nowS()),
      str(e.event, 40),
      str(e.state, 30),
      str(e.mode, 20),
      str(e.incident, 32),
      str(e.sensor),
      str(e.room),
      str(e.user),
      detail,
    )
    .run();
}

function parseEvent(row) {
  return { ...row, detail: row.detail ? JSON.parse(row.detail) : null };
}

export async function eventsSince(env, since, limit = 10000) {
  const db = await database(env);
  const { results } = await db
    .prepare("SELECT id, ts, event, state, mode, incident, sensor, room, user, detail FROM events WHERE ts >= ? ORDER BY ts, id LIMIT ?")
    .bind(since, limit)
    .all();
  return results.map(parseEvent);
}

export async function lastEventBefore(env, ts) {
  const db = await database(env);
  const row = await db
    .prepare("SELECT id, ts, event, state, mode, incident, sensor, room, user, detail FROM events WHERE ts < ? AND state IS NOT NULL ORDER BY ts DESC, id DESC LIMIT 1")
    .bind(ts)
    .first();
  return row ? parseEvent(row) : null;
}

export async function recentEvents(env, since, limit = 6) {
  const db = await database(env);
  const { results } = await db
    .prepare("SELECT id, ts, event, state, mode, incident, sensor, room, user, detail FROM events WHERE ts >= ? ORDER BY ts DESC, id DESC LIMIT ?")
    .bind(since, limit)
    .all();
  return results.map(parseEvent);
}

export async function incidentEvents(env, incident) {
  const db = await database(env);
  const { results } = await db
    .prepare("SELECT id, ts, event, state, mode, incident, sensor, room, user, detail FROM events WHERE incident = ? ORDER BY ts, id LIMIT 500")
    .bind(incident)
    .all();
  return results.map(parseEvent);
}

// -------------------------------------------------------------- snapshots
export async function addSnapshot(env, s) {
  const db = await database(env);
  const res = await db
    .prepare("INSERT INTO snapshots (ts, incident, camera, type, data) VALUES (?, ?, ?, ?, ?)")
    .bind(Math.floor(Number(s.ts) || nowS()), s.incident, str(s.camera), s.type, s.data)
    .run();
  return res.meta?.last_row_id ?? null;
}

export async function snapshotList(env, incident) {
  const db = await database(env);
  const { results } = await db
    .prepare("SELECT id, ts, camera, type FROM snapshots WHERE incident = ? ORDER BY ts, id LIMIT 200")
    .bind(incident)
    .all();
  return results;
}

export async function snapshotCounts(env, since) {
  const db = await database(env);
  const { results } = await db
    .prepare("SELECT incident, COUNT(*) AS n FROM snapshots WHERE ts >= ? GROUP BY incident")
    .bind(since)
    .all();
  return Object.fromEntries(results.map((r) => [r.incident, r.n]));
}

export async function getSnapshot(env, id) {
  const db = await database(env);
  return db.prepare("SELECT id, ts, incident, camera, type, data FROM snapshots WHERE id = ?").bind(id).first();
}

// --------------------------------------------------------------- receipts
export async function addReceipt(env, r) {
  const db = await database(env);
  await db
    .prepare("INSERT OR IGNORE INTO receipts (receipt, ts, kind, incident, expires) VALUES (?, ?, ?, ?, ?)")
    .bind(r.receipt, nowS(), r.kind, str(r.incident, 32), r.expires)
    .run();
}

export async function getReceipt(env, receipt) {
  const db = await database(env);
  return db.prepare("SELECT * FROM receipts WHERE receipt = ?").bind(receipt).first();
}

export async function openReceipts(env, kind = null, limit = 10) {
  const db = await database(env);
  const sql =
    "SELECT * FROM receipts WHERE acked_at IS NULL AND cancelled = 0 AND expires > ?" +
    (kind ? " AND kind = ?" : "") +
    " ORDER BY ts DESC LIMIT ?";
  const stmt = kind ? db.prepare(sql).bind(nowS(), kind, limit) : db.prepare(sql).bind(nowS(), limit);
  return (await stmt.all()).results;
}

export async function markAcked(env, receipt, at, by) {
  const db = await database(env);
  await db
    .prepare("UPDATE receipts SET acked_at = ?, acked_by = ? WHERE receipt = ? AND acked_at IS NULL")
    .bind(at, str(by, 60), receipt)
    .run();
}

export async function markCancelled(env, receipt) {
  const db = await database(env);
  await db.prepare("UPDATE receipts SET cancelled = 1 WHERE receipt = ?").bind(receipt).run();
}

export async function unseenAcks(env) {
  const db = await database(env);
  const { results } = await db
    .prepare("SELECT receipt, kind, incident, acked_at AS at, acked_by AS by FROM receipts WHERE acked_at IS NOT NULL AND ha_seen = 0 ORDER BY acked_at LIMIT 10")
    .all();
  return results;
}

export async function markSeen(env, receipts) {
  const db = await database(env);
  const stmt = db.prepare("UPDATE receipts SET ha_seen = 1 WHERE receipt = ?");
  await db.batch(receipts.map((r) => stmt.bind(String(r).slice(0, 40))));
}

export async function receiptsSince(env, since) {
  const db = await database(env);
  const { results } = await db
    .prepare("SELECT receipt, ts, kind, incident, acked_at, acked_by, cancelled FROM receipts WHERE ts >= ? ORDER BY ts LIMIT 2000")
    .bind(since)
    .all();
  return results;
}

// -------------------------------------------------------------- retention
export async function cleanup(env, { logDays = 365, snapshotDays = 30 } = {}) {
  const db = await database(env);
  const now = nowS();
  await db.batch([
    db.prepare("DELETE FROM events WHERE ts < ?").bind(now - logDays * 86400),
    db.prepare("DELETE FROM snapshots WHERE ts < ?").bind(now - snapshotDays * 86400),
    db.prepare("DELETE FROM receipts WHERE ts < ?").bind(now - 30 * 86400),
  ]);
}
