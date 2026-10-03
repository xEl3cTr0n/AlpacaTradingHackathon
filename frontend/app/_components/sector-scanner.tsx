"use client";

import { useState } from "react";
import useSWR from "swr";
import type { SectorScanSnapshot } from "@/lib/types";

const pct = (n: number | null | undefined) => n == null ? "—" : `${n >= 0 ? "+" : ""}${(n * 100).toFixed(2)}%`;
const breadth = (n: number | null | undefined) => n == null ? "—" : `${(n * 100).toFixed(0)}%`;
const money = (n: number | null | undefined) => n == null ? "—" : `$${n.toFixed(2)}`;
async function fetchSectors(url: string): Promise<SectorScanSnapshot> {
  const response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(45_000) });
  if (!response.ok) throw new Error("Sector scan unavailable");
  return response.json();
}
function useSectors() {
  return useSWR<SectorScanSnapshot>("/api/v1/sector-scanner", fetchSectors, {
    refreshInterval: 60_000, dedupingInterval: 55_000, errorRetryCount: 1,
    refreshWhenHidden: false, refreshWhenOffline: false, keepPreviousData: false,
  });
}

export function SectorRail({ selected, onSelect }: { selected: string; onSelect: (symbol: string) => void }) {
  const { data, error, isValidating, mutate } = useSectors();
  const [direction, setDirection] = useState("all");
  const [cohesive, setCohesive] = useState(false);
  const rows = data?.sectors.filter(r => (direction === "all" || r.trend === direction)
    && (!cohesive || ((r.agreement ?? 0) >= 0.6 && r.sample_coverage >= 0.6 && (r.chop ?? 100) <= 61.8))) ?? [];
  return <div className="sector-rail">
    <label>ETF trend<select value={direction} onChange={e => setDirection(e.target.value)}><option value="all">Both directions</option><option value="bullish">Bullish</option><option value="bearish">Bearish</option></select></label>
    <label className="sector-check"><input type="checkbox" checked={cohesive} onChange={e => setCohesive(e.target.checked)} /> Cohesive, not choppy</label>
    <button className="secondary-action" type="button" onClick={() => void mutate()} disabled={isValidating}>{isValidating ? "Scanning…" : "Refresh sectors"}</button>
    {error && <p role="alert" className="workspace-warning">Refresh failed. Previous results are not current.</p>}
    {!data && <p role="status" className="rail-note">{error ? "Retry sector scan above." : "Loading 11 ETFs and 55 sample stocks…"}</p>}
    <div className="opportunity-list">{rows.map(row => <button type="button" key={row.symbol} aria-pressed={selected === row.symbol} className={selected === row.symbol ? "selected" : ""} onClick={() => onSelect(row.symbol)}>
      <span><strong>{row.symbol}</strong><b className={(row.session_return ?? 0) < 0 ? "negative" : "positive"}>{pct(row.session_return)}</b></span>
      <span><small>{row.name}</small></span>
      <span><small>{row.trend} · {error ? "stale" : row.signal.replaceAll("_", " ")}</small></span>
      <span><small>Agree {breadth(row.agreement)}</small><small>CHOP {row.chop?.toFixed(0) ?? "—"}</small></span>
      <span className="sector-score" aria-label={`Directional rank ${row.score ?? "unavailable"}, not probability`}><i style={{ width: `${Math.abs(row.score ?? 0)}%`, background: (row.score ?? 0) < 0 ? "var(--red)" : "var(--cyan)" }} /><small>{row.score ?? "—"}</small></span>
    </button>)}</div>
    {data && !rows.length && <p className="rail-note">No sectors match. Loosen filters.</p>}
    <p className="rail-note">Since session open · 15m bars<br />Ranked by absolute directional score. Research filters only.</p>
  </div>;
}

