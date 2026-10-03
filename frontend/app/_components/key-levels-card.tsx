"use client";

import { Fragment } from "react";
import { targetCorridorSummary } from "@/lib/chart-context";
import type { ChartContextSnapshot } from "@/lib/types";

const price = (value?: number | null) => (value == null ? "—" : value.toFixed(2));

/** Implied-move corridor and structure levels, nearest first, outside the chart canvas. */
export function KeyLevelsCard({ symbol, context, loading, failed }: {
  symbol: string; context: ChartContextSnapshot | null; loading: boolean; failed: boolean;
}) {
  const t = targetCorridorSummary(context);
  const vp = context?.volume_profile;
  const spot = t.spot;
  const rows = [
    { label: "Extreme +2σ", value: t.extremeUpper, tone: "bull" },
    { label: "Weekly +1σ", value: t.weeklyUpper, tone: "bull" },
    { label: "Call wall", value: t.callWall, tone: "wall" },
    { label: "1D bull target", value: t.dailyUpper, tone: "bull" },
    { label: "Prior day high", value: t.priorDayHigh, tone: "" },
    { label: "Value area high", value: vp?.vah, tone: "" },
    { label: "Volume POC", value: vp?.poc, tone: "" },
    { label: "Session VWAP", value: context?.structural_levels?.session_vwap, tone: "" },
    { label: "Prior day close", value: t.priorDayClose, tone: "" },
    { label: "Value area low", value: vp?.val, tone: "" },
    { label: "Prior day low", value: t.priorDayLow, tone: "" },
    { label: "1D bear target", value: t.dailyLower, tone: "bear" },
    { label: "Put wall", value: t.putWall, tone: "wall" },
    { label: "Weekly −1σ", value: t.weeklyLower, tone: "bear" },
    { label: "Extreme −2σ", value: t.extremeLower, tone: "bear" },
  ].filter((row): row is { label: string; value: number; tone: string } => typeof row.value === "number" && Number.isFinite(row.value) && row.value > 0)
    .sort((a, b) => b.value - a.value);
  const spotIndex = spot == null ? -1 : rows.findIndex((row) => row.value < spot);
  return <section className="side-card key-levels" aria-label={`${symbol} key levels`} aria-busy={loading}>
    <div className="side-card-heading"><strong>{symbol} key levels</strong><span>{failed ? "Unavailable" : loading && !context ? "Loading…" : spot != null ? `Spot ${price(spot)}` : "—"}</span></div>
    <div className="move-pills">
      <span>1D ±{price(t.dailyExpectedMove)}{t.dailyPct != null && ` (${t.dailyPct}%)`}</span>
      <span>7D ±{price(t.weeklyExpectedMove)}{t.weeklyPct != null && ` (${t.weeklyPct}%)`}</span>
    </div>
    {rows.length ? <table className="levels-table"><tbody>
      {rows.map((row, index) => <Fragment key={row.label}>
        {index === spotIndex && <tr className="spot-row"><th>▶ Spot</th><td>{price(spot)}</td><td /></tr>}
        <tr className={row.tone}><th>{row.label}</th><td>{row.value.toFixed(2)}</td><td>{spot ? `${row.value >= spot ? "+" : ""}${((row.value / spot - 1) * 100).toFixed(2)}%` : ""}</td></tr>
      </Fragment>)}
      {spotIndex === -1 && spot != null && <tr className="spot-row"><th>▶ Spot</th><td>{price(spot)}</td><td /></tr>}
    </tbody></table> : <p className="rail-note">{failed ? "Options context failed. Chart remains available." : "No levels yet."}</p>}
    <p className="rail-note">IV moves from Alpaca option chain · walls are GEX positioning proxies, not dealer inventory.</p>
  </section>;
}
