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
  // Login and security events reported by Home Assistant (deduplicated by uid).
  `CREATE TABLE IF NOT EXISTS secevents (
     uid TEXT PRIMARY KEY, ts INTEGER NOT NULL, type TEXT NOT NULL, ip TEXT, user TEXT, geo TEXT, detail TEXT)`,
  `CREATE INDEX IF NOT EXISTS secevents_ts ON secevents(ts)`,
  // Rejected requests against the worker itself, counted per 10 minutes.
  `CREATE TABLE IF NOT EXISTS attempts (
     bucket INTEGER NOT NULL, ip TEXT NOT NULL, kind TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0,
     country TEXT, path TEXT, PRIMARY KEY (bucket, ip, kind))`,
  `CREATE TABLE IF NOT EXISTS blocked (
     ip TEXT PRIMARY KEY, ts INTEGER NOT NULL, until INTEGER NOT NULL, reason TEXT, n INTEGER, country TEXT)`,
];

const ready = new WeakMap();

async function migrate(db) {
  await db.batch(SCHEMA.map((sql) => db.prepare(sql)));
  // v2: events.uid lets Home Assistant resend its log without duplicates.
  try {
    await db.prepare("ALTER TABLE events ADD COLUMN uid TEXT").run();
  } catch {
    /* column exists */
  }
  await db.prepare("CREATE UNIQUE INDEX IF NOT EXISTS events_uid ON events(uid)").run();
}

