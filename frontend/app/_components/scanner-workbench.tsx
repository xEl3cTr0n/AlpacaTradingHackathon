"use client";

import { useState, useSyncExternalStore } from "react";
import { BUILTIN_PRESETS, DEFAULT_FILTERS, parsePresets } from "@/lib/scanner-filters";
import type { ScannerFilters } from "@/lib/scanner-filters";
import type { ScannerCandidate } from "@/lib/types";
import research from "@/lib/scanner-research-results.json";

const STORAGE_KEY = "regimeshift.scanner-presets.v1";
function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("scanner-presets", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("scanner-presets", callback);
  };
}
function storedPresets() {
  try { return localStorage.getItem(STORAGE_KEY) ?? "[]"; } catch { return "[]"; }
}
const serverPresets = () => "[]";

export function ScannerFilterBar({ filters, onChange, matches, total }: {
  filters: ScannerFilters; onChange: (filters: ScannerFilters) => void; matches: number; total: number;
}) {
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const raw = useSyncExternalStore(subscribe, storedPresets, serverPresets);
  const saved = parsePresets(raw);
  function update<K extends keyof ScannerFilters>(key: K, value: ScannerFilters[K]) {
    onChange({ ...filters, [key]: value });
  }
  function save() {
    if (!name.trim()) { setMessage("Name your preset first."); return; }
    const existing = saved.filter((p) => p.name !== name.trim());
    if (existing.length >= 10) { setMessage("10 presets saved. Reuse a name to replace it."); return; }
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify([...existing, { name: name.trim(), filters }]));
      window.dispatchEvent(new Event("scanner-presets"));
      setMessage("Preset saved on this browser.");
    } catch { setMessage("Browser storage unavailable. Filters still work this session."); }
  }
  return <section className="scanner-filters panel" aria-label="Research scanner filters">
    <div className="panel-heading"><div><p className="eyebrow">Build your scan</p><h2>Chop, momentum & exhaustion</h2></div><strong role="status" aria-live="polite">{matches} / {total} match</strong></div>
    <p>View filters only. Daily R-Factor and bar-timeframe RSI do not change the trading worker.</p>
    <div className="scanner-presets">{BUILTIN_PRESETS.map((preset) => <button key={preset.name} type="button" onClick={() => onChange(preset.filters)}>{preset.name}</button>)}</div>
    <div className="scanner-filter-grid">
      <label>Chop condition<select value={filters.chop} onChange={(e) => update("chop", e.target.value as ScannerFilters["chop"])}><option value="all">Any condition</option><option value="not_chop">Exclude chop</option><option value="trend">Trending · &lt;38.2</option><option value="transition">Transition · 38.2–61.8</option><option value="chop">Chopping · &gt;61.8</option></select></label>
      <label>Chop timeframe<select value={filters.chopTimeframe} onChange={(e) => update("chopTimeframe", e.target.value as ScannerFilters["chopTimeframe"])}><option value="intraday">Scanner bars (usually 15m)</option><option value="daily">Completed daily bars</option></select></label>
      <label>Daily R-Factor<select value={filters.rFactor} onChange={(e) => update("rFactor", e.target.value as ScannerFilters["rFactor"])}><option value="all">Any score</option><option value="bullish">Bullish · above +threshold</option><option value="bearish">Bearish mirror · below −threshold</option></select></label>
      <label>Daily bar<select value={filters.dailyBar} onChange={(e) => update("dailyBar", e.target.value as ScannerFilters["dailyBar"])}><option value="completed">Last completed session</option><option value="provisional">Today · provisional</option></select></label>
      <label>R-Factor threshold<input type="number" min="0" max="1000" step="1" value={filters.threshold} onChange={(e) => { if (e.target.validity.valid) update("threshold", Number(e.target.value)); }} /></label>
      <label>Minimum daily RVOL<input type="number" min="0" max="14" step="0.1" value={filters.minRvol} onChange={(e) => { if (e.target.validity.valid) update("minRvol", Number(e.target.value)); }} /></label>
      <label>RSI + volume event<select value={filters.rsiSignal} onChange={(e) => update("rsiSignal", e.target.value as ScannerFilters["rsiSignal"])}><option value="all">Any / no event</option><option value="raw">Original extreme + volume</option><option value="quiet">New quiet extreme only</option><option value="reversal">Price-confirmed reversal</option><option value="continuation">Continuation context</option></select></label>
      <label>Sort by<select value={filters.sort} onChange={(e) => update("sort", e.target.value as ScannerFilters["sort"])}><option value="rank">Scanner rank</option><option value="r_factor">R-Factor magnitude</option><option value="chop">Least choppy first</option></select></label>
    </div>
    <div className="scanner-filter-options"><label><input type="checkbox" checked={filters.lowVolFilter} onChange={(e) => update("lowVolFilter", e.target.checked)} /> RSI low-vol filter: ATR/price ≥0.5%</label><label><input type="checkbox" checked={filters.freshOnly} onChange={(e) => update("freshOnly", e.target.checked)} /> Hide stale plans</label><button type="button" onClick={() => onChange(DEFAULT_FILTERS)}>Reset filters</button></div>
    <div className="scanner-save"><label>Preset name<input maxLength={32} value={name} onChange={(e) => setName(e.target.value)} placeholder="My momentum scan" /></label><button type="button" onClick={save}>Save preset</button><label>Saved on this browser<select value="" onChange={(e) => { const p = saved.find((p) => p.name === e.target.value); if (p) { onChange(p.filters); setName(p.name); } }}><option value="">Load preset…</option>{saved.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}</select></label></div>
    {message && <p role="status">{message}</p>}
  </section>;
}

