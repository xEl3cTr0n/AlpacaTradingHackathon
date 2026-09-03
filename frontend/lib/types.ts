export type Direction = "bullish" | "sideways" | "bearish";
export type Volatility = "low" | "normal" | "high";
export type Stance = "support" | "oppose" | "neutral" | "veto";
export type StrategyMode = "adaptive" | "bullish" | "bearish" | "neutral";
export type InstrumentMode = "auto" | "equity_option" | "index_option";
export type RotationSignal = "risk_on" | "mixed" | "defensive";
export type RotationPhase = "leading" | "improving" | "weakening" | "lagging";
export type SwingSignal = "bullish_breakout" | "bullish_reversal" | "bearish_breakdown" | "bearish_reversal" | "neutral";
export type VoteChoice = "support" | "oppose" | "abstain";
export type ScannerPattern =
  | "bullish_18ema_cross"
  | "bearish_18ema_cross"
  | "bullish_trend_watch"
  | "bearish_trend_watch"
  | "no_setup";

export interface AnalysisControls {
  strategy_mode: StrategyMode;
  instrument_mode: InstrumentMode;
  max_risk_pct: number;
  min_confidence: number;
  target_dte: number;
  max_loss_cap_dollars?: number | null;
}

export interface PricePoint {
  timestamp: string;
  close: number;
  volume: number;
  open?: number | null;
  high?: number | null;
  low?: number | null;
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
  swing: {
    signal: SwingSignal;
    confidence: number;
    lookback: number;
    swing_low: number;
    swing_high: number;
    range_position: number;
    rationale: string;
  };
  sector_rotation: {
    benchmark_symbol: string;
    as_of: string;
    signal: RotationSignal;
    confidence: number;
    breadth: number;
    leaders: string[];
    laggards: string[];
    sectors: Array<{
      rank: number;
      symbol: string;
      name: string;
      one_month_return: number;
      three_month_return: number;
      relative_strength_1m: number;
      relative_strength_3m: number;
      rotation_score: number;
      phase: RotationPhase;
    }>;
    rationale: string;
  };
  agents: AgentVerdict[];
  council: {
    votes: Array<{
      agent: string;
      vote: VoteChoice;
      confidence: number;
      reason: string;
    }>;
    support_count: number;
    oppose_count: number;
    abstain_count: number;
    weighted_support: number;
    approval_threshold: number;
    quorum_met: boolean;
    approved: boolean;
  };
  tool_evidence: Array<{
    provider: string;
    capability: string;
    status: string;
    summary: string;
  }>;
  strategy: {
    name: string;
    display_name: string;
    signal_symbol: string;
    underlying_symbol: string;
    instrument_type: InstrumentMode;
    option_style: string;
    settlement: string;
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

export interface ScannerCandidate {
  rank: number;
  symbol: string;
  name: string;
  as_of: string;
  pattern: ScannerPattern;
  direction: Direction;
  option_bias: string;
  conviction: number;
  actionable: boolean;
  signal_tier: "production" | "exploration" | "watch";
  risk_cap_dollars: number;
  current_price: number;
  ema_18: number;
  ema_50: number;
  ema_18_slope_5d: number;
  rsi_14: number;
  volume_ratio: number;
  relative_strength_20d: number;
  realized_volatility: number;
  average_dollar_volume: number;
  market_aligned: boolean;
  liquidity_tier: string;
  evidence: string[];
}

export interface ScannerSnapshot {
  generated_at: string;
  source: string;
  interval_minutes: number;
  timeframe: string;
  universe_size: number;
  scanned_count: number;
  actionable_count: number;
  minimum_conviction: number;
  ema_period: number;
  methodology: string;
  candidates: ScannerCandidate[];
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
