import type {
  DecisionSnapshot,
  PlatformSnapshot,
  PricePoint,
  ScannerSnapshot,
} from "@/lib/types";

function demoPrices(): PricePoint[] {
  const start = Date.UTC(2026, 4, 21);
  return Array.from({ length: 100 }, (_, index) => ({
    timestamp: new Date(start + index * 86_400_000).toISOString(),
    open: Number((522.7 + index * 0.48 + Math.sin(index / 6) * 6.8).toFixed(2)),
    high: Number((524.2 + index * 0.48 + Math.sin(index / 6) * 6.8).toFixed(2)),
    low: Number((521.9 + index * 0.48 + Math.sin(index / 6) * 6.8).toFixed(2)),
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
    swing: {
      signal: "bullish_breakout",
      confidence: 0.74,
      lookback: 20,
      swing_low: 558.21,
      swing_high: 568.44,
      range_position: 1,
      rationale: "Close confirmed a 20-session swing-high breakout with positive momentum.",
    },
    sector_rotation: {
      benchmark_symbol: "SPY",
      as_of: prices.at(-1)?.timestamp ?? new Date().toISOString(),
      signal: "risk_on",
      confidence: 0.76,
      breadth: 0.64,
      leaders: ["XLK", "XLI", "XLF"],
      laggards: ["XLP", "XLU", "XLRE"],
      sectors: [
        ["XLK", "Technology", 0.042, 0.096, 0.025, 0.051, 0.035, "leading"],
        ["XLI", "Industrials", 0.035, 0.082, 0.018, 0.037, 0.026, "leading"],
        ["XLF", "Financials", 0.031, 0.071, 0.014, 0.026, 0.019, "leading"],
        ["XLY", "Consumer Discretionary", 0.027, 0.064, 0.01, 0.019, 0.014, "leading"],
        ["XLC", "Communication Services", 0.024, 0.058, 0.007, 0.013, 0.009, "leading"],
        ["XLB", "Materials", 0.02, 0.052, 0.003, 0.007, 0.005, "leading"],
        ["XLE", "Energy", 0.018, 0.048, 0.001, 0.003, 0.002, "leading"],
        ["XLV", "Health Care", 0.013, 0.04, -0.004, -0.005, -0.004, "lagging"],
        ["XLP", "Consumer Staples", 0.009, 0.034, -0.008, -0.011, -0.009, "lagging"],
        ["XLU", "Utilities", 0.006, 0.029, -0.011, -0.016, -0.013, "lagging"],
        ["XLRE", "Real Estate", 0.003, 0.023, -0.014, -0.022, -0.017, "lagging"],
      ].map(([symbol, name, oneMonth, threeMonth, relative1m, relative3m, score, phase], index) => ({
        rank: index + 1,
        symbol: symbol as string,
        name: name as string,
        one_month_return: oneMonth as number,
        three_month_return: threeMonth as number,
        relative_strength_1m: relative1m as number,
        relative_strength_3m: relative3m as number,
        rotation_score: score as number,
        phase: phase as "leading" | "lagging",
      })),
      rationale: "64% of sectors outperform SPY; cyclical leadership is broadening.",
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
        agent: "Swing",
        stance: "support",
        confidence: 0.74,
        summary: "Bullish breakout",
        evidence: ["20-session high cleared", "Three-session momentum confirmed"],
      },
      {
        agent: "Research",
        stance: "neutral",
        confidence: 0.62,
        summary: "No concentrated headline-risk cluster detected.",
        evidence: ["Macro catalysts remain the primary near-term event risk"],
      },
      {
        agent: "Rotation",
        stance: "support",
        confidence: 0.76,
        summary: "Sector leadership is risk on.",
        evidence: ["Leadership breadth versus SPY is 64%", "Leaders: XLK, XLI, XLF", "Laggards: XLP, XLU, XLRE"],
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
    council: {
      votes: [
        { agent: "Technical", vote: "support", confidence: 0.78, reason: "Bullish regime aligns with the proposal." },
        { agent: "Swing", vote: "support", confidence: 0.74, reason: "Confirmed 20-session breakout." },
        { agent: "Rotation", vote: "support", confidence: 0.76, reason: "Risk-on breadth confirms the direction." },
        { agent: "Research", vote: "abstain", confidence: 0.62, reason: "No concentrated headline-risk cluster." },
        { agent: "Advocacy", vote: "support", confidence: 0.83, reason: "Bull case outweighs the counter-thesis." },
      ],
      support_count: 4,
      oppose_count: 0,
      abstain_count: 1,
      weighted_support: 1,
      approval_threshold: 0.52,
      quorum_met: true,
      approved: true,
    },
    tool_evidence: [
      { provider: "Alpaca Trading API", capability: "Market and paper-account telemetry", status: "used", summary: "Normalized bars, news, and account state." },
      { provider: "Alpaca MCP", capability: "Agent-native research", status: "configured", summary: "Read-only stock, news, options, and account tools." },
      { provider: "Alpaca CLI", capability: "Paper contract discovery and execution", status: "enabled", summary: "Risk-approved XSP multi-leg orders only." },
    ],
    strategy: {
      name: "bull_call_spread",
      display_name: "XSP Bull call debit spread",
      signal_symbol: "SPY",
      underlying_symbol: "XSP",
      instrument_type: "index_option",
      option_style: "European",
      settlement: "cash",
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
      instrument_mode: "auto",
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
      { id: "mcp", name: "Alpaca MCP Server", status: "configured", detail: "Repo-scoped read-only MCP runs outside Vercel", capability: "agent-native account, news, and options tools" },
      { id: "cli", name: "Alpaca CLI", status: "external_runner", detail: "Pinned paper-only runner handles gated execution", capability: "contract discovery and multi-leg paper orders" },
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

export function getDemoScanner(): ScannerSnapshot {
  const asOf = new Date().toISOString();
  const rows = [
    ["NVDA", "NVIDIA", "bullish_18ema_cross", "bullish", 0.78, 184.62, 181.94, 174.83, 1.42, 0.057, "very_high"],
    ["JPM", "JPMorgan Chase", "bearish_18ema_cross", "bearish", 0.69, 292.14, 294.03, 298.77, 1.28, -0.031, "high"],
    ["MSFT", "Microsoft", "bullish_trend_watch", "bullish", 0.54, 518.33, 511.48, 502.16, 0.94, 0.022, "very_high"],
    ["AMZN", "Amazon", "bullish_trend_watch", "bullish", 0.51, 228.76, 224.91, 219.02, 1.07, 0.018, "very_high"],
    ["XOM", "Exxon Mobil", "bearish_trend_watch", "bearish", 0.47, 116.04, 117.28, 119.45, 0.83, -0.014, "high"],
    ["AAPL", "Apple", "no_setup", "sideways", 0.15, 229.84, 229.31, 227.77, 0.88, -0.004, "very_high"],
  ] as const;
  return {
    generated_at: asOf,
    source: "offline scanner preview",
    interval_minutes: 15,
    universe_size: 24,
    scanned_count: 24,
    actionable_count: 2,
    minimum_conviction: 0.6,
    ema_period: 18,
    methodology:
      "Large-cap and $100M dollar-volume screen, followed by 18 EMA cross, trend, SPY, relative-strength, and volume confirmation.",
    candidates: rows.map((row, index) => ({
      rank: index + 1,
      symbol: row[0],
      name: row[1],
      as_of: asOf,
      pattern: row[2],
      direction: row[3],
      option_bias:
        row[3] === "bullish" ? "call_debit_spread" : row[3] === "bearish" ? "put_debit_spread" : "no_trade",
      conviction: row[4],
      actionable: index < 2,
      current_price: row[5],
      ema_18: row[6],
      ema_50: row[7],
      ema_18_slope_5d: row[3] === "bearish" ? -0.018 : row[3] === "bullish" ? 0.021 : 0.001,
      rsi_14: row[3] === "bearish" ? 41.8 : row[3] === "bullish" ? 62.4 : 50.2,
      volume_ratio: row[8],
      relative_strength_20d: row[9],
      realized_volatility: 0.29,
      average_dollar_volume: row[10] === "very_high" ? 7_800_000_000 : 1_840_000_000,
      market_aligned: row[3] !== "sideways",
      liquidity_tier: row[10],
      evidence: [
        `Price ${row[5]} vs EMA(18) ${row[6]}`,
        `20-session relative strength vs SPY ${(row[9] * 100).toFixed(1)}%`,
        "Option-chain liquidity is verified only after council approval",
      ],
    })),
  };
}
