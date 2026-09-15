"use client";

import dynamic from "next/dynamic";
import type { PlatformSnapshot } from "@/lib/types";
import { useWorkspacePreferences } from "@/lib/use-workspace-preferences";

const ManualTradeTicket = dynamic(() => import("./manual-trade-ticket").then((m) => m.ManualTradeTicket), {
  loading: () => <p className="workspace-empty">Loading options chain…</p>,
});
const money = (value: number) => value.toLocaleString("en-US", { style: "currency", currency: "USD" });

export function TradingDock({ symbol, onSymbolChange, platform, accountError, onRefreshAccount }: {
  symbol: string; onSymbolChange: (symbol: string) => void; platform: PlatformSnapshot | null;
  accountError: boolean; onRefreshAccount: () => void;
}) {
  const [preferences, updatePreferences] = useWorkspacePreferences();
  const tab = preferences.dock;
  return <section className="trading-dock" aria-label="Options, positions and orders">
    <div className="dock-heading"><nav aria-label="Trading dock">{(["positions", "orders", "options"] as const).map((item) => <button key={item} type="button" aria-pressed={tab === item} className={tab === item ? "active" : ""} onClick={() => updatePreferences({ dock: item })}>{item === "options" ? symbol + " options chain" : item === "positions" ? "Positions" : "Orders"}{item !== "options" && <span>{platform ? platform[item].length : "—"}</span>}</button>)}</nav><button type="button" onClick={onRefreshAccount}>Refresh account</button></div>
    {tab !== "options" && <p className={accountError || !platform ? "workspace-warning" : "dock-caption"}>{accountError ? "Account refresh failed — showing last snapshot, not current state." : !platform ? "Account unavailable. No positions or orders inferred." : "All account symbols · as of " + new Date(platform.generated_at).toLocaleString()}</p>}
    {tab === "options" ? <ManualTradeTicket key={symbol} defaultSymbol={symbol} onSymbolChange={onSymbolChange} compact onOrderSubmitted={onRefreshAccount} /> : platform && <div className="dock-table-scroll" tabIndex={0} role="region" aria-label={tab === "positions" ? "Paper positions table" : "Recent paper orders table"}>
      {tab === "positions" ? <table><thead><tr><th>Symbol</th><th>Qty</th><th>Average</th><th>Mark</th><th>Value</th><th>Unrealized P&amp;L</th></tr></thead><tbody>{platform.positions.map((position) => <tr key={position.symbol}><th>{position.symbol}</th><td>{position.quantity}</td><td>{money(position.average_entry)}</td><td>{money(position.current_price)}</td><td>{money(position.market_value)}</td><td className={position.unrealized_pnl >= 0 ? "positive" : "negative"}>{money(position.unrealized_pnl)}</td></tr>)}{!platform.positions.length && <tr><td colSpan={6}>No open paper positions.</td></tr>}</tbody></table>
        : <table><thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Type</th><th>Status</th><th>Submitted</th></tr></thead><tbody>{platform.orders.map((order) => <tr key={order.id}><th>{order.symbol}</th><td>{order.side}</td><td>{order.quantity}</td><td>{order.order_type}</td><td>{order.status}</td><td>{new Date(order.submitted_at).toLocaleString()}</td></tr>)}{!platform.orders.length && <tr><td colSpan={6}>No recent orders returned by Alpaca.</td></tr>}</tbody></table>}
    </div>}
  </section>;
}
