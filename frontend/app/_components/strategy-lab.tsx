"use client";

import { Bot, CheckCircle2, CircleDollarSign, Clock3, Download, Gauge, Layers3, RefreshCw, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { useState, useTransition } from "react";
import { runAnalysis } from "@/app/actions";
import { AgentCard } from "@/app/_components/agent-card";
import { PriceChart } from "@/app/_components/price-chart";
import { buildDecisionReceipt, decisionReceiptFilename } from "@/lib/decision-receipt";
import type { AnalysisControls, DecisionSnapshot, InstrumentMode, StrategyMode } from "@/lib/types";

const pct = (value: number, digits = 0) => `${(value * 100).toFixed(digits)}%`;

export function StrategyLab({ snapshot, onSnapshot }: { snapshot: DecisionSnapshot; onSnapshot: (value: DecisionSnapshot) => void }) {
  const [symbol, setSymbol] = useState(snapshot.market.symbol);
  const [controls, setControls] = useState<AnalysisControls>(snapshot.controls);
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState("Ready to run a new council review.");
  const rotationMaxScore = Math.max(...snapshot.sector_rotation.sectors.map((sector) => Math.abs(sector.rotation_score)), 0.001);

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

  function downloadReceipt() {
    const receipt = buildDecisionReceipt(snapshot);
    const url = URL.createObjectURL(new Blob([JSON.stringify(receipt, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = decisionReceiptFilename(snapshot);
    anchor.click();
    URL.revokeObjectURL(url);
    setMessage(`Decision receipt exported for ${snapshot.market.symbol}.`);
  }

  return (
    <div className="view-stack">
      <header className="view-heading"><div><p className="eyebrow">Autonomous strategy workbench</p><h1>Strategy Lab</h1><p>Change policy constraints, run the council, and inspect every decision.</p></div><div className="heading-actions"><button type="button" className="secondary-action" onClick={downloadReceipt}><Download size={15} aria-hidden="true" /> Export decision receipt</button><span className="decision-chip approved"><ShieldCheck size={15} aria-hidden="true" /> Risk gate enforced</span></div></header>

      <section className="strategy-controls panel" aria-labelledby="controls-title">
        <div className="controls-heading"><SlidersHorizontal size={18} aria-hidden="true" /><div><h2 id="controls-title">Run configuration</h2><p>These settings are sent to the backend policy engine.</p></div></div>
        <div className="control-grid">
          <label>Underlying<input value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} maxLength={10} /></label>
          <label>Strategy mode<select value={controls.strategy_mode} onChange={(event) => setControls({ ...controls, strategy_mode: event.target.value as StrategyMode })}><option value="adaptive">Adaptive to regime</option><option value="bullish">Bullish test</option><option value="bearish">Bearish test</option><option value="neutral">Neutral premium</option></select></label>
          <label>Instrument<select value={controls.instrument_mode} onChange={(event) => setControls({ ...controls, instrument_mode: event.target.value as InstrumentMode })}><option value="auto">Auto · prefer XSP</option><option value="index_option">Index option</option><option value="equity_option">ETF / equity option</option></select></label>
          <label>Risk per trade<select value={controls.max_risk_pct} onChange={(event) => setControls({ ...controls, max_risk_pct: Number(event.target.value) })}><option value="0.0025">0.25%</option><option value="0.005">0.50%</option><option value="0.0075">0.75%</option><option value="0.01">1.00% · max</option></select></label>
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
        <article><span>Risk decision</span><strong className={snapshot.risk.approved ? "positive" : "negative"}>{snapshot.risk.approved ? "Approved" : "Vetoed"}</strong><p>{snapshot.council.support_count}–{snapshot.council.oppose_count} council vote</p></article>
      </section>

      <section className="decision-intel-grid" aria-label="Swing, voting, and tool evidence">
        <article className="panel swing-panel">
          <div className="panel-heading"><div><p className="eyebrow">Validated 20-session setup</p><h2>Swing structure</h2></div><span className={`vote-chip ${snapshot.swing.signal === "neutral" ? "abstain" : "support"}`}>{snapshot.swing.signal.replaceAll("_", " ")}</span></div>
          <div className="swing-range"><span style={{ left: `${snapshot.swing.range_position * 100}%` }} /></div>
          <div className="swing-labels"><span>Low ${snapshot.swing.swing_low.toFixed(2)}</span><span>Price location</span><span>High ${snapshot.swing.swing_high.toFixed(2)}</span></div>
          <p>{snapshot.swing.rationale}</p>
        </article>
        <article className="panel council-panel">
          <div className="panel-heading"><div><p className="eyebrow">Deterministic consensus</p><h2>{snapshot.council.votes.length}-agent vote</h2></div><strong>{pct(snapshot.council.weighted_support)}</strong></div>
          <div className="vote-summary"><span className="support">{snapshot.council.support_count}/{snapshot.council.required_support} support</span><span className="oppose">{snapshot.council.oppose_count} oppose</span><span className="abstain">{snapshot.council.abstain_count} abstain</span></div>
          <ul>{snapshot.council.votes.map((vote) => <li key={vote.agent}><strong>{vote.agent}</strong><span className={`vote-chip ${vote.vote}`}>{vote.vote}</span><small>{pct(vote.confidence)}</small></li>)}</ul>
        </article>
        <article className="panel tools-panel">
          <div className="panel-heading"><div><p className="eyebrow">Hackathon toolchain</p><h2>Alpaca evidence</h2></div><Bot size={19} aria-hidden="true" /></div>
          <ul>{snapshot.tool_evidence.map((tool) => <li key={tool.provider}><div><strong>{tool.provider}</strong><small>{tool.capability}</small></div><span className={`tool-status ${tool.status}`}>{tool.status}</span></li>)}</ul>
        </article>
      </section>

      <section className="primary-grid">
        <article className="panel market-panel"><div className="panel-heading"><div><p className="eyebrow">Market tape</p><h2>{snapshot.market.symbol} price structure</h2></div><span className="source-label">{snapshot.market.source}</span></div><PriceChart prices={snapshot.market.prices} symbol={snapshot.market.symbol} /><div className="indicator-row"><div><span>EMA 20</span><strong>{snapshot.regime.metrics.ema_fast.toFixed(2)}</strong></div><div><span>EMA 50</span><strong>{snapshot.regime.metrics.ema_slow.toFixed(2)}</strong></div><div><span>RSI 14</span><strong>{snapshot.regime.metrics.rsi_14.toFixed(1)}</strong></div><div><span>Realized vol</span><strong>{pct(snapshot.regime.metrics.realized_volatility, 1)}</strong></div></div></article>
        <aside className="panel regime-panel"><div className="panel-heading"><div><p className="eyebrow">Classifier output</p><h2>Regime map</h2></div><Gauge size={20} aria-hidden="true" /></div><div className="regime-label"><span className="pulse-dot" />{snapshot.regime.label.replace("_", " / ")}</div><div className="axis-block"><div className="axis-label"><span>Bearish</span><span>Direction</span><span>Bullish</span></div><div className="axis-track"><span style={{ left: `${(snapshot.regime.metrics.trend_score + 1) * 50}%` }} /></div></div><div className="axis-block"><div className="axis-label"><span>Low</span><span>Volatility</span><span>High</span></div><div className="axis-track volatility"><span style={{ left: pct(snapshot.regime.metrics.volatility_percentile) }} /></div></div><p className="regime-rationale">{snapshot.regime.rationale}</p><div className="as-of"><Clock3 size={14} aria-hidden="true" /> As of {new Date(snapshot.market.as_of).toLocaleString()}</div></aside>
      </section>

      <section className="panel rotation-panel" aria-labelledby="rotation-title">
        <div className="panel-heading">
          <div><p className="eyebrow">Cross-market confirmation</p><h2 id="rotation-title">Sector rotation</h2></div>
          <span className={`rotation-signal ${snapshot.sector_rotation.signal}`}><Layers3 size={15} aria-hidden="true" />{snapshot.sector_rotation.signal.replace("_", " ")}</span>
        </div>
        <div className="rotation-summary">
          <div><span>Breadth vs SPY</span><strong>{pct(snapshot.sector_rotation.breadth)}</strong></div>
          <div><span>Signal confidence</span><strong>{pct(snapshot.sector_rotation.confidence)}</strong></div>
          <div><span>Leaders</span><strong>{snapshot.sector_rotation.leaders.join(" · ")}</strong></div>
          <div><span>Laggards</span><strong>{snapshot.sector_rotation.laggards.join(" · ")}</strong></div>
        </div>
        <p className="rotation-rationale">{snapshot.sector_rotation.rationale}</p>
        <div className="rotation-table-wrap">
          <table className="rotation-table">
            <caption>Sector ETF performance and relative strength ranked against SPY</caption>
            <thead><tr><th>Rank</th><th>Sector</th><th>1M</th><th>3M</th><th>Relative score</th><th>Phase</th></tr></thead>
            <tbody>
              {snapshot.sector_rotation.sectors.map((sector) => {
                const barWidth = `${Math.max(5, Math.abs(sector.rotation_score) / rotationMaxScore * 100)}%`;
                return <tr key={sector.symbol}><td>#{sector.rank}</td><td><strong>{sector.symbol}</strong><span>{sector.name}</span></td><td className={sector.one_month_return >= 0 ? "positive" : "negative"}>{pct(sector.one_month_return, 1)}</td><td className={sector.three_month_return >= 0 ? "positive" : "negative"}>{pct(sector.three_month_return, 1)}</td><td><div className={`rotation-bar ${sector.rotation_score >= 0 ? "positive-bar" : "negative-bar"}`}><span style={{ width: barWidth }} /></div><small>{sector.rotation_score >= 0 ? "+" : ""}{pct(sector.rotation_score, 1)}</small></td><td><span className={`phase-chip ${sector.phase}`}>{sector.phase}</span></td></tr>;
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel microstructure-panel" aria-labelledby="microstructure-title">
        <div className="panel-heading">
          <div><p className="eyebrow">Professor framework · Alpaca chain</p><h2 id="microstructure-title">Options body language</h2></div>
          <span className={`rotation-signal ${snapshot.options_microstructure.gamma_regime === "amplifying" ? "defensive" : snapshot.options_microstructure.gamma_regime === "stabilizing" ? "risk_on" : "mixed"}`}>{snapshot.options_microstructure.gamma_regime}</span>
        </div>
        <div className="microstructure-grid">
          <div><span>Net GEX</span><strong>{snapshot.options_microstructure.net_gex.toLocaleString(undefined, { maximumFractionDigits: 0 })}</strong></div>
          <div><span>Gamma concentration</span><strong>{snapshot.options_microstructure.gamma_concentration == null ? "N/A" : pct(snapshot.options_microstructure.gamma_concentration)}</strong></div>
          <div><span>Call wall</span><strong>{snapshot.options_microstructure.call_wall?.toFixed(0) ?? "N/A"}</strong></div>
          <div><span>Put wall</span><strong>{snapshot.options_microstructure.put_wall?.toFixed(0) ?? "N/A"}</strong></div>
          <div><span>Chain quality</span><strong>{pct(snapshot.options_microstructure.data_quality)}</strong></div>
          <div><span>Contracts</span><strong>{snapshot.options_microstructure.contract_count}</strong></div>
        </div>
        <p className="rotation-rationale">{snapshot.options_microstructure.rationale}</p>
        <small className="microstructure-source">{snapshot.options_microstructure.source}. GEX is a dealer-position proxy; GEX+, GIV, CR(x), GRIP, and REPH remain off until their required inputs/formulas are available.</small>
      </section>

      <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Adversarial review</p><h2>Agent council</h2></div><p>Independent evidence, thesis, counter-thesis, and deterministic authorization.</p></div><div className="agent-grid">{snapshot.agents.map((agent) => <AgentCard key={agent.agent} verdict={agent} />)}</div></section>

      <section className="decision-grid">
        <article className="panel strategy-panel"><div className="panel-heading"><div><p className="eyebrow">Policy recommendation</p><h2>{snapshot.strategy.display_name}</h2></div><span className={`decision-chip ${snapshot.risk.approved ? "approved" : "vetoed"}`}>{snapshot.risk.approved ? <CheckCircle2 size={15} aria-hidden="true" /> : <ShieldCheck size={15} aria-hidden="true" />}{snapshot.strategy.status}</span></div><p className="strategy-thesis">{snapshot.strategy.thesis}</p><div className="instrument-meta"><span>Signal <strong>{snapshot.strategy.signal_symbol}</strong></span><span>Trade <strong>{snapshot.strategy.underlying_symbol}</strong></span><span>{snapshot.strategy.option_style} · {snapshot.strategy.settlement} settled</span></div><ol className="legs">{snapshot.strategy.structure.map((leg, index) => <li key={leg}><span>{index + 1}</span>{leg}</li>)}</ol><div className="rules-grid"><div><h3>Entry gates</h3><ul>{snapshot.strategy.entry_rules.map((rule) => <li key={rule}>{rule}</li>)}</ul></div><div><h3>Exit policy</h3><ul>{snapshot.strategy.exit_rules.map((rule) => <li key={rule}>{rule}</li>)}</ul></div></div></article>
        <aside className="panel risk-panel"><div className="risk-number"><span><CircleDollarSign size={17} aria-hidden="true" /> Worst-case position loss</span><strong>${snapshot.strategy.max_loss_dollars.toLocaleString()}</strong><small>{pct(snapshot.strategy.risk_percent, 2)} of modeled equity</small><span>Managed stop <b>−${snapshot.strategy.stop_loss_dollars.toLocaleString()}</b> ({pct(snapshot.strategy.stop_loss_fraction)})</span></div><ul className="risk-reasons">{snapshot.risk.reasons.map((reason) => <li key={reason}><ShieldCheck size={15} aria-hidden="true" />{reason}</li>)}</ul></aside>
      </section>
    </div>
  );
}
