export type Direction = "bullish" | "sideways" | "bearish";
export type Volatility = "low" | "normal" | "high";
export type Stance = "support" | "oppose" | "neutral" | "veto";

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
  };
  risk: {
    approved: boolean;
    max_allowed_loss: number;
    approved_contracts: number;
    reasons: string[];
  };
  disclaimer: string;
}

