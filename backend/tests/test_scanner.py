from datetime import UTC, datetime, timedelta

from regimeshift.domain.models import PricePoint, ScannerPattern
from regimeshift.domain.scanner import LARGE_CAP_UNIVERSE, LargeCapScanner
from regimeshift.services.market_data import DemoMarketDataProvider


def _points(closes: list[float], *, volume: int) -> list[PricePoint]:
    start = datetime(2025, 1, 2, tzinfo=UTC)
    return [
        PricePoint(
            timestamp=start + timedelta(days=index),
            open=close,
            high=close * 1.01,
            low=close * 0.99,
            close=close,
            volume=volume * (2 if index == len(closes) - 1 else 1),
        )
        for index, close in enumerate(closes)
    ]


def test_bullish_18_ema_cross_is_actionable_only_with_confirmations() -> None:
    benchmark = _points([400 + index * 0.5 for index in range(80)], volume=5_000_000)
    closes = [100 + index * 0.8 for index in range(80)]
    closes[-2] = 145
    closes[-1] = 180
    candidate = LargeCapScanner().score(
        "AAPL", "Apple", _points(closes, volume=2_000_000), benchmark, 79
    )

    assert candidate is not None
    assert candidate.pattern == ScannerPattern.BULLISH_18EMA_CROSS
    assert candidate.market_aligned is True
    assert candidate.conviction >= 0.60
    assert candidate.actionable is True
    assert candidate.signal_tier == "production"
    assert candidate.risk_cap_dollars == 1_000
    assert candidate.option_bias == "call_debit_spread"


def test_opposite_cross_inside_trend_is_watch_only() -> None:
    benchmark = _points([400 + index * 0.5 for index in range(80)], volume=5_000_000)
    closes = [100 + index * 0.8 for index in range(80)]
    closes[-2] = 180
    closes[-1] = 120

    candidate = LargeCapScanner().score(
        "AAPL", "Apple", _points(closes, volume=2_000_000), benchmark, 79
    )

    assert candidate is not None
    assert candidate.pattern == ScannerPattern.BULLISH_TREND_WATCH
    assert candidate.actionable is False
    assert candidate.signal_tier == "watch"


def test_scanner_is_ranked_and_bounded() -> None:
    provider = DemoMarketDataProvider()
    histories = provider.get_price_history(["SPY", *LARGE_CAP_UNIVERSE], days=365)

    snapshot = LargeCapScanner().scan(histories, limit=5, source="test tape")

    assert snapshot.universe_size == 24
    assert snapshot.scanned_count == 24
    assert len(snapshot.candidates) == 5
    assert [candidate.rank for candidate in snapshot.candidates] == [1, 2, 3, 4, 5]
    assert snapshot.source == "test tape"
