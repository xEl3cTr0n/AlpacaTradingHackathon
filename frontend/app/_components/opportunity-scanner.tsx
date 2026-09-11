"use client";

import {
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  ChartNoAxesCombined,
  Crosshair,
  Gauge,
  RefreshCw,
  Search,
  ShieldAlert,
  Target,
  TriangleAlert,
} from "lucide-react";
import { useState, useTransition } from "react";
import type { CSSProperties } from "react";
import { loadOptionsThesis, refreshScanner, runAnalysis } from "@/app/actions";
import type { DecisionSnapshot, OptionsThesisSnapshot, ScannerCandidate, ScannerSnapshot } from "@/lib/types";

function patternLabel(pattern: ScannerCandidate["pattern"]): string {
  return pattern.replaceAll("_", " ").replace("18ema", "18 EMA");
}

function compactDollars(value: number): string {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 1,
  }).format(value);
}

function tradeLabel(candidate: ScannerCandidate, actionable: boolean): string {
  const side = candidate.direction === "bearish" ? "Sell" : "Buy";
  return actionable ? `Run ${side} council` : `${side} watch`;
}

export function OpportunityScanner({
  initialScanner,
  onSnapshot,
}: {
  initialScanner: ScannerSnapshot;
  onSnapshot: (snapshot: DecisionSnapshot) => void;
}) {
  const [scanner, setScanner] = useState(initialScanner);
  const [selectedSymbol, setSelectedSymbol] = useState(
    initialScanner.candidates[0]?.symbol ?? "",
  );
  const [error, setError] = useState("");
  const [activeSymbol, setActiveSymbol] = useState("");
  const [optionsThesis, setOptionsThesis] = useState<OptionsThesisSnapshot | null>(null);
  const [optionsError, setOptionsError] = useState("");
  const [isPending, startTransition] = useTransition();
  const [isOptionsPending, startOptionsTransition] = useTransition();

  function rescan() {
    setError("");
    startTransition(async () => {
      try {
        const nextScanner = await refreshScanner();
        setScanner(nextScanner);
        setSelectedSymbol(nextScanner.candidates[0]?.symbol ?? "");
        setOptionsThesis(null);
      } catch (scanError) {
        setError(scanError instanceof Error ? scanError.message : "Scanner refresh failed");
      }
    });
  }

  function inspectCandidate(candidate: ScannerCandidate) {
    setSelectedSymbol(candidate.symbol);
    setOptionsThesis(null);
    setOptionsError("");
  }

  function inspectOptions(candidate: ScannerCandidate) {
    setOptionsError("");
    startOptionsTransition(async () => {
      try {
        setOptionsThesis(await loadOptionsThesis(candidate.symbol));
      } catch (optionsLoadError) {
        setOptionsError(
          optionsLoadError instanceof Error
            ? optionsLoadError.message
            : "Alpaca options context failed",
        );
      }
    });
  }

  function analyze(candidate: ScannerCandidate) {
    setError("");
    setActiveSymbol(candidate.symbol);
    startTransition(async () => {
      try {
        const snapshot = await runAnalysis(candidate.symbol, {
          strategy_mode: "adaptive",
          instrument_mode: "equity_option",
          max_risk_pct: 0.01,
          min_confidence: Math.min(0.9, Math.max(0.55, candidate.conviction)),
          target_dte: 30,
          max_loss_cap_dollars: candidate.signal_tier === "exploration" ? 500 : null,
        });
        onSnapshot(snapshot);
      } catch (analysisError) {
        setError(
          analysisError instanceof Error ? analysisError.message : "Council analysis failed",
        );
      } finally {
        setActiveSymbol("");
      }
    });
  }

  const lead =
    scanner.candidates.find((candidate) => candidate.symbol === selectedSymbol) ??
    scanner.candidates[0];
  return (
    <div className="view-stack scanner-view">
      <header className="view-heading">
        <div>
          <p className="eyebrow">Opportunity engine</p>
          <h1>Large-cap options scanner</h1>
          <p>Ranks liquid names every {scanner.interval_minutes} minutes; no signal is a valid result.</p>
        </div>
        <button className="primary-action" type="button" onClick={rescan} disabled={isPending}>
          <RefreshCw size={16} className={isPending && !activeSymbol ? "spinning" : ""} aria-hidden="true" />
          {isPending && !activeSymbol ? "Scanning…" : "Run scan"}
        </button>
      </header>

      <section className="scanner-kpis" aria-label="Scanner summary">
        <article><Search size={18} aria-hidden="true" /><div><span>Universe</span><strong>{scanner.scanned_count}/{scanner.universe_size}</strong><small>large-cap names scanned</small></div></article>
        <article><Crosshair size={18} aria-hidden="true" /><div><span>Council-ready</span><strong>{scanner.actionable_count}</strong><small>$1,000 production · $500 exploration</small></div></article>
        <article><CheckCircle2 size={18} aria-hidden="true" /><div><span>Primary trigger</span><strong>{scanner.ema_period} EMA</strong><small>confirmed price crossover</small></div></article>
        <article><ShieldAlert size={18} aria-hidden="true" /><div><span>Intraday backtest</span><strong>{scanner.execution_gates?.intraday_exploration_backtest_passed ? "Exploration passed" : "Fail closed"}</strong><small>{scanner.execution_gates?.intraday_production_backtest_passed ? "production passed" : "production locked"} · runtime gates still apply</small></div></article>
      </section>

      {lead && (
        <>
          <section className={`scanner-lead panel ${lead.actionable ? "actionable" : "watch"}`}>
            <div className="scanner-lead-copy">
              <p className="eyebrow">Selected setup · rank {lead.rank.toString().padStart(2, "0")}</p>
              <div className="scanner-symbol-line">
                <strong>{lead.symbol}</strong><span>{lead.name}</span>
                <b className={lead.direction === "bullish" ? "positive" : lead.direction === "bearish" ? "negative" : ""}>
                  {lead.direction === "bullish" ? <ArrowUpRight size={15} /> : lead.direction === "bearish" ? <ArrowDownRight size={15} /> : null}
                  {patternLabel(lead.pattern)}
                </b>
                <b>{lead.signal_tier} · ${lead.risk_cap_dollars.toFixed(0)} max</b>
              </div>
              <p>{lead.evidence.slice(0, 3).join(" · ")}</p>
            </div>
            <div className="conviction-orbit" aria-label={`${Math.round(lead.conviction * 100)} percent conviction`} style={{ "--conviction": `${Math.round(lead.conviction * 360)}deg` } as CSSProperties}>
              <span><strong>{Math.round(lead.conviction * 100)}%</strong><small>conviction</small></span>
            </div>
          </section>

          <section className="move-thesis panel" aria-label={`${lead.symbol} potential move thesis`}>
            <div className="move-range">
              <div className="panel-heading">
                <div><p className="eyebrow">Potential move</p><h2>{lead.move_thesis.horizon_sessions}-session range</h2></div>
                <span className="source-label">bars · not implied</span>
              </div>
              <div className="move-range-values">
                <span className="negative">${lead.move_thesis.lower_bound.toFixed(2)}</span>
                <strong>${lead.current_price.toFixed(2)}</strong>
                <span className="positive">${lead.move_thesis.upper_bound.toFixed(2)}</span>
              </div>
              <div className="move-range-track" aria-label={`Estimated range from ${lead.move_thesis.lower_bound.toFixed(2)} to ${lead.move_thesis.upper_bound.toFixed(2)}`}>
                <i /><b />
              </div>
              <div className="move-stats">
                <span><Gauge size={14} /><b>±${lead.move_thesis.expected_move_dollars.toFixed(2)}</b><small>{(lead.move_thesis.expected_move_pct * 100).toFixed(1)}% expected</small></span>
                <span><Target size={14} /><b>{lead.move_thesis.direction_score > 0 ? "+" : ""}{lead.move_thesis.direction_score.toFixed(0)}</b><small>direction score</small></span>
                <span><CheckCircle2 size={14} /><b>{Math.round(lead.move_thesis.move_confidence * 100)}%</b><small>range confidence</small></span>
              </div>
              <p className="move-basis">{lead.move_thesis.basis}</p>
              <button className="scanner-options-load" type="button" onClick={() => inspectOptions(lead)} disabled={isOptionsPending}>
                <ChartNoAxesCombined size={14} aria-hidden="true" />
                {isOptionsPending ? "Loading Alpaca options…" : optionsThesis?.underlying_symbol === lead.symbol ? "Refresh options context" : "Load options context"}
              </button>
              {optionsError && <p className="scanner-error" role="alert">{optionsError}</p>}
            </div>

            <div className="thesis-rules">
              <div><span>Trigger</span><p>{lead.move_thesis.trigger}</p></div>
              <div><span>Target</span><p>{lead.move_thesis.target}</p></div>
              <div className="invalidation"><span>Invalidation</span><p>{lead.move_thesis.invalidation}</p></div>
            </div>

            <div className="thesis-evidence support">
              <h3><CheckCircle2 size={14} /> Support</h3>
              <ul>{lead.move_thesis.supporting_evidence.map((item) => <li key={item}>{item}</li>)}</ul>
            </div>
            <div className="thesis-evidence conflict">
              <h3><TriangleAlert size={14} /> Conflict</h3>
              {lead.move_thesis.conflicting_evidence.length ? (
                <ul>{lead.move_thesis.conflicting_evidence.map((item) => <li key={item}>{item}</li>)}</ul>
              ) : <p>No measured conflict.</p>}
            </div>
          </section>
          {optionsThesis && optionsThesis.underlying_symbol === lead.symbol && (
            <section className="options-thesis panel" aria-label={`${lead.symbol} Alpaca options context`}>
              <div className="panel-heading">
                <div><p className="eyebrow">Alpaca options confirmation · read only</p><h2>{lead.symbol} expiry move and gamma map</h2></div>
                <span className="source-label">{optionsThesis.status} · {optionsThesis.dte} DTE</span>
              </div>
              <div className="options-thesis-grid">
                <article><span>IV expiry move</span><strong>{optionsThesis.iv_expected_move_dollars != null ? `±$${optionsThesis.iv_expected_move_dollars.toFixed(2)}` : "N/A"}</strong><small>{optionsThesis.average_implied_volatility != null ? `${(optionsThesis.average_implied_volatility * 100).toFixed(1)}% average IV` : "IV unavailable"}</small></article>
                <article><span>Call + put midpoint</span><strong>{optionsThesis.straddle_cost_dollars != null ? `$${optionsThesis.straddle_cost_dollars.toFixed(2)}` : "N/A"}</strong><small>{optionsThesis.estimator_agreement != null ? `${Math.round(optionsThesis.estimator_agreement * 100)}% estimator agreement` : "Agreement unavailable"}</small></article>
                <article><span>Gamma regime</span><strong>{optionsThesis.gamma_regime}</strong><small>{optionsThesis.gamma_concentration != null ? `${Math.round(optionsThesis.gamma_concentration * 100)}% concentration` : "Concentration unavailable"}</small></article>
                <article><span>Gamma walls</span><strong>{optionsThesis.put_wall != null ? optionsThesis.put_wall.toFixed(0) : "—"} / {optionsThesis.call_wall != null ? optionsThesis.call_wall.toFixed(0) : "—"}</strong><small>put / call</small></article>
                <article><span>Quote quality</span><strong>{optionsThesis.maximum_quote_spread_pct != null ? `${(optionsThesis.maximum_quote_spread_pct * 100).toFixed(1)}%` : "N/A"}</strong><small>{optionsThesis.minimum_open_interest != null ? `${optionsThesis.minimum_open_interest.toLocaleString()} min OI` : "OI unavailable"}</small></article>
              </div>
              <div className="options-evidence-grid">
                <div><h3>Measured evidence</h3><ul>{optionsThesis.evidence.map((item) => <li key={item}>{item}</li>)}</ul></div>
                <div><h3>Limits</h3><ul>{optionsThesis.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>
              </div>
              <footer className="scanner-freshness"><span>Expiry {new Date(`${optionsThesis.expiration}T00:00:00`).toLocaleDateString()}</span><span>{optionsThesis.source}</span></footer>
            </section>
          )}
        </>
      )}

      <section className="panel scanner-table-panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Ranked tape</p><h2>Pattern recognition queue</h2></div>
          <span className="source-label">{scanner.source}</span>
        </div>
        <div className="scanner-methodology">{scanner.methodology}</div>
        {scanner.execution_gates && (
          <div className={`scanner-gate-evidence ${scanner.execution_gates.evidence_valid ? "valid" : "invalid"}`}>
            <strong>{scanner.execution_gates.evidence_valid ? "Backtest evidence verified" : "Backtest evidence invalid — all tiers locked"}</strong>
            <span>{scanner.execution_gates.details.join(" · ")}</span>
          </div>
        )}
        {error && <p className="scanner-error" role="alert">{error}</p>}
        <div className="table-scroll">
          <table className="scanner-table">
            <caption>Ranked large-cap 18 EMA scanner candidates</caption>
            <thead><tr><th>Rank</th><th>Symbol / setup</th><th>Price vs 18 EMA</th><th>5-session move</th><th>Conviction</th><th>Relative strength</th><th>Volume</th><th>Liquidity</th><th>Actions</th></tr></thead>
            <tbody>
              {scanner.candidates.map((candidate) => (
                <tr key={candidate.symbol} className={`${candidate.actionable ? "actionable-row" : ""} ${candidate.symbol === lead.symbol ? "selected-row" : ""}`.trim()}>
                  <td><span className="scanner-rank">{candidate.rank.toString().padStart(2, "0")}</span></td>
                  <td><strong>{candidate.symbol}</strong><small>{patternLabel(candidate.pattern)} · {candidate.signal_tier}</small></td>
                  <td><strong>${candidate.current_price.toFixed(2)}</strong><small>EMA ${candidate.ema_18.toFixed(2)}</small></td>
                  <td><strong>±${candidate.move_thesis.expected_move_dollars.toFixed(2)}</strong><small>{candidate.move_thesis.lower_bound.toFixed(2)}–{candidate.move_thesis.upper_bound.toFixed(2)}</small></td>
                  <td><div className="mini-conviction"><span style={{ width: `${candidate.conviction * 100}%` }} /></div><small>{Math.round(candidate.conviction * 100)}%</small></td>
                  <td className={candidate.relative_strength_20d >= 0 ? "positive" : "negative"}>{candidate.relative_strength_20d >= 0 ? "+" : ""}{(candidate.relative_strength_20d * 100).toFixed(1)}%</td>
                  <td><strong>{candidate.volume_ratio.toFixed(2)}×</strong><small>20-bar average</small></td>
                  <td><span className={`liquidity-chip ${candidate.liquidity_tier}`}>{candidate.liquidity_tier.replace("_", " ")}</span><small>{compactDollars(candidate.average_dollar_volume)} / day</small></td>
                  <td>
                    <div className="scanner-row-actions">
                      <button type="button" className="scanner-inspect" onClick={() => inspectCandidate(candidate)} aria-pressed={candidate.symbol === lead.symbol}>Inspect</button>
                      <button type="button" className="scanner-analyze" onClick={() => analyze(candidate)} disabled={isPending || !candidate.actionable} title={candidate.actionable ? "Send to the voting council" : "Waiting for a confirmed crossover"}>
                        {isPending && activeSymbol === candidate.symbol ? "Running…" : tradeLabel(candidate, candidate.actionable)}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <footer className="scanner-freshness">
          <span>Last bar {new Date(scanner.generated_at).toLocaleString()}</span>
          <span>Live contract spreads and open interest are checked only after approval</span>
        </footer>
      </section>
    </div>
  );
}
