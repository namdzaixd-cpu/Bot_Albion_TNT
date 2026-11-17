import assert from "node:assert/strict";
import test from "node:test";
import { enqueueSave, loadAfterSaves } from "../src/lib/clientSaveQueue.ts";
import { fetchAllRows } from "../src/lib/fetchAllRows.ts";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const tick = () => new Promise((resolve) => setTimeout(resolve, 10));

test("saves run strictly one after another and a failed save does not block the next", async () => {
  const log = [];
  const first = enqueueSave(async () => { log.push("a-start"); await tick(); log.push("a-end"); throw new Error("boom"); });
  const second = enqueueSave(async () => { log.push("b-start"); await tick(); log.push("b-end"); });
  await first.catch(() => undefined);
  await second;
  assert.deepEqual(log, ["a-start", "a-end", "b-start", "b-end"]);
});

test("a read started after a save waits for it and sees the saved value", async () => {
  let stored = "old";
  const save = enqueueSave(async () => { await tick(); await tick(); stored = "new"; });
  const value = await loadAfterSaves(async () => stored);
  assert.equal(value, "new");
  await save;
});

test("a save queued while a read is in flight discards that read and re-reads after it", async () => {
  let stored = "old";
  let reads = 0;
  const value = await loadAfterSaves(async () => {
    reads += 1;
    const seen = stored;
    if (reads === 1) enqueueSave(async () => { await tick(); stored = "new"; });
    await tick();
    return seen;
  });
  assert.equal(value, "new");
  assert.equal(reads, 2);
});

// Fake PostgREST: honors .range() but caps every response at 1000 rows like the real max-rows setting.
function fakeTable(rows, { failOnCall, mutateOnCall } = {}) {
  let calls = 0;
  return (from, to) => {
    calls += 1;
    if (calls === failOnCall) return Promise.resolve({ data: null, error: { message: "down" }, count: null });
    if (calls === mutateOnCall) rows = rows.slice(1);
    const slice = rows.slice(from, Math.min(to, from + 999) + 1);
    return Promise.resolve({ data: slice, error: null, count: rows.length });
  };
}
const makeRows = (n) => Array.from({ length: n }, (_, i) => ({ user_id: `u${String(i).padStart(5, "0")}`, silver_pieces: n - i }));

test("fetchAllRows returns every row beyond the 1000-row cap, in order, so totals are exact", async () => {
  const rows = makeRows(2503);
  const got = await fetchAllRows(fakeTable(rows));
  assert.equal(got.length, 2503);
  assert.deepEqual(got, rows);
  assert.equal(got.reduce((sum, r) => sum + r.silver_pieces, 0), rows.reduce((sum, r) => sum + r.silver_pieces, 0));
});

test("fetchAllRows fails instead of returning a partial list when a later page errors", async () => {
  await assert.rejects(fetchAllRows(fakeTable(makeRows(2500), { failOnCall: 2 })));
});

test("fetchAllRows fails when rows change between pages", async () => {
  await assert.rejects(fetchAllRows(fakeTable(makeRows(2500), { mutateOnCall: 2 })));
});

test("fetchAllRows handles an empty table", async () => {
  assert.deepEqual(await fetchAllRows(fakeTable([])), []);
});

test("blacklist paging keeps every user when a timestamp changes between pages", async () => {
  const rows = Array.from({ length: 1003 }, (_, index) => ({
    discord_id: (100000000000000000n + BigInt(index)).toString(),
    timestamp: "2026-01-01T00:00:00Z",
  }));
  let page = 0;
  const supabase = {
    from() {
      const orders = [];
      return {
        select() { return this; },
        order(key, { ascending = true } = {}) { orders.push({ key, ascending }); return this; },
        range(from, to) {
          if (++page === 2) rows[1002].timestamp = "2026-02-01T00:00:00Z";
          const ordered = [...rows].sort((left, right) => {
            for (const { key, ascending } of orders) {
              const compared = String(left[key]).localeCompare(String(right[key]));
              if (compared) return ascending ? compared : -compared;
            }
            return 0;
          });
          return Promise.resolve({
            data: ordered.slice(from, to + 1).map(row => ({ ...row })),
            error: null, count: rows.length,
          });
        },
      };
    },
  };
  const dependencies = {
    "next/server": { NextResponse: { json: (value, init) => Response.json(value, init) } },
    "next-auth/next": { getServerSession: async () => ({ user: { id: "officer" } }) },
    "@/lib/auth": { authOptions: {}, isAdmin: () => true },
    "@/lib/guild": { GUILD_ID: "guild" },
    "@/lib/supabaseServer": { supabase },
    "@/lib/fetchAllRows": { fetchAllRows },
  };
  const source = fs.readFileSync(new URL("../src/app/api/blacklist/route.ts", import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const exported = {};
  vm.runInNewContext(compiled, {
    exports: exported,
    require: name => {
      if (!(name in dependencies)) throw new Error(`Unexpected dependency: ${name}`);
      return dependencies[name];
    },
  });
  const response = await exported.GET();
  assert.equal(response.status, 200);
  const result = await response.json();
  assert.equal(result.length, 1003);
  assert.equal(new Set(result.map(row => row.discord_id)).size, 1003);
  assert.equal(result[0].discord_id, rows[1002].discord_id);
});
