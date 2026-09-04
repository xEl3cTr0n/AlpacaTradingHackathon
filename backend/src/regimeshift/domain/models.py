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


class InstrumentMode(StrEnum):
    AUTO = "auto"
    EQUITY_OPTION = "equity_option"
    INDEX_OPTION = "index_option"


class SwingSignal(StrEnum):
    BULLISH_BREAKOUT = "bullish_breakout"
    BULLISH_REVERSAL = "bullish_reversal"
    BEARISH_BREAKDOWN = "bearish_breakdown"
    BEARISH_REVERSAL = "bearish_reversal"
    NEUTRAL = "neutral"


class VoteChoice(StrEnum):
    SUPPORT = "support"
    OPPOSE = "oppose"
    ABSTAIN = "abstain"


class RotationSignal(StrEnum):
    RISK_ON = "risk_on"
    MIXED = "mixed"
    DEFENSIVE = "defensive"


class RotationPhase(StrEnum):
    LEADING = "leading"
    IMPROVING = "improving"
    WEAKENING = "weakening"
    LAGGING = "lagging"


class ScannerPattern(StrEnum):
    BULLISH_18EMA_CROSS = "bullish_18ema_cross"
    BEARISH_18EMA_CROSS = "bearish_18ema_cross"
    BULLISH_TREND_WATCH = "bullish_trend_watch"
    BEARISH_TREND_WATCH = "bearish_trend_watch"
    NO_SETUP = "no_setup"


class GammaRegime(StrEnum):
    STABILIZING = "stabilizing"
    AMPLIFYING = "amplifying"
    MIXED = "mixed"
    UNAVAILABLE = "unavailable"


class MacroQuad(StrEnum):
    QUAD_I = "quad_i"
    QUAD_II = "quad_ii"
    QUAD_III = "quad_iii"
    QUAD_IV = "quad_iv"
    UNAVAILABLE = "unavailable"


class BottomUpQuad(StrEnum):
    QUAD_1 = "quad_1"
    QUAD_2 = "quad_2"
    QUAD_3 = "quad_3"
    QUAD_4 = "quad_4"


class VibeRegime(StrEnum):
    VOLATILITY = "volatility"
    INDIFFERENCE = "indifference"
    BTFD = "btfd"
    EUPHORIA = "euphoria"
    UNAVAILABLE = "unavailable"


class PricePoint(BaseModel):
    timestamp: datetime
    close: float
    volume: int
    open: float | None = None
    high: float | None = None
    low: float | None = None


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
    signal_symbol: str
    underlying_symbol: str
    instrument_type: InstrumentMode
    option_style: str
    settlement: str
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


class SectorPerformance(BaseModel):
    rank: int = Field(ge=1, le=11)
    symbol: str
    name: str
    one_month_return: float
    three_month_return: float
    relative_strength_1m: float
    relative_strength_3m: float
    rotation_score: float
    phase: RotationPhase


class SectorRotationAssessment(BaseModel):
    benchmark_symbol: str = "SPY"
    as_of: datetime
    signal: RotationSignal
    confidence: float = Field(ge=0, le=1)
    breadth: float = Field(ge=0, le=1)
    leaders: list[str]
    laggards: list[str]
    sectors: list[SectorPerformance]
    rationale: str


class OptionsMicrostructureAssessment(BaseModel):
    underlying_symbol: str
    as_of: datetime
    source: str
    status: str
    contract_count: int = Field(ge=0)
    net_gex: float
    gross_gex: float = Field(ge=0)
    gamma_concentration: float | None = Field(default=None, ge=0, le=1)
    nope_options: float | None = Field(default=None, ge=-1, le=1)
    put_vega_intensity: float | None = Field(default=None, ge=0, le=1)
    call_wall: float | None = Field(default=None, gt=0)
    put_wall: float | None = Field(default=None, gt=0)
    gamma_regime: GammaRegime
    data_quality: float = Field(ge=0, le=1)
    rationale: str
    evidence: list[str]


class MacroQuadAssessment(BaseModel):
    quadrant: MacroQuad
    label: str
    real_gdp_yoy: float | None = None
    cpi_yoy: float | None = None
    growth_accelerating: bool | None = None
    inflation_accelerating: bool | None = None
    data_as_of: datetime | None = None
    source: str
    status: str
    confidence: float = Field(ge=0, le=1)
    rationale: str


class BottomUpQuadAssessment(BaseModel):
    quadrant: BottomUpQuad
    label: str
    trend_positive: bool
    breadth_positive: bool
    confidence: float = Field(ge=0, le=1)
    rationale: str


class MoodVibeAssessment(BaseModel):
    mood: str
    vibe: VibeRegime
    status: str
    confidence: float = Field(ge=0, le=1)
    input_coverage: float = Field(ge=0, le=1)
    rationale: str
    missing_inputs: list[str]


class LayeredMarketState(BaseModel):
    macro: MacroQuadAssessment
    bottom_up: BottomUpQuadAssessment
    mood_vibe: MoodVibeAssessment
    hierarchy: list[str] = Field(
        default_factory=lambda: [
            "Top-down GDP/CPI macro quadrant",
            "Bottom-up security and ETF participation quadrant",
            "Options microstructure MOOD/VIBE research proxy",
        ]
    )


