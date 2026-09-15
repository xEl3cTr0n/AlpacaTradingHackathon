"use client";

import { RefreshCw, SlidersHorizontal, Star, X } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState, useTransition } from "react";
import useSWR from "swr";
import { runScannerAnalysis } from "@/app/actions";
import { BUILTIN_PRESETS, DEFAULT_FILTERS, filterCandidates } from "@/lib/scanner-filters";
import { useWorkspacePreferences } from "@/lib/use-workspace-preferences";
import type { DecisionSnapshot, PlatformSnapshot, ScannerSnapshot } from "@/lib/types";
import { ScannerFilterBar } from "./scanner-workbench";
import { TradingDock } from "./trading-dock";

const MarketChartTerminal = dynamic(() => import("./market-chart-terminal").then((m) => m.MarketChartTerminal), {
  ssr: false, loading: () => <div className="chart-placeholder">Loading chart workspace…</div>,
});
async function scanFetcher(url: string): Promise<ScannerSnapshot> {
  const response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(20_000) });
  if (!response.ok) throw new Error("Scanner unavailable.");
  return response.json() as Promise<ScannerSnapshot>;
}
const money = (value?: number | null) => value == null ? "—" : "$" + value.toFixed(2);

export function TradingWorkspace({ snapshot, initialScanner, symbol, onSymbolChange, onSnapshot, onOpenResearch, platform, accountError, onRefreshAccount }: {
  snapshot: DecisionSnapshot; initialScanner: ScannerSnapshot; symbol: string;
  onSymbolChange: (value: string) => void; onSnapshot: (value: DecisionSnapshot) => void;
  onOpenResearch: () => void; platform: PlatformSnapshot | null; accountError: boolean; onRefreshAccount: () => void;
}) {
  const [preferences, updatePreferences] = useWorkspacePreferences();
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [message, setMessage] = useState("");
  const [pending, startTransition] = useTransition();
  const filterDialog = useRef<HTMLDialogElement>(null);
  const latestSymbol = useRef(symbol);
  const requestId = useRef(0);
  useEffect(() => { latestSymbol.current = symbol; requestId.current += 1; }, [symbol]);
  const { data: scanner, error, isValidating, mutate } = useSWR("/api/v1/scanner?limit=24", scanFetcher, {
    fallbackData: initialScanner, refreshInterval: 60_000, dedupingInterval: 45_000,
    refreshWhenHidden: false, refreshWhenOffline: false, errorRetryCount: 1,
  });
  const candidates = filterCandidates(scanner.candidates, filters);
  const candidate = scanner.candidates.find((item) => item.symbol === symbol);
  const diagnostics = candidate?.diagnostics;
  const plan = diagnostics?.plans.find((item) => item.side === (candidate?.direction === "bearish" ? "put" : "call"));
  const matchingDecision = snapshot.market.symbol === symbol;
  const watched = preferences.watchlist.includes(symbol);
  const shownSymbols = preferences.rail === "scanner" ? candidates.map((item) => item.symbol) : preferences.watchlist;
  const presetIndex = BUILTIN_PRESETS.findIndex((item) => JSON.stringify(item.filters) === JSON.stringify(filters));
  const stale = Boolean(error || !diagnostics || diagnostics.stale);

  function selectSymbol(next: string) {
    latestSymbol.current = next; requestId.current += 1; setMessage(""); onSymbolChange(next);
  }
  function toggleWatch() {
    if (!watched && preferences.watchlist.length >= 40) { setMessage("Watchlist holds 40 tickers. Remove one first."); return; }
    updatePreferences({ watchlist: watched ? preferences.watchlist.filter((item) => item !== symbol) : [...preferences.watchlist, symbol] });
  }
  function review() {
    const reviewedSymbol = symbol;
    latestSymbol.current = symbol;
    const id = ++requestId.current;
    setMessage("Reviewing " + symbol + "; no order will be placed.");
    startTransition(async () => {
      try {
        const decision = await runScannerAnalysis(reviewedSymbol);
        if (id !== requestId.current || latestSymbol.current !== reviewedSymbol) return;
        onSnapshot(decision);
        setMessage("Council " + (decision.council.approved ? "supports " : "does not support ") + reviewedSymbol + ". Risk " + (decision.risk.approved ? "approved." : "vetoed.") + " Read-only review.");
      } catch (cause) {
        if (id === requestId.current) setMessage(cause instanceof Error ? cause.message : "Review failed.");
      }
    });
  }

  return <div className="terminal-workspace focused-workspace">
    <h1 className="sr-only">Trade workspace</h1>
    <div className="terminal-grid">
      <aside className="opportunity-rail" aria-label="Ticker watchlist and scanner">
        <nav className="rail-tabs" aria-label="Ticker list">{(["scanner", "watchlist"] as const).map((tab) => <button key={tab} type="button" aria-pressed={preferences.rail === tab} className={preferences.rail === tab ? "active" : ""} onClick={() => updatePreferences({ rail: tab })}>{tab === "scanner" ? "Scanner" : "Watchlist"}</button>)}</nav>
        <div className="rail-controls">
          {preferences.rail === "scanner" ? <label className="rail-filter"><span className="sr-only">Scanner preset</span><select value={presetIndex} onChange={(event) => { const preset = BUILTIN_PRESETS[Number(event.target.value)]; if (preset) setFilters(preset.filters); }}><option value={-1} disabled>Custom filters</option>{BUILTIN_PRESETS.map((item, index) => <option key={item.name} value={index}>{item.name}</option>)}</select></label> : <button type="button" onClick={toggleWatch} aria-pressed={watched}><Star size={13} aria-hidden="true" />{watched ? "Remove " : "Add "}{symbol}</button>}
          <button type="button" className="icon-action" onClick={() => filterDialog.current?.showModal()} aria-label="Open scanner filters"><SlidersHorizontal size={15} aria-hidden="true" /></button>
          <button type="button" className="icon-action" onClick={() => void mutate()} disabled={isValidating} aria-label="Refresh scanner"><RefreshCw size={15} className={isValidating ? "spinning" : ""} aria-hidden="true" /></button>
        </div>
        {error && <p className="workspace-warning" role="alert">Scan refresh failed. Last readings may be stale.</p>}
        <div className="opportunity-list">
          {shownSymbols.map((ticker) => {
            const item = scanner.candidates.find((entry) => entry.symbol === ticker);
            const status = !item ? "NO SCAN" : error || item.diagnostics?.stale ? "STALE" : !item.diagnostics ? "UNVERIFIED" : item.actionable ? "SETUP" : "WATCH";
            return <button type="button" key={ticker} aria-pressed={symbol === ticker} className={symbol === ticker ? "selected" : ""} onClick={() => selectSymbol(ticker)}>
              <span><strong>{ticker}</strong><b>{money(item?.current_price)}</b></span>
              <span><small>{item?.direction ?? "Chart only"}</small><small>{status}</small></span>
              <span><small>CHOP {item?.diagnostics?.chop.value?.toFixed(1) ?? "—"}</small><small>R {item?.diagnostics?.daily_r_factor?.score.toFixed(0) ?? "—"}</small></span>
            </button>;
          })}
          {!shownSymbols.length && <p className="workspace-empty">{preferences.rail === "scanner" ? "No matches. Adjust filters." : "Watchlist empty. Search a ticker, then add it above."}</p>}
        </div>
        <p className="rail-note">{shownSymbols.length} names · 15m scanner<br />Scan {new Date(scanner.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · refresh 60s</p>
        <details className="rail-policy"><summary>Execution eligibility</summary><p>{scanner.execution_gates?.paper_experiment_enabled ? "Paper experiments eligible." : "Holdout-gated entries."} Filters affect this view only. Worker checks are separate from quote refresh.</p></details>
      </aside>
      <div className="workspace-chart-column">
        <MarketChartTerminal snapshot={snapshot} symbol={symbol} onSymbolChange={selectSymbol} quoteRefreshMs={preferences.quoteSeconds * 1000} compact />
        <section className="workspace-thesis compact-thesis" aria-label={symbol + " research thesis"}>
          <div className="thesis-summary">
            <strong>{symbol} · {candidate?.direction ?? "No scanner thesis"}</strong>
            <span>Entry <b>{money(plan?.entry)}</b></span>
            <span>Invalidation <b>{money(plan?.invalidation)}</b></span>
            <span>Targets <b>{money(plan?.target_1)} / {money(plan?.target_2)}</b></span>
            <button type="button" className="secondary-action" onClick={toggleWatch} aria-pressed={watched}><Star size={14} aria-hidden="true" />{watched ? "Watching" : "Watch"}</button>
            <button type="button" className="primary-action" onClick={() => updatePreferences({ dock: "options" })}>Options chain</button>
          </div>
          <p className={stale ? "workspace-warning" : "thesis-caption"}>{stale ? "Stale or unverified plan — research only." : "Underlying price levels — not option premiums or submitted stops."}</p>
          <details className="workspace-evidence"><summary>Why this setup? · evidence & council</summary>
            {candidate ? <><p>{candidate.move_thesis.trigger}</p><p>{candidate.move_thesis.horizon_sessions}-session expected range ±{money(candidate.move_thesis.expected_move_dollars)} · magnitude, not direction.</p><h3>Supports</h3><ul>{candidate.move_thesis.supporting_evidence.map((item) => <li key={item}>{item}</li>)}</ul><h3>Conflicts</h3><ul>{candidate.move_thesis.conflicting_evidence.map((item) => <li key={item}>{item}</li>)}</ul><p>Signal {new Date(candidate.as_of).toLocaleString()} · scores are not calibrated probabilities.</p></> : <p>No current scanner thesis for this ticker. Chart and manual chain remain available.</p>}
            <div className="workspace-review"><button type="button" className="secondary-action" disabled={pending || !candidate?.actionable || stale} onClick={review}>{pending ? "Reviewing…" : "Review with council"}</button><button type="button" className="secondary-action" onClick={onOpenResearch}>Full research</button><span>{matchingDecision ? "Last " + symbol + " council: " + snapshot.council.support_count + " support · risk " + (snapshot.risk.approved ? "approved" : "vetoed") : "No council review for this ticker"}</span></div>
          </details>
          {message && <p className="run-status" role="status">{message}</p>}
        </section>
        <TradingDock symbol={symbol} onSymbolChange={selectSymbol} platform={platform} accountError={accountError} onRefreshAccount={onRefreshAccount} />
      </div>
    </div>
    <dialog ref={filterDialog} className="scanner-filter-dialog" aria-labelledby="filter-dialog-title">
      <div className="dialog-heading"><h2 id="filter-dialog-title">Scanner filters</h2><button type="button" onClick={() => filterDialog.current?.close()} aria-label="Close scanner filters"><X size={18} aria-hidden="true" /></button></div>
      <ScannerFilterBar filters={filters} onChange={(next) => { setFilters(next); updatePreferences({ rail: "scanner" }); }} matches={candidates.length} total={scanner.candidates.length} />
      <button type="button" className="primary-action" onClick={() => filterDialog.current?.close()}>Show {candidates.length} matches</button>
    </dialog>
  </div>;
}