export function SectorDetail({ selected, onSymbolChange }: { selected: string; onSymbolChange: (symbol: string) => void }) {
  const { data, error } = useSectors();
  const [sort, setSort] = useState<"leaders" | "laggards" | "correlation">("leaders");
  const row = data?.sectors.find(r => r.symbol === selected);
  if (!row || !data) return null;
  const members = [...row.members].sort((a, b) => {
    const av = sort === "correlation" ? a.correlation : a.relative_to_sector;
    const bv = sort === "correlation" ? b.correlation : b.relative_to_sector;
    if (av == null) return bv == null ? 0 : 1;
    if (bv == null) return -1;
    return sort === "laggards" ? av - bv : bv - av;
  });
  const side = row.trend === "bearish" ? "put" : "call";
  return <section className="sector-detail workspace-thesis" aria-label={`${selected} sector confirmation`}>
    <div className="sector-detail-heading"><h2>{selected} · {row.name}</h2><button className="secondary-action" type="button" onClick={() => onSymbolChange(selected)}>Chart sector ETF</button></div>
    <p className={error || row.stale || !row.available ? "workspace-warning" : "rail-note"}>{error ? "Refresh failed — cached research only." : row.signal.replaceAll("_", " ")} · reference bar {row.as_of ? new Date(row.as_of).toLocaleString() : "unavailable"}</p>
    <div className="sector-metrics"><span>Since open <b>{pct(row.session_return)}</b></span><span>vs SPY <b>{pct(row.relative_to_spy)}</b></span><span>Sample bull/bear <b>{breadth(row.bullish_breadth)} / {breadth(row.bearish_breadth)}</b></span><span>Coverage <b>{row.members.filter(m => m.available).length}/5</b></span><span>VWAP proxy <b>{money(row.session_vwap)}</b></span>{["1D", "5D", "20D"].map(period => <span key={period}>{period} completed <b>{pct(row.daily_returns[period])}</b></span>)}</div>
    <details open><summary>Sample leaders, laggards & future triggers · not full sector breadth</summary>
      <p>Daily returns through session {row.daily_as_of ? new Date(row.daily_as_of).toLocaleDateString(undefined, { timeZone: "America/New_York" }) : "unavailable"} (ET). Sample agreement is historical context when the session is closed.</p>
      <label className="sector-sort">Stock ranking<select value={sort} onChange={e => setSort(e.target.value as typeof sort)}><option value="leaders">Leaders vs sector</option><option value="laggards">Laggards vs sector</option><option value="correlation">Correlation to ETF</option></select></label>
      <div className="dock-table-scroll sector-table" role="region" tabIndex={0} aria-label="Sector sample stocks and research levels"><table><caption>{side === "put" ? "Bearish put-direction" : "Bullish call-direction"} future breakout levels in underlying dollars. Mixed ETF trend is not a directional signal.</caption><thead><tr><th>Stock / chart</th><th>Since open</th><th>vs ETF</th><th>Trend</th><th>Correlation / n</th><th>Confirms</th><th>Trigger</th><th>Invalidation</th><th>Target 1</th></tr></thead><tbody>{members.map(m => {
        const plan = m.plans.find(p => p.side === side);
        return <tr key={m.symbol}><th><button className="secondary-action" type="button" onClick={() => onSymbolChange(m.symbol)}>{m.symbol}</button></th><td>{pct(m.session_return)}</td><td>{pct(m.relative_to_sector)}</td><td>{m.trend}</td><td>{m.correlation?.toFixed(2) ?? "—"} / {m.correlation_pairs}</td><td>{!m.available ? "Missing" : m.confirms ? "Yes" : "No"}</td><td>{money(plan?.entry)}</td><td>{money(plan?.invalidation)}</td><td>{money(plan?.target_1)}</td></tr>;
      })}</tbody></table></div>
    </details>
    <details><summary>Confirmation checklist & method</summary><ul>{row.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul><p>{data.source} · retrieved {new Date(data.generated_at).toLocaleString()} · refresh/cache 60s.</p><ul>{data.notes.map(note => <li key={note}>{note}</li>)}</ul></details>
  </section>;
}
