import { CalendarRange, CheckCircle2, DatabaseZap, ShieldCheck, TrendingDown, TrendingUp } from "lucide-react";
import { backtestReports } from "@/lib/backtest-results";

const pct = (value: number) => `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;

export function BacktestView() {
  return (
    <div className="view-stack backtest-view">
      <header className="view-heading">
        <div><p className="eyebrow">Historical validation</p><h1>Backtesting</h1><p>Out-of-sample evidence from dated Alpaca market history—not simulated dashboard data.</p></div>
        <span className="decision-chip approved"><DatabaseZap size={15} aria-hidden="true" /> Alpaca historical bars</span>
      </header>
      <section className="backtest-disclosure panel"><ShieldCheck size={19} aria-hidden="true" /><div><strong>Chronological holdouts only</strong><p>Results were frozen before evaluation. They are underlying-direction proxies and do not represent option fills or future returns.</p></div></section>
      {backtestReports.map((report) => (
        <section className="panel backtest-report" key={report.id}>
          <div className="panel-heading"><div><p className="eyebrow">{report.instrument}</p><h2>{report.name}</h2></div><span className={`decision-chip ${report.gatePassed ? "approved" : "vetoed"}`}><CheckCircle2 size={14} aria-hidden="true" /> {report.gatePassed ? "Gate passed" : "Gate failed"}</span></div>
          <div className="backtest-meta"><span><CalendarRange size={13} />{report.period}</span><span>{report.bars.toLocaleString()} daily bars</span><span>Generated {new Date(report.generatedAt).toLocaleDateString()}</span></div>
          <div className="backtest-score-grid">
            <article><span>Holdout trades</span><strong>{report.holdout.trades}</strong><small>Train: {report.train.trades}</small></article>
            <article><span>Win rate</span><strong>{pct(report.holdout.winRate)}</strong><small>Train: {pct(report.train.winRate)}</small></article>
            <article><span>Total return</span><strong className={report.holdout.totalReturn >= 0 ? "positive" : "negative"}><TrendingUp size={17} />{pct(report.holdout.totalReturn)}</strong><small>After modeled friction</small></article>
            <article><span>Sharpe proxy</span><strong>{report.holdout.sharpe.toFixed(3)}</strong><small>Train: {report.train.sharpe.toFixed(3)}</small></article>
            <article><span>Max drawdown</span><strong className="negative"><TrendingDown size={17} />{pct(report.holdout.maxDrawdown)}</strong><small>Holdout period</small></article>
          </div>
          <div className="backtest-detail-grid"><div><h3>Fixed policy</h3><dl>{report.parameters.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl></div><div><h3>Method &amp; limits</h3><p>{report.methodology}</p><ul>{report.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div></div>
        </section>
      ))}
    </div>
  );
}
