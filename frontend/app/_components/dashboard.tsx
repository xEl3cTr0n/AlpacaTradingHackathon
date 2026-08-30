"use client";

import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  Gauge,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { useState, useTransition } from "react";
import { runAnalysis } from "@/app/actions";
import { AgentCard } from "@/app/_components/agent-card";
import { PriceChart } from "@/app/_components/price-chart";
import type { DecisionSnapshot } from "@/lib/types";

const pct = (value: number, digits = 0) => `${(value * 100).toFixed(digits)}%`;

export function Dashboard({ initialSnapshot }: { initialSnapshot: DecisionSnapshot }) {
  const [snapshot, setSnapshot] = useState(initialSnapshot);
  const [symbol, setSymbol] = useState(initialSnapshot.market.symbol);
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();
  const positive = snapshot.market.price_change_pct >= 0;
  const ChangeIcon = positive ? ArrowUpRight : ArrowDownRight;

  function analyze() {
    setError("");
    startTransition(async () => {
      try {
        setSnapshot(await runAnalysis(symbol));
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Analysis failed. Try again.");
      }
    });
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#main-content" aria-label="RegimeShift AI dashboard home">
          <span className="brand-mark"><Activity size={20} aria-hidden="true" /></span>
          <span>REGIME<span>SHIFT</span></span>
        </a>
        <div className="topbar-status">
          <span className="connection-dot" aria-hidden="true" />
          <span>{snapshot.mode}</span>
          <span className="paper-badge"><LockKeyhole size={13} aria-hidden="true" /> Preview only</span>
        </div>
      </header>

      <div className="workspace" id="main-content">
        <section className="command-row" aria-labelledby="dashboard-title">
          <div>
            <p className="eyebrow">Autonomous decision cockpit</p>
            <h1 id="dashboard-title">Market regime intelligence</h1>
            <p className="subhead">Evidence first. Risk always has the final word.</p>
          </div>
          <div className="symbol-control">
            <label htmlFor="symbol">Underlying</label>
            <input
              id="symbol"
              value={symbol}
              onChange={(event) => setSymbol(event.target.value.toUpperCase())}
              maxLength={10}
              spellCheck={false}
            />
            <button type="button" onClick={analyze} disabled={pending}>
              <RefreshCw size={17} className={pending ? "spinning" : ""} aria-hidden="true" />
              {pending ? "Analyzing" : "Run analysis"}
            </button>
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
        </section>

        <section className="metric-strip" aria-label="Current market summary">
          <article>
            <span>Underlying</span>
            <strong>{snapshot.market.symbol} <small>${snapshot.market.current_price.toFixed(2)}</small></strong>
            <p className={positive ? "positive" : "negative"}>
              <ChangeIcon size={15} aria-hidden="true" /> {positive ? "+" : ""}{snapshot.market.price_change_pct.toFixed(2)}% today
            </p>
          </article>
          <article>
            <span>Detected regime</span>
            <strong className="capitalize">{snapshot.regime.direction}</strong>
            <p>{snapshot.regime.volatility} volatility</p>
          </article>
          <article>
            <span>Regime confidence</span>
            <strong>{pct(snapshot.regime.confidence)}</strong>
            <div className="confidence-track" aria-label={`${pct(snapshot.regime.confidence)} confidence`}>
              <span style={{ width: pct(snapshot.regime.confidence) }} />
            </div>
          </article>
          <article>
            <span>Risk decision</span>
            <strong className={snapshot.risk.approved ? "positive" : "negative"}>
              {snapshot.risk.approved ? "Approved" : "Vetoed"}
            </strong>
            <p>{snapshot.risk.approved_contracts} contract preview</p>
          </article>
        </section>

        <section className="primary-grid">
          <article className="panel market-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Market tape</p>
                <h2>{snapshot.market.symbol} price structure</h2>
              </div>
              <span className="source-label">{snapshot.market.source}</span>
            </div>
            <PriceChart prices={snapshot.market.prices} symbol={snapshot.market.symbol} />
            <div className="indicator-row">
              <div><span>EMA 20</span><strong>{snapshot.regime.metrics.ema_fast.toFixed(2)}</strong></div>
              <div><span>EMA 50</span><strong>{snapshot.regime.metrics.ema_slow.toFixed(2)}</strong></div>
              <div><span>RSI 14</span><strong>{snapshot.regime.metrics.rsi_14.toFixed(1)}</strong></div>
              <div><span>Realized vol</span><strong>{pct(snapshot.regime.metrics.realized_volatility, 1)}</strong></div>
            </div>
          </article>

          <aside className="panel regime-panel">
            <div className="panel-heading">
              <div><p className="eyebrow">Classifier output</p><h2>Regime map</h2></div>
              <Gauge size={20} aria-hidden="true" />
            </div>
            <div className="regime-label">
              <span className="pulse-dot" aria-hidden="true" />
              {snapshot.regime.label.replace("_", " / ")}
            </div>
            <div className="axis-block">
              <div className="axis-label"><span>Bearish</span><span>Direction</span><span>Bullish</span></div>
              <div className="axis-track">
                <span style={{ left: `${(snapshot.regime.metrics.trend_score + 1) * 50}%` }} />
              </div>
            </div>
            <div className="axis-block">
              <div className="axis-label"><span>Low</span><span>Volatility</span><span>High</span></div>
              <div className="axis-track volatility">
                <span style={{ left: pct(snapshot.regime.metrics.volatility_percentile) }} />
              </div>
            </div>
            <p className="regime-rationale">{snapshot.regime.rationale}</p>
            <div className="as-of"><Clock3 size={14} aria-hidden="true" /> As of {new Date(snapshot.market.as_of).toLocaleString()}</div>
          </aside>
        </section>

        <section className="section-block" aria-labelledby="agents-title">
          <div className="section-heading">
            <div><p className="eyebrow">Adversarial review</p><h2 id="agents-title">Agent council</h2></div>
            <p>Each agent exposes its evidence and confidence.</p>
          </div>
          <div className="agent-grid">
            {snapshot.agents.map((agent) => <AgentCard key={agent.agent} verdict={agent} />)}
          </div>
        </section>

        <section className="decision-grid" aria-labelledby="decision-title">
          <article className="panel strategy-panel">
            <div className="panel-heading">
              <div><p className="eyebrow">Policy recommendation</p><h2 id="decision-title">{snapshot.strategy.display_name}</h2></div>
              <span className={`decision-chip ${snapshot.risk.approved ? "approved" : "vetoed"}`}>
                {snapshot.risk.approved ? <CheckCircle2 size={15} aria-hidden="true" /> : <ShieldCheck size={15} aria-hidden="true" />}
                {snapshot.strategy.status}
              </span>
            </div>
            <p className="strategy-thesis">{snapshot.strategy.thesis}</p>
            <ol className="legs">
              {snapshot.strategy.structure.map((leg, index) => <li key={leg}><span>{index + 1}</span>{leg}</li>)}
            </ol>
          </article>
          <aside className="panel risk-panel">
            <div className="risk-number">
              <span><CircleDollarSign size={17} aria-hidden="true" /> Maximum preview loss</span>
              <strong>${snapshot.strategy.max_loss_dollars.toLocaleString()}</strong>
              <small>{pct(snapshot.strategy.risk_percent, 2)} of modeled equity</small>
            </div>
            <ul className="risk-reasons">
              {snapshot.risk.reasons.map((reason) => <li key={reason}><ShieldCheck size={15} aria-hidden="true" />{reason}</li>)}
            </ul>
          </aside>
        </section>

        <footer>
          <span>Decision {snapshot.decision_id.slice(0, 12)}</span>
          <span>{snapshot.disclaimer}</span>
        </footer>
      </div>
    </main>
  );
}

