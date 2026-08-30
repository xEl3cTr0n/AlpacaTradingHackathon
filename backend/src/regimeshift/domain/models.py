from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Direction(StrEnum):
    BULLISH = "bullish"
    SIDEWAYS = "sideways"
    BEARISH = "bearish"


class Volatility(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class Stance(StrEnum):
    SUPPORT = "support"
    OPPOSE = "oppose"
    NEUTRAL = "neutral"
    VETO = "veto"


class StrategyName(StrEnum):
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_PUT_SPREAD = "bear_put_spread"
    IRON_CONDOR = "iron_condor"
    NO_TRADE = "no_trade"


class PricePoint(BaseModel):
    timestamp: datetime
    close: float
    volume: int


class RegimeMetrics(BaseModel):
    ema_fast: float
    ema_slow: float
    rsi_14: float
    realized_volatility: float
    volatility_percentile: float = Field(ge=0, le=1)
    trend_score: float = Field(ge=-1, le=1)


class RegimeAssessment(BaseModel):
    direction: Direction
    volatility: Volatility
    label: str
    confidence: float = Field(ge=0, le=1)
    metrics: RegimeMetrics
    rationale: str


class AgentVerdict(BaseModel):
    agent: str
    stance: Stance
    confidence: float = Field(ge=0, le=1)
    summary: str
    evidence: list[str]


class StrategyProposal(BaseModel):
    name: StrategyName
    display_name: str
    thesis: str
    structure: list[str]
    max_loss_dollars: float = Field(ge=0)
    risk_percent: float = Field(ge=0)
    status: str


class RiskDecision(BaseModel):
    approved: bool
    max_allowed_loss: float = Field(ge=0)
    approved_contracts: int = Field(ge=0)
    reasons: list[str]


class MarketContext(BaseModel):
    symbol: str
    as_of: datetime
    source: str
    current_price: float
    price_change_pct: float
    prices: list[PricePoint]
    headlines: list[str]


class DecisionSnapshot(BaseModel):
    decision_id: str
    generated_at: datetime
    mode: str
    market: MarketContext
    regime: RegimeAssessment
    agents: list[AgentVerdict]
    strategy: StrategyProposal
    risk: RiskDecision
    disclaimer: str = "Educational paper-trading prototype. Not investment advice."


class AnalyzeRequest(BaseModel):
    symbol: str = Field(default="SPY", min_length=1, max_length=10, pattern=r"^[A-Za-z.]+$")
