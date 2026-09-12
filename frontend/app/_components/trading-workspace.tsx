"use client";

import { ArrowUpRight, RefreshCw, SlidersHorizontal } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState, useTransition } from "react";
import useSWR from "swr";
import { runScannerAnalysis } from "@/app/actions";
import { BUILTIN_PRESETS, filterCandidates } from "@/lib/scanner-filters";
import type { DecisionSnapshot, ScannerSnapshot } from "@/lib/types";

const MarketChartTerminal = dynamic(() => import("./market-chart-terminal").then((m) => m.MarketChartTerminal), {
  ssr: false, loading: () => <div className="chart-placeholder">Loading chart workspace…</div>,
});
const ManualTradeTicket = dynamic(() => import("./manual-trade-ticket").then((m) => m.ManualTradeTicket));

async function scanFetcher(url: string): Promise<ScannerSnapshot> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error("Scanner unavailable. Retry or inspect the last snapshot.");
  return response.json() as Promise<ScannerSnapshot>;
}

const money = (value?: number | null) => value == null ? "—" : `$${value.toFixed(2)}`;

export function TradingWorkspace({ snapshot, initialScanner, symbol, onSymbolChange, onSnapshot, onOpenScanner, onOpenResearch, initialTicketOpen = false }: {
  snapshot: DecisionSnapshot;
  initialScanner: ScannerSnapshot;
  symbol: string;
  onSymbolChange: (value: string) => void;
  onSnapshot: (value: DecisionSnapshot) => void;
  onOpenScanner: () => void;
  onOpenResearch: () => void;
  initialTicketOpen?: boolean;
}) {
  const [preset, setPreset] = useState(0);
  const [seconds, setSeconds] = useState(5);
  const [ticketOpen, setTicketOpen] = useState(initialTicketOpen);
  const [message, setMessage] = useState("");
  const [pending, startTransition] = useTransition();
  const latestSymbol = useRef(symbol);
  // The request id prevents a slow council response replacing a newer selection.
  const requestId = useRef(0);
  useEffect(() => {
    latestSymbol.current = symbol;
    requestId.current += 1;
  }, [symbol]);
  const { data: scanner, error, isValidating, mutate } = useSWR("/api/v1/scanner?limit=24", scanFetcher, {
    fallbackData: initialScanner, refreshInterval: 60_000, dedupingInterval: 45_000,
    refreshWhenHidden: false, refreshWhenOffline: false, errorRetryCount: 1,
  });
  const candidates = filterCandidates(scanner.candidates, BUILTIN_PRESETS[preset].filters);
  const candidate = scanner.candidates.find((item) => item.symbol === symbol);
  const diagnostics = candidate?.diagnostics;
  const plan = diagnostics?.plans.find((item) => item.side === (candidate?.direction === "bearish" ? "put" : "call"));
  const matchingDecision = snapshot.market.symbol === symbol;

  function selectSymbol(next: string) {
    latestSymbol.current = next;
    requestId.current += 1;
    setMessage("");
    onSymbolChange(next);
  }

  function review() {
    const reviewedSymbol = symbol;
    latestSymbol.current = symbol;
    const id = ++requestId.current;
    setMessage(`Reviewing ${symbol}; no order will be placed.`);
    startTransition(async () => {
      try {
        const decision = await runScannerAnalysis(reviewedSymbol);
        if (id !== requestId.current || latestSymbol.current !== reviewedSymbol) return;
        onSnapshot(decision);
        setMessage(`Council ${decision.council.approved ? "supports" : "does not support"} ${reviewedSymbol}. Risk ${decision.risk.approved ? "approved" : "vetoed"}. Read-only review.`);
      } catch (cause) {
        if (id === requestId.current) setMessage(cause instanceof Error ? cause.message : "Review failed. Retry the scanner.");
      }
    });
  }

  return <div className="terminal-workspace">
    <header className="workspace-heading">
      <div><p className="eyebrow">Alpaca · paper research</p><h1>Trade workspace</h1></div>
      <div className="workspace-actions">
        <label>Quote refresh<select value={seconds} onChange={(event) => setSeconds(Number(event.target.value))}>
          <option value={0}>Paused</option><option value={1}>1 second</option><option value={5}>5 seconds</option><option value={10}>10 seconds</option>
        </select></label>
        <button type="button" className="secondary-action" onClick={onOpenScanner}><SlidersHorizontal size={15} aria-hidden="true" /> All filters</button>
      </div>
    </header>
    <div className="workspace-policy">
      <span>{scanner.execution_gates?.paper_experiment_enabled ? "Paper experiments eligible" : "Holdout-gated entries"}</span>
      <span>Hard risk enforced</span><span>Worker: 5-minute checks · not 10-second execution</span>
    </div>
    <div className="terminal-grid">
      <aside className="opportunity-rail" aria-labelledby="opportunity-rail-title">
        <div className="rail-heading"><h2 id="opportunity-rail-title">Opportunities</h2><button type="button" className="secondary-action icon-action" onClick={() => void mutate()} disabled={isValidating} aria-label="Refresh opportunities"><RefreshCw size={15} className={isValidating ? "spinning" : ""} aria-hidden="true" /></button></div>
        <label className="rail-filter">Scanner preset<select value={preset} onChange={(event) => setPreset(Number(event.target.value))}>{BUILTIN_PRESETS.map((item, index) => <option value={index} key={item.name}>{item.name}</option>)}</select></label>
        <p className="rail-note">{candidates.length} matches · filters do not place orders</p>
        {error && <p className="workspace-warning" role="alert">Refresh failed. Showing last scan; retry above.</p>}
        <div className="opportunity-list">
          {candidates.map((item) => <button type="button" key={item.symbol} aria-pressed={symbol === item.symbol} className={symbol === item.symbol ? "selected" : ""} onClick={() => selectSymbol(item.symbol)}>
            <span><strong>{item.symbol}</strong><b>{money(item.current_price)}</b></span>
            <span><small>{item.direction} · {Math.round(item.conviction * 100)} score</small><small>{item.diagnostics?.stale ? "STALE" : item.actionable ? "SETUP" : "WATCH"}</small></span>
            <span><small>CHOP {item.diagnostics?.chop.value?.toFixed(1) ?? "—"}</small><small>R {item.diagnostics?.daily_r_factor?.score.toFixed(0) ?? "—"}</small></span>
          </button>)}
          {!candidates.length && <p className="workspace-empty">No matches. Change preset or open all filters. No trade is valid.</p>}
        </div>
        <p className="rail-note">15-minute scanner · refresh 60s<br />Scan {new Date(scanner.generated_at).toLocaleString()}</p>
      </aside>
      <div className="workspace-chart-column">
        <MarketChartTerminal snapshot={snapshot} symbol={symbol} onSymbolChange={selectSymbol} quoteRefreshMs={seconds * 1000} />
        <section className="workspace-thesis" aria-labelledby="workspace-thesis-title">
          <div className="rail-heading"><div><p className="eyebrow">Research thesis · underlying prices</p><h2 id="workspace-thesis-title">{symbol} · {candidate?.option_bias ?? "Chart exploration"}</h2></div><button type="button" className="primary-action" onClick={() => setTicketOpen(!ticketOpen)} aria-expanded={ticketOpen} aria-controls="workspace-ticket">{ticketOpen ? "Close ticket" : "Options ticket"}<ArrowUpRight size={15} aria-hidden="true" /></button></div>
          {candidate ? <>
            <div className="thesis-levels">
              <div><span>{candidate.move_thesis.horizon_sessions}-session range</span><strong>±{money(candidate.move_thesis.expected_move_dollars)}</strong><small>Magnitude only; ATR / realized vol</small></div>
              <div><span>Entry trigger</span><strong>{money(plan?.entry)}</strong><small>{plan?.state.replaceAll("_", " ") ?? "No level"}</small></div>
              <div><span>Invalidation</span><strong>{money(plan?.invalidation)}</strong><small>Underlying level, not option stop</small></div>
              <div><span>Target 1 / 2</span><strong>{money(plan?.target_1)} / {money(plan?.target_2)}</strong><small>{diagnostics?.stale ? "Stale — do not act on levels" : "Research levels, not fills"}</small></div>
            </div>
            <div className="thesis-signal-strip"><span>Direction {candidate.move_thesis.direction_score > 0 ? "+" : ""}{candidate.move_thesis.direction_score.toFixed(0)}</span><span>CHOP: {diagnostics?.chop.state ?? "unavailable"}</span><span>RSI/volume: {diagnostics?.volume_rsi?.context.replaceAll("_", " ") ?? "unavailable"}</span></div>
            <details className="workspace-evidence"><summary>Supporting evidence, conflicts &amp; freshness</summary><p>{candidate.move_thesis.trigger}</p><h3>Supports</h3><ul>{candidate.move_thesis.supporting_evidence.map((item) => <li key={item}>{item}</li>)}</ul><h3>Conflicts</h3><ul>{candidate.move_thesis.conflicting_evidence.map((item) => <li key={item}>{item}</li>)}</ul><p>Signal {new Date(candidate.as_of).toLocaleString()} · level bars {diagnostics?.levels_as_of ? new Date(diagnostics.levels_as_of).toLocaleString() : "unavailable"}. Direction scores are not calibrated probabilities. RSI extremes alone do not prove reversal.</p></details>
          </> : <p className="workspace-empty">This ticker has no current large-cap scanner thesis. Chart and manual chain remain available; no borrowed signal from another symbol.</p>}
          <div className="workspace-review"><button type="button" className="secondary-action" disabled={pending || !candidate?.actionable || diagnostics?.stale} onClick={review}>{pending ? "Reviewing…" : "Review with council"}</button><button type="button" className="secondary-action" onClick={onOpenResearch}>Research &amp; backtests</button><span>{matchingDecision ? `Last ${symbol} decision: ${snapshot.council.support_count} support · risk ${snapshot.risk.approved ? "approved" : "vetoed"}` : "No council review for this symbol"}</span></div>
          {message && <p className="run-status" role="status">{message}</p>}
        </section>
      </div>
    </div>
    <section id="workspace-ticket" aria-label={`${symbol} manual paper options ticket`}>
      {ticketOpen && <ManualTradeTicket key={symbol} defaultSymbol={symbol} onSymbolChange={selectSymbol} />}
    </section>
  </div>;
}
