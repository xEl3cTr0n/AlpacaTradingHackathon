import { ArrowUpRight, Bot, CircleDollarSign, CreditCard, Landmark, WalletCards } from "lucide-react";
import { EquityChart } from "@/app/_components/equity-chart";
import type { PlatformSnapshot } from "@/lib/types";

const money = (value: number) => value.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const percent = (value: number) => `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;

export function PortfolioView({ platform, onOpenStrategy }: { platform: PlatformSnapshot; onOpenStrategy: () => void }) {
  const { account } = platform;
  return (
    <div className="view-stack">
      <header className="view-heading"><div><p className="eyebrow">Alpaca paper environment</p><h1>Portfolio command center</h1><p>Track agent performance, exposure, and execution quality in one place.</p></div><button type="button" className="primary-action" onClick={onOpenStrategy}><Bot size={17} aria-hidden="true" /> Configure next run</button></header>
      <section className="portfolio-kpis" aria-label="Paper account metrics">
        <article><span className="kpi-icon"><WalletCards size={18} aria-hidden="true" /></span><div><p>Net liquidation</p><strong>{money(account.equity)}</strong><small>Paper account equity</small></div></article>
        <article><span className="kpi-icon"><ArrowUpRight size={18} aria-hidden="true" /></span><div><p>Today&apos;s P&amp;L</p><strong className={account.day_pnl >= 0 ? "positive" : "negative"}>{money(account.day_pnl)}</strong><small>{percent(account.day_pnl_pct)} today</small></div></article>
        <article><span className="kpi-icon"><CircleDollarSign size={18} aria-hidden="true" /></span><div><p>Total P&amp;L</p><strong className={account.total_pnl >= 0 ? "positive" : "negative"}>{money(account.total_pnl)}</strong><small>{percent(account.total_pnl_pct)} since baseline</small></div></article>
        <article><span className="kpi-icon"><CreditCard size={18} aria-hidden="true" /></span><div><p>Buying power</p><strong>{money(account.buying_power)}</strong><small>{money(account.options_buying_power)} options</small></div></article>
      </section>
      <section className="portfolio-grid">
        <article className="panel performance-panel"><div className="panel-heading"><div><p className="eyebrow">P&amp;L performance</p><h2>Paper equity curve</h2></div><span className="source-label">{platform.mode}</span></div><EquityChart points={platform.equity_curve} /></article>
        <aside className="panel account-panel"><div className="panel-heading"><div><p className="eyebrow">Account state</p><h2>Risk capacity</h2></div><Landmark size={19} aria-hidden="true" /></div><dl><div><dt>Cash</dt><dd>{money(account.cash)}</dd></div><div><dt>Options buying power</dt><dd>{money(account.options_buying_power)}</dd></div><div><dt>Options level</dt><dd>Level {account.options_level}</dd></div><div><dt>Trading status</dt><dd className={account.trading_blocked ? "negative" : "positive"}>{account.trading_blocked ? "Blocked" : "Enabled"}</dd></div></dl><div className="risk-meter"><span style={{ width: "36%" }} /><small>36% modeled capital deployed</small></div></aside>
      </section>
      <section className="data-grid">
        <article className="panel table-panel"><div className="panel-heading"><div><p className="eyebrow">Live exposure</p><h2>Open positions</h2></div><span>{platform.positions.length} positions</span></div><div className="table-scroll"><table><thead><tr><th>Symbol</th><th>Class</th><th>Qty</th><th>Market value</th><th>Avg / Current</th><th>Unrealized P&amp;L</th></tr></thead><tbody>{platform.positions.map((position) => <tr key={position.symbol}><td><strong>{position.symbol}</strong></td><td>{position.asset_class.replace("us_", "")}</td><td>{position.quantity}</td><td>{money(position.market_value)}</td><td>{money(position.average_entry)} / {money(position.current_price)}</td><td className={position.unrealized_pnl >= 0 ? "positive" : "negative"}>{money(position.unrealized_pnl)} <small>{percent(position.unrealized_pnl_pct)}</small></td></tr>)}</tbody></table></div></article>
        <article className="panel order-panel"><div className="panel-heading"><div><p className="eyebrow">Execution tape</p><h2>Recent orders</h2></div><span>{platform.orders.length} shown</span></div><div className="order-list">{platform.orders.map((order) => <article key={order.id}><span className={`order-side ${order.side}`}>{order.side}</span><div><strong>{order.symbol}</strong><small>{order.quantity} · {order.order_type}</small></div><div><b>{order.status}</b><time>{new Date(order.submitted_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time></div></article>)}</div></article>
      </section>
    </div>
  );
}
