from regimeshift.domain.models import PricePoint, SwingAssessment, SwingSignal


def _high(point: PricePoint) -> float:
    return point.high if point.high is not None else point.close


def _low(point: PricePoint) -> float:
    return point.low if point.low is not None else point.close


class SwingEngine:
    """Detect confirmed breakouts and reversals without looking beyond the current bar."""

    minimum_points = 25

    def __init__(self, lookback: int = 20, confirmation_return: float = 0.004):
        if lookback < 5:
            raise ValueError("Swing lookback must be at least 5 sessions")
        self.lookback = lookback
        self.confirmation_return = confirmation_return

    def assess(self, prices: list[PricePoint]) -> SwingAssessment:
        required = max(self.minimum_points, self.lookback + 4)
        if len(prices) < required:
            raise ValueError(f"Swing analysis requires at least {required} price points")

        prior = prices[-(self.lookback + 1) : -1]
        current = prices[-1].close
        swing_low = min(_low(point) for point in prior)
        swing_high = max(_high(point) for point in prior)
        span = max(swing_high - swing_low, current * 0.005)
        range_position = max(0.0, min(1.0, (current - swing_low) / span))
        momentum = (current / prices[-4].close) - 1
        breakout_margin = (current / swing_high) - 1
        breakdown_margin = (swing_low / current) - 1

        if current > swing_high and momentum >= self.confirmation_return:
            signal = SwingSignal.BULLISH_BREAKOUT
            strength = min(1.0, breakout_margin / 0.02)
            rationale = (
                f"Close {current:.2f} broke the {self.lookback}-session swing high "
                f"{swing_high:.2f} with {momentum:+.1%} three-session momentum."
            )
        elif current < swing_low and momentum <= -self.confirmation_return:
            signal = SwingSignal.BEARISH_BREAKDOWN
            strength = min(1.0, breakdown_margin / 0.02)
            rationale = (
                f"Close {current:.2f} broke the {self.lookback}-session swing low "
                f"{swing_low:.2f} with {momentum:+.1%} three-session momentum."
            )
        elif range_position <= 0.25 and momentum >= self.confirmation_return:
            signal = SwingSignal.BULLISH_REVERSAL
            strength = min(1.0, (0.25 - range_position) / 0.25 + momentum / 0.04)
            rationale = (
                f"Price confirmed a bounce from the {swing_low:.2f} swing-low zone; "
                f"range position is {range_position:.0%}."
            )
        elif range_position >= 0.75 and momentum <= -self.confirmation_return:
            signal = SwingSignal.BEARISH_REVERSAL
            strength = min(1.0, (range_position - 0.75) / 0.25 + abs(momentum) / 0.04)
            rationale = (
                f"Price rejected the {swing_high:.2f} swing-high zone; "
                f"range position is {range_position:.0%}."
            )
        else:
            signal = SwingSignal.NEUTRAL
            strength = 0.0
            rationale = (
                f"Price remains inside the {swing_low:.2f}–{swing_high:.2f} swing range "
                "without reversal confirmation."
            )

        confidence = 0.45 if signal == SwingSignal.NEUTRAL else min(0.92, 0.58 + strength * 0.24)
        return SwingAssessment(
            signal=signal,
            confidence=round(confidence, 3),
            lookback=self.lookback,
            swing_low=round(swing_low, 2),
            swing_high=round(swing_high, 2),
            range_position=round(range_position, 3),
            rationale=rationale,
        )
