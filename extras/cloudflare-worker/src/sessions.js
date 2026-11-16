// Dashboard access log: who opened the dashboard, from where and with which device.
//
// One row per device (e-mail + browser/OS) and IP while it is in use; 30 minutes
// without a request start a new session. A new device or a new country for an
// account is pushed (ACCESS_ALERT: "new" = default, "all" = every session, "off").

import { notify } from "./notify.js";
import * as store from "./store.js";
import { clientIp, deviceLabel, geo, later, nowS, sha256Hex, writeBudget } from "./util.js";

const SESSION_GAP = 1800;
const TOUCH_EVERY = 300;

export async function trackAccess(request, env, ctx, user) {
  if (!env.DB || !user || !user.email) return;
  await later(ctx, async () => {
    const email = user.email;
    const ip = clientIp(request);
    const { country, city } = geo(request);
    const agent = request.headers.get("user-agent") || "";
    const label = deviceLabel(agent);
    const device = (await sha256Hex(`${email}|${label}`)).slice(0, 24);
    const last = await store.lastSession(env, device, ip);
    const now = nowS();
    if (last && now - last.last < SESSION_GAP) {
      if (now - last.last >= TOUCH_EVERY && writeBudget()) await store.touchSession(env, last.id);
      return;
    }
    if (!writeBudget()) return;
    const seen = await store.known(env, { device, email, country });
    const newDevice = !seen.device;
    const newCountry = Boolean(country) && seen.email && !seen.country;
    await store.addSession(env, { device, email, label, ip, country, city, agent, newDevice, newCountry });
    if (newDevice || newCountry) {
      await store.addNotice(env, "dashboard_access", { email, ip, country, city, device: label, new_device: newDevice, new_country: newCountry });
    }
    const mode = env.ACCESS_ALERT || "new";
    if (mode === "off" || (mode !== "all" && !newDevice && !newCountry)) return;
    const title = newDevice ? "🔐 Dashboard: neues Gerät" : newCountry ? "🔐 Dashboard: Zugriff aus neuem Land" : "🔐 Dashboard geöffnet";
    await notify(env, {
      title,
      message:
        `${email}\n${label}\n${ip}${country ? ` (${[city, country].filter(Boolean).join(", ")})` : ""}\n\n` +
        "Warst du das nicht: in Cloudflare Zero Trust die Sitzung widerrufen und die Anmeldung absichern.",
      priority: newDevice || newCountry ? "high" : "default",
    });
  }, "access log");
}
