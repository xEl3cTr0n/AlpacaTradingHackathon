export type Direction = "bullish" | "sideways" | "bearish";
export type Volatility = "low" | "normal" | "high";
export type Stance = "support" | "oppose" | "neutral" | "veto";
export type StrategyMode = "adaptive" | "bullish" | "bearish" | "neutral";

export interface AnalysisControls {
  strategy_mode: StrategyMode;
  max_risk_pct: number;
  min_confidence: number;
  target_dte: number;
}

export interface PricePoint {
  timestamp: string;
  close: number;
  volume: number;
}

export interface AgentVerdict {
  agent: string;
  stance: Stance;
  confidence: number;
  summary: string;
  evidence: string[];
}

export interface DecisionSnapshot {
  decision_id: string;
  generated_at: string;
  mode: string;
  market: {
    symbol: string;
    as_of: string;
    source: string;
    current_price: number;
    price_change_pct: number;
    prices: PricePoint[];
    headlines: string[];
  };
  regime: {
    direction: Direction;
    volatility: Volatility;
    label: string;
    confidence: number;
    metrics: {
      ema_fast: number;
      ema_slow: number;
      rsi_14: number;
      realized_volatility: number;
      volatility_percentile: number;
      trend_score: number;
    };
    rationale: string;
  };
  agents: AgentVerdict[];
  strategy: {
    name: string;
    display_name: string;
    thesis: string;
    structure: string[];
    max_loss_dollars: number;
    risk_percent: number;
    status: string;
    entry_rules: string[];
    exit_rules: string[];
  };
  risk: {
    approved: boolean;
    max_allowed_loss: number;
    approved_contracts: number;
    reasons: string[];
  };
  controls: AnalysisControls;
  disclaimer: string;
}

export interface EquityPoint {
  timestamp: string;
  equity: number;
  profit_loss: number;
}

export interface PlatformSnapshot {
  mode: string;
  account: {
    equity: number;
    cash: number;
    buying_power: number;
    day_pnl: number;
    day_pnl_pct: number;
    total_pnl: number;
    total_pnl_pct: number;
    options_buying_power: number;
    options_level: number;
    trading_blocked: boolean;
  };
  equity_curve: EquityPoint[];
  positions: Array<{
    symbol: string;
    asset_class: string;
    quantity: number;
    market_value: number;
    average_entry: number;
    current_price: number;
    unrealized_pnl: number;
    unrealized_pnl_pct: number;
  }>;
  orders: Array<{
    id: string;
    symbol: string;
    side: string;
    quantity: number;
    order_type: string;
    status: string;
    submitted_at: string;
  }>;
  integrations: Array<{
    id: string;
    name: string;
    status: string;
    detail: string;
    capability: string;
  }>;
  activity: Array<{
    timestamp: string;
    source: string;
    title: string;
    detail: string;
    status: string;
  }>;
  generated_at: string;
}
