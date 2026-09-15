"use client";

import { Activity, RefreshCw, Search } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";
import { TradingWorkspace } from "./trading-workspace";
import { normalizeTicker } from "@/lib/workspace-preferences";
import { useWorkspacePreferences } from "@/lib/use-workspace-preferences";
import type { DecisionSnapshot, PlatformSnapshot, ScannerSnapshot } from "@/lib/types";

const PortfolioView = dynamic(() => import("./portfolio-view").then((m) => m.PortfolioView));
const StrategyLab = dynamic(() => import("./strategy-lab").then((m) => m.StrategyLab));
const BacktestView = dynamic(() => import("./backtest-view").then((m) => m.BacktestView));
const AgentOps = dynamic(() => import("./agent-ops").then((m) => m.AgentOps));
const MarketLayers = dynamic(() => import("./market-layers").then((m) => m.MarketLayers));
const OpportunityScanner = dynamic(() => import("./opportunity-scanner").then((m) => m.OpportunityScanner));

type View = "workspace" | "portfolio" | "research";
type ResearchView = "strategy" | "context" | "backtests" | "ops" | "scanner";
const navItems: { id: View; label: string }[] = [
  { id: "workspace", label: "Trade" }, { id: "portfolio", label: "Portfolio" }, { id: "research", label: "Research" },
];
const researchItems: { id: ResearchView; label: string }[] = [
  { id: "strategy", label: "Thesis & council" }, { id: "context", label: "Market context" },
  { id: "backtests", label: "Backtests" }, { id: "ops", label: "Worker & tools" },
  { id: "scanner", label: "Scanner diagnostics" },
];
async function platformFetcher(url: string): Promise<PlatformSnapshot> {
  const response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(15_000) });
  if (!response.ok) throw new Error("Account refresh failed");
  return response.json() as Promise<PlatformSnapshot>;
}
const dollars = (value: number) => value.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export function Dashboard({ initialSnapshot, initialPlatform, initialScanner }: {
  initialSnapshot: DecisionSnapshot; initialPlatform: PlatformSnapshot | null; initialScanner: ScannerSnapshot;
}) {
  const [view, setView] = useState<View>("workspace");
  const [research, setResearch] = useState<ResearchView>("strategy");
  const [snapshot, setSnapshot] = useState(initialSnapshot);
  const [preferences, updatePreferences] = useWorkspacePreferences();
  const searchRef = useRef<HTMLInputElement>(null);
  const symbol = preferences.symbol;
  const { data: platform, error, mutate: refreshAccount, isValidating: refreshingAccount } = useSWR("/api/v1/platform", platformFetcher, {
    fallbackData: initialPlatform ?? undefined, refreshInterval: 30_000, dedupingInterval: 20_000,
    refreshWhenHidden: false, refreshWhenOffline: false, errorRetryCount: 1,
  });

  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); searchRef.current?.focus(); searchRef.current?.select();
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);

  function openResearch(section: ResearchView = "strategy") { setResearch(section); setView("research"); }
  function openSymbol(next: string) {
    const value = normalizeTicker(next);
    if (value) { updatePreferences({ symbol: value }); setView("workspace"); }
  }

  return <main className="platform-shell terminal-shell focused-shell">
    <a className="workspace-skip" href="#platform-content">Skip to workspace</a>
    <header className="terminal-header">
      <button type="button" className="terminal-brand" onClick={() => setView("workspace")} aria-label="RegimeShift Trade"><Activity size={20} aria-hidden="true" /><span>REGIME<span className="positive">SHIFT</span></span></button>
      <nav className="terminal-nav" aria-label="Primary navigation">{navItems.map(({ id, label }) => <button key={id} type="button" className={view === id ? "active" : ""} aria-pressed={view === id} onClick={() => setView(id)}>{label}</button>)}</nav>
      <form className="terminal-search" key={symbol} onSubmit={(event) => { event.preventDefault(); openSymbol(String(new FormData(event.currentTarget).get("symbol") ?? "")); }}>
        <label htmlFor="workspace-symbol" className="sr-only">Search ticker</label>
        <Search size={15} aria-hidden="true" /><input ref={searchRef} id="workspace-symbol" name="symbol" defaultValue={symbol} list="workspace-symbols" pattern="[A-Za-z][A-Za-z.]{0,9}" maxLength={10} required autoComplete="off" spellCheck={false} aria-keyshortcuts="Meta+K Control+K" />
        <button type="submit">Go <kbd>⌘K</kbd></button>
        <datalist id="workspace-symbols">{[...new Set([...preferences.watchlist, ...initialScanner.candidates.map((c) => c.symbol)])].map((ticker) => <option key={ticker} value={ticker} />)}</datalist>
      </form>
      <span className="paper-badge">PAPER ONLY</span>
    </header>
    <div className="terminal-status" aria-label="Account and automation status">
      <span className={error || !platform ? "negative" : ""}>{error ? "Account stale · refresh failed" : !platform ? "Account unavailable" : platform.automation.market_open ? "Market open" : "Market closed"}</span>
      <span>Equity <b>{platform ? dollars(platform.account.equity) : "—"}</b></span>
      <span>Today <b className={(platform?.account.day_pnl ?? 0) >= 0 ? "positive" : "negative"}>{platform ? dollars(platform.account.day_pnl) : "—"}</b></span>
      <span>Account {platform ? new Date(platform.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}</span>
      <button type="button" onClick={() => openResearch("ops")}>Worker: unverified · {platform?.automation.scan_interval_minutes ?? 5}m checks</button>
      <span>Hard risk enforced</span>
      {platform?.account.trading_blocked && <strong className="negative">Broker trading blocked</strong>}
      <button type="button" className="status-refresh" onClick={() => void refreshAccount()} disabled={refreshingAccount} aria-label="Refresh paper account"><RefreshCw size={14} aria-hidden="true" /></button>
    </div>
    <section className="platform-main">
      <div className="platform-content" id="platform-content" tabIndex={-1}>
        {view === "workspace" && <TradingWorkspace snapshot={snapshot} initialScanner={initialScanner} symbol={symbol} onSymbolChange={openSymbol} onSnapshot={setSnapshot} onOpenResearch={() => openResearch()} platform={platform ?? null} accountError={Boolean(error)} onRefreshAccount={() => void refreshAccount()} />}
        {view === "portfolio" && (platform ? <PortfolioView platform={platform} onOpenStrategy={() => openResearch()} /> : <section className="panel workspace-thesis"><h1>Account unavailable</h1><p>Market research remains available. Retry account above.</p></section>)}
        {view === "research" && <div className="view-stack"><nav className="research-tabs" aria-label="Research sections">{researchItems.map((item) => <button key={item.id} type="button" aria-pressed={research === item.id} className={research === item.id ? "active" : ""} onClick={() => setResearch(item.id)}>{item.label}</button>)}</nav>
          {research === "strategy" && <StrategyLab snapshot={snapshot} onSnapshot={setSnapshot} />}
          {research === "context" && <><h1>Last council context · {snapshot.market.symbol}</h1><MarketLayers snapshot={snapshot} /></>}
          {research === "backtests" && <BacktestView />}
          {research === "ops" && (platform ? <AgentOps platform={platform} snapshot={snapshot} /> : <p role="status">Worker/account details unavailable. Retry account above.</p>)}
          {research === "scanner" && <OpportunityScanner initialScanner={initialScanner} onSnapshot={(next) => { setSnapshot(next); openSymbol(next.market.symbol); }} onOpenManual={(next) => { openSymbol(next); updatePreferences({ dock: "options" }); }} />}
        </div>}
      </div>
      <footer className="platform-footer"><span>Paper simulation · not live trading</span><span>Quotes, scanner and worker run at different intervals. Simulated fills do not prove live performance.</span></footer>
    </section>
  </main>;
}
