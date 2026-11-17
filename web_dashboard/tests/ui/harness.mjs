// Throwaway-browser harness: copies the dashboard UI (without src/app/api, proxy.ts or any .env) into a
// temp Next app, drives headless Chrome over CDP and answers every /api/* call from the test itself.
// Nothing here can reach Supabase/Discord: the app has no API routes and no credentials.
import { spawn } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..", "..");
const CHROME = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";

const freePort = () => new Promise((resolve) => {
  const server = net.createServer().listen(0, "127.0.0.1", () => {
    const { port } = server.address();
    server.close(() => resolve(port));
  });
});

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export function deferred() {
  let resolve;
  const promise = new Promise((r) => { resolve = r; });
  return { promise, resolve };
}

function waitForOutput(child, pattern, ms, label) {
  return new Promise((resolve, reject) => {
    let seen = "";
    const timer = setTimeout(() => reject(new Error(`${label} not ready:\n${seen}`)), ms);
    const onData = (chunk) => {
      seen += chunk;
      const match = seen.match(pattern);
      if (match) { clearTimeout(timer); resolve(match); }
    };
    child.stdout?.on("data", onData);
    child.stderr?.on("data", onData);
    child.once("exit", () => { clearTimeout(timer); reject(new Error(`${label} exited:\n${seen}`)); });
  });
}

export async function startApp() {
  const dir = fs.mkdtempSync(path.join(root, "tests", ".ui-app-"));
  fs.cpSync(path.join(root, "src"), path.join(dir, "src"), {
    recursive: true,
    filter: (source) => !source.endsWith(path.join("app", "api")) && !source.endsWith("proxy.ts"),
  });
  for (const file of ["tsconfig.json", "postcss.config.mjs", "package.json"]) {
    fs.copyFileSync(path.join(root, file), path.join(dir, file));
  }
  fs.writeFileSync(path.join(dir, "next.config.mjs"), `export default { turbopack: { root: ${JSON.stringify(root)} } };\n`);
  const port = await freePort();
  const server = spawn(process.execPath, [path.join(root, "node_modules/next/dist/bin/next"), "dev", "-p", String(port)], {
    cwd: dir,
    env: { PATH: process.env.PATH, HOME: process.env.HOME, NEXT_TELEMETRY_DISABLED: "1" },
    stdio: ["ignore", "pipe", "pipe"],
    detached: true, // own process group so stop() also kills next's worker processes (they would keep the pipes open)
  });
  const stop = async () => {
    try { process.kill(-server.pid, "SIGKILL"); } catch { /* already gone */ }
    server.stdout.destroy();
    server.stderr.destroy();
    fs.rmSync(dir, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
  };
  const origin = `http://localhost:${port}`;
  try {
    await waitForOutput(server, /Ready in/, 120000, "next dev");
    const warm = await fetch(`${origin}/dashboard`);
    if (!warm.ok) throw new Error(`warm-up /dashboard -> ${warm.status}`);
  } catch (error) {
    await stop();
    throw error;
  }
  return { origin, stop };
}

export async function startBrowser(origin) {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "ui-chrome-"));
  const chrome = spawn(CHROME, [
    "--headless=new", "--remote-debugging-port=0", `--user-data-dir=${profile}`,
    "--no-first-run", "--no-default-browser-check", "--disable-gpu", "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });
  const [, wsBase] = await waitForOutput(chrome, /DevTools listening on (ws:\/\/[^\s]+)/, 30000, "chrome");
  const httpBase = wsBase.replace(/^ws:/, "http:").replace(/\/devtools\/browser.*$/, "");
  const target = await (await fetch(`${httpBase}/json/new?about:blank`, { method: "PUT" })).json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });

  let nextId = 1;
  const pending = new Map();
  let router = async () => ({ status: 500, json: { error: "unrouted" } });
  const requests = [];
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });

  ws.onmessage = async ({ data }) => {
    const message = JSON.parse(data);
    if (message.id) {
      const entry = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) entry.reject(new Error(JSON.stringify(message.error)));
      else entry.resolve(message.result);
      return;
    }
    if (message.method !== "Fetch.requestPaused") return;
    const { requestId, request } = message.params;
    const entry = { method: request.method, path: new URL(request.url).pathname, body: request.postData ?? null, seq: requests.length };
    requests.push(entry);
    const { status = 200, json = {} } = await router(entry);
    await send("Fetch.fulfillRequest", {
      requestId,
      responseCode: status,
      responseHeaders: [{ name: "content-type", value: "application/json" }],
      body: Buffer.from(JSON.stringify(json)).toString("base64"),
    }).catch(() => undefined);
  };

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Emulation.setFocusEmulationEnabled", { enabled: true });
  await send("Fetch.enable", { patterns: [{ urlPattern: `${origin}/api/*` }] });

  const evaluate = async (expression) => {
    const { result, exceptionDetails } = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (exceptionDetails) throw new Error(exceptionDetails.exception?.description || exceptionDetails.text);
    return result.value;
  };
  const waitFor = async (expression, label, ms = 20000) => {
    const end = Date.now() + ms;
    while (Date.now() < end) {
      if (await evaluate(expression).catch(() => false)) return;
      await sleep(50);
    }
    throw new Error(`timeout waiting for ${label}\nrequests: ${JSON.stringify(requests.map((r) => `${r.method} ${r.path}`))}`);
  };

  return {
    requests,
    sleep,
    evaluate,
    waitFor,
    route: (fn) => { router = fn; },
    goto: async (url) => { await send("Page.navigate", { url }); },
    clickText: (selector, text) => evaluate(`(() => {
      const el = [...document.querySelectorAll(${JSON.stringify(selector)})].find((e) => e.textContent.includes(${JSON.stringify(text)}));
      if (!el) throw new Error("no ${selector} with text " + ${JSON.stringify(text)});
      el.click(); return true; })()`),
    // Types like a user: React-visible input event, then blur (the page saves on blur).
    typeAndBlur: (selector, value) => evaluate(`(() => {
      const el = document.querySelector(${JSON.stringify(selector)});
      el.focus();
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(el, ${JSON.stringify(value)});
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.blur(); return true; })()`),
    async screenshot(file) {
      const { data } = await send("Page.captureScreenshot", { format: "png" });
      fs.writeFileSync(file, Buffer.from(data, "base64"));
    },
    async close() {
      ws.close();
      const exited = new Promise((resolve) => chrome.once("exit", resolve));
      chrome.kill("SIGKILL");
      await exited;
      fs.rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
    },
  };
}
