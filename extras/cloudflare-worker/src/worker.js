// Bastion external probe.
//
// Connects back to the public IP the request came from and reports which TCP
// ports accept connections. It never probes any other address, so it cannot
// be used to scan third parties.

import { connect } from "cloudflare:sockets";

const DEFAULT_PORTS = [
  21, 22, 23, 80, 139, 443, 445, 1880, 1883, 2375, 2376, 3000, 3389, 5000,
  5001, 5900, 6052, 8080, 8086, 8123, 8883, 9000, 9443,
];
const MAX_PORTS = 40;
const TIMEOUT_MS = 3000;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

function timingSafeEqual(a, b) {
  const enc = new TextEncoder();
  const x = enc.encode(a);
  const y = enc.encode(b);
  if (x.length !== y.length) return false;
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function probe(ip, port) {
  const started = Date.now();
  let socket;
  try {
    socket = connect({ hostname: ip, port });
    const open = await Promise.race([
      socket.opened.then(() => true),
      sleep(TIMEOUT_MS).then(() => false),
    ]);
    return { port, open, ms: Date.now() - started };
  } catch (err) {
    return { port, open: false, error: String(err).slice(0, 80) };
  } finally {
    try {
      if (socket) await socket.close();
    } catch {
      /* ignore */
    }
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/probe") return json({ error: "not found" }, 404);
    if (request.method !== "POST") return json({ error: "method not allowed" }, 405);

    if (env.PROBE_TOKEN) {
      const auth = request.headers.get("authorization") || "";
      if (!timingSafeEqual(auth, `Bearer ${env.PROBE_TOKEN}`)) {
        return json({ error: "unauthorized" }, 401);
      }
    }

    const ip = request.headers.get("cf-connecting-ip");
    if (!ip) return json({ error: "no client ip" }, 400);

    let ports = DEFAULT_PORTS;
    try {
      const body = await request.json();
      if (Array.isArray(body.ports) && body.ports.length) {
        ports = [...new Set(body.ports.map(Number))]
          .filter((p) => Number.isInteger(p) && p > 0 && p < 65536 && p !== 25)
          .slice(0, MAX_PORTS);
      }
    } catch {
      /* no body: defaults */
    }

    const results = await Promise.all(ports.map((port) => probe(ip, port)));
    return json({ ip, results, checked_at: new Date().toISOString() });
  },
};
