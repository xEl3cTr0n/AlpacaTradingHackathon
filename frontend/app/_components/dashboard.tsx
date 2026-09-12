"use client";

import { Activity, BookOpen, ChartNoAxesCombined, ChevronRight, ScanSearch, ShieldCheck, WalletCards } from "lucide-react";
import dynamic from "next/dynamic";
import { useState } from "react";
import useSWR from "swr";
import { TradingWorkspace } from "./trading-workspace";
import type { DecisionSnapshot, PlatformSnapshot, ScannerSnapshot } from "@/lib/types";

const OpportunityScanner = dynamic(() => import("./opportunity-scanner").then((m) => m.OpportunityScanner));
const PortfolioView = dynamic(() => import("./portfolio-view").then((m) => m.PortfolioView));
const StrategyLab = dynamic(() => import("./strategy-lab").then((m) => m.StrategyLab));
const BacktestView = dynamic(() => import("./backtest-view").then((m) => m.BacktestView));
const AgentOps = dynamic(() => import("./agent-ops").then((m) => m.AgentOps));
const MarketLayers = dynamic(() => import("./market-layers").then((m) => m.MarketLayers));

type View = "workspace" | "scanner" | "portfolio" | "research";
type ResearchView = "strategy" | "context" | "backtests" | "ops";
const navItems = [
  { id: "workspace" as const, label: "Trade", icon: ChartNoAxesCombined },
  { id: "scanner" as const, label: "Scanners", icon: ScanSearch },
  { id: "portfolio" as const, label: "Portfolio", icon: WalletCards },
  { id: "research" as const, label: "Research", icon: BookOpen },
];
const researchItems = [
  { id: "strategy" as const, label: "Thesis & council" },
  { id: "context" as const, label: "Market context" },
  { id: "backtests" as const, label: "Backtests" },
  { id: "ops" as const, label: "Worker & tools" },
];

async function platformFetcher(url: string): Promise<PlatformSnapshot> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error("Account refresh failed");
  return response.json() as Promise<PlatformSnapshot>;
}

