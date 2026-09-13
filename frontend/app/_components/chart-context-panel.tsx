"use client";

import type { ChartContextSnapshot } from "@/lib/types";
import { nearbyGexRows } from "@/lib/chart-context";

const amount = (value: number) => Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2, signDisplay: "exceptZero" }).format(value);
const price = (value?: number | null) => value == null ? "—" : `$${value.toFixed(2)}`;

export function ChartContextPanel({ symbol, context, loading, failed, onRetry }: {
  symbol: string;
  context: ChartContextSnapshot | null;
  loading: boolean;
  failed: boolean;
  onRetry: () => void;
}) {
  const micro = context?.options_microstructure;
  const rows = nearbyGexRows(context);
  const maximum = Math.max(...rows.map((row) => Math.abs(row.net_gex)), 1);
  return <section className="chart-context-panel" aria-label={`${symbol} automatic chart context`} aria-busy={loading}>
    <div className="chart-context-heading"><strong>{symbol} overlays</strong><span role="status">{loading ? "Loading ticker context…" : failed ? "Context unavailable" : context?.status === "partial" ? "Partial data" : context?.status === "available" ? "Research data loaded" : "Context unavailable"}</span><button type="button" className="secondary-action" onClick={onRetry} disabled={loading}>Refresh overlays</button></div>
    <div className="chart-context-metrics">
      <div><span>Net GEX proxy</span><strong>{micro ? amount(micro.net_gex) : "Unavailable"}</strong><small>{micro?.gamma_regime ?? "No invented gamma"}</small></div>
      <div><span>Put / call wall</span><strong>{price(micro?.put_wall)} / {price(micro?.call_wall)}</strong><small>{micro ? `${micro.contract_count} usable contracts` : "Option data missing"}</small></div>
      <div><span>Key gamma / hedge wall</span><strong>{price(micro?.key_gamma_strike)} / {price(micro?.hedge_wall)}</strong><small>Hedge wall ≠ zero gamma</small></div>
      <div><span>20-session swing low / high</span><strong>{price(context?.swing?.swing_low)} / {price(context?.swing?.swing_high)}</strong><small>Completed daily bars</small></div>
    </div>
    {failed && <p className="workspace-warning">Price chart stays available. Retry overlays; old ticker levels are not reused.</p>}
    {rows.length > 0 && <details className="chart-gex-profile" open><summary>GEX by strike · {rows.length} nearest strikes · signed proxy</summary>
      <div className="gex-histogram" role="img" aria-label={`Signed net gamma positioning proxy across ${rows.length} nearby ${symbol} strikes. Bars above zero are positive; below zero are negative. Exact values in table below.`}>
        {rows.map((row) => <div key={row.strike} className="gex-column"><div className="gex-column-plot"><span className={row.net_gex >= 0 ? "gex-positive" : "gex-negative"} style={{ height: `${Math.abs(row.net_gex) / maximum * 48}%` }} /></div><span>{row.strike}</span></div>)}
      </div>
      <p>Above zero: +GEX · below zero: −GEX. Each column is a strike category, not an evenly spaced price axis.</p>
      <details><summary>Exact strike values</summary><div className="table-scroll"><table className="gex-data-table"><caption>Exact GEX proxy values · γ × OI × 100 × spot, calls positive / puts negative</caption><thead><tr><th>Strike</th><th>Call GEX</th><th>Put GEX</th><th>Net GEX</th></tr></thead><tbody>{rows.map((row) => <tr key={row.strike}><td>{row.strike.toFixed(2)}</td><td>{row.call_gex.toLocaleString()}</td><td>{row.put_gex.toLocaleString()}</td><td>{row.net_gex.toLocaleString()}</td></tr>)}</tbody></table></div></details>
    </details>}
    <details className="chart-context-notes"><summary>Sources &amp; freshness · automatic 60-second refresh</summary>
      <p>Chart context loads without the council. These overlays do not authorize orders.</p>
      {context && <><p>Retrieved {new Date(context.generated_at).toLocaleString()} · spot timestamp {context.spot_as_of ? new Date(context.spot_as_of).toLocaleString() : "unavailable"} · daily bar {context.swing_as_of ? new Date(context.swing_as_of).toLocaleDateString() : "unavailable"}.</p><p>{micro?.source ?? "Options source unavailable"}</p><ul>{context.notes.map((note) => <li key={note}>{note}</li>)}</ul></>}
      <p>Greek/OI timestamp freshness unverified. This is not measured dealer inventory or a live-flow feed.</p>
    </details>
  </section>;
}