const price = (value: number) => `$${value.toFixed(2)}`;
const words = (value: string) => value.replaceAll("_", " ");

const researchNames: Record<keyof typeof research.variants, string> = {
  r_factor: "R-Factor breakout · both directions",
  r_factor_exclude_chop: "R-Factor · exclude chop",
  r_factor_trend_only: "R-Factor · trending only",
  rsi_raw_fade: "RSI original · 5-session fade",
  rsi_quiet_fade: "RSI quiet · 5-session fade",
  rsi_confirmed_reversal: "RSI confirmed · 5-session reversal",
};

function ScannerResearchEvidence() {
  const reduction = 100 * (1 - research.signal_counts.quiet_rsi_alerts / research.signal_counts.raw_rsi_alerts);
  return <details className="scanner-research-evidence"><summary>Backtest evidence · {research.symbols} stocks / {research.session_count} daily sessions</summary>
    <p>{research.start.slice(0, 10)}–{research.end.slice(0, 10)} · holdout from {research.holdout_start.slice(0, 10)}. Quiet mode reduced counted alerts {reduction.toFixed(1)}% ({research.signal_counts.raw_rsi_alerts} → {research.signal_counts.quiet_rsi_alerts}). That measures alert frequency, not accuracy.</p>
    <div className="table-scroll"><table className="scanner-plan-table"><caption>Underlying proxies after 10bps round-trip cost · not option returns</caption><thead><tr><th>Variant</th><th>Train mean / trade</th><th>Holdout mean / trade</th><th>Holdout N</th><th>Evidence</th></tr></thead><tbody>{Object.entries(research.variants).map(([key, result]) => {
      const training = result.train.mean_underlying_return;
      const holdout = result.holdout.mean_underlying_return;
      const status = training == null || holdout == null ? "Insufficient data"
        : training > 0 && holdout > 0 ? "Positive proxy · unvalidated for options"
        : training <= 0 && holdout <= 0 ? "Negative proxy" : "Mixed across periods";
      return <tr key={key}><th>{researchNames[key as keyof typeof research.variants]}</th><td>{training == null ? "—" : `${(training * 100).toFixed(2)}%`}</td><td>{holdout == null ? "—" : `${(holdout * 100).toFixed(2)}%`}</td><td>{result.holdout.trades}</td><td>{status}</td></tr>;
    })}</tbody></table></div><ul>{research.methodology.map((line) => <li key={line}>{line}</li>)}</ul>
    <p>All six remain research-only. No execution authorization from this experiment.</p>
  </details>;
}