export function Dashboard({ initialSnapshot, initialPlatform, initialScanner }: {
  initialSnapshot: DecisionSnapshot;
  initialPlatform: PlatformSnapshot | null;
  initialScanner: ScannerSnapshot;
}) {
  const [view, setView] = useState<View>("workspace");
  const [research, setResearch] = useState<ResearchView>("strategy");
  const [snapshot, setSnapshot] = useState(initialSnapshot);
  const [symbol, setSymbol] = useState(initialScanner.candidates[0]?.symbol ?? initialSnapshot.market.symbol);
  const [openTicket, setOpenTicket] = useState(false);
  const { data: platform, error, mutate: refreshAccount, isValidating: refreshingAccount } = useSWR("/api/v1/platform", platformFetcher, {
    fallbackData: initialPlatform ?? undefined, refreshInterval: 30_000, dedupingInterval: 20_000,
    refreshWhenHidden: false, refreshWhenOffline: false, errorRetryCount: 1,
  });
  const accountPositive = (platform?.account.day_pnl ?? 0) >= 0;

  function openResearch() { setResearch("strategy"); setView("research"); }
  function openSymbol(next: string) { setOpenTicket(false); setSymbol(next); setView("workspace"); }

  return <main className="platform-shell terminal-shell">
    <a className="workspace-skip" href="#platform-content">Skip to workspace</a>
    <aside className="platform-sidebar" aria-label="Primary navigation">
      <a className="platform-brand" href="#platform-content" aria-label="RegimeShift home" onClick={() => setView("workspace")}><span className="brand-mark"><Activity size={19} aria-hidden="true" /></span><span>REGIME<b>SHIFT</b></span></a>
      <nav className="platform-nav"><p>Workspace</p>{navItems.map(({ id, label, icon: Icon }) => <button key={id} type="button" className={view === id ? "active" : ""} aria-pressed={view === id} onClick={() => setView(id)}><Icon size={18} aria-hidden="true" /><span>{label}</span>{view === id && <ChevronRight size={15} aria-hidden="true" />}</button>)}</nav>
      <div className="watchlist"><div className="sidebar-section-title">Market charts</div>{["SPY", "QQQ", "IWM"].map((item) => <button key={item} type="button" onClick={() => openSymbol(item)}><span>{item}</span><ChartNoAxesCombined size={14} aria-hidden="true" /></button>)}</div>
      <div className="sidebar-safety"><ShieldCheck size={18} aria-hidden="true" /><div><strong>Paper only</strong><span>Hard risk enforced</span></div></div>
    </aside>
    <section className="platform-main">
      <header className="platform-topbar">
        <div className="market-status"><span className={`connection-dot ${error || !platform?.automation.market_open ? "waiting" : ""}`} aria-hidden="true" /><div><strong>{error ? "Account refresh failed" : !platform ? "Account unavailable" : platform.automation.market_open ? "Paper market open" : "Paper market closed"}</strong><small>{platform ? `Account as of ${new Date(platform.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Waiting for account data"} · worker heartbeat unverified</small></div></div>
        <div className="topbar-account"><div><span>Paper equity</span><strong>{platform ? `$${platform.account.equity.toLocaleString(undefined, { maximumFractionDigits: 2 })}` : "—"}</strong></div><div><span>Today</span><strong className={accountPositive ? "positive" : "negative"}>{platform ? `${accountPositive ? "+" : ""}$${platform.account.day_pnl.toFixed(2)}` : "—"}</strong></div></div>
      </header>
      <nav className="mobile-tabs" aria-label="Mobile navigation">{navItems.map(({ id, label, icon: Icon }) => <button key={id} type="button" aria-pressed={view === id} className={view === id ? "active" : ""} onClick={() => setView(id)}><Icon size={17} aria-hidden="true" />{label}</button>)}</nav>
      <div className="platform-content" id="platform-content" tabIndex={-1}>
        {view === "workspace" && <TradingWorkspace snapshot={snapshot} initialScanner={initialScanner} symbol={symbol} onSymbolChange={setSymbol} onSnapshot={setSnapshot} onOpenScanner={() => setView("scanner")} onOpenResearch={openResearch} initialTicketOpen={openTicket} />}
        {view === "scanner" && <OpportunityScanner initialScanner={initialScanner} onSnapshot={(next) => { setSnapshot(next); openSymbol(next.market.symbol); }} onOpenManual={(next) => { openSymbol(next); setOpenTicket(true); }} />}
        {view === "portfolio" && (platform ? <PortfolioView platform={platform} onOpenStrategy={openResearch} /> : <section className="panel workspace-thesis"><h1>Account unavailable</h1><p>Market research remains available. No balance or position values are being inferred.</p><button type="button" className="secondary-action" disabled={refreshingAccount} onClick={() => void refreshAccount()}>Retry account</button></section>)}
        {view === "research" && <div className="view-stack"><nav className="research-tabs" aria-label="Research sections">{researchItems.map((item) => <button key={item.id} type="button" aria-pressed={research === item.id} className={research === item.id ? "active" : ""} onClick={() => setResearch(item.id)}>{item.label}</button>)}</nav>
          {research === "strategy" && <StrategyLab snapshot={snapshot} onSnapshot={setSnapshot} />}
          {research === "context" && <><h1>Market context · {snapshot.market.symbol}</h1><MarketLayers snapshot={snapshot} /></>}
          {research === "backtests" && <BacktestView />}
          {research === "ops" && (platform ? <AgentOps platform={platform} snapshot={snapshot} /> : <p role="status">Worker/account details unavailable. Retry from Portfolio.</p>)}
        </div>}
      </div>
      <footer className="platform-footer"><span>Paper simulation · not live trading</span><span>Account updates 30s · simulation fills do not prove live performance</span></footer>
    </section>
  </main>;
}
