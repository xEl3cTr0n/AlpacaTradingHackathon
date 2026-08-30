"use client";

import { Bot, CheckCircle2, CircleDollarSign, Clock3, Gauge, RefreshCw, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { useState, useTransition } from "react";
import { runAnalysis } from "@/app/actions";
import { AgentCard } from "@/app/_components/agent-card";
import { PriceChart } from "@/app/_components/price-chart";
import type { AnalysisControls, DecisionSnapshot, StrategyMode } from "@/lib/types";

const pct = (value: number, digits = 0) => `${(value * 100).toFixed(digits)}%`;

export function StrategyLab({ snapshot, onSnapshot }: { snapshot: DecisionSnapshot; onSnapshot: (value: DecisionSnapshot) => void }) {
  const [symbol, setSymbol] = useState(snapshot.market.symbol);
  const [controls, setControls] = useState<AnalysisControls>(snapshot.controls);
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState("Ready to run a new council review.");

  function analyze() {
    setMessage("Fetching market context and convening the agent council…");
    startTransition(async () => {
      try {
        const result = await runAnalysis(symbol, controls);
        onSnapshot(result);
        setMessage(`Decision complete: ${result.strategy.display_name} is ${result.strategy.status}.`);
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Analysis failed. Check the API connection.");
      }
    });
  }

  return (
    <div className="view-stack">
      <header className="view-heading"><div><p className="eyebrow">Autonomous strategy workbench</p><h1>Strategy Lab</h1><p>Change policy constraints, run the council, and inspect every decision.</p></div><span className="decision-chip approved"><ShieldCheck size={15} aria-hidden="true" /> Risk gate enforced</span></header>

      <section className="strategy-controls panel" aria-labelledby="controls-title">
        <div className="controls-heading"><SlidersHorizontal size={18} aria-hidden="true" /><div><h2 id="controls-title">Run configuration</h2><p>These settings are sent to the backend policy engine.</p></div></div>
        <div className="control-grid">
          <label>Underlying<input value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} maxLength={10} /></label>
          <label>Strategy mode<select value={controls.strategy_mode} onChange={(event) => setControls({ ...controls, strategy_mode: event.target.value as StrategyMode })}><option value="adaptive">Adaptive to regime</option><option value="bullish">Bullish test</option><option value="bearish">Bearish test</option><option value="neutral">Neutral premium</option></select></label>
          <label>Risk per trade<select value={controls.max_risk_pct} onChange={(event) => setControls({ ...controls, max_risk_pct: Number(event.target.value) })}><option value="0.005">0.50%</option><option value="0.01">1.00%</option><option value="0.015">1.50%</option><option value="0.02">2.00%</option></select></label>
          <label>Target expiration<select value={controls.target_dte} onChange={(event) => setControls({ ...controls, target_dte: Number(event.target.value) })}><option value="14">14 DTE</option><option value="30">30 DTE</option><option value="45">45 DTE</option><option value="60">60 DTE</option></select></label>
          <label className="confidence-control">Minimum confidence <output>{pct(controls.min_confidence)}</output><input type="range" min="0.5" max="0.9" step="0.05" value={controls.min_confidence} onChange={(event) => setControls({ ...controls, min_confidence: Number(event.target.value) })} /></label>
          <button type="button" className="primary-action" onClick={analyze} disabled={pending}><RefreshCw size={17} className={pending ? "spinning" : ""} aria-hidden="true" />{pending ? "Council running" : "Run agent council"}</button>
        </div>
        <p className="run-status" role="status" aria-atomic="true"><Bot size={15} aria-hidden="true" />{message}</p>
      </section>

      <section className="metric-strip" aria-label="Current market summary">
        <article><span>Underlying</span><strong>{snapshot.market.symbol} <small>${snapshot.market.current_price.toFixed(2)}</small></strong><p>{snapshot.market.price_change_pct >= 0 ? "+" : ""}{snapshot.market.price_change_pct.toFixed(2)}% today</p></article>
        <article><span>Detected regime</span><strong className="capitalize">{snapshot.regime.direction}</strong><p>{snapshot.regime.volatility} volatility</p></article>
        <article><span>Regime confidence</span><strong>{pct(snapshot.regime.confidence)}</strong><div className="confidence-track"><span style={{ width: pct(snapshot.regime.confidence) }} /></div></article>
        <article><span>Risk decision</span><strong className={snapshot.risk.approved ? "positive" : "negative"}>{snapshot.risk.approved ? "Approved" : "Vetoed"}</strong><p>{snapshot.controls.strategy_mode} policy</p></article>
      </section>

      <section className="primary-grid">
        <article className="panel market-panel"><div className="panel-heading"><div><p className="eyebrow">Market tape</p><h2>{snapshot.market.symbol} price structure</h2></div><span className="source-label">{snapshot.market.source}</span></div><PriceChart prices={snapshot.market.prices} symbol={snapshot.market.symbol} /><div className="indicator-row"><div><span>EMA 20</span><strong>{snapshot.regime.metrics.ema_fast.toFixed(2)}</strong></div><div><span>EMA 50</span><strong>{snapshot.regime.metrics.ema_slow.toFixed(2)}</strong></div><div><span>RSI 14</span><strong>{snapshot.regime.metrics.rsi_14.toFixed(1)}</strong></div><div><span>Realized vol</span><strong>{pct(snapshot.regime.metrics.realized_volatility, 1)}</strong></div></div></article>
        <aside className="panel regime-panel"><div className="panel-heading"><div><p className="eyebrow">Classifier output</p><h2>Regime map</h2></div><Gauge size={20} aria-hidden="true" /></div><div className="regime-label"><span className="pulse-dot" />{snapshot.regime.label.replace("_", " / ")}</div><div className="axis-block"><div className="axis-label"><span>Bearish</span><span>Direction</span><span>Bullish</span></div><div className="axis-track"><span style={{ left: `${(snapshot.regime.metrics.trend_score + 1) * 50}%` }} /></div></div><div className="axis-block"><div className="axis-label"><span>Low</span><span>Volatility</span><span>High</span></div><div className="axis-track volatility"><span style={{ left: pct(snapshot.regime.metrics.volatility_percentile) }} /></div></div><p className="regime-rationale">{snapshot.regime.rationale}</p><div className="as-of"><Clock3 size={14} aria-hidden="true" /> As of {new Date(snapshot.market.as_of).toLocaleString()}</div></aside>
      </section>

      <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Adversarial review</p><h2>Agent council</h2></div><p>Independent evidence, thesis, counter-thesis, and deterministic authorization.</p></div><div className="agent-grid">{snapshot.agents.map((agent) => <AgentCard key={agent.agent} verdict={agent} />)}</div></section>

      <section className="decision-grid">
        <article className="panel strategy-panel"><div className="panel-heading"><div><p className="eyebrow">Policy recommendation</p><h2>{snapshot.strategy.display_name}</h2></div><span className={`decision-chip ${snapshot.risk.approved ? "approved" : "vetoed"}`}>{snapshot.risk.approved ? <CheckCircle2 size={15} aria-hidden="true" /> : <ShieldCheck size={15} aria-hidden="true" />}{snapshot.strategy.status}</span></div><p className="strategy-thesis">{snapshot.strategy.thesis}</p><ol className="legs">{snapshot.strategy.structure.map((leg, index) => <li key={leg}><span>{index + 1}</span>{leg}</li>)}</ol><div className="rules-grid"><div><h3>Entry gates</h3><ul>{snapshot.strategy.entry_rules.map((rule) => <li key={rule}>{rule}</li>)}</ul></div><div><h3>Exit policy</h3><ul>{snapshot.strategy.exit_rules.map((rule) => <li key={rule}>{rule}</li>)}</ul></div></div></article>
        <aside className="panel risk-panel"><div className="risk-number"><span><CircleDollarSign size={17} aria-hidden="true" /> Maximum preview loss</span><strong>${snapshot.strategy.max_loss_dollars.toLocaleString()}</strong><small>{pct(snapshot.strategy.risk_percent, 2)} of modeled equity</small></div><ul className="risk-reasons">{snapshot.risk.reasons.map((reason) => <li key={reason}><ShieldCheck size={15} aria-hidden="true" />{reason}</li>)}</ul></aside>
      </section>
    </div>
  );
}
