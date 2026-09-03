from datetime import UTC, datetime
from uuid import uuid4

from regimeshift.config import Settings
from regimeshift.domain.council import VotingCouncil
from regimeshift.domain.models import (
    AgentVerdict,
    AnalysisControls,
    CouncilDecision,
    DecisionSnapshot,
    Direction,
    InstrumentMode,
    MarketContext,
    OptionsMicrostructureAssessment,
    RegimeAssessment,
    RiskDecision,
    RotationSignal,
    SectorRotationAssessment,
    Stance,
    StrategyMode,
    StrategyName,
    StrategyProposal,
    SwingAssessment,
    SwingSignal,
    ToolEvidence,
    Volatility,
)
from regimeshift.domain.regime import RegimeEngine
from regimeshift.domain.sector_rotation import SECTOR_UNIVERSE, SectorRotationEngine
from regimeshift.domain.swing import SwingEngine
from regimeshift.services.market_data import MarketDataProvider
from regimeshift.services.options_data import build_options_provider

INDEX_OPTION_PROXIES = {"SPY": "XSP"}


class DecisionPipeline:
    def __init__(self, settings: Settings, market_data: MarketDataProvider):
        self.settings = settings
        self.market_data = market_data
        self.regime_engine = RegimeEngine()
        self.rotation_engine = SectorRotationEngine()
        self.swing_engine = SwingEngine()
        self.voting_council = VotingCouncil()
        self.options_provider = build_options_provider(settings)

    def analyze(self, symbol: str, controls: AnalysisControls | None = None) -> DecisionSnapshot:
        controls = controls or AnalysisControls(max_risk_pct=self.settings.max_risk_per_trade_pct)
        market = self.market_data.get_context(symbol)
        regime = self.regime_engine.assess(market.prices)
        swing = self.swing_engine.assess(market.prices)
        rotation_symbols = [self.rotation_engine.benchmark_symbol, *SECTOR_UNIVERSE]
        rotation = self.rotation_engine.assess(
            self.market_data.get_price_history(rotation_symbols)
        )
        microstructure = self.options_provider.get_assessment(
            market.symbol, market.current_price
        )
        technical = self._technical_agent(regime)
        microstructure_agent = self._microstructure_agent(microstructure)
        swing_agent = self._swing_agent(swing)
        research = self._research_agent(market)
        rotation_agent = self._rotation_agent(rotation)
        bull = self._bull_agent(regime, research, rotation)
        bear = self._bear_agent(regime, research, rotation)
        strategy = self._select_strategy(market.symbol, regime, swing, controls)
        council = self.voting_council.evaluate(
            strategy.name,
            regime,
            swing,
            rotation,
            research,
            bull,
            bear,
            microstructure,
            threshold=0.52,
        )
        risk = self._risk_gate(
            regime, swing, microstructure, strategy, bull, bear, council, controls
        )
        strategy.status = "paper candidate" if risk.approved else "vetoed"

        return DecisionSnapshot(
            decision_id=str(uuid4()),
            generated_at=datetime.now(UTC),
            mode=self.settings.market_data_mode.lower(),
            market=market,
            regime=regime,
            swing=swing,
            sector_rotation=rotation,
            options_microstructure=microstructure,
            agents=[
                technical,
                microstructure_agent,
                swing_agent,
                research,
                rotation_agent,
                bull,
                bear,
                self._risk_verdict(risk),
            ],
            council=council,
            tool_evidence=self._tool_evidence(),
            strategy=strategy,
            risk=risk,
            controls=controls,
        )

    @staticmethod
    def _microstructure_agent(
        assessment: OptionsMicrostructureAssessment,
    ) -> AgentVerdict:
        if assessment.status != "live":
            stance = Stance.NEUTRAL
        elif assessment.gamma_regime.value == "amplifying":
            stance = Stance.OPPOSE
        else:
            stance = Stance.SUPPORT
        return AgentVerdict(
            agent="Microstructure",
            stance=stance,
            confidence=assessment.data_quality,
            summary=assessment.rationale,
            evidence=assessment.evidence,
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

    @staticmethod
    def _swing_agent(swing: SwingAssessment) -> AgentVerdict:
        stance = Stance.NEUTRAL if swing.signal == SwingSignal.NEUTRAL else Stance.SUPPORT
        return AgentVerdict(
            agent="Swing",
            stance=stance,
            confidence=swing.confidence,
            summary=swing.signal.value.replace("_", " ").title(),
            evidence=[
                f"{swing.lookback}-session low {swing.swing_low:.2f}",
                f"{swing.lookback}-session high {swing.swing_high:.2f}",
                swing.rationale,
            ],
        )

    def _rotation_agent(self, rotation: SectorRotationAssessment) -> AgentVerdict:
        stance = Stance.NEUTRAL
        if rotation.signal == RotationSignal.RISK_ON:
            stance = Stance.SUPPORT
        elif rotation.signal == RotationSignal.DEFENSIVE:
            stance = Stance.OPPOSE
        return AgentVerdict(
            agent="Rotation",
            stance=stance,
            confidence=rotation.confidence,
            summary=f"Sector leadership is {rotation.signal.value.replace('_', ' ')}.",
            evidence=[
                f"Leadership breadth versus SPY is {rotation.breadth:.0%}",
                f"Leaders: {', '.join(rotation.leaders)}",
                f"Laggards: {', '.join(rotation.laggards)}",
            ],
        )

    def _bull_agent(
        self,
        regime: RegimeAssessment,
        research: AgentVerdict,
        rotation: SectorRotationAssessment,
    ) -> AgentVerdict:
        aligned = regime.direction == Direction.BULLISH
        rotation_adjustment = 0.05 if rotation.signal == RotationSignal.RISK_ON else 0
        if rotation.signal == RotationSignal.DEFENSIVE:
            rotation_adjustment = -0.1
        confidence = min(
            0.9,
            regime.confidence + (0.05 if aligned else -0.14) + rotation_adjustment,
        )
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
                f"Sector rotation is {rotation.signal.value.replace('_', ' ')}",
                research.summary,
            ],
        )

    def _bear_agent(
        self,
        regime: RegimeAssessment,
        research: AgentVerdict,
        rotation: SectorRotationAssessment,
    ) -> AgentVerdict:
        volatility_risk = regime.volatility == Volatility.HIGH
        confidence = 0.72 if volatility_risk else 0.56
        if rotation.signal == RotationSignal.DEFENSIVE:
            confidence = min(0.9, confidence + 0.1)
        elif rotation.signal == RotationSignal.RISK_ON:
            confidence = max(0.35, confidence - 0.05)
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
                f"Sector rotation is {rotation.signal.value.replace('_', ' ')}",
                "A close through the slow trend would invalidate directional momentum",
                research.summary,
            ],
        )

    def _select_strategy(
        self,
        signal_symbol: str,
        regime: RegimeAssessment,
        swing: SwingAssessment,
        controls: AnalysisControls,
    ) -> StrategyProposal:
        account_risk = self.settings.account_equity * controls.max_risk_pct
        if controls.max_loss_cap_dollars is not None:
            account_risk = min(account_risk, controls.max_loss_cap_dollars)
        effective_direction = regime.direction
        if controls.strategy_mode == StrategyMode.BULLISH:
            effective_direction = Direction.BULLISH
        elif controls.strategy_mode == StrategyMode.BEARISH:
            effective_direction = Direction.BEARISH
        elif controls.strategy_mode == StrategyMode.NEUTRAL:
            effective_direction = Direction.SIDEWAYS

        index_underlying = INDEX_OPTION_PROXIES.get(signal_symbol)
        if controls.instrument_mode == InstrumentMode.INDEX_OPTION and not index_underlying:
            raise ValueError("Validated index-option mode currently supports only SPY→XSP signals")
        use_index = bool(
            index_underlying
            and controls.instrument_mode in {InstrumentMode.AUTO, InstrumentMode.INDEX_OPTION}
        )
        instrument_type = (
            InstrumentMode.INDEX_OPTION if use_index else InstrumentMode.EQUITY_OPTION
        )
        underlying_symbol = index_underlying if use_index and index_underlying else signal_symbol
        option_style = "European" if use_index else "American"
        settlement = "cash" if use_index else "physical"

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
            display_name=f"{underlying_symbol} {display}",
            signal_symbol=signal_symbol,
            underlying_symbol=underlying_symbol,
            instrument_type=instrument_type,
            option_style=option_style,
            settlement=settlement,
            thesis=thesis,
            structure=structure,
            max_loss_dollars=max_loss,
            risk_percent=max_loss / self.settings.account_equity,
            status="pending risk review",
            entry_rules=[
                f"Regime confidence at least {controls.min_confidence:.0%}",
                f"Swing signal: {swing.signal.value.replace('_', ' ')}",
                "At least 3 of 6 deterministic council votes support the proposal",
                "Live option-chain GEX must pass completeness and structure checks",
                "Sector rotation must not materially oppose the directional thesis",
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
        swing: SwingAssessment,
        microstructure: OptionsMicrostructureAssessment,
        strategy: StrategyProposal,
        bull: AgentVerdict,
        bear: AgentVerdict,
        council: CouncilDecision,
        controls: AnalysisControls,
    ) -> RiskDecision:
        max_allowed = self.settings.account_equity * controls.max_risk_pct
        if controls.max_loss_cap_dollars is not None:
            max_allowed = min(max_allowed, controls.max_loss_cap_dollars)
        reasons: list[str] = []
        approved = True
        if strategy.name == StrategyName.NO_TRADE:
            approved = False
            reasons.append("Policy selected no trade because no regime-specific edge was present")
        if strategy.max_loss_dollars > max_allowed:
            approved = False
            reasons.append("Preview loss exceeds the account risk budget")
        if self.settings.market_data_mode.lower() == "alpaca":
            if microstructure.status != "live" or microstructure.data_quality < 0.6:
                approved = False
                reasons.append("Live GEX evidence is unavailable or below 60% data quality")
            elif microstructure.gamma_regime.value == "amplifying":
                max_allowed = min(max_allowed, 200.0)
                if strategy.max_loss_dollars > max_allowed:
                    approved = False
                    reasons.append("Negative-gamma conditions cap maximum loss at $200")
            elif (
                microstructure.gamma_concentration is not None
                and microstructure.gamma_concentration >= 0.6
                and strategy.name
                in {StrategyName.BULL_CALL_SPREAD, StrategyName.BEAR_PUT_SPREAD}
                and swing.signal
                not in {SwingSignal.BULLISH_BREAKOUT, SwingSignal.BEARISH_BREAKDOWN}
            ):
                approved = False
                reasons.append("High gamma concentration requires a confirmed breakout")
        if regime.confidence < controls.min_confidence:
            approved = False
            reasons.append(
                "Regime confidence is below the "
                f"{controls.min_confidence:.0%} authorization threshold"
            )
        if not council.approved and strategy.name != StrategyName.NO_TRADE:
            approved = False
            reasons.append(
                f"Council rejected the proposal: {council.support_count} support, "
                f"{council.oppose_count} oppose, {council.abstain_count} abstain"
            )
        index_candidate = (
            strategy.instrument_type == InstrumentMode.INDEX_OPTION
            and strategy.name != StrategyName.NO_TRADE
        )
        if (
            index_candidate and not 21 <= controls.target_dte <= 45
        ):
            approved = False
            reasons.append("Index swing positions require a 21–45 DTE target")
        if index_candidate and swing.signal not in {
            SwingSignal.BULLISH_BREAKOUT,
            SwingSignal.BEARISH_BREAKDOWN,
        }:
            approved = False
            reasons.append("Validated XSP policy requires a confirmed 20-session breakout")
        if index_candidate and regime.metrics.volatility_percentile > 0.7:
            approved = False
            reasons.append("Validated XSP policy excludes the top 30% volatility regime")
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

    def _tool_evidence(self) -> list[ToolEvidence]:
        return [
            ToolEvidence(
                provider="Alpaca Options API",
                capability="live Greeks, open interest, and GEX evidence",
                status="used" if self.settings.alpaca_configured else "offline",
                summary="Computes transparent GEX and gamma concentration from the bounded chain.",
            ),
            ToolEvidence(
                provider="Alpaca Trading API",
                capability="market data and paper-account telemetry",
                status="used" if self.settings.alpaca_configured else "demo",
                summary="Normalized price, news, account, and option-ready evidence.",
            ),
            ToolEvidence(
                provider="Alpaca MCP",
                capability="agent-native research",
                status="connected" if self.settings.alpaca_mcp_enabled else "configured",
                summary=(
                    "Read-only agent toolsets are available in this runtime."
                    if self.settings.alpaca_mcp_enabled
                    else "Repo-scoped read-only MCP runs with Claude/Gemini outside Vercel."
                ),
            ),
            ToolEvidence(
                provider="Alpaca CLI",
                capability="reproducible paper execution",
                status="enabled" if self.settings.alpaca_cli_enabled else "external_runner",
                summary=(
                    "The autonomy runner may execute only a Risk-approved order plan."
                    if self.settings.alpaca_cli_enabled
                    else "Pinned paper-only runner performs contract discovery and gated orders."
                ),
            ),
        ]
