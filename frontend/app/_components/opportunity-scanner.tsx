"use client";

import {
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  Crosshair,
  RefreshCw,
  Search,
  ShieldAlert,
} from "lucide-react";
import { useState, useTransition } from "react";
import type { CSSProperties } from "react";
import { refreshScanner, runAnalysis } from "@/app/actions";
import type { DecisionSnapshot, ScannerCandidate, ScannerSnapshot } from "@/lib/types";

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

export function OpportunityScanner({
  initialScanner,
  onSnapshot,
}: {
  initialScanner: ScannerSnapshot;
  onSnapshot: (snapshot: DecisionSnapshot) => void;
}) {
  const [scanner, setScanner] = useState(initialScanner);
  const [error, setError] = useState("");
  const [activeSymbol, setActiveSymbol] = useState("");
  const [isPending, startTransition] = useTransition();

  function rescan() {
    setError("");
    startTransition(async () => {
      try {
        setScanner(await refreshScanner());
      } catch (scanError) {
        setError(scanError instanceof Error ? scanError.message : "Scanner refresh failed");
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

  const lead = scanner.candidates[0];
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
        <article><Crosshair size={18} aria-hidden="true" /><div><span>Actionable now</span><strong>{scanner.actionable_count}</strong><small>above {Math.round(scanner.minimum_conviction * 100)}% conviction</small></div></article>
        <article><CheckCircle2 size={18} aria-hidden="true" /><div><span>Primary trigger</span><strong>{scanner.ema_period} EMA</strong><small>confirmed price crossover</small></div></article>
        <article><ShieldAlert size={18} aria-hidden="true" /><div><span>Execution</span><strong>Paper only</strong><small>council + risk + liquidity gates</small></div></article>
      </section>

      {lead && (
        <section className={`scanner-lead panel ${lead.actionable ? "actionable" : "watch"}`}>
          <div className="scanner-lead-copy">
            <p className="eyebrow">Highest-ranked setup</p>
            <div className="scanner-symbol-line">
              <strong>{lead.symbol}</strong><span>{lead.name}</span>
              <b className={lead.direction === "bullish" ? "positive" : lead.direction === "bearish" ? "negative" : ""}>
                {lead.direction === "bullish" ? <ArrowUpRight size={15} /> : lead.direction === "bearish" ? <ArrowDownRight size={15} /> : null}
                {patternLabel(lead.pattern)}
              </b>
            </div>
            <p>{lead.evidence.slice(0, 3).join(" · ")}</p>
          </div>
          <div className="conviction-orbit" aria-label={`${Math.round(lead.conviction * 100)} percent conviction`} style={{ "--conviction": `${Math.round(lead.conviction * 360)}deg` } as CSSProperties}>
            <span><strong>{Math.round(lead.conviction * 100)}%</strong><small>conviction</small></span>
          </div>
        </section>
      )}

      <section className="panel scanner-table-panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Ranked tape</p><h2>Pattern recognition queue</h2></div>
          <span className="source-label">{scanner.source}</span>
        </div>
        <div className="scanner-methodology">{scanner.methodology}</div>
        {error && <p className="scanner-error" role="alert">{error}</p>}
        <div className="table-scroll">
          <table className="scanner-table">
            <caption>Ranked large-cap 18 EMA scanner candidates</caption>
            <thead><tr><th>Rank</th><th>Symbol / setup</th><th>Price vs 18 EMA</th><th>Conviction</th><th>Relative strength</th><th>Volume</th><th>Liquidity</th><th>Agent handoff</th></tr></thead>
            <tbody>
              {scanner.candidates.map((candidate) => (
                <tr key={candidate.symbol} className={candidate.actionable ? "actionable-row" : ""}>
                  <td><span className="scanner-rank">{candidate.rank.toString().padStart(2, "0")}</span></td>
                  <td><strong>{candidate.symbol}</strong><small>{patternLabel(candidate.pattern)}</small></td>
                  <td><strong>${candidate.current_price.toFixed(2)}</strong><small>EMA ${candidate.ema_18.toFixed(2)}</small></td>
                  <td><div className="mini-conviction"><span style={{ width: `${candidate.conviction * 100}%` }} /></div><small>{Math.round(candidate.conviction * 100)}%</small></td>
                  <td className={candidate.relative_strength_20d >= 0 ? "positive" : "negative"}>{candidate.relative_strength_20d >= 0 ? "+" : ""}{(candidate.relative_strength_20d * 100).toFixed(1)}%</td>
                  <td><strong>{candidate.volume_ratio.toFixed(2)}×</strong><small>20-day average</small></td>
                  <td><span className={`liquidity-chip ${candidate.liquidity_tier}`}>{candidate.liquidity_tier.replace("_", " ")}</span><small>{compactDollars(candidate.average_dollar_volume)} / day</small></td>
                  <td>
                    <button type="button" className="scanner-analyze" onClick={() => analyze(candidate)} disabled={isPending || !candidate.actionable} title={candidate.actionable ? "Send to the voting council" : "Waiting for a confirmed crossover"}>
                      {isPending && activeSymbol === candidate.symbol ? "Running…" : candidate.actionable ? "Run council" : "Watch"}
                    </button>
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
