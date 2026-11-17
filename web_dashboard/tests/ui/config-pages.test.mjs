// Real-browser regression tests for the AI / CoreBank pages. Run: node --test tests/ui/config-pages.test.mjs
import assert from "node:assert/strict";
import { after, before, beforeEach, test } from "node:test";
import { deferred, startApp, startBrowser } from "./harness.mjs";
import os from "node:os";

let app;
let browser;
const getsOf = (path) => browser.requests.filter((r) => r.method === "GET" && r.path === path);
const shot = (name) => `${process.env.UI_SHOT_DIR || os.tmpdir()}/dashboard-${name}.png`;
const patchesOf = (path) => browser.requests.filter((r) => r.method === "PATCH" && r.path === path);
const bodyText = () => browser.evaluate("document.body.innerText");
const nav = (name) => browser.clickText("aside button", name);

const common = (req) => {
  if (req.path === "/api/auth/session") return { json: { user: { name: "Tester", id: "1" }, expires: "2999-01-01T00:00:00.000Z" } };
  if (req.path === "/api/discord-data") return { json: { channels: [], roles: [] } };
  if (req.path === "/api/overview") return { json: { modules: [] } };
  if (req.path === "/api/config") return { json: {} };
  if (req.path.startsWith("/api/auth/")) return { json: {} };
  return null;
};
const aiConfig = (model) => ({ model, intercept_channels: [], autowiki_channels: [], library_channel_ids: [], vision_channels: [] });
const coreConfig = (autoReact) => ({ core_channel_id: "", bank_channel_id: "", token_configured: false, auto_react: autoReact, emoji_map: {} });
const modelInput = "input[type=text]";

before(async () => {
  app = await startApp();
  browser = await startBrowser(app.origin);
}, { timeout: 180000 });

after(async () => {
  await browser?.close();
  await app?.stop();
});

beforeEach(async () => {
  browser.requests.length = 0;
  browser.route(async (req) => common(req) ?? { status: 500, json: { error: "unrouted" } });
  await browser.goto("about:blank");
});

async function openDashboard() {
  await browser.goto(`${app.origin}/dashboard`);
  await browser.waitFor(`[...document.querySelectorAll("aside button")].some((b) => b.textContent.includes("AI Assistant"))`, "sidebar");
}

// React dev StrictMode mounts effects twice, so a mount may issue 2 GETs; only ordering vs the save matters.
function assertGetsOnlyAfterSave(events) {
  const start = events.indexOf("patch-start");
  const done = events.indexOf("patch-done");
  assert.ok(start >= 0 && done > start, `save ran: ${events}`);
  assert.ok(!events.slice(start, done).includes("get"), `GET fired while save pending: ${events}`);
  assert.ok(events.slice(done).includes("get"), `no GET after save: ${events}`);
}

test("AI: failed config GET opens no editor and no save, explicit retry loads persisted values", async () => {
  let failing = true;
  browser.route(async (req) => {
    if (req.path === "/api/ai-config" && req.method === "GET") {
      return failing ? { status: 500, json: { error: "db down" } } : { json: aiConfig("persisted/model") };
    }
    return common(req) ?? { status: 500, json: {} };
  });
  await openDashboard();
  await nav("AI Assistant");
  await browser.waitFor(`document.body.innerText.includes("Không tải được cấu hình AI")`, "error state");
  assert.equal(await browser.evaluate(`document.querySelector("${modelInput}")`), null, "no editor with default values");
  await browser.screenshot(shot("ai-error"));
  assert.equal(patchesOf("/api/ai-config").length, 0);
  failing = false;
  await browser.clickText("button", "Thử lại");
  await browser.waitFor(`document.querySelector("${modelInput}")?.value === "persisted/model"`, "retry success");
  await browser.screenshot(shot("ai-ready-after-retry"));
});

test("AI: navigating away and back with a pending save waits for it and shows the saved value", async () => {
  const gate = deferred();
  const events = [];
  let stored = "m0";
  browser.route(async (req) => {
    if (req.path === "/api/ai-config" && req.method === "GET") { events.push("get"); return { json: aiConfig(stored) }; }
    if (req.path === "/api/ai-config" && req.method === "PATCH") {
      events.push("patch-start");
      await gate.promise;
      stored = JSON.parse(req.body).model;
      events.push("patch-done");
      return { json: { applied: true } };
    }
    return common(req) ?? { status: 500, json: {} };
  });
  await openDashboard();
  await nav("AI Assistant");
  await browser.waitFor(`document.querySelector("${modelInput}")?.value === "m0"`, "first load");
  await browser.typeAndBlur(modelInput, "m1");
  while (!patchesOf("/api/ai-config").length) await browser.sleep(20);

  const getsBefore = getsOf("/api/ai-config").length;
  await nav("Tổng quan");
  await nav("AI Assistant");
  await browser.sleep(600);
  assert.equal(getsOf("/api/ai-config").length, getsBefore, "GET must wait for the pending save");
  assert.ok((await bodyText()).includes("Đang tải cấu hình AI"));
  await browser.screenshot(shot("ai-loading-pending-save"));
  assert.equal(await browser.evaluate(`document.querySelector("${modelInput}")`), null, "editor stays closed while loading");

  gate.resolve();
  await browser.waitFor(`document.querySelector("${modelInput}")?.value === "m1"`, "saved value after remount");
  assertGetsOnlyAfterSave(events);
});

