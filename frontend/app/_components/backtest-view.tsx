import { CalendarRange, CheckCircle2, DatabaseZap, History, ShieldCheck, ShieldX, TrendingDown, TrendingUp } from "lucide-react";
import { backtestReports, potentialMoveCalibration } from "@/lib/backtest-results";

const pct = (value: number) => `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
const plainPct = (value: number) => `${(value * 100).toFixed(2)}%`;

export function BacktestView() {
  return (
    <div className="view-stack backtest-view">
      <header className="view-heading">
        <div><p className="eyebrow">Historical validation</p><h1>Backtesting</h1><p>Out-of-sample evidence from dated Alpaca market history—not simulated dashboard data.</p></div>
        <span className="decision-chip approved"><DatabaseZap size={15} aria-hidden="true" /> Alpaca historical bars</span>
      </header>
      <section className="backtest-disclosure panel"><ShieldCheck size={19} aria-hidden="true" /><div><strong>Chronological holdouts only</strong><p>Results were frozen before evaluation. They are underlying-direction proxies and do not represent option fills or future returns.</p></div></section>
      <section className="panel backtest-report calibration-report">
        <div className="panel-heading">
          <div><p className="eyebrow">Potential-move calibration · {potentialMoveCalibration.symbols} symbols</p><h2>{potentialMoveCalibration.name}</h2></div>
          <span className="decision-chip approved"><CheckCircle2 size={14} aria-hidden="true" /> Calibration passed</span>
        </div>
        <div className="backtest-meta">
          <span><CalendarRange size={13} />{potentialMoveCalibration.period}</span>
          <span>{potentialMoveCalibration.bars.toLocaleString()} benchmark bars</span>
          <span>Split {new Date(potentialMoveCalibration.splitDate).toLocaleDateString()}</span>
          <span>{potentialMoveCalibration.source}</span>
        </div>
        <div className="backtest-score-grid calibration-score-grid">
          <article><span>Holdout windows</span><strong>{potentialMoveCalibration.holdout.observations.toLocaleString()}</strong><small>Train: {potentialMoveCalibration.train.observations.toLocaleString()}</small></article>
          <article><span>Terminal coverage</span><strong>{plainPct(potentialMoveCalibration.holdout.terminalCoverage)}</strong><small>Train: {plainPct(potentialMoveCalibration.train.terminalCoverage)}</small></article>
          <article><span>Full-path coverage</span><strong>{plainPct(potentialMoveCalibration.holdout.pathCoverage)}</strong><small>Train: {plainPct(potentialMoveCalibration.train.pathCoverage)}</small></article>
          <article><span>Expected move</span><strong>±{plainPct(potentialMoveCalibration.holdout.meanExpectedMove)}</strong><small>Five sessions</small></article>
          <article><span>Realized move</span><strong>{plainPct(potentialMoveCalibration.holdout.meanRealizedMove)}</strong><small>Absolute close move</small></article>
          <article><span>Realized / expected</span><strong>{potentialMoveCalibration.holdout.medianRealizedToExpected.toFixed(3)}×</strong><small>Holdout median</small></article>
        </div>
        <div className="indicator-validation-grid" aria-label="Research indicator holdout results">
          {potentialMoveCalibration.indicatorResearch.map((indicator) => (
            <article className={indicator.status} key={indicator.name}>
              <header><span>{indicator.name}</span><b>{indicator.status}</b></header>
              <strong>{indicator.result}</strong>
              <small>{indicator.observations.toLocaleString()} holdout observations · {indicator.role}</small>
            </article>
          ))}
        </div>
        <div className="execution-lock-note"><ShieldX size={16} aria-hidden="true" /><div><strong>Execution remains locked</strong><p>Calibration passed for display, but this historical range cannot vote, size, or authorize an Alpaca paper order.</p></div></div>
        <div className="backtest-detail-grid">
          <div><h3>Fixed policy</h3><dl>{potentialMoveCalibration.parameters.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></div>
          <div><h3>Method &amp; limits</h3><p>{potentialMoveCalibration.methodology}</p><ul>{potentialMoveCalibration.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>
        </div>
      </section>
      {backtestReports.map((report) => (
        <section className="panel backtest-report" key={report.id}>
          <div className="panel-heading"><div><p className="eyebrow">{report.instrument}</p><h2>{report.name}</h2></div><span className={`decision-chip ${report.gatePassed ? "approved" : "vetoed"}`}><CheckCircle2 size={14} aria-hidden="true" /> {report.gatePassed ? "Gate passed" : "Gate failed"}</span></div>
          <div className="backtest-meta"><span><CalendarRange size={13} />{report.period}</span><span>{report.bars.toLocaleString()} {report.barSize} bars</span><span>Generated {new Date(report.generatedAt).toLocaleDateString()}</span></div>
          <div className="backtest-score-grid">
            <article><span>Holdout trades</span><strong>{report.holdout.trades}</strong><small>Train: {report.train.trades}</small></article>
            <article><span>Win rate</span><strong>{pct(report.holdout.winRate)}</strong><small>Train: {pct(report.train.winRate)}</small></article>
            <article><span>Total return</span><strong className={report.holdout.totalReturn >= 0 ? "positive" : "negative"}><TrendingUp size={17} />{pct(report.holdout.totalReturn)}</strong><small>After modeled friction</small></article>
            <article><span>Sharpe proxy</span><strong>{report.holdout.sharpe.toFixed(3)}</strong><small>Train: {report.train.sharpe.toFixed(3)}</small></article>
            <article><span>Max drawdown</span><strong className="negative"><TrendingDown size={17} />{pct(report.holdout.maxDrawdown)}</strong><small>Holdout period</small></article>
          </div>
          <div className="backtest-detail-grid"><div><h3>Fixed policy</h3><dl>{report.parameters.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></div><div><h3>Method &amp; limits</h3><p>{report.methodology}</p><ul>{report.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div></div>
          {report.trades && report.trades.length > 0 && (
            <details className="replay-ledger">
              <summary><span><History size={15} aria-hidden="true" /> Historical execution replay</span><small>{report.trades.length} recent holdout signals</small></summary>
              <p className="replay-warning"><ShieldCheck size={14} aria-hidden="true" /> Backtest proxy only. These are not Alpaca paper fills and are excluded from live account P&amp;L.</p>
              <div className="replay-table-scroll">
                <table>
                  <caption>Recent out-of-sample scanner signals and their underlying proxy returns</caption>
                  <thead><tr><th>Signal time</th><th>Symbol</th><th>Bias</th><th>Conviction</th><th>8-bar return</th></tr></thead>
                  <tbody>{report.trades.map((trade) => (
                    <tr key={`${trade.signalAt}-${trade.symbol}`}>
                      <td>{new Date(trade.signalAt).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</td>
                      <td><strong>{trade.symbol}</strong></td>
                      <td><span className={`replay-bias ${trade.direction}`}>{trade.direction === "bullish" ? "CALL" : "PUT"}</span></td>
                      <td>{(trade.conviction * 100).toFixed(1)}%</td>
                      <td className={trade.underlyingProxyReturn >= 0 ? "positive" : "negative"}>{pct(trade.underlyingProxyReturn)}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            </details>
          )}
        </section>
      ))}
    </div>
  );
}
