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


class StrategyMode(StrEnum):
    ADAPTIVE = "adaptive"
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


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
    entry_rules: list[str] = Field(default_factory=list)
    exit_rules: list[str] = Field(default_factory=list)


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
    controls: "AnalysisControls"
    disclaimer: str = "Educational paper-trading prototype. Not investment advice."


class AnalysisControls(BaseModel):
    strategy_mode: StrategyMode = StrategyMode.ADAPTIVE
    max_risk_pct: float = Field(default=0.01, ge=0.001, le=0.02)
    min_confidence: float = Field(default=0.55, ge=0.5, le=0.95)
    target_dte: int = Field(default=30, ge=7, le=60)


class AnalyzeRequest(AnalysisControls):
    symbol: str = Field(default="SPY", min_length=1, max_length=10, pattern=r"^[A-Za-z.]+$")


class EquityPoint(BaseModel):
    timestamp: datetime
    equity: float
    profit_loss: float


class AccountSummary(BaseModel):
    equity: float
    cash: float
    buying_power: float
    day_pnl: float
    day_pnl_pct: float
    total_pnl: float
    total_pnl_pct: float
    options_buying_power: float
    options_level: int
    trading_blocked: bool


class PositionSummary(BaseModel):
    symbol: str
    asset_class: str
    quantity: float
    market_value: float
    average_entry: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class OrderSummary(BaseModel):
    id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    status: str
    submitted_at: datetime


class IntegrationStatus(BaseModel):
    id: str
    name: str
    status: str
    detail: str
    capability: str


class ActivityEvent(BaseModel):
    timestamp: datetime
    source: str
    title: str
    detail: str
    status: str


class PlatformSnapshot(BaseModel):
    mode: str
    account: AccountSummary
    equity_curve: list[EquityPoint]
    positions: list[PositionSummary]
    orders: list[OrderSummary]
    integrations: list[IntegrationStatus]
    activity: list[ActivityEvent]
    generated_at: datetime
