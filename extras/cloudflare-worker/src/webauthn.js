// Passkeys (WebAuthn) without dependencies: CBOR, COSE keys, signature checks.
//
// Registration accepts any attestation format but does not trust it (the
// dashboard asks for "none"); what counts is that the credential was created
// for this origin with user verification. Supported keys: ES256, RS256, EdDSA.

const enc = new TextEncoder();
const dec = new TextDecoder();

export function b64url(bytes) {
  const b = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let bin = "";
  for (let i = 0; i < b.length; i++) bin += String.fromCharCode(b[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function fromB64url(s) {
  if (typeof s !== "string" || !/^[A-Za-z0-9_-]*={0,2}$/.test(s)) throw new Error("invalid base64url");
  const t = s.replace(/=+$/, "").replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(t + "===".slice((t.length + 3) % 4));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export function randomB64url(n = 32) {
  return b64url(crypto.getRandomValues(new Uint8Array(n)));
}

async function sha256(bytes) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
}

function equal(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

// ------------------------------------------------------------------ CBOR
// Decodes one item; returns { value, end }. Maps become Map (integer keys in COSE).
export function cborDecode(bytes, start = 0, depth = 0) {
  if (depth > 16) throw new Error("cbor too deep");
  let pos = start;
  const need = (n) => {
    if (pos + n > bytes.length) throw new Error("cbor truncated");
  };
  need(1);
  const first = bytes[pos++];
  const major = first >> 5;
  const info = first & 31;
  let len = info;
  if (info === 24) { need(1); len = bytes[pos]; pos += 1; }
  else if (info === 25) { need(2); len = (bytes[pos] << 8) | bytes[pos + 1]; pos += 2; }
  else if (info === 26) { need(4); len = ((bytes[pos] << 24) >>> 0) + (bytes[pos + 1] << 16) + (bytes[pos + 2] << 8) + bytes[pos + 3]; pos += 4; }
  else if (info === 27) {
    need(8);
    let v = 0;
    for (let i = 0; i < 8; i++) v = v * 256 + bytes[pos + i];
    len = v;
    pos += 8;
  } else if (info > 27) throw new Error("cbor indefinite length not supported");
  switch (major) {
    case 0:
      return { value: len, end: pos };
    case 1:
      return { value: -1 - len, end: pos };
    case 2:
      need(len);
      return { value: bytes.slice(pos, pos + len), end: pos + len };
    case 3:
      need(len);
      return { value: dec.decode(bytes.slice(pos, pos + len)), end: pos + len };
    case 4: {
      const arr = [];
      for (let i = 0; i < len; i++) {
        const item = cborDecode(bytes, pos, depth + 1);
        arr.push(item.value);
        pos = item.end;
      }
      return { value: arr, end: pos };
    }
    case 5: {
      const map = new Map();
      for (let i = 0; i < len; i++) {
        const k = cborDecode(bytes, pos, depth + 1);
        const v = cborDecode(bytes, k.end, depth + 1);
        map.set(k.value, v.value);
        pos = v.end;
      }
      return { value: map, end: pos };
    }
    case 7:
      if (info === 20) return { value: false, end: pos };
      if (info === 21) return { value: true, end: pos };
      if (info === 22 || info === 23) return { value: null, end: pos };
      throw new Error("cbor float not supported");
    default:
      throw new Error("cbor tag not supported");
  }
}

// ----------------------------------------------------------- COSE keys
const ALGS = {
  [-7]: { import: { name: "ECDSA", namedCurve: "P-256" }, verify: { name: "ECDSA", hash: "SHA-256" }, der: true },
  [-257]: { import: { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, verify: { name: "RSASSA-PKCS1-v1_5" } },
  [-8]: { import: { name: "Ed25519" }, verify: { name: "Ed25519" } },
};
export const SUPPORTED_ALGS = [-7, -8, -257];

function coseToJwk(cose) {
  const kty = cose.get(1);
  const alg = cose.get(3);
  if (kty === 2 && alg === -7 && cose.get(-1) === 1) {
    return { alg, jwk: { kty: "EC", crv: "P-256", x: b64url(cose.get(-2)), y: b64url(cose.get(-3)), ext: true } };
  }
  if (kty === 3 && alg === -257) {
    return { alg, jwk: { kty: "RSA", n: b64url(cose.get(-1)), e: b64url(cose.get(-2)), alg: "RS256", ext: true } };
  }
  if (kty === 1 && alg === -8 && cose.get(-1) === 6) {
    return { alg, jwk: { kty: "OKP", crv: "Ed25519", x: b64url(cose.get(-2)), ext: true } };
  }
  throw new Error("unsupported key type");
}

// ECDSA signatures in WebAuthn are DER; WebCrypto wants r||s.
function derToRaw(der) {
  if (der[0] !== 0x30) throw new Error("invalid signature");
  let pos = 2;
  if (der[1] & 0x80) pos = 2 + (der[1] & 0x7f);
  const part = () => {
    if (der[pos] !== 0x02) throw new Error("invalid signature");
    const len = der[pos + 1];
    let v = der.slice(pos + 2, pos + 2 + len);
    pos += 2 + len;
    while (v.length > 32 && v[0] === 0) v = v.slice(1);
    if (v.length > 32) throw new Error("invalid signature");
    const out = new Uint8Array(32);
    out.set(v, 32 - v.length);
    return out;
  };
  const r = part();
  const s = part();
  const raw = new Uint8Array(64);
  raw.set(r, 0);
  raw.set(s, 32);
  return raw;
}

// ----------------------------------------------------------- auth data
const FLAG_UP = 0x01;
const FLAG_UV = 0x04;
const FLAG_AT = 0x40;

function parseAuthData(data) {
  if (data.length < 37) throw new Error("auth data too short");
  const out = {
    rpIdHash: data.slice(0, 32),
    flags: data[32],
    counter: ((data[33] << 24) >>> 0) + (data[34] << 16) + (data[35] << 8) + data[36],
  };
  if (out.flags & FLAG_AT) {
    if (data.length < 55) throw new Error("auth data too short");
    const idLen = (data[53] << 8) | data[54];
    out.credentialId = data.slice(55, 55 + idLen);
    if (out.credentialId.length !== idLen) throw new Error("auth data truncated");
    out.cose = cborDecode(data, 55 + idLen).value;
  }
  return out;
}

function clientData(raw, type, challenge, origin) {
  let data;
  try {
    data = JSON.parse(dec.decode(raw));
  } catch {
    throw new Error("invalid client data");
  }
  if (data.type !== type) throw new Error("wrong ceremony");
  if (typeof data.challenge !== "string" || !equal(enc.encode(data.challenge), enc.encode(challenge))) throw new Error("wrong challenge");
  if (data.origin !== origin) throw new Error("wrong origin");
  if (data.crossOrigin === true) throw new Error("cross origin");
  return data;
}

async function checkAuthData(auth, rpId) {
  if (!equal(auth.rpIdHash, await sha256(enc.encode(rpId)))) throw new Error("wrong rp id");
  if (!(auth.flags & FLAG_UP)) throw new Error("user not present");
  if (!(auth.flags & FLAG_UV)) throw new Error("user not verified");
}

function credentialField(credential, name) {
  const v = credential && credential.response && credential.response[name];
  if (typeof v !== "string" || v.length > 16384) throw new Error(`missing ${name}`);
  return fromB64url(v);
}

// Returns { id, alg, key, counter } of a new passkey.
export async function verifyRegistration(credential, { challenge, origin, rpId }) {
  if (!credential || credential.type !== "public-key" || typeof credential.id !== "string") throw new Error("invalid credential");
  clientData(credentialField(credential, "clientDataJSON"), "webauthn.create", challenge, origin);
  const att = cborDecode(credentialField(credential, "attestationObject")).value;
  if (!(att instanceof Map) || !(att.get("authData") instanceof Uint8Array)) throw new Error("invalid attestation");
  const auth = parseAuthData(att.get("authData"));
  await checkAuthData(auth, rpId);
  if (!auth.credentialId || !(auth.cose instanceof Map)) throw new Error("no credential data");
  const id = b64url(auth.credentialId);
  if (id !== credential.id) throw new Error("credential id mismatch");
  const { alg, jwk } = coseToJwk(auth.cose);
  // Import once to reject malformed keys right away.
  await crypto.subtle.importKey("jwk", jwk, ALGS[alg].import, true, ["verify"]);
  return { id, alg, key: JSON.stringify(jwk), counter: auth.counter };
}

// passkey: { alg, key, counter }; returns { counter } on success, throws otherwise.
export async function verifyAssertion(credential, passkey, { challenge, origin, rpId }) {
  if (!credential || credential.type !== "public-key") throw new Error("invalid credential");
  const raw = credentialField(credential, "clientDataJSON");
  clientData(raw, "webauthn.get", challenge, origin);
  const authData = credentialField(credential, "authenticatorData");
  const auth = parseAuthData(authData);
  await checkAuthData(auth, rpId);
  const spec = ALGS[passkey.alg];
  if (!spec) throw new Error("unsupported algorithm");
  const key = await crypto.subtle.importKey("jwk", JSON.parse(passkey.key), spec.import, false, ["verify"]);
  let sig = credentialField(credential, "signature");
  if (spec.der) sig = derToRaw(sig);
  const signed = new Uint8Array(authData.length + 32);
  signed.set(authData, 0);
  signed.set(await sha256(raw), authData.length);
  if (!(await crypto.subtle.verify(spec.verify, key, sig, signed))) throw new Error("invalid signature");
  // A counter that does not grow points to a cloned authenticator (0 = not supported).
  if ((auth.counter || passkey.counter) && auth.counter <= passkey.counter) throw new Error("counter replay");
  return { counter: auth.counter };
}
