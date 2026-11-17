// Cloudflare Access: verifies the JWT Access adds to every request it lets through.
//
// The dashboard is only served when the request carries a valid token for this
// application (audience ACCESS_AUD, issuer https://ACCESS_TEAM_DOMAIN). That way
// the workers.dev address, which Access does not cover, cannot bypass the login.
// Defense in depth against a misconfigured Access policy: ALLOWED_EMAILS limits the
// identities, ACCESS_MAX_AGE_HOURS the age of the Access login (iat).

const keyCache = new Map(); // team -> { at, keys: Map(kid -> CryptoKey) }
const KEY_TTL = 3600 * 1000;

function b64urlBytes(s) {
  const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(s.length / 4) * 4, "="));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function b64urlJson(s) {
  return JSON.parse(new TextDecoder().decode(b64urlBytes(s)));
}

async function loadKeys(team, force = false) {
  const cached = keyCache.get(team);
  if (cached && !force && Date.now() - cached.at < KEY_TTL) return cached.keys;
  const r = await fetch(`https://${team}/cdn-cgi/access/certs`);
  if (!r.ok) throw new Error(`access certs ${r.status}`);
  const { keys = [] } = await r.json();
  const map = new Map();
  for (const jwk of keys) {
    if (jwk.kty !== "RSA") continue;
    const key = await crypto.subtle.importKey(
      "jwk",
      { kty: jwk.kty, n: jwk.n, e: jwk.e, alg: "RS256", ext: true },
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
      false,
      ["verify"],
    );
    map.set(jwk.kid, key);
  }
  keyCache.set(team, { at: Date.now(), keys: map });
  return map;
}

export function allowedEmails(env) {
  return String(env.ALLOWED_EMAILS || "").toLowerCase().split(/[\s,;]+/).filter((e) => e.includes("@"));
}

export function accessConfigured(env) {
  return Boolean(env.ACCESS_TEAM_DOMAIN && env.ACCESS_AUD);
}

// Returns { email } for a valid token, otherwise null.
export async function verifyAccess(request, env) {
  if (!accessConfigured(env)) return null;
  const token = request.headers.get("cf-access-jwt-assertion");
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  let header;
  let payload;
  try {
    header = b64urlJson(parts[0]);
    payload = b64urlJson(parts[1]);
  } catch {
    return null;
  }
  if (header.alg !== "RS256") return null;
  const team = String(env.ACCESS_TEAM_DOMAIN).replace(/^https?:\/\//, "").replace(/\/.*$/, "");
  const now = Date.now() / 1000;
  if (typeof payload.exp !== "number" || payload.exp < now) return null;
  if (payload.nbf && payload.nbf > now + 60) return null;
  const maxAge = (Number(env.ACCESS_MAX_AGE_HOURS) || 168) * 3600;
  if (typeof payload.iat === "number" && (payload.iat > now + 60 || now - payload.iat > maxAge)) return null;
  if (payload.iss !== `https://${team}`) return null;
  const audiences = Array.isArray(payload.aud) ? payload.aud : [payload.aud];
  if (!audiences.includes(env.ACCESS_AUD)) return null;
  let keys = await loadKeys(team);
  if (!keys.has(header.kid)) keys = await loadKeys(team, true);
  const key = keys.get(header.kid);
  if (!key) return null;
  const ok = await crypto.subtle.verify(
    "RSASSA-PKCS1-v1_5",
    key,
    b64urlBytes(parts[2]),
    new TextEncoder().encode(`${parts[0]}.${parts[1]}`),
  );
  if (!ok) return null;
  const email = String(payload.email || payload.common_name || "");
  const allowed = allowedEmails(env);
  if (allowed.length && !allowed.includes(email.toLowerCase())) return null;
  return { email };
}
