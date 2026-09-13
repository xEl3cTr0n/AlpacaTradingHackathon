// Compile frontend/lib/chart-context.ts to CHART_TEST_BUILD_DIR before running.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";
const require = createRequire(import.meta.url);
const { matchingChartContext, chartContextLevels, nearbyGexRows } = require(`${process.env.CHART_TEST_BUILD_DIR}/chart-context.js`);
const fixture = () => ({ symbol: "AAPL", read_only: true, underlying_price: 100,
  swing: { swing_low: 90, swing_high: 110 },
  options_microstructure: { underlying_symbol: "AAPL", put_wall: 95, call_wall: 105, key_gamma_strike: 102, hedge_wall: 99,
    gex_by_strike: [80, 95, 100, 105, 130].map(strike => ({ strike, call_gex: 100, put_gex: -70, net_gex: 30 })) },
});
test("ticker switch removes prior overlays until matching context arrives", () => {
  const old = fixture();
  assert.equal(matchingChartContext("MSFT", old), null);
  assert.deepEqual(chartContextLevels(matchingChartContext("MSFT", old)), []);
  assert.equal(chartContextLevels(matchingChartContext("AAPL", old)).length, 6);
});
test("errors, mixed-symbol payloads, and missing inputs never become levels", () => {
  assert.equal(matchingChartContext("AAPL", fixture(), true), null);
  const mixed = fixture(); mixed.options_microstructure.underlying_symbol = "MSFT";
  assert.equal(matchingChartContext("AAPL", mixed), null);
  assert.deepEqual(chartContextLevels(null), []);
  const partial = fixture(); partial.options_microstructure = null;
  assert.equal(chartContextLevels(partial).length, 2);
  partial.swing.swing_high = NaN;
  assert.equal(chartContextLevels(partial).length, 1);
});
test("GEX profile shows nearby actual strikes without mutating the response", () => {
  const context = fixture(), before = JSON.stringify(context);
  assert.deepEqual(nearbyGexRows(context, 3).map(row => row.strike), [95, 100, 105]);
  assert.equal(JSON.stringify(context), before);
  assert.deepEqual(nearbyGexRows(null), []);
});
