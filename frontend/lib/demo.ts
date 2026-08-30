import type { DecisionSnapshot, PricePoint } from "@/lib/types";

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
    disclaimer: "Educational paper-trading prototype. Not investment advice.",
  };
}

