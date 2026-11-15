// Notification channels: Pushover, Telegram, ntfy, webhook.
//
// Pushover alarms use emergency priority: they repeat every minute until
// someone acknowledges them. The worker keeps the receipt, learns about the
// acknowledgement (callback or polling) and cancels open alarms on disarm.

const PUSHOVER = "https://api.pushover.net/1";
// Pushover priorities: 2 = emergency (repeats until acknowledged), 1 = high, 0 = normal.
const PUSHOVER_PRIORITY = { urgent: 2, high: 1, default: 0 };
export const EMERGENCY_EXPIRE = 1800;

export function pushoverEnabled(env) {
  return Boolean(env.PUSHOVER_TOKEN && env.PUSHOVER_USER);
}

// msg: { title, message, priority, url, urlTitle, callback }
// Returns { sent: [channel...], receipt }.
export async function notify(env, msg) {
  const { title, message = "", priority = "default", url, urlTitle, callback } = msg;
  const sent = [];
  let receipt = null;
  const tasks = [];
  if (pushoverEnabled(env)) {
    const level = PUSHOVER_PRIORITY[priority] ?? 0;
    const form = new URLSearchParams({
      token: env.PUSHOVER_TOKEN,
      user: env.PUSHOVER_USER,
      title: title.slice(0, 250),
      message: message.slice(0, 1024) || title,
      priority: String(level),
    });
    if (level === 2) {
      form.set("retry", "60");
      form.set("expire", String(EMERGENCY_EXPIRE));
      form.set("sound", env.PUSHOVER_SOUND || "siren");
      if (callback) form.set("callback", callback);
    }
    if (url) {
      form.set("url", url);
      form.set("url_title", (urlTitle || "Details").slice(0, 100));
    }
    if (env.PUSHOVER_DEVICE) form.set("device", env.PUSHOVER_DEVICE);
    tasks.push(
      fetch(`${PUSHOVER}/messages.json`, { method: "POST", body: form }).then(async (r) => {
        if (!r.ok) return;
        sent.push("pushover");
        try {
          const data = await r.json();
          if (data && data.receipt) receipt = String(data.receipt);
        } catch {
          /* no receipt */
        }
      }),
    );
  }
  const withLink = url ? `${message}\n\n${urlTitle || "Details"}: ${url}` : message;
  if (env.TELEGRAM_BOT_TOKEN && env.TELEGRAM_CHAT_ID) {
    tasks.push(
      fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text: `${title}\n${withLink}`, disable_web_page_preview: true }),
      }).then((r) => r.ok && sent.push("telegram")),
    );
  }
  if (env.NTFY_URL) {
    const headers = { Title: encodeURIComponent(title), Priority: priority === "urgent" ? "5" : priority === "high" ? "4" : "3", Tags: "rotating_light" };
    if (url) headers.Click = url;
    if (env.NTFY_TOKEN) headers.Authorization = `Bearer ${env.NTFY_TOKEN}`;
    tasks.push(fetch(env.NTFY_URL, { method: "POST", headers, body: message || title }).then((r) => r.ok && sent.push("ntfy")));
  }
  if (env.WEBHOOK_URL) {
    tasks.push(
      fetch(env.WEBHOOK_URL, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title, message, priority, url: url || null }),
      }).then((r) => r.ok && sent.push("webhook")),
    );
  }
  await Promise.allSettled(tasks);
  return { sent, receipt };
}

// Receipt status: { acknowledged, acknowledged_at, acknowledged_by_device, expired, ... } or null.
export async function pushoverReceipt(env, receipt) {
  if (!env.PUSHOVER_TOKEN) return null;
  const r = await fetch(`${PUSHOVER}/receipts/${encodeURIComponent(receipt)}.json?token=${encodeURIComponent(env.PUSHOVER_TOKEN)}`);
  if (!r.ok) return null;
  try {
    return await r.json();
  } catch {
    return null;
  }
}

// Stops the repeating emergency notification on every device.
export async function pushoverCancel(env, receipt) {
  if (!env.PUSHOVER_TOKEN) return false;
  const r = await fetch(`${PUSHOVER}/receipts/${encodeURIComponent(receipt)}/cancel.json`, {
    method: "POST",
    body: new URLSearchParams({ token: env.PUSHOVER_TOKEN }),
  });
  return r.ok;
}
