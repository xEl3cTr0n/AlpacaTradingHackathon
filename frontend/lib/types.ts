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
  options_microstructure: {
    underlying_symbol: string;
    as_of: string;
    source: string;
    status: string;
    contract_count: number;
    net_gex: number;
    gross_gex: number;
    gamma_concentration?: number | null;
    nope_options?: number | null;
    put_vega_intensity?: number | null;
    call_wall?: number | null;
    put_wall?: number | null;
    call_directional_bias?: number | null;
    put_directional_bias?: number | null;
    key_gamma_strike?: number | null;
    key_delta_strike?: number | null;
    hedge_wall?: number | null;
    gamma_regime: "stabilizing" | "amplifying" | "mixed" | "unavailable";
    data_quality: number;
    rationale: string;
    evidence: string[];
  };
  market_layers: {
    macro: {
      quadrant: "quad_i" | "quad_ii" | "quad_iii" | "quad_iv" | "unavailable";
      label: string;
      real_gdp_yoy?: number | null;
      cpi_yoy?: number | null;
      growth_accelerating?: boolean | null;
      inflation_accelerating?: boolean | null;
      data_as_of?: string | null;
      source: string;
      status: string;
      confidence: number;
      rationale: string;
    };
    bottom_up: {
      quadrant: "quad_1" | "quad_2" | "quad_3" | "quad_4";
      label: string;
      trend_positive: boolean;
      breadth_positive: boolean;
      confidence: number;
      rationale: string;
    };
    mood_vibe: {
      mood: string;
      vibe: "volatility" | "indifference" | "btfd" | "euphoria" | "unavailable";
      status: string;
      confidence: number;
      input_coverage: number;
      rationale: string;
      missing_inputs: string[];
    };
    hierarchy: string[];
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
    required_support: number;
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
    stop_loss_dollars: number;
    stop_loss_fraction: number;
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
  scanner_signal?: ScannerCandidate | null;
  disclaimer: string;
}

export interface ManualTradeRequest {
  long_symbol: string;
  short_symbol: string;
  limit_debit: number;
  quantity: 1;
  rationale: string;
}

export interface ManualTradePreview {
  valid: boolean;
  paper_only: true;
  underlying_symbol: string;
  option_type: string;
  expiration: string;
  long_strike: number;
  short_strike: number;
  width: number;
  limit_debit: number;
  market_debit?: number | null;
  maximum_loss: number;
  stop_loss_dollars: number;
  stop_loss_fraction: number;
  maximum_reward: number;
  risk_budget: number;
  liquidity_passed: boolean;
  quote_checks: Array<{
    symbol: string;
    valid: boolean;
    as_of: string | null;
    age_seconds: number | null;
    maximum_age_seconds: number;
    bid: number | null;
    ask: number | null;
    reasons: string[];
  }>;
  capacity_passed: boolean;
  market_open: boolean;
  reasons: string[];
}

export interface ManualTradeResult {
  status: string;
  paper_only: true;
  order_id: string;
  client_order_id: string;
}

export interface LiveMarketTick {
  symbol: string;
  as_of: string;
  price: number;
  bid?: number | null;
  ask?: number | null;
  spread_bps?: number | null;
  day_change_pct?: number | null;
  source: string;
}

export interface ChartSnapshot {
  symbol: string;
  timeframe: "1Min" | "5Min" | "15Min" | "1Day";
  generated_at: string;
  source: string;
  bars: PricePoint[];
  volume_rsi_signals?: VolumeRsiReading[];
}

export interface OptionChainContract {
  symbol: string;
  option_type: "call" | "put";
  expiration: string;
  strike: number;
  moneyness: "itm" | "otm";
  bid?: number | null;
  ask?: number | null;
  midpoint?: number | null;
  spread_percent?: number | null;
  open_interest?: number | null;
  implied_volatility?: number | null;
  delta?: number | null;
  gamma?: number | null;
}

export interface OptionChainSnapshot {
  underlying_symbol: string;
  underlying_price: number;
  option_type: "call" | "put";
  moneyness: "itm" | "otm";
  expiration: string;
  expirations: string[];
  contracts: OptionChainContract[];
  as_of: string;
  source: string;
}