export async function database(env) {
  if (!env.DB) throw new Error("D1 binding DB missing");
  if (!ready.has(env.DB)) {
    ready.set(
      env.DB,
      migrate(env.DB).catch((err) => {
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
const UID = /^[a-f0-9]{16,64}$/;

function eventValues(e) {
  const detail = e.detail && typeof e.detail === "object" && Object.keys(e.detail).length ? JSON.stringify(e.detail).slice(0, 2000) : null;
  return [
    Math.floor(Number(e.ts) || nowS()),
    str(e.event, 40),
    str(e.state, 30),
    str(e.mode, 20),
    str(e.incident, 32),
    str(e.sensor),
    str(e.room),
    str(e.user),
    detail,
    typeof e.uid === "string" && UID.test(e.uid) ? e.uid : null,
  ];
}

export async function addEvent(env, e) {
  const db = await database(env);
  await db
    .prepare(
      "INSERT OR IGNORE INTO events (ts, event, state, mode, incident, sensor, room, user, detail, uid) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
    )
    .bind(...eventValues(e))
    .run();
}

// Log resent by Home Assistant: skip what is stored already, also rows from before uids existed.
export async function addEventsBackfill(env, events) {
  if (!events.length) return 0;
  const db = await database(env);
  const stmt = db.prepare(
    "INSERT INTO events (ts, event, state, mode, incident, sensor, room, user, detail, uid) " +
      "SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM events WHERE uid = ?) " +
      "AND NOT EXISTS (SELECT 1 FROM events WHERE uid IS NULL AND event = ? AND ts BETWEEN ? AND ?)",
  );
  const rows = events.map(eventValues).filter((v) => v[1] && v[9]);
  const results = await db.batch(rows.map((v) => stmt.bind(...v, v[9], v[1], v[0] - 5, v[0] + 5)));
  return results.reduce((n, r) => n + ((r.meta && r.meta.changes) || 0), 0);
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

// ------------------------------------------------------- security events
export async function addSecEvents(env, events) {
  if (!events.length) return 0;
  const db = await database(env);
  const stmt = db.prepare("INSERT OR IGNORE INTO secevents (uid, ts, type, ip, user, geo, detail) VALUES (?, ?, ?, ?, ?, ?, ?)");
  const results = await db.batch(
    events.map((e) =>
      stmt.bind(
        str(e.uid, 64),
        Math.floor(Number(e.ts) || nowS()),
        str(e.type, 40),
        str(e.ip, 64),
        str(e.user, 80),
        str(e.geo, 80),
        e.detail && typeof e.detail === "object" && Object.keys(e.detail).length ? JSON.stringify(e.detail).slice(0, 500) : null,
      ),
    ),
  );
  return results.reduce((n, r) => n + ((r.meta && r.meta.changes) || 0), 0);
}

export async function secEventsSince(env, since, limit = 5000) {
  const db = await database(env);
  const { results } = await db
    .prepare("SELECT ts, type, ip, user, geo, detail FROM secevents WHERE ts >= ? ORDER BY ts DESC LIMIT ?")
    .bind(since, limit)
    .all();
  return results.map((r) => ({ ...r, detail: r.detail ? JSON.parse(r.detail) : null }));
}

// ------------------------------------------------------ attack detection
export const BUCKET = 600;

export async function addAttempt(env, { ip, kind, country, path }) {
  const db = await database(env);
  const bucket = Math.floor(nowS() / BUCKET);
  await db
    .prepare(
      "INSERT INTO attempts (bucket, ip, kind, n, country, path) VALUES (?, ?, ?, 1, ?, ?) " +
        "ON CONFLICT(bucket, ip, kind) DO UPDATE SET n = n + 1, path = excluded.path",
    )
    .bind(bucket, str(ip, 64), str(kind, 30), str(country, 4), str(path, 120))
    .run();
}

// Attempts per IP within the last `buckets` buckets (current one included).
export async function recentAttempts(env, buckets = 2) {
  const db = await database(env);
  const since = Math.floor(nowS() / BUCKET) - (buckets - 1);
  const { results } = await db
    .prepare(
      "SELECT ip, MAX(country) AS country, SUM(n) AS n, GROUP_CONCAT(DISTINCT kind) AS kinds, MAX(path) AS path " +
        "FROM attempts WHERE bucket >= ? GROUP BY ip ORDER BY n DESC LIMIT 20",
    )
    .bind(since)
    .all();
  return results;
}

export async function attemptsSince(env, since) {
  const db = await database(env);
  const { results } = await db
    .prepare(
      "SELECT bucket * ? AS ts, ip, kind, n, country, path FROM attempts WHERE bucket >= ? ORDER BY bucket DESC LIMIT 3000",
    )
    .bind(BUCKET, Math.floor(since / BUCKET))
    .all();
  return results;
}

export async function blockedUntil(env, ip) {
  const db = await database(env);
  const row = await db.prepare("SELECT until FROM blocked WHERE ip = ?").bind(ip).first();
  return row && row.until > nowS() ? row.until : null;
}

export async function block(env, { ip, minutes, reason, n, country }) {
  const db = await database(env);
  const until = nowS() + minutes * 60;
  await db
    .prepare(
      "INSERT INTO blocked (ip, ts, until, reason, n, country) VALUES (?, ?, ?, ?, ?, ?) " +
        "ON CONFLICT(ip) DO UPDATE SET until = excluded.until, reason = excluded.reason, n = excluded.n",
    )
    .bind(str(ip, 64), nowS(), until, str(reason, 120), n, str(country, 4))
    .run();
  return until;
}

export async function unblock(env, ip) {
  const db = await database(env);
  await db.prepare("DELETE FROM blocked WHERE ip = ?").bind(ip).run();
}

export async function blockedList(env, since) {
  const db = await database(env);
  const { results } = await db
    .prepare("SELECT ip, ts, until, reason, n, country FROM blocked WHERE until > ? OR ts >= ? ORDER BY ts DESC LIMIT 200")
    .bind(nowS(), since)
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
    db.prepare("DELETE FROM secevents WHERE ts < ?").bind(now - logDays * 86400),
    db.prepare("DELETE FROM attempts WHERE bucket < ?").bind(Math.floor((now - 90 * 86400) / BUCKET)),
    db.prepare("DELETE FROM blocked WHERE until < ? AND ts < ?").bind(now, now - 90 * 86400),
  ]);
}
