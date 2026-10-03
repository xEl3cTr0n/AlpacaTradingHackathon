// Compile frontend/lib/indicators.ts to INDICATOR_TEST_BUILD_DIR before running.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";
const require = createRequire(import.meta.url);
const ind = require(`${process.env.INDICATOR_TEST_BUILD_DIR}/indicators.js`);
const close = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);
const bar = (timestamp, price, volume = 100, extra = {}) => ({ timestamp, close: price, open: price, high: price, low: price, volume, ...extra });

test("SMA, EMA and momentum follow thinkorswim definitions", () => {
  assert.deepEqual(ind.sma([1, 2, 3, 4, 5], 3), [null, null, 2, 3, 4]);
  assert.deepEqual(ind.momentum([1, 2, 4, 7], 2), [null, null, 3, 5]);
  const e = ind.ema([10, 20], 3);
  close(e[0], 10); close(e[1], 15);
});

test("Wilder RSI matches a hand calculation and saturates on one-way moves", () => {
  const r = ind.rsi([10, 11, 10, 12], 2);
  assert.equal(r[1], null);
  close(r[2], 50);
  close(r[3], 100 - 100 / 6);
  assert.equal(ind.rsi([1, 2, 3, 4, 5], 2).at(-1), 100);
});

test("crosses needs the prior bar at or through the reference", () => {
  assert.deepEqual(ind.crosses([1, 2, 3], [2, 2, 2]), [{ index: 2, direction: "up" }]);
  assert.deepEqual(ind.crosses([3, 1, 1, 3], 2), [{ index: 1, direction: "down" }, { index: 3, direction: "up" }]);
  assert.deepEqual(ind.crosses([null, 3, 1], [2, 2, 2]), [{ index: 2, direction: "down" }]);
  assert.deepEqual(ind.crosses([1, 1, 1], 1), []);
});

test("VWAP bands weight bar VWAP by volume and reset on the New York date", () => {
  const bars = [
    bar("2026-09-30T19:00:00Z", 1, 100, { vwap: 1 }), // older, cut-off period
    bar("2026-10-01T14:00:00Z", 99, 100, { vwap: 10 }),
    bar("2026-10-02T01:00:00Z", 99, 300, { vwap: 12 }), // 21:00 ET, still Oct 1
    bar("2026-10-02T13:35:00Z", 50, 200, { vwap: 20 }),
  ];
  const v = ind.vwapBands(bars, 2, "day");
  assert.equal(v.vwap[0], null); // the first loaded period is partial, so it is not drawn
  assert.equal(v.startsBeforeWindow, false);
  close(v.vwap[2], 11.5);
  close(v.deviation[2], Math.sqrt(0.75));
  close(v.upper[2], 11.5 + 2 * Math.sqrt(0.75));
  close(v.lower[2], 11.5 - 2 * Math.sqrt(0.75));
  close(v.vwap[3], 20);
  assert.equal(v.deviation[3], 0);
});

test("a lone bar has exactly zero deviation and the readout uses % distance", () => {
  const bars = [
    bar("2026-09-30T19:00:00Z", 400, 100, { vwap: 400 }),
    bar("2026-10-01T15:00:00Z", 403.86, 966440, { vwap: 407.9393 }),
  ];
  const settings = { showVwap: true, vwapDeviation: 2, vwapAnchor: "day", showSmaCross: false, smaFast: 15, smaSlow: 30, showMomentum: false, momentumLength: 12, showEma: false, showRsi: false };
  const studies = ind.computeStudies(bars, settings, "5Min");
  assert.equal(studies.vwap.deviation[1], 0);
  const [chip] = ind.signalReadout(bars, studies, settings, null);
  assert.equal(chip.label, "VWAP -1.00%");
  assert.equal(chip.tone, "bear");
  assert.match(chip.detail, /Bands form after the first bar/);
});

test("VWAP falls back to HLC/3 and weekly anchors roll on Sunday", () => {
  const v = ind.vwapBands([{ timestamp: "2026-10-01T14:00:00Z", open: 1, high: 12, low: 6, close: 9, volume: 10 }]);
  close(v.vwap[0], 9);
  const fri = ind.periodKey("2026-10-02T15:00:00Z", "week");
  const sun = ind.periodKey("2026-10-04T15:00:00Z", "week");
  const mon = ind.periodKey("2026-10-05T15:00:00Z", "week");
  assert.notEqual(fri, sun); assert.equal(sun, mon);
  assert.equal(ind.periodKey("2026-10-31T15:00:00Z", "month") + 1, ind.periodKey("2026-11-02T15:00:00Z", "month"));
  assert.equal(ind.effectiveVwapAnchor("day", "1Day"), "month");
  assert.equal(ind.effectiveVwapAnchor("week", "1Day"), "week");
});

test("forming bar detection keeps unfinished candles out of confirmed signals", () => {
  const now = Date.parse("2026-10-02T15:00:00Z");
  assert.equal(ind.formingBarIndex([bar("2026-10-02T14:58:00Z", 1)], "5Min", now), 0);
  assert.equal(ind.formingBarIndex([bar("2026-10-02T14:54:00Z", 1)], "5Min", now), null);
  assert.equal(ind.formingBarIndex([bar("2026-10-02T04:00:00Z", 1)], "1Day", now), 0);
  assert.equal(ind.formingBarIndex([bar("2026-10-01T04:00:00Z", 1)], "1Day", now), null);
  assert.equal(ind.formingBarIndex([], "5Min", now), null);
});

test("signal readout reports confirmed and unconfirmed crosses honestly", () => {
  const settings = { showVwap: true, vwapDeviation: 2, vwapAnchor: "day", showSmaCross: true, smaFast: 2, smaSlow: 3, showMomentum: true, momentumLength: 2, showEma: false, showRsi: false };
  const bars = [5, 4, 3, 4, 6].map((p, i) => bar(`2026-10-02T14:${String(i * 5).padStart(2, "0")}:00Z`, p));
  const studies = ind.computeStudies(bars, settings, "5Min");
  assert.deepEqual(studies.smaCrosses, [{ index: 4, direction: "up" }]);
  const confirmed = ind.signalReadout(bars, studies, settings, null);
  assert.deepEqual(confirmed.map((c) => c.id), ["vwap", "sma", "momentum"]);
  assert.match(confirmed[1].detail, /crossed this bar/);
  assert.match(ind.signalReadout(bars, studies, settings, 4)[1].detail, /unconfirmed/);
  assert.equal(studies.vwap.startsBeforeWindow, true); // one period in view
  assert.match(confirmed[0].detail, /period starts before loaded bars/);
  assert.equal(studies.ema18, null);
  assert.deepEqual(ind.signalReadout([], studies, settings, null), []);
});

test("readout wording handles zero momentum and a single bar", () => {
  const settings = { showVwap: false, vwapDeviation: 2, vwapAnchor: "day", showSmaCross: false, smaFast: 15, smaSlow: 30, showMomentum: true, momentumLength: 1, showEma: false, showRsi: false };
  const flat = [3, 1, 3, 3].map((p, i) => bar(`2026-10-02T14:${String(i * 5).padStart(2, "0")}:00Z`, p));
  const atZero = ind.signalReadout(flat, ind.computeStudies(flat, settings, "5Min"), settings, null)[0];
  assert.equal(atZero.label, "MOM(1) 0.00");
  assert.match(atZero.detail, /^At zero · crossed 1 bar ago$/);
  assert.equal(atZero.tone, "neutral");
});