export interface OptionsThesisSnapshot {
  underlying_symbol: string;
  underlying_price: number;
  expiration: string;
  dte: number;
  as_of: string;
  source: string;
  status: "available" | "partial";
  call_symbol: string;
  put_symbol: string;
  call_strike: number;
  put_strike: number;
  average_implied_volatility?: number | null;
  iv_expected_move_dollars?: number | null;
  iv_expected_move_pct?: number | null;
  straddle_cost_dollars?: number | null;
  straddle_cost_pct?: number | null;
  estimator_agreement?: number | null;
  maximum_quote_spread_pct?: number | null;
  minimum_open_interest?: number | null;
  gamma_regime: "stabilizing" | "amplifying" | "mixed" | "unavailable";
  net_gex: number;
  gamma_concentration?: number | null;
  call_wall?: number | null;
  put_wall?: number | null;
  key_gamma_strike?: number | null;
  data_quality: number;
  evidence: string[];
  limitations: string[];
}

export interface EquityPoint {
  timestamp: string;
  equity: number;
  profit_loss: number;
}

export interface RFactorReading {
  as_of: string;
  provisional: boolean;
  score: number;
  relative_volume: number;
  directional_volume: number;
  open_change_pct: number;
  momentum_pct: number;
  typical_price_distance_pct: number;
  bullish_match: boolean;
  bearish_match: boolean;
}

export interface ChopReading {
  as_of: string | null;
  timeframe: string;
  value: number | null;
  state: "trend" | "transition" | "chop" | "unavailable";
}

export interface VolumeRsiReading {
  as_of: string;
  rsi: number;
  volume_ratio: number;
  atr_fraction: number;
  low_volatility: boolean;
  low_vol_filter_enabled: boolean;
  raw_signal: "overbought" | "oversold" | "none";
  quiet_signal: "overbought" | "oversold" | "none";
  context: "reversal_down" | "reversal_up" | "up_continuation" | "down_continuation" | "extreme_watch" | "none";
  event_at: string | null;
  event_age_bars: number | null;
}

export interface ScannerDiagnostics {
  research_only: true;
  evaluated_at: string;
  levels_as_of: string | null;
  levels_price: number | null;
  timeframe: string;
  stale: boolean;
  daily_r_factor: RFactorReading | null;
  provisional_r_factor: RFactorReading | null;
  chop: ChopReading;
  daily_chop: ChopReading;
  volume_rsi: VolumeRsiReading | null;
  volume_rsi_low_vol_filtered: VolumeRsiReading | null;
  recent_rsi_events: VolumeRsiReading[];
  plans: Array<{
    side: "call" | "put";
    entry: number;
    invalidation: number;
    target_1: number;
    target_2: number;
    risk_per_share: number;
    entry_valid_bars: number;
    time_exit_bars: number;
    state: "wait_breakout" | "wait_chop" | "stale";
  }>;
  notes: string[];
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
  diagnostics?: ScannerDiagnostics | null;
  move_thesis: {
    horizon_sessions: number;
    expected_move_dollars: number;
    expected_move_pct: number;
    lower_bound: number;
    upper_bound: number;
    atr_14: number;
    realized_vol_move_pct: number;
    directional_efficiency_20d: number;
    volatility_expansion_ratio: number;
    average_gap_pct_20d: number;
    direction_score: number;
    move_confidence: number;
    research_only: true;
    trigger: string;
    target: string;
    invalidation: string;
    basis: string;
    research_indicators: Array<{
      indicator: string;
      value: number;
      status: "holdout_failed" | "mixed" | "holdout_supported";
      role: "diagnostic_only" | "range_context_only" | "risk_warning_only";
      holdout_observations: number;
      validation_summary: string;
    }>;
    supporting_evidence: string[];
    conflicting_evidence: string[];
  };
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
  execution_gates?: {
    evidence_valid: boolean;
    evidence_as_of?: string | null;
    source: string;
    intraday_production_backtest_passed: boolean;
    intraday_exploration_backtest_passed: boolean;
    daily_production_backtest_passed: boolean;
    paper_only: true;
    paper_experiment_enabled?: boolean;
    details: string[];
  } | null;
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
  automation: {
    status: string;
    market_open: boolean;
    next_open: string;
    next_close: string;
    scan_interval_minutes: number;
    worker: string;
    paper_only: boolean;
  };
  generated_at: string;
}
