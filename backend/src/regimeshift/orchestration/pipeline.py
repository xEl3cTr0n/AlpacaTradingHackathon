from datetime import UTC, datetime
from uuid import uuid4

from regimeshift.config import Settings
from regimeshift.domain.models import (
    AgentVerdict,
    AnalysisControls,
    DecisionSnapshot,
    Direction,
    MarketContext,
    RegimeAssessment,
    RiskDecision,
    Stance,
    StrategyMode,
    StrategyName,
    StrategyProposal,
    Volatility,
)
from regimeshift.domain.regime import RegimeEngine
from regimeshift.services.market_data import MarketDataProvider


class DecisionPipeline:
    def __init__(self, settings: Settings, market_data: MarketDataProvider):
        self.settings = settings
        self.market_data = market_data
        self.regime_engine = RegimeEngine()

    def analyze(self, symbol: str, controls: AnalysisControls | None = None) -> DecisionSnapshot:
        controls = controls or AnalysisControls(max_risk_pct=self.settings.max_risk_per_trade_pct)
        market = self.market_data.get_context(symbol)
        regime = self.regime_engine.assess(market.prices)
        technical = self._technical_agent(regime)
        research = self._research_agent(market)
        bull = self._bull_agent(regime, research)
        bear = self._bear_agent(regime, research)
        strategy = self._select_strategy(regime, controls)
        risk = self._risk_gate(regime, strategy, bull, bear, controls)
        strategy.status = "approved preview" if risk.approved else "vetoed"

        return DecisionSnapshot(
            decision_id=str(uuid4()),
            generated_at=datetime.now(UTC),
            mode=self.settings.market_data_mode.lower(),
            market=market,
            regime=regime,
            agents=[technical, research, bull, bear, self._risk_verdict(risk)],
            strategy=strategy,
            risk=risk,
            controls=controls,
        )

    def _technical_agent(self, regime: RegimeAssessment) -> AgentVerdict:
        metrics = regime.metrics
        stance = Stance.SUPPORT if regime.direction != Direction.SIDEWAYS else Stance.NEUTRAL
        return AgentVerdict(
            agent="Technical",
            stance=stance,
            confidence=regime.confidence,
            summary=f"Price structure indicates a {regime.label.replace('_', ' ')} regime.",
            evidence=[
                f"20-day EMA {metrics.ema_fast:.2f} vs 50-day EMA {metrics.ema_slow:.2f}",
                f"RSI(14) is {metrics.rsi_14:.1f}",
                f"Annualized realized volatility is {metrics.realized_volatility:.1%}",
            ],
        )

    def _research_agent(self, market: MarketContext) -> AgentVerdict:
        risk_words = {"warning", "cuts", "probe", "lawsuit", "miss", "uncertain"}
        risk_hits = sum(
            any(word in headline.lower() for word in risk_words) for headline in market.headlines
        )
        stance = Stance.OPPOSE if risk_hits >= 2 else Stance.NEUTRAL
        return AgentVerdict(
            agent="Research",
            stance=stance,
            confidence=0.62 if market.headlines else 0.35,
            summary=(
                "No concentrated headline-risk cluster detected."
                if risk_hits < 2
                else "Recent headlines contain a concentrated risk cluster."
            ),
            evidence=market.headlines[:3] or ["No recent headlines were returned"],
        )

    def _bull_agent(self, regime: RegimeAssessment, research: AgentVerdict) -> AgentVerdict:
        aligned = regime.direction == Direction.BULLISH
        confidence = min(0.9, regime.confidence + (0.05 if aligned else -0.14))
        return AgentVerdict(
            agent="Bull",
            stance=Stance.SUPPORT if aligned else Stance.NEUTRAL,
            confidence=max(0.2, confidence),
            summary=(
                "Positive trend persistence supports a defined-risk upside structure."
                if aligned
                else "The bullish case lacks strong directional confirmation."
            ),
            evidence=[
                f"Trend score is {regime.metrics.trend_score:+.2f}",
                f"Regime confidence is {regime.confidence:.0%}",
                research.summary,
            ],
        )

    def _bear_agent(self, regime: RegimeAssessment, research: AgentVerdict) -> AgentVerdict:
        volatility_risk = regime.volatility == Volatility.HIGH
        confidence = 0.72 if volatility_risk else 0.56
        return AgentVerdict(
            agent="Bear",
            stance=Stance.OPPOSE,
            confidence=confidence,
            summary=(
                "Elevated volatility raises whipsaw and gap-risk concerns."
                if volatility_risk
                else "A regime reversal remains the primary invalidation risk."
            ),
            evidence=[
                f"Volatility percentile is {regime.metrics.volatility_percentile:.0%}",
                "A close through the slow trend would invalidate directional momentum",
                research.summary,
            ],
        )

    def _select_strategy(
        self, regime: RegimeAssessment, controls: AnalysisControls
    ) -> StrategyProposal:
        account_risk = self.settings.account_equity * controls.max_risk_pct
        effective_direction = regime.direction
        if controls.strategy_mode == StrategyMode.BULLISH:
            effective_direction = Direction.BULLISH
        elif controls.strategy_mode == StrategyMode.BEARISH:
            effective_direction = Direction.BEARISH
        elif controls.strategy_mode == StrategyMode.NEUTRAL:
            effective_direction = Direction.SIDEWAYS

        if effective_direction == Direction.BULLISH:
            name = StrategyName.BULL_CALL_SPREAD
            display = "Bull call debit spread"
            structure = ["Buy call near 0.55 delta", "Sell higher-strike call near 0.30 delta"]
            thesis = "Participate in upside momentum while capping premium at risk."
        elif effective_direction == Direction.BEARISH:
            name = StrategyName.BEAR_PUT_SPREAD
            display = "Bear put debit spread"
            structure = ["Buy put near -0.55 delta", "Sell lower-strike put near -0.30 delta"]
            thesis = "Express downside momentum with a predefined maximum loss."
        elif regime.volatility == Volatility.HIGH or controls.strategy_mode == StrategyMode.NEUTRAL:
            name = StrategyName.IRON_CONDOR
            display = "Defined-risk iron condor"
            structure = [
                "Sell call and put near 0.20 absolute delta",
                "Buy protective wings one strike farther out",
            ]
            thesis = "Harvest elevated premium only while price remains range-bound."
        else:
            name = StrategyName.NO_TRADE
            display = "No trade"
            structure = []
            thesis = "Directional and volatility edges are insufficiently distinct."

        max_loss = 0.0 if name == StrategyName.NO_TRADE else min(650.0, account_risk)
        return StrategyProposal(
            name=name,
            display_name=display,
            thesis=thesis,
            structure=structure,
            max_loss_dollars=max_loss,
            risk_percent=max_loss / self.settings.account_equity,
            status="pending risk review",
            entry_rules=[
                f"Regime confidence at least {controls.min_confidence:.0%}",
                f"Target expiration near {controls.target_dte} DTE",
                "Bid/ask spread and open-interest liquidity checks pass",
            ],
            exit_rules=[
                "Take profit at 50% of maximum reward",
                "Exit at 75% of maximum loss",
                "Close or reduce when the detected regime changes",
            ],
        )

    def _risk_gate(
        self,
        regime: RegimeAssessment,
        strategy: StrategyProposal,
        bull: AgentVerdict,
        bear: AgentVerdict,
        controls: AnalysisControls,
    ) -> RiskDecision:
        max_allowed = self.settings.account_equity * controls.max_risk_pct
        reasons: list[str] = []
        approved = True
        if strategy.name == StrategyName.NO_TRADE:
            approved = False
            reasons.append("Policy selected no trade because no regime-specific edge was present")
        if strategy.max_loss_dollars > max_allowed:
            approved = False
            reasons.append("Preview loss exceeds the account risk budget")
        if regime.confidence < controls.min_confidence:
            approved = False
            reasons.append(
                "Regime confidence is below the "
                f"{controls.min_confidence:.0%} authorization threshold"
            )
        if bear.confidence > bull.confidence + 0.15:
            approved = False
            reasons.append("Bear case materially outweighs the Bull case")
        if approved:
            reasons.extend(
                [
                    f"Maximum loss stays below the ${max_allowed:,.0f} risk budget",
                    "Defined-risk structure; naked short options are prohibited",
                    "Execution remains preview-only until contract quotes are resolved",
                ]
            )
        return RiskDecision(
            approved=approved,
            max_allowed_loss=round(max_allowed, 2),
            approved_contracts=1 if approved else 0,
            reasons=reasons,
        )

    @staticmethod
    def _risk_verdict(risk: RiskDecision) -> AgentVerdict:
        return AgentVerdict(
            agent="Risk",
            stance=Stance.SUPPORT if risk.approved else Stance.VETO,
            confidence=0.94,
            summary="Risk budget approved for preview." if risk.approved else "Trade vetoed.",
            evidence=risk.reasons,
        )
