// Test loader: stubs cloudflare:sockets and loads .html files as text modules (like wrangler's Text rule).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export async function resolve(specifier, context, next) {
  if (specifier === "cloudflare:sockets") {
    return { url: "data:text/javascript,export const connect = () => { throw new Error('no sockets'); };", shortCircuit: true };
  }
  return next(specifier, context);
}

export async function load(url, context, next) {
  if (url.endsWith(".html")) {
    return { format: "module", source: `export default ${JSON.stringify(readFileSync(fileURLToPath(url), "utf8"))};`, shortCircuit: true };
  }
  return next(url, context);
}