export function ScannerDiagnosticsPanel({ candidate, lowVolFilter, onOpenManual }: {
  candidate: ScannerCandidate; lowVolFilter: boolean; onOpenManual: (symbol: string) => void;
}) {
  const d = candidate.diagnostics;
  if (!d) return <section className="scanner-diagnostics panel"><h2>Research diagnostics unavailable</h2><p>Run a fresh scan to load chop, R-Factor and RSI/volume readings.</p></section>;
  const v = lowVolFilter ? d.volume_rsi_low_vol_filtered : d.volume_rsi;
  return <section className="scanner-diagnostics panel" aria-label={`${candidate.symbol} chop and entry exit plans`}>
    <div className="panel-heading"><div><p className="eyebrow">Measured context · not trade permission</p><h2>{candidate.symbol} signal workbench</h2></div><span className={d.stale ? "negative" : "source-label"}>{d.stale ? "Stale · re-scan before entry" : `${d.timeframe} completed bars`}</span></div>
    <div className="scanner-diagnostic-grid">
      <article><span>CHOP(14) · {d.timeframe}</span><strong>{d.chop.value?.toFixed(1) ?? "—"} <small>{d.chop.state}</small></strong><p>Daily: {d.daily_chop.value?.toFixed(1) ?? "—"} · {d.daily_chop.state}. CHOP does not tell direction.</p></article>
      {[{ label: "Completed daily R-Factor", r: d.daily_r_factor }, { label: "Today’s R-Factor · provisional", r: d.provisional_r_factor }].map(({ label, r }) => <article key={label}><span>{label}</span><strong>{r?.score.toFixed(1) ?? "—"}</strong><p>{r ? `${r.relative_volume.toFixed(2)}× RVOL · ${r.bullish_match ? "original >150 match" : r.bearish_match ? "bearish <−150 mirror" : "no ±150 match"}` : "Daily data unavailable"}</p><small>{r ? new Date(r.as_of).toLocaleDateString("en-US", { timeZone: "America/New_York" }) : ""}</small></article>)}
      <article><span>RSI14 + volume · {d.timeframe}</span><strong>{v?.rsi.toFixed(1) ?? "—"} <small>RSI</small></strong><p>{v ? `${v.volume_ratio.toFixed(2)}× SMA20 volume · ATR/price ${(v.atr_fraction * 100).toFixed(2)}%` : "Insufficient valid bars"}</p><small>Low-vol filter {lowVolFilter ? "on" : "off"}{v?.low_volatility ? " · low volatility detected" : ""}</small></article>
    </div>
    <div className="scanner-rsi-context"><span>Original: <b>{words(v?.raw_signal ?? "unavailable")}</b></span><span>Quiet alert: <b>{words(v?.quiet_signal ?? "unavailable")}</b></span><span>Context: <b>{words(v?.context ?? "unavailable")}</b></span></div>
    <p>Overbought is not automatically a put; oversold is not automatically a call. Quiet mode needs RSI reset + 5-bar cooldown. Reversal needs an opposite close beyond the signal candle within 5 bars. Continuation and extreme alerts can prompt profit review on an existing position.</p>
    <div className="panel-heading"><div><h3>Underlying entry / exit map</h3><p>{d.levels_price != null ? `${price(d.levels_price)} stock reference · ` : ""}{d.levels_as_of ? new Date(d.levels_as_of).toLocaleString() : "No completed bar"}</p></div><button type="button" onClick={() => onOpenManual(candidate.symbol)}>Open paper options chain</button></div>
    <div className="table-scroll"><table className="scanner-plan-table"><caption>Research breakout plans · stock prices, not option premiums</caption><thead><tr><th>Direction</th><th>Entry trigger</th><th>Invalidation</th><th>Target 1 · 1R</th><th>Target 2 · 2R</th><th>Status</th></tr></thead><tbody>{d.plans.map((p) => <tr key={p.side}><th>{p.side === "call" ? "Calls / bullish spread" : "Puts / bearish spread"}</th><td>{p.side === "call" ? "Above " : "Below "}{price(p.entry)}</td><td>{price(p.invalidation)}</td><td>{price(p.target_1)}</td><td>{price(p.target_2)}</td><td>{words(p.state)}</td></tr>)}</tbody></table></div>
    {!d.plans.length && <p>No valid plan: OHLC history or nonzero range missing.</p>}
    <p>Next 3 bars only · 20-bar range breakout + 0.1 ATR buffer · structural stop capped at 2 ATR · exit after 8 bars from entry. Re-scan when entry window expires. No orders or stops placed here.</p>
    <ScannerResearchEvidence />
    <details><summary>Formula, data limits & recent quiet events</summary><ul>{d.notes.map((note) => <li key={note}>{note}</li>)}</ul><p>R = 100 × (0.50 × directional RVOL + 0.25 × open change % + 0.15 × momentum % + 0.10 × typical-price distance %). Round to 1 decimal; original match is strictly &gt;150. The supplied code does not cap volume.</p><ul>{d.recent_rsi_events.map((event) => <li key={event.as_of}>{new Date(event.as_of).toLocaleString()} · {words(event.quiet_signal !== "none" ? event.quiet_signal : event.context)} · RSI {event.rsi.toFixed(1)}</li>)}</ul><p>Event history uses original low-vol filter OFF. Quieter is not proven more profitable. Daily underlying backtests do not validate intraday option P&amp;L.</p></details>
  </section>;
}
