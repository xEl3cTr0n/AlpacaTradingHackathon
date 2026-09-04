from regimeshift.domain.models import (
    AgentVerdict,
    CouncilDecision,
    CouncilVote,
    Direction,
    GammaRegime,
    OptionsMicrostructureAssessment,
    RegimeAssessment,
    RotationSignal,
    ScannerCandidate,
    SectorRotationAssessment,
    Stance,
    StrategyName,
    SwingAssessment,
    SwingSignal,
    VoteChoice,
)

BULLISH_SWINGS = {SwingSignal.BULLISH_BREAKOUT, SwingSignal.BULLISH_REVERSAL}
BEARISH_SWINGS = {SwingSignal.BEARISH_BREAKDOWN, SwingSignal.BEARISH_REVERSAL}


def strategy_direction(strategy: StrategyName) -> Direction:
    if strategy == StrategyName.BULL_CALL_SPREAD:
        return Direction.BULLISH
    if strategy == StrategyName.BEAR_PUT_SPREAD:
        return Direction.BEARISH
    return Direction.SIDEWAYS


def _vote(agent: str, choice: VoteChoice, confidence: float, reason: str) -> CouncilVote:
    return CouncilVote(agent=agent, vote=choice, confidence=confidence, reason=reason)


class VotingCouncil:
    """Deterministic proposal-relative voting; the Risk Agent remains a separate hard gate."""

    minimum_directional_support = 3

    def evaluate(
        self,
        strategy: StrategyName,
        regime: RegimeAssessment,
        swing: SwingAssessment,
        rotation: SectorRotationAssessment,
        research: AgentVerdict,
        bull: AgentVerdict,
        bear: AgentVerdict,
        microstructure: OptionsMicrostructureAssessment,
        scanner_signal: ScannerCandidate | None = None,
        threshold: float = 0.56,
    ) -> CouncilDecision:
        direction = strategy_direction(strategy)
        votes = [
            self._technical_vote(direction, regime),
            self._swing_vote(direction, swing),
            self._rotation_vote(direction, rotation),
            self._research_vote(research),
            self._advocate_vote(direction, bull, bear),
            self._microstructure_vote(strategy, microstructure),
        ]
        if scanner_signal is not None:
            votes.append(self._scanner_vote(direction, scanner_signal))
        support = [vote for vote in votes if vote.vote == VoteChoice.SUPPORT]
        oppose = [vote for vote in votes if vote.vote == VoteChoice.OPPOSE]
        abstain_count = sum(vote.vote == VoteChoice.ABSTAIN for vote in votes)
        directional_weight = sum(vote.confidence for vote in [*support, *oppose])
        weighted_support = (
            sum(vote.confidence for vote in support) / directional_weight
            if directional_weight
            else 0.0
        )
        quorum_met = len(support) + len(oppose) >= 3
        approved = (
            strategy != StrategyName.NO_TRADE
            and quorum_met
            and len(support) >= self.minimum_directional_support
            and weighted_support >= threshold
        )
        return CouncilDecision(
            votes=votes,
            support_count=len(support),
            oppose_count=len(oppose),
            abstain_count=abstain_count,
            weighted_support=round(weighted_support, 3),
            approval_threshold=threshold,
            quorum_met=quorum_met,
            approved=approved,
        )

    @staticmethod
    def _scanner_vote(
        direction: Direction, signal: ScannerCandidate
    ) -> CouncilVote:
        aligned = (
            signal.actionable
            and signal.market_aligned
            and signal.direction == direction
        )
        return _vote(
            "Scanner",
            VoteChoice.SUPPORT if aligned else VoteChoice.OPPOSE,
            signal.conviction,
            (
                f"{signal.pattern.value} at {signal.conviction:.0%} conviction; "
                f"market alignment is {signal.market_aligned}."
            ),
        )

    @staticmethod
    def _microstructure_vote(
        strategy: StrategyName, assessment: OptionsMicrostructureAssessment
    ) -> CouncilVote:
        if assessment.status != "live" or assessment.data_quality < 0.6:
            return _vote(
                "Microstructure",
                VoteChoice.ABSTAIN,
                max(0.1, assessment.data_quality),
                assessment.rationale,
            )
        directional = strategy in {
            StrategyName.BULL_CALL_SPREAD,
            StrategyName.BEAR_PUT_SPREAD,
        }
        if strategy == StrategyName.IRON_CONDOR:
            choice = (
                VoteChoice.SUPPORT
                if assessment.gamma_regime == GammaRegime.STABILIZING
                and (assessment.gamma_concentration or 0) >= 0.5
                else VoteChoice.OPPOSE
            )
        elif directional and assessment.gamma_regime == GammaRegime.AMPLIFYING:
            choice = VoteChoice.SUPPORT
        elif directional and (assessment.gamma_concentration or 0) >= 0.6:
            choice = VoteChoice.OPPOSE
        else:
            choice = VoteChoice.ABSTAIN
        return _vote(
            "Microstructure",
            choice,
            assessment.data_quality,
            assessment.rationale,
        )

    @staticmethod
    def _technical_vote(direction: Direction, regime: RegimeAssessment) -> CouncilVote:
        if direction == Direction.SIDEWAYS:
            choice = (
                VoteChoice.SUPPORT
                if regime.direction == Direction.SIDEWAYS
                else VoteChoice.OPPOSE
            )
        elif regime.direction == direction:
            choice = VoteChoice.SUPPORT
        elif regime.direction == Direction.SIDEWAYS:
            choice = VoteChoice.ABSTAIN
        else:
            choice = VoteChoice.OPPOSE
        return _vote("Technical", choice, regime.confidence, regime.rationale)

    @staticmethod
    def _swing_vote(direction: Direction, swing: SwingAssessment) -> CouncilVote:
        swing_direction = Direction.SIDEWAYS
        if swing.signal in BULLISH_SWINGS:
            swing_direction = Direction.BULLISH
        elif swing.signal in BEARISH_SWINGS:
            swing_direction = Direction.BEARISH

        if direction == Direction.SIDEWAYS:
            choice = (
                VoteChoice.SUPPORT
                if swing_direction == Direction.SIDEWAYS
                else VoteChoice.OPPOSE
            )
        elif swing_direction == Direction.SIDEWAYS:
            choice = VoteChoice.ABSTAIN
        elif swing_direction == direction:
            choice = VoteChoice.SUPPORT
        else:
            choice = VoteChoice.OPPOSE
        return _vote("Swing", choice, swing.confidence, swing.rationale)

    @staticmethod
    def _rotation_vote(
        direction: Direction, rotation: SectorRotationAssessment
    ) -> CouncilVote:
        if rotation.signal == RotationSignal.MIXED:
            choice = VoteChoice.SUPPORT if direction == Direction.SIDEWAYS else VoteChoice.ABSTAIN
        elif direction == Direction.BULLISH:
            choice = (
                VoteChoice.SUPPORT
                if rotation.signal == RotationSignal.RISK_ON
                else VoteChoice.OPPOSE
            )
        elif direction == Direction.BEARISH:
            choice = (
                VoteChoice.SUPPORT
                if rotation.signal == RotationSignal.DEFENSIVE
                else VoteChoice.OPPOSE
            )
        else:
            choice = VoteChoice.OPPOSE
        return _vote("Rotation", choice, rotation.confidence, rotation.rationale)

    @staticmethod
    def _research_vote(research: AgentVerdict) -> CouncilVote:
        if research.stance == Stance.OPPOSE:
            choice = VoteChoice.OPPOSE
        elif research.stance == Stance.SUPPORT:
            choice = VoteChoice.SUPPORT
        else:
            choice = VoteChoice.ABSTAIN
        return _vote("Research", choice, research.confidence, research.summary)

    @staticmethod
    def _advocate_vote(
        direction: Direction, bull: AgentVerdict, bear: AgentVerdict
    ) -> CouncilVote:
        if direction == Direction.BULLISH:
            margin = bull.confidence - bear.confidence
            choice = VoteChoice.SUPPORT if margin >= 0.08 else VoteChoice.OPPOSE
            confidence = max(bull.confidence, bear.confidence)
        elif direction == Direction.BEARISH:
            margin = bear.confidence - bull.confidence
            choice = VoteChoice.SUPPORT if margin >= 0.08 else VoteChoice.OPPOSE
            confidence = max(bull.confidence, bear.confidence)
        else:
            margin = -abs(bull.confidence - bear.confidence)
            choice = VoteChoice.SUPPORT if abs(margin) <= 0.1 else VoteChoice.OPPOSE
            confidence = max(bull.confidence, bear.confidence)
        return _vote(
            "Advocacy",
            choice,
            confidence,
            f"Bull/bear confidence margin for the proposal is {margin:+.0%}.",
        )
