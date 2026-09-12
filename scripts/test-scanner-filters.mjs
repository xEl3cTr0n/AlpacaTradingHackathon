// Compile frontend/lib/scanner-filters.ts into SCANNER_TEST_BUILD_DIR first; see docs/scanner-workbench.md.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

const require = createRequire(import.meta.url);
const { DEFAULT_FILTERS, filterCandidates, parsePresets } = require(
  `${process.env.SCANNER_TEST_BUILD_DIR}/scanner-filters.js`,
);
const candidate = (symbol, rank, score, state = "trend") => ({
  symbol, rank, actionable: false,
  diagnostics: {
    stale: false, chop: { state, value: state === "trend" ? 25 : 75 },
    daily_chop: { state: "chop", value: 75 },
    daily_r_factor: { score, relative_volume: 2 },
    provisional_r_factor: { score: -score, relative_volume: .5 },
    volume_rsi: { raw_signal: "overbought", quiet_signal: "none", context: "up_continuation" },
    volume_rsi_low_vol_filtered: { raw_signal: "none", quiet_signal: "none", context: "none" },
  },
});

test("filters cover full universe without mutating candidates or authorizing watch names", () => {
  const names = Array.from({ length: 24 }, (_, i) => candidate(`S${i}`, i + 1, i === 23 ? 200 : 100));
  const original = JSON.stringify(names);
  const found = filterCandidates(names, { ...DEFAULT_FILTERS, rFactor: "bullish" });
  assert.equal(found.length, 1);
  assert.equal(found[0].symbol, "S23");
  assert.equal(found[0].actionable, false);
  assert.equal(JSON.stringify(names), original);
});

test("daily R-Factor uses strict threshold and explicitly selected completed or provisional bar", () => {
  const names = [candidate("A", 1, 150), candidate("B", 2, 150.1)];
  assert.deepEqual(filterCandidates(names, { ...DEFAULT_FILTERS, rFactor: "bullish" }).map(c => c.symbol), ["B"]);
  assert.deepEqual(filterCandidates(names, { ...DEFAULT_FILTERS, rFactor: "bearish", dailyBar: "provisional" }).map(c => c.symbol), ["B"]);
  assert.equal(filterCandidates(names, { ...DEFAULT_FILTERS, minRvol: 1, dailyBar: "provisional" }).length, 0);
});

test("missing diagnostics never passes an active condition; reset includes it", () => {
  const name = { symbol: "MISSING", rank: 1 };
  assert.equal(filterCandidates([name], DEFAULT_FILTERS).length, 1);
  for (const active of [{ chop: "not_chop" }, { rFactor: "bullish" }, { minRvol: 1 }, { rsiSignal: "raw" }, { freshOnly: true }]) {
    assert.equal(filterCandidates([name], { ...DEFAULT_FILTERS, ...active }).length, 0);
  }
});

test("chop timeframe and raw/quiet/filtered RSI remain independent", () => {
  const names = [candidate("A", 1, 200)];
  assert.equal(filterCandidates(names, { ...DEFAULT_FILTERS, chop: "trend" }).length, 1);
  assert.equal(filterCandidates(names, { ...DEFAULT_FILTERS, chop: "trend", chopTimeframe: "daily" }).length, 0);
  assert.equal(filterCandidates(names, { ...DEFAULT_FILTERS, rsiSignal: "raw" }).length, 1);
  assert.equal(filterCandidates(names, { ...DEFAULT_FILTERS, rsiSignal: "quiet" }).length, 0);
  assert.equal(filterCandidates(names, { ...DEFAULT_FILTERS, rsiSignal: "continuation" }).length, 1);
  assert.equal(filterCandidates(names, { ...DEFAULT_FILTERS, rsiSignal: "raw", lowVolFilter: true }).length, 0);
});

test("presets validate corrupted storage and round-trip valid controls", () => {
  for (const raw of ["invalid", "null", "{}", '[{"name":"Bad","filters":{}}]']) assert.deepEqual(parsePresets(raw), []);
  const preset = { name: "My scan", filters: { ...DEFAULT_FILTERS, rFactor: "bullish", threshold: 200 } };
  assert.deepEqual(parsePresets(JSON.stringify([preset])), [preset]);
  assert.deepEqual(parsePresets(JSON.stringify([{ ...preset, filters: { ...preset.filters, threshold: -1 } }])), []);
});
