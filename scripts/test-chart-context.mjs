// Compile frontend/lib/chart-context.ts to CHART_TEST_BUILD_DIR before running.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";
const require = createRequire(import.meta.url);
const { matchingChartContext, chartContextLevels, nearbyGexRows, formatSessionDate, strikeHeatmapRows, heatmapSummary, targetCorridorSummary } = require(`${process.env.CHART_TEST_BUILD_DIR}/chart-context.js`);
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
test("formatSessionDate standardizes exchange date to America/New_York regardless of local timezone", () => {
  assert.equal(formatSessionDate(null), "unavailable");
  assert.equal(formatSessionDate(""), "unavailable");
  assert.equal(formatSessionDate("invalid-date"), "unavailable");
  assert.equal(formatSessionDate("2026-09-14T04:00:00Z"), "9/14/2026");
});
test("chartContextLevels includes IV walls, POC, VAH, VAL, and Ichimoku Kijun when present", () => {
  const full = {
    ...fixture(),
    iv_levels: { upper_1s: 115, lower_1s: 85, session_upper: 103, session_lower: 97, prior_day_high: 108, prior_day_low: 94 },
    volume_profile: { poc: 101, vah: 108, val: 92 },
    structural_levels: { kijun_sen: 100, session_vwap: 99.5 },
  };
  const levels = chartContextLevels(full);
  // 6 original + 6 IV + 3 volume profile + 2 structural = 17 levels
  assert.equal(levels.length, 17);
  assert(levels.some((l) => l.title === "Weekly +1σ"));
  assert(levels.some((l) => l.title === "Session +1σ"));
  assert(levels.some((l) => l.title === "Prior Day High"));
  assert(levels.some((l) => l.title === "Volume POC"));
  assert(levels.some((l) => l.title === "Ichimoku Kijun"));
  assert(levels.some((l) => l.title === "Session VWAP"));

  const targets = targetCorridorSummary(full);
  assert.equal(targets.spot, 100);
  assert.equal(targets.weeklyUpper, 115);
  assert.equal(targets.dailyUpper, 103);
  assert.equal(targets.priorDayHigh, 108);
});
test("strikeHeatmapRows identifies ATM strike and normalizes intensities", () => {
  const context = {
    symbol: "SPY",
    read_only: true,
    underlying_price: 500,
    options_microstructure: {
      underlying_symbol: "SPY",
      gex_by_strike: [
        { strike: 490, call_gex: 50, put_gex: -100, net_gex: -50, call_oi: 500, put_oi: 2000, call_volume: 100, put_volume: 400, average_iv: 0.22 },
        { strike: 500, call_gex: 300, put_gex: -50, net_gex: 250, call_oi: 4000, put_oi: 1500, call_volume: 1200, put_volume: 300, average_iv: 0.18 },
        { strike: 510, call_gex: 150, put_gex: -20, net_gex: 130, call_oi: 2000, put_oi: 400, call_volume: 600, put_volume: 100, average_iv: 0.19 },
      ],
    },
  };
  const rows = strikeHeatmapRows(context, 10, "strike", "asc");
  assert.equal(rows.length, 3);
  assert.equal(rows[1].strike, 500);
  assert.equal(rows[1].isAtm, true);
  assert.equal(rows[0].isAtm, false);
  assert.equal(rows[1].callOiIntensity, 1.0); // max call oi is 4000 at 500
  assert.equal(rows[0].putOiIntensity, 1.0); // max put oi is 2000 at 490
  assert.equal(rows[1].gexIntensity, 1.0); // max abs net gex is 250 at 500

  const summary = heatmapSummary(context);
  assert.equal(summary.totalCallOi, 6500);
  assert.equal(summary.totalPutOi, 3900);
  assert.equal(summary.totalOi, 10400);
  assert.equal(summary.pcOiRatio, 0.6);
  assert.equal(summary.atmStrike, 500);
  assert.equal(summary.atmIv, 0.18);
});

