"use client";

import {
  Activity,
  Bot,
  Braces,
  ChartNoAxesCombined,
  ChevronRight,
  CircleDollarSign,
  FlaskConical,
  LockKeyhole,
  PanelLeftClose,
  Radio,
  ShieldCheck,
  WalletCards,
} from "lucide-react";
import { useState } from "react";
import { AgentOps } from "@/app/_components/agent-ops";
import { PortfolioView } from "@/app/_components/portfolio-view";
import { StrategyLab } from "@/app/_components/strategy-lab";
import type { DecisionSnapshot, PlatformSnapshot } from "@/lib/types";

type View = "portfolio" | "strategy" | "ops";

const navItems = [
  { id: "portfolio" as const, label: "Portfolio", icon: WalletCards },
  { id: "strategy" as const, label: "Strategy Lab", icon: FlaskConical },
  { id: "ops" as const, label: "Agent Ops", icon: Bot },
];

export function Dashboard({
  initialSnapshot,
  initialPlatform,
}: {
  initialSnapshot: DecisionSnapshot;
  initialPlatform: PlatformSnapshot;
}) {
  const [view, setView] = useState<View>("portfolio");
  const [snapshot, setSnapshot] = useState(initialSnapshot);
  const accountPositive = initialPlatform.account.day_pnl >= 0;

  return (
    <main className="platform-shell">
      <aside className="platform-sidebar" aria-label="Primary navigation">
        <a className="platform-brand" href="#platform-content" aria-label="RegimeShift home">
          <span className="brand-mark"><Activity size={19} aria-hidden="true" /></span>
          <span>REGIME<b>SHIFT</b></span>
        </a>
        <nav className="platform-nav">
          <p>Workspace</p>
          {navItems.map(({ id, label, icon: Icon }) => (
            <button key={id} type="button" className={view === id ? "active" : ""} aria-pressed={view === id} onClick={() => setView(id)}>
              <Icon size={18} aria-hidden="true" /><span>{label}</span>
              {view === id && <ChevronRight size={15} aria-hidden="true" />}
            </button>
          ))}
        </nav>
        <div className="watchlist">
          <div className="sidebar-section-title"><span>Watchlist</span><Radio size={14} aria-hidden="true" /></div>
          {[["SPY", "+0.64%"], ["QQQ", "+0.41%"], ["IWM", "-0.22%"]].map(([symbol, change]) => (
            <button key={symbol} type="button" onClick={() => setView("strategy")}><span>{symbol}</span><strong className={change.startsWith("+") ? "positive" : "negative"}>{change}</strong></button>
          ))}
        </div>
        <div className="sidebar-safety"><ShieldCheck size={18} aria-hidden="true" /><div><strong>Paper only</strong><span>Execution lock active</span></div></div>
      </aside>

      <section className="platform-main">
        <header className="platform-topbar">
          <div className="mobile-brand"><PanelLeftClose size={18} aria-hidden="true" /> RegimeShift</div>
          <div className="market-status"><span className="connection-dot" aria-hidden="true" /><div><strong>Agent online</strong><small>{initialPlatform.mode} telemetry</small></div></div>
          <div className="topbar-account">
            <div><span>Paper equity</span><strong>${initialPlatform.account.equity.toLocaleString(undefined, { maximumFractionDigits: 2 })}</strong></div>
            <div><span>Today</span><strong className={accountPositive ? "positive" : "negative"}>{accountPositive ? "+" : ""}${initialPlatform.account.day_pnl.toFixed(2)}</strong></div>
            <button type="button" onClick={() => setView("strategy")}><Bot size={16} aria-hidden="true" /> Run agent</button>
          </div>
        </header>
        <nav className="mobile-tabs" aria-label="Mobile navigation">
          {navItems.map(({ id, label, icon: Icon }) => <button key={id} type="button" aria-pressed={view === id} className={view === id ? "active" : ""} onClick={() => setView(id)}><Icon size={17} aria-hidden="true" />{label}</button>)}
        </nav>
        <div className="platform-content" id="platform-content">
          {view === "portfolio" && <PortfolioView platform={initialPlatform} onOpenStrategy={() => setView("strategy")} />}
          {view === "strategy" && <StrategyLab snapshot={snapshot} onSnapshot={setSnapshot} />}
          {view === "ops" && <AgentOps platform={initialPlatform} snapshot={snapshot} />}
        </div>
        <footer className="platform-footer"><span><LockKeyhole size={12} aria-hidden="true" /> Paper environment</span><span><Braces size={12} aria-hidden="true" /> Decision {snapshot.decision_id.slice(0, 12)}</span><span><ChartNoAxesCombined size={12} aria-hidden="true" /> Not investment advice</span><span><CircleDollarSign size={12} aria-hidden="true" /> P&amp;L from {initialPlatform.mode}</span></footer>
      </section>
    </main>
  );
}
