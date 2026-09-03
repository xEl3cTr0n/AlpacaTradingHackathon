from datetime import UTC, datetime, timedelta

from regimeshift.domain.models import PricePoint, SwingSignal
from regimeshift.domain.swing import SwingEngine


def _points(closes: list[float]) -> list[PricePoint]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        PricePoint(
            timestamp=start + timedelta(days=index),
            open=close,
            high=close + 0.25,
            low=close - 0.25,
            close=close,
            volume=1_000_000,
        )
        for index, close in enumerate(closes)
    ]


def test_swing_engine_confirms_breakout_without_future_bars() -> None:
    closes = [100 + (index % 4) * 0.2 for index in range(27)] + [100.8, 101.2, 103.0]

    result = SwingEngine(lookback=10).assess(_points(closes))

    assert result.signal == SwingSignal.BULLISH_BREAKOUT
    assert result.swing_high < closes[-1]
    assert result.confidence > 0.5


def test_swing_engine_abstains_inside_range() -> None:
    closes = [100 + (index % 5) * 0.2 for index in range(30)]

    result = SwingEngine(lookback=10).assess(_points(closes))

    assert result.signal == SwingSignal.NEUTRAL