test("AI: a stale initial GET that resolves after a remount cannot overwrite the newer load", async () => {
  const stale = deferred();
  let gets = 0;
  browser.route(async (req) => {
    if (req.path === "/api/ai-config" && req.method === "GET") {
      gets += 1;
      if (gets === 1) { await stale.promise; return { json: aiConfig("stale") }; }
      return { json: aiConfig("fresh") };
    }
    return common(req) ?? { status: 500, json: {} };
  });
  await openDashboard();
  await nav("AI Assistant");
  while (gets < 1) await browser.sleep(20);
  await nav("Tổng quan");
  await nav("AI Assistant");
  await browser.waitFor(`document.querySelector("${modelInput}")?.value === "fresh"`, "fresh load");
  stale.resolve();
  await browser.sleep(500);
  assert.equal(await browser.evaluate(`document.querySelector("${modelInput}").value`), "fresh");
});

test("CoreBank: failed GET shows retry instead of the editor; retry loads persisted values", async () => {
  let failing = true;
  browser.route(async (req) => {
    if (req.path === "/api/corebank" && req.method === "GET") {
      return failing ? { status: 500, json: { error: "db down" } } : { json: coreConfig(false) };
    }
    return common(req) ?? { status: 500, json: {} };
  });
  await openDashboard();
  await nav("Core-Bank");
  await browser.waitFor(`document.body.innerText.includes("Không tải được cấu hình CoreBank")`, "error state");
  assert.ok(!(await browser.evaluate("document.body.textContent")).includes("Thêm Core Mới"), "no editor on failed load");
  await browser.screenshot(shot("corebank-error"));
  assert.equal(patchesOf("/api/corebank").length, 0);
  failing = false;
  await browser.clickText("button", "Thử lại");
  await browser.waitFor(`document.body.textContent.includes("Thêm Core Mới")`, "editor after retry");
  assert.equal(await browser.evaluate(`document.querySelector("button.inline-flex.h-6").className.includes("bg-green-500")`), false, "persisted auto_react=false, not the default true");
});

test("CoreBank: navigating away and back with a pending save waits for it", async () => {
  const gate = deferred();
  const events = [];
  let autoReact = true;
  browser.route(async (req) => {
    if (req.path === "/api/corebank" && req.method === "GET") { events.push("get"); return { json: coreConfig(autoReact) }; }
    if (req.path === "/api/corebank" && req.method === "PATCH") {
      events.push("patch-start");
      await gate.promise;
      autoReact = JSON.parse(req.body).auto_react;
      events.push("patch-done");
      return { json: { saved: true, applied: true } };
    }
    return common(req) ?? { status: 500, json: {} };
  });
  await openDashboard();
  await nav("Core-Bank");
  await browser.waitFor(`!!document.querySelector("button.inline-flex.h-6")`, "first load");
  await browser.evaluate(`document.querySelector("button.inline-flex.h-6").click()`);
  while (!patchesOf("/api/corebank").length) await browser.sleep(20);
  const getsBefore = getsOf("/api/corebank").length;
  await nav("AI Assistant");
  await nav("Core-Bank");
  await browser.sleep(600);
  assert.equal(getsOf("/api/corebank").length, getsBefore, "GET must wait for the pending save");
  gate.resolve();
  await browser.waitFor(`document.querySelector("button.inline-flex.h-6") && !document.querySelector("button.inline-flex.h-6").className.includes("bg-green-500")`, "saved auto_react=false after remount");
  assertGetsOnlyAfterSave(events);
});

test("Siphoned: failed read shows an error with retry, never 0 people / 0 SP", async () => {
  let failing = true;
  browser.route(async (req) => {
    if (req.path === "/api/siphoned") {
      return failing
        ? { status: 500, json: { error: "Không thể tải dữ liệu Siphoned." } }
        : { json: { last_update: "2026-01-01", leaderboard: [{ user_id: "alice", silver_pieces: 7 }, { user_id: "bob", silver_pieces: 3 }] } };
    }
    return common(req) ?? { status: 500, json: {} };
  });
  await openDashboard();
  await nav("Siphoned Energy");
  await browser.waitFor(`document.body.innerText.includes("Không tải được dữ liệu Siphoned")`, "error state");
  assert.ok(!(await bodyText()).includes("0 SP"), "no empty-success totals");
  await browser.screenshot(shot("siphoned-error"));
  failing = false;
  await browser.clickText("button", "Thử lại");
  await browser.waitFor(`document.body.innerText.includes("alice") && document.body.innerText.includes("10 SP")`, "rows and exact total after retry");
});
