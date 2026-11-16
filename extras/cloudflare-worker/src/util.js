// Small helpers shared by the worker modules.

export const nowS = () => Math.floor(Date.now() / 1000);

export function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store", "x-content-type-options": "nosniff" },
  });
}

export function timingSafeEqual(a, b) {
  const enc = new TextEncoder();
  const x = enc.encode(String(a));
  const y = enc.encode(String(b));
  if (x.length !== y.length) return false;
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

const keys = new Map(); // secret -> CryptoKey (per isolate)

async function hmacKey(secret) {
  let key = keys.get(secret);
  if (!key) {
    key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
    if (keys.size > 20) keys.clear();
    keys.set(secret, key);
  }
  return key;
}

export async function hmacBytes(secret, message) {
  return new Uint8Array(await crypto.subtle.sign("HMAC", await hmacKey(secret), new TextEncoder().encode(message)));
}

export async function hmacHex(secret, message) {
  return [...(await hmacBytes(secret, message))].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(text) {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)));
  return [...digest].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function clientIp(request) {
  return request.headers.get("cf-connecting-ip") || "unknown";
}

export function geo(request) {
  const cf = request.cf || {};
  return { country: String(cf.country || "").slice(0, 4), city: String(cf.city || "").slice(0, 60) };
}

// Caps D1 writes per isolate so a flood cannot exhaust the daily write quota.
const writes = { minute: 0, n: 0 };

export function writeBudget() {
  const minute = Math.floor(Date.now() / 60000);
  if (writes.minute !== minute) Object.assign(writes, { minute, n: 0 });
  return ++writes.n <= 60;
}

// Runs a job after the response (or right away where waitUntil is missing, e.g. in tests).
export async function later(ctx, job, label) {
  const p = Promise.resolve()
    .then(job)
    .catch((err) => console.error(`bastion ${label}`, err && err.stack ? err.stack : err));
  if (ctx && typeof ctx.waitUntil === "function") ctx.waitUntil(p);
  else await p;
}

// Coarse device name from the user agent ("iPhone · Safari").
export function deviceLabel(agent) {
  const ua = String(agent || "");
  const os = /iPhone/.test(ua) ? "iPhone" : /iPad/.test(ua) ? "iPad" : /Android/.test(ua) ? "Android" : /Windows/.test(ua) ? "Windows"
    : /CrOS/.test(ua) ? "ChromeOS" : /Macintosh|Mac OS X/.test(ua) ? "Mac" : /Linux/.test(ua) ? "Linux" : "Gerät";
  const browser = /Edg(e|A|iOS)?\//.test(ua) ? "Edge" : /OPR\/|Opera/.test(ua) ? "Opera" : /SamsungBrowser/.test(ua) ? "Samsung Internet"
    : /Firefox\/|FxiOS/.test(ua) ? "Firefox" : /Chrome\/|CriOS/.test(ua) ? "Chrome" : /Safari\//.test(ua) ? "Safari" : "Browser";
  return `${os} · ${browser}`;
}
