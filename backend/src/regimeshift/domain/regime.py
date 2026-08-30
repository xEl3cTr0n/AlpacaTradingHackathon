from math import sqrt
from statistics import mean, pstdev

from regimeshift.domain.models import (
    Direction,
    PricePoint,
    RegimeAssessment,
    RegimeMetrics,
    Volatility,
)


def _ema(values: list[float], period: int) -> float:
    multiplier = 2 / (period + 1)
    current = values[0]
    for value in values[1:]:
        current = (value * multiplier) + (current * (1 - multiplier))
    return current


def _rsi(values: list[float], period: int = 14) -> float:
    changes = [current - previous for previous, current in zip(values, values[1:], strict=False)]
    window = changes[-period:]
    gains = mean([max(change, 0) for change in window])
    losses = mean([abs(min(change, 0)) for change in window])
    if losses == 0:
        return 100.0
    relative_strength = gains / losses
    return 100 - (100 / (1 + relative_strength))


def _returns(values: list[float]) -> list[float]:
    return [(current / previous) - 1 for previous, current in zip(values, values[1:], strict=False)]


def _volatility_percentile(returns: list[float], window: int = 20) -> tuple[float, float]:
    current = pstdev(returns[-window:]) * sqrt(252)
    history = [
        pstdev(returns[index - window : index]) * sqrt(252)
        for index in range(window, len(returns) + 1)
    ]
    percentile = sum(value <= current for value in history) / len(history)
    return current, percentile


class RegimeEngine:
    minimum_points = 55

    def assess(self, prices: list[PricePoint]) -> RegimeAssessment:
        if len(prices) < self.minimum_points:
            raise ValueError(f"At least {self.minimum_points} price points are required")

        closes = [point.close for point in prices]
        returns = _returns(closes)
        ema_fast = _ema(closes[-50:], 20)
        ema_slow = _ema(closes[-80:], 50)
        rsi = _rsi(closes)
        realized_volatility, volatility_percentile = _volatility_percentile(returns)

        volatility_floor = max(realized_volatility, 0.08)
        normalized_spread = ((ema_fast / ema_slow) - 1) / (volatility_floor / sqrt(252) * 10)
        momentum = (rsi - 50) / 50
        trend_score = max(-1.0, min(1.0, (normalized_spread * 0.7) + (momentum * 0.3)))

        if trend_score >= 0.18:
            direction = Direction.BULLISH
        elif trend_score <= -0.18:
            direction = Direction.BEARISH
        else:
            direction = Direction.SIDEWAYS

        if volatility_percentile >= 0.70:
            volatility = Volatility.HIGH
        elif volatility_percentile <= 0.30:
            volatility = Volatility.LOW
        else:
            volatility = Volatility.NORMAL

        confidence = min(
            0.96,
            0.48 + abs(trend_score) * 0.32 + abs(volatility_percentile - 0.5) * 0.22,
        )
        metrics = RegimeMetrics(
            ema_fast=round(ema_fast, 2),
            ema_slow=round(ema_slow, 2),
            rsi_14=round(rsi, 1),
            realized_volatility=round(realized_volatility, 4),
            volatility_percentile=round(volatility_percentile, 3),
            trend_score=round(trend_score, 3),
        )
        label = f"{direction.value}_{volatility.value}"
        rationale = (
            f"Trend score {trend_score:+.2f} with RSI {rsi:.1f}; "
            f"realized volatility is in the {volatility_percentile:.0%} rolling percentile."
        )
        return RegimeAssessment(
            direction=direction,
            volatility=volatility,
            label=label,
            confidence=round(confidence, 3),
            metrics=metrics,
            rationale=rationale,
        )
