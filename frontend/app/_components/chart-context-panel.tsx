"use client";

import { useState } from "react";
import type { ChartContextSnapshot } from "@/lib/types";
import {
  formatSessionDate,
  nearbyGexRows,
  strikeHeatmapRows,
  heatmapSummary,
} from "@/lib/chart-context";
import { useWorkspacePreferences } from "@/lib/use-workspace-preferences";

const amount = (value: number) =>
  Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
    signDisplay: "exceptZero",
  }).format(value);

const price = (value?: number | null) => (value == null ? "—" : `$${value.toFixed(2)}`);

export function ChartContextPanel({
  symbol,
  context,
  loading,
  failed,
  onRetry,
}: {
  symbol: string;
  context: ChartContextSnapshot | null;
  loading: boolean;
  failed: boolean;
  onRetry: () => void;
}) {
  const [preferences, updatePreferences] = useWorkspacePreferences();
  const [viewMode, setViewMode] = useState<"matrix" | "histogram">("matrix");
  const [sortBy, setSortBy] = useState<"strike" | "net_gex" | "volume" | "oi">("strike");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [depthLimit, setDepthLimit] = useState<number>(25);

  const micro = context?.options_microstructure;
  const rows = nearbyGexRows(context);
  const maximum = Math.max(...rows.map((row) => Math.abs(row.net_gex)), 1);

  const heatmapRows = strikeHeatmapRows(context, depthLimit, sortBy, sortDir);
  const summary = heatmapSummary(context);

  const toggleSort = (column: "strike" | "net_gex" | "volume" | "oi") => {
    if (sortBy === column) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(column);
      setSortDir(column === "strike" ? "asc" : "desc");
    }
  };

  return (
    <section className="chart-context-panel" aria-label={`${symbol} automatic chart context`} aria-busy={loading}>
      <div className="chart-context-heading">
        <strong>{symbol} overlays</strong>
        <span role="status">
          {loading
            ? "Loading ticker context…"
            : failed
            ? "Context unavailable"
            : context?.status === "partial"
            ? "Partial data"
            : context?.status === "available"
            ? "Research data loaded"
            : "Context unavailable"}
        </span>
        <button type="button" className="secondary-action" onClick={onRetry} disabled={loading}>
          Refresh overlays
        </button>
      </div>

      <div className="chart-context-metrics">
        <div>
          <span>Net GEX proxy</span>
          <strong>{micro ? amount(micro.net_gex) : "Unavailable"}</strong>
          <small>{micro?.gamma_regime ?? "No invented gamma"}</small>
        </div>
        <div>
          <span>Put / call wall</span>
          <strong>{price(micro?.put_wall)} / {price(micro?.call_wall)}</strong>
          <small>{micro ? `${micro.contract_count} usable contracts` : "Option data missing"}</small>
        </div>
        <div>
          <span>±1σ IV Wall (7-DTE)</span>
          <strong>{context?.iv_levels?.lower_1s ? `${price(context.iv_levels.lower_1s)} / ${price(context.iv_levels.upper_1s)}` : "Unavailable"}</strong>
          <small>
            {context?.iv_levels?.average_iv
              ? `${(context.iv_levels.average_iv * 100).toFixed(1)}% ATM IV (±$${context.iv_levels.expected_move?.toFixed(2)})`
              : "IV pending"}
          </small>
        </div>
        <div>
          <span>Volume POC · Value Area</span>
          <strong>{price(context?.volume_profile?.poc)}</strong>
          <small>
            {context?.volume_profile?.val
              ? `VA: ${price(context.volume_profile.val)} – ${price(context.volume_profile.vah)}`
              : "Profile pending"}
          </small>
        </div>
        <div>
          <span>Ichimoku Kijun · VWAP</span>
          <strong>{price(context?.structural_levels?.kijun_sen)} / {price(context?.structural_levels?.session_vwap)}</strong>
          <small>26-period base equilibrium</small>
        </div>
        <div>
          <span>20-session swing low / high</span>
          <strong>{price(context?.swing?.swing_low)} / {price(context?.swing?.swing_high)}</strong>
          <small>Completed daily bars</small>
        </div>
      </div>

      {failed && (
        <p className="workspace-warning">Price chart stays available. Retry overlays; old ticker levels are not reused.</p>
      )}

      {(rows.length > 0 || heatmapRows.length > 0) && (
        <details
          className="chart-gex-profile"
          open={preferences.showGex}
          onToggle={(event) => {
            if (event.currentTarget.open !== preferences.showGex) {
              updatePreferences({ showGex: event.currentTarget.open });
            }
          }}
        >
          <summary>
            Options Positioning &amp; Liquidity Matrix · {micro?.contract_count ?? rows.length} contracts · positioning proxy
          </summary>

          <div className="heatmap-view-header">
            <div className="heatmap-view-tabs" role="tablist" aria-label="Positioning views">
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "matrix"}
                className={`heatmap-tab ${viewMode === "matrix" ? "active" : ""}`}
                onClick={() => setViewMode("matrix")}
              >
                🔥 Liquidity &amp; IV Matrix
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "histogram"}
                className={`heatmap-tab ${viewMode === "histogram" ? "active" : ""}`}
                onClick={() => setViewMode("histogram")}
              >
                📊 GEX Histogram
              </button>
            </div>

            {viewMode === "matrix" && (
              <div className="heatmap-controls">
                <div className="heatmap-depth-group">
                  <span>Strikes:</span>
                  <button
                    type="button"
                    className={`heatmap-chip ${depthLimit === 15 ? "active" : ""}`}
                    onClick={() => setDepthLimit(15)}
                  >
                    15
                  </button>
                  <button
                    type="button"
                    className={`heatmap-chip ${depthLimit === 25 ? "active" : ""}`}
                    onClick={() => setDepthLimit(25)}
                  >
                    25
                  </button>
                  <button
                    type="button"
                    className={`heatmap-chip ${depthLimit === 0 ? "active" : ""}`}
                    onClick={() => setDepthLimit(0)}
                  >
                    All
                  </button>
                </div>
              </div>
            )}
          </div>

          {viewMode === "matrix" ? (
            <div className="heatmap-matrix-wrapper">
              <div className="heatmap-summary-strip">
                <div className="heatmap-summary-card">
                  <span className="summary-label">Call Open Interest</span>
                  <strong>{summary.totalCallOi.toLocaleString()}</strong>
                  <small>P/C OI Ratio: {summary.pcOiRatio ?? "—"}</small>
                </div>
                <div className="heatmap-summary-card">
                  <span className="summary-label">Put Open Interest</span>
                  <strong>{summary.totalPutOi.toLocaleString()}</strong>
                  <small>Total OI: {summary.totalOi.toLocaleString()}</small>
                </div>
                <div className="heatmap-summary-card">
                  <span className="summary-label">Call / Put Volume</span>
                  <strong>
                    {summary.totalCallVol.toLocaleString()} / {summary.totalPutVol.toLocaleString()}
                  </strong>
                  <small>P/C Vol Ratio: {summary.pcVolRatio ?? "—"}</small>
                </div>
                <div className="heatmap-summary-card">
                  <span className="summary-label">ATM Reference &amp; IV</span>
                  <strong>{summary.atmStrike ? price(summary.atmStrike) : "—"}</strong>
                  <small>{summary.atmIv ? `${(summary.atmIv * 100).toFixed(1)}% Implied Vol` : "IV pending"}</small>
                </div>
              </div>

              <div className="table-scroll heatmap-scroll">
                <table className="heatmap-table" aria-label={`${symbol} Options Liquidity and IV Matrix`}>
                  <thead>
                    <tr>
                      <th
                        className="sortable"
                        onClick={() => toggleSort("oi")}
                        title="Click to sort by Call Open Interest"
                      >
                        Call OI {sortBy === "oi" && (sortDir === "asc" ? "▲" : "▼")}
                      </th>
                      <th
                        className="sortable"
                        onClick={() => toggleSort("volume")}
                        title="Click to sort by Call Volume"
                      >
                        Call Vol {sortBy === "volume" && (sortDir === "asc" ? "▲" : "▼")}
                      </th>
                      <th
                        className="sortable strike-header"
                        onClick={() => toggleSort("strike")}
                        title="Click to sort by Strike"
                      >
                        Strike {sortBy === "strike" && (sortDir === "asc" ? "▲" : "▼")}
                      </th>
                      <th
                        className="sortable"
                        onClick={() => toggleSort("net_gex")}
                        title="Click to sort by Net Gamma Exposure"
                      >
                        Net GEX {sortBy === "net_gex" && (sortDir === "asc" ? "▲" : "▼")}
                      </th>
                      <th>Avg IV</th>
                      <th
                        className="sortable"
                        onClick={() => toggleSort("volume")}
                        title="Click to sort by Put Volume"
                      >
                        Put Vol {sortBy === "volume" && (sortDir === "asc" ? "▲" : "▼")}
                      </th>
                      <th
                        className="sortable"
                        onClick={() => toggleSort("oi")}
                        title="Click to sort by Put Open Interest"
                      >
                        Put OI {sortBy === "oi" && (sortDir === "asc" ? "▲" : "▼")}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {heatmapRows.map((row) => (
                      <tr key={row.strike} className={row.isAtm ? "atm-row" : ""}>
                        <td
                          className="heat-cell call-cell"
                          style={{
                            backgroundColor: `rgba(34, 197, 94, ${0.05 + row.callOiIntensity * 0.42})`,
                          }}
                        >
                          {row.call_oi.toLocaleString()}
                        </td>
                        <td
                          className="heat-cell call-cell"
                          style={{
                            backgroundColor: `rgba(34, 197, 94, ${0.05 + row.callVolIntensity * 0.42})`,
                          }}
                        >
                          {row.call_volume.toLocaleString()}
                        </td>
                        <td className="strike-cell">
                          <span className="strike-val">${row.strike.toFixed(2)}</span>
                          {row.isAtm && <span className="atm-tag">ATM</span>}
                        </td>
                        <td
                          className={`heat-cell gex-cell ${row.net_gex >= 0 ? "gex-positive" : "gex-negative"}`}
                          style={{
                            backgroundColor:
                              row.net_gex >= 0
                                ? `rgba(16, 185, 129, ${0.06 + row.gexIntensity * 0.42})`
                                : `rgba(244, 63, 94, ${0.06 + row.gexIntensity * 0.42})`,
                          }}
                        >
                          {amount(row.net_gex)}
                        </td>
                        <td
                          className="heat-cell iv-cell"
                          style={{
                            backgroundColor:
                              row.average_iv != null
                                ? `rgba(168, 85, 247, ${0.06 + row.ivIntensity * 0.44})`
                                : undefined,
                          }}
                        >
                          {row.average_iv != null ? `${(row.average_iv * 100).toFixed(1)}%` : "—"}
                        </td>
                        <td
                          className="heat-cell put-cell"
                          style={{
                            backgroundColor: `rgba(239, 68, 68, ${0.05 + row.putVolIntensity * 0.42})`,
                          }}
                        >
                          {row.put_volume.toLocaleString()}
                        </td>
                        <td
                          className="heat-cell put-cell"
                          style={{
                            backgroundColor: `rgba(239, 68, 68, ${0.05 + row.putOiIntensity * 0.42})`,
                          }}
                        >
                          {row.put_oi.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="heatmap-legend-note">
                Intensity scaling: Green = Call liquidity · Red = Put liquidity · Emerald/Rose = Net Gamma · Purple = Implied Volatility skew.
              </p>
            </div>
          ) : (
            <>
              <div
                className="gex-histogram"
                role="img"
                aria-label={`Signed net gamma positioning proxy across ${rows.length} nearby ${symbol} strikes. Bars above zero are positive; below zero are negative. Exact values in table below.`}
              >
                {rows.map((row) => (
                  <div key={row.strike} className="gex-column">
                    <div className="gex-column-plot">
                      <span
                        className={row.net_gex >= 0 ? "gex-positive" : "gex-negative"}
                        style={{ height: `${(Math.abs(row.net_gex) / maximum) * 48}%` }}
                      />
                    </div>
                    <span>{row.strike}</span>
                  </div>
                ))}
              </div>
              <p>Above zero: +GEX · below zero: −GEX. Each column is a strike category, not an evenly spaced price axis.</p>
              <details>
                <summary>Exact strike values</summary>
                <div className="table-scroll">
                  <table className="gex-data-table">
                    <caption>Exact GEX proxy values · γ × OI × 100 × spot, calls positive / puts negative</caption>
                    <thead>
                      <tr>
                        <th>Strike</th>
                        <th>Call GEX</th>
                        <th>Put GEX</th>
                        <th>Net GEX</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <tr key={row.strike}>
                          <td>{row.strike.toFixed(2)}</td>
                          <td>{row.call_gex.toLocaleString()}</td>
                          <td>{row.put_gex.toLocaleString()}</td>
                          <td>{row.net_gex.toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </>
          )}
        </details>
      )}

      <details className="chart-context-notes">
        <summary>Sources &amp; freshness · automatic 60-second refresh</summary>
        <p>Chart context loads without the council. These overlays do not authorize orders.</p>
        {context && (
          <>
            <p>
              Retrieved {new Date(context.generated_at).toLocaleString()} · spot timestamp{" "}
              {context.spot_as_of ? new Date(context.spot_as_of).toLocaleString() : "unavailable"} · daily bar{" "}
              {formatSessionDate(context.swing_as_of)} (ET).
            </p>
            <p>{micro?.source ?? "Options source unavailable"}</p>
            <ul>
              {context.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </>
        )}
        <p>Greek/OI timestamp freshness unverified. This is not measured dealer inventory or a live-flow feed.</p>
      </details>
    </section>
  );
}

