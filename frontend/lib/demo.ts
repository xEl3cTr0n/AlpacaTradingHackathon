import type { DecisionSnapshot, PlatformSnapshot, PricePoint } from "@/lib/types";

function demoPrices(): PricePoint[] {
  const start = Date.UTC(2026, 4, 21);
  return Array.from({ length: 100 }, (_, index) => ({
    timestamp: new Date(start + index * 86_400_000).toISOString(),
    close: Number((523 + index * 0.48 + Math.sin(index / 6) * 6.8).toFixed(2)),
    volume: Math.round(62_000_000 + (Math.sin(index / 4) + 1) * 9_000_000),
  }));
}

export function getDemoSnapshot(): DecisionSnapshot {
  const prices = demoPrices();
  return {
    decision_id: "demo-offline-preview",
    generated_at: new Date().toISOString(),
    mode: "offline demo",
    market: {
      symbol: "SPY",
      as_of: prices.at(-1)?.timestamp ?? new Date().toISOString(),
      source: "frontend fallback tape",
      current_price: prices.at(-1)?.close ?? 0,
      price_change_pct: 0.64,
      prices,
      headlines: [
        "Large-cap momentum holds while traders assess upcoming macro catalysts",
        "Options markets price a wider range of outcomes into the coming sessions",
        "Market liquidity remains firm as volatility rises from recent lows",
      ],
    },
    regime: {
      direction: "bullish",
      volatility: "normal",
      label: "bullish_normal",
      confidence: 0.78,
      metrics: {
        ema_fast: 568.42,
        ema_slow: 559.18,
        rsi_14: 61.4,
        realized_volatility: 0.174,
        volatility_percentile: 0.58,
        trend_score: 0.61,
      },
      rationale:
        "Trend score +0.61 with RSI 61.4; realized volatility is in the 58% rolling percentile.",
    },
    agents: [
      {
        agent: "Technical",
        stance: "support",
        confidence: 0.78,
        summary: "Price structure indicates a bullish normal-volatility regime.",
        evidence: ["20-day EMA is above the 50-day EMA", "RSI confirms momentum without an extreme reading"],
      },
      {
        agent: "Research",
        stance: "neutral",
        confidence: 0.62,
        summary: "No concentrated headline-risk cluster detected.",
        evidence: ["Macro catalysts remain the primary near-term event risk"],
      },
      {
        agent: "Bull",
        stance: "support",
        confidence: 0.83,
        summary: "Positive trend persistence supports a defined-risk upside structure.",
        evidence: ["Trend and momentum agree", "Upside can be expressed with capped premium risk"],
      },
      {
        agent: "Bear",
        stance: "oppose",
        confidence: 0.56,
        summary: "A regime reversal remains the primary invalidation risk.",
        evidence: ["A close through the slow trend would invalidate momentum"],
      },
      {
        agent: "Risk",
        stance: "support",
        confidence: 0.94,
        summary: "Risk budget approved for preview.",
        evidence: ["Defined-risk structure", "Maximum loss remains within the 1% account budget"],
      },
    ],
    strategy: {
      name: "bull_call_spread",
      display_name: "Bull call debit spread",
      thesis: "Participate in upside momentum while capping premium at risk.",
      structure: ["Buy call near 0.55 delta", "Sell higher-strike call near 0.30 delta"],
      max_loss_dollars: 650,
      risk_percent: 0.0065,
      status: "approved preview",
      entry_rules: [
        "Regime confidence at least 55%",
        "Target expiration near 30 DTE",
        "Bid/ask spread and open-interest liquidity checks pass",
      ],
      exit_rules: [
        "Take profit at 50% of maximum reward",
        "Exit at 75% of maximum loss",
        "Close or reduce when the detected regime changes",
      ],
    },
    risk: {
      approved: true,
      max_allowed_loss: 1000,
      approved_contracts: 1,
      reasons: [
        "Maximum loss stays below the $1,000 risk budget",
        "Defined-risk structure; naked short options are prohibited",
        "Execution remains preview-only until contract quotes are resolved",
      ],
    },
    controls: {
      strategy_mode: "adaptive",
      max_risk_pct: 0.01,
      min_confidence: 0.55,
      target_dte: 30,
    },
    disclaimer: "Educational paper-trading prototype. Not investment advice.",
  };
}