class SwingAssessment(BaseModel):
    signal: SwingSignal
    confidence: float = Field(ge=0, le=1)
    lookback: int = Field(ge=5)
    swing_low: float
    swing_high: float
    range_position: float = Field(ge=0, le=1)
    rationale: str


class CouncilVote(BaseModel):
    agent: str
    vote: VoteChoice
    confidence: float = Field(ge=0, le=1)
    reason: str


class CouncilDecision(BaseModel):
    votes: list[CouncilVote]
    support_count: int = Field(ge=0)
    oppose_count: int = Field(ge=0)
    abstain_count: int = Field(ge=0)
    weighted_support: float = Field(ge=0, le=1)
    approval_threshold: float = Field(ge=0.5, le=0.9)
    quorum_met: bool
    approved: bool


class ToolEvidence(BaseModel):
    provider: str
    capability: str
    status: str
    summary: str


class ScannerCandidate(BaseModel):
    rank: int = Field(ge=1)
    symbol: str
    name: str
    as_of: datetime
    pattern: ScannerPattern
    direction: Direction
    option_bias: str
    conviction: float = Field(ge=0, le=1)
    actionable: bool
    signal_tier: str = "watch"
    risk_cap_dollars: float = Field(default=0, ge=0)
    current_price: float = Field(gt=0)
    ema_18: float = Field(gt=0)
    ema_50: float = Field(gt=0)
    ema_18_slope_5d: float
    rsi_14: float = Field(ge=0, le=100)
    volume_ratio: float = Field(ge=0)
    relative_strength_20d: float
    realized_volatility: float = Field(ge=0)
    average_dollar_volume: float = Field(ge=0)
    market_aligned: bool
    liquidity_tier: str
    evidence: list[str]


class ScannerSnapshot(BaseModel):
    generated_at: datetime
    source: str
    interval_minutes: int = Field(ge=5, le=240)
    timeframe: str = "1Day"
    universe_size: int = Field(ge=1)
    scanned_count: int = Field(ge=0)
    actionable_count: int = Field(ge=0)
    minimum_conviction: float = Field(ge=0.5, le=0.9)
    ema_period: int = Field(ge=2)
    methodology: str
    candidates: list[ScannerCandidate]


class DecisionSnapshot(BaseModel):
    decision_id: str
    generated_at: datetime
    mode: str
    market: MarketContext
    regime: RegimeAssessment
    swing: SwingAssessment
    sector_rotation: SectorRotationAssessment
    options_microstructure: OptionsMicrostructureAssessment
    market_layers: LayeredMarketState
    agents: list[AgentVerdict]
    council: CouncilDecision
    tool_evidence: list[ToolEvidence]
    strategy: StrategyProposal
    risk: RiskDecision
    controls: "AnalysisControls"
    disclaimer: str = "Educational paper-trading prototype. Not investment advice."


class AnalysisControls(BaseModel):
    strategy_mode: StrategyMode = StrategyMode.ADAPTIVE
    instrument_mode: InstrumentMode = InstrumentMode.AUTO
    max_risk_pct: float = Field(default=0.01, ge=0.001, le=0.02)
    min_confidence: float = Field(default=0.55, ge=0.5, le=0.95)
    target_dte: int = Field(default=30, ge=7, le=60)
    max_loss_cap_dollars: float | None = Field(default=None, ge=50, le=2_000)


class AnalyzeRequest(AnalysisControls):
    symbol: str = Field(default="SPY", min_length=1, max_length=10, pattern=r"^[A-Za-z.]+$")


class ManualTradeRequest(BaseModel):
    long_symbol: str = Field(min_length=16, max_length=24, pattern=r"^[A-Za-z.0-9]+$")
    short_symbol: str = Field(min_length=16, max_length=24, pattern=r"^[A-Za-z.0-9]+$")
    limit_debit: float = Field(gt=0, le=20)
    quantity: int = Field(default=1, ge=1, le=1)
    rationale: str = Field(default="Operator-entered paper trade", max_length=240)


class ManualTradePreview(BaseModel):
    valid: bool
    paper_only: bool = True
    underlying_symbol: str
    option_type: str
    expiration: datetime
    long_strike: float
    short_strike: float
    width: float
    limit_debit: float
    market_debit: float | None = None
    maximum_loss: float
    maximum_reward: float
    risk_budget: float
    liquidity_passed: bool
    reasons: list[str]


class ManualTradeResult(BaseModel):
    status: str
    paper_only: bool = True
    order_id: str
    client_order_id: str


class LiveMarketTick(BaseModel):
    symbol: str
    as_of: datetime
    price: float = Field(gt=0)
    bid: float | None = Field(default=None, gt=0)
    ask: float | None = Field(default=None, gt=0)
    spread_bps: float | None = Field(default=None, ge=0)
    day_change_pct: float | None = None
    source: str


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
