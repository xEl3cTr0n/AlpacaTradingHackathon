import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { DEFAULT_WORKSPACE, parseWorkspace, mergeWorkspace, normalizeTicker } = require(process.env.WORKSPACE_TEST_BUILD_DIR + "/workspace-preferences.js");

test("corrupt, null and array storage use display defaults", () => {
  for (const raw of [null, "bad", "null", "[]", "3"]) assert.deepEqual(parseWorkspace(raw), DEFAULT_WORKSPACE);
});
test("ticker input normalizes valid symbols and rejects non-tickers", () => {
  assert.equal(normalizeTicker(" brk.b "), "BRK.B");
  for (const value of ["../env", ".", "SPY<script>", 123, "AAPL260918C00100000", "ABCDEFGHIJK"]) assert.equal(normalizeTicker(value), null);
});
test("display preferences survive round trip and symbol switch", () => {
  const first = mergeWorkspace(null, { symbol: "msft", timeframe: "15Min", rsiMode: "off", showGex: false, quoteSeconds: 10, rail: "watchlist", dock: "orders" });
  assert.equal(first.symbol, "MSFT");
  const next = mergeWorkspace(JSON.stringify(first), { symbol: "AAPL" });
  assert.equal(next.symbol, "AAPL");
  assert.equal(next.timeframe, "15Min");
  assert.equal(next.showGex, false);
  assert.equal(next.dock, "orders");
});
test("unknown fields including order state and secrets are never persisted", () => {
  const next = mergeWorkspace(null, { symbol: "NVDA", token: "fake-token", paper_orders_enabled: true, long_symbol: "FAKE", confirmation: "PAPER", quantity: 99 });
  assert.deepEqual(Object.keys(next).sort(), Object.keys(DEFAULT_WORKSPACE).sort());
  assert.equal(JSON.stringify(next).includes("fake-token"), false);
});
test("invalid enums and types cannot enable invalid display state", () => {
  const next = parseWorkspace(JSON.stringify({ timeframe: "10s", rsiMode: "sell", lowVolFilter: "false", showLevels: "false", showGex: 0, quoteSeconds: -1, dock: "live", rail: "admin" }));
  assert.deepEqual(next, DEFAULT_WORKSPACE);
});
test("watchlist is deduplicated, bounded and supports intentionally empty lists", () => {
  assert.deepEqual(parseWorkspace('{"watchlist":["aapl","AAPL"," msft ","../bad",null]}').watchlist, ["AAPL", "MSFT"]);
  assert.deepEqual(parseWorkspace('{"watchlist":[]}').watchlist, []);
  const many = Array.from({ length: 60 }, (_, i) => "A" + String.fromCharCode(65 + Math.floor(i / 26)) + String.fromCharCode(65 + i % 26));
  assert.equal(parseWorkspace(JSON.stringify({ watchlist: many })).watchlist.length, 40);
});