export function getDemoPlatform(): PlatformSnapshot {
  const now = Date.now();
  const equity_curve = Array.from({ length: 31 }, (_, index) => {
    const equity = 100_000 + index * 112 + Math.sin(index / 2.8) * 460;
    return {
      timestamp: new Date(now - (30 - index) * 86_400_000).toISOString(),
      equity: Number(equity.toFixed(2)),
      profit_loss: Number((equity - 100_000).toFixed(2)),
    };
  });
  return {
    mode: "offline demo",
    account: {
      equity: 103_842.17,
      cash: 77_406.32,
      buying_power: 154_812.64,
      day_pnl: 184.72,
      day_pnl_pct: 0.0018,
      total_pnl: 3_842.17,
      total_pnl_pct: 0.0384,
      options_buying_power: 61_925.06,
      options_level: 3,
      trading_blocked: false,
    },
    equity_curve,
    positions: [
      { symbol: "SPY", asset_class: "us_equity", quantity: 12, market_value: 6902.64, average_entry: 566.1, current_price: 575.22, unrealized_pnl: 109.44, unrealized_pnl_pct: 0.0161 },
      { symbol: "QQQ", asset_class: "us_equity", quantity: 8, market_value: 4058.4, average_entry: 498.7, current_price: 507.3, unrealized_pnl: 68.8, unrealized_pnl_pct: 0.0172 },
      { symbol: "SPY260918C00580000", asset_class: "us_option", quantity: 1, market_value: 642, average_entry: 5.75, current_price: 6.42, unrealized_pnl: 67, unrealized_pnl_pct: 0.1165 },
    ],
    orders: [
      { id: "demo-ord-1", symbol: "SPY260918C00580000", side: "buy", quantity: 1, order_type: "limit", status: "filled", submitted_at: new Date(now - 11_880_000).toISOString() },
      { id: "demo-ord-2", symbol: "SPY260918C00590000", side: "sell", quantity: 1, order_type: "limit", status: "filled", submitted_at: new Date(now - 11_880_000).toISOString() },
      { id: "demo-ord-3", symbol: "QQQ", side: "buy", quantity: 8, order_type: "market", status: "filled", submitted_at: new Date(now - 93_600_000).toISOString() },
    ],
    integrations: [
      { id: "trading-api", name: "Alpaca Trading API", status: "setup_required", detail: "Add paper credentials to the root .env", capability: "paper account, portfolio, orders, news, and market data" },
      { id: "mcp", name: "Alpaca MCP Server", status: "not_connected", detail: "Enable after configuring the Alpaca MCP server", capability: "agent-native account, news, and options tools" },
      { id: "cli", name: "Alpaca CLI", status: "not_connected", detail: "Use for operator inspection and reproducible demos", capability: "terminal account and order inspection" },
    ],
    activity: [
      { timestamp: new Date(now - 120_000).toISOString(), source: "Risk", title: "Trade preview approved", detail: "Maximum modeled loss is inside the 1% account budget.", status: "success" },
      { timestamp: new Date(now - 180_000).toISOString(), source: "Bear", title: "Counter-thesis completed", detail: "Whipsaw risk remains below the veto threshold.", status: "complete" },
      { timestamp: new Date(now - 240_000).toISOString(), source: "Technical", title: "Regime classified", detail: "Bullish direction with normal volatility confidence.", status: "complete" },
      { timestamp: new Date(now - 300_000).toISOString(), source: "API", title: "Market snapshot received", detail: "Bars, news, and option telemetry normalized.", status: "complete" },
    ],
    generated_at: new Date(now).toISOString(),
  };
}
