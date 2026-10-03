from datetime import UTC, datetime, timedelta

from regimeshift.domain.levels import (
    calculate_iv_levels,
    calculate_structural_levels,
    calculate_volume_profile,
)
from regimeshift.domain.models import PricePoint


def _make_bar(
    timestamp: datetime, close: float, volume: int, high: float | None = None, low: float | None = None
) -> PricePoint:
    return PricePoint(
        timestamp=timestamp,
        open=close,
        high=high or (close * 1.01),
        low=low or (close * 0.99),
        close=close,
        volume=volume,
    )


def test_calculate_iv_levels_produces_expected_boundaries() -> None:
    spot = 500.0
    iv = 0.20
    dte = 365
    # For 1 year, expected move = spot * iv * 1.0 = 100.0
    levels = calculate_iv_levels(spot, iv, dte)
    assert levels.average_iv == 0.20
    assert levels.expected_move == 100.0
    assert levels.upper_1s == 600.0
    assert levels.lower_1s == 400.0
    assert levels.upper_2s == 700.0
    assert levels.lower_2s == 300.0


def test_calculate_iv_levels_handles_missing_or_zero_iv() -> None:
    empty = calculate_iv_levels(500.0, None)
    assert empty.average_iv is None
    assert empty.upper_1s is None
    assert empty.lower_1s is None


def test_calculate_volume_profile_identifies_poc_and_value_area() -> None:
    start = datetime(2026, 9, 17, 9, 30, tzinfo=UTC)
    # Heavy volume centered at 100.0
    bars = [
        _make_bar(start + timedelta(minutes=15 * 0), 95.0, 1_000),
        _make_bar(start + timedelta(minutes=15 * 1), 98.0, 2_000),
        _make_bar(start + timedelta(minutes=15 * 2), 100.0, 50_000, high=100.5, low=99.5),
        _make_bar(start + timedelta(minutes=15 * 3), 100.2, 45_000, high=100.6, low=99.8),
        _make_bar(start + timedelta(minutes=15 * 4), 102.0, 2_000),
        _make_bar(start + timedelta(minutes=15 * 5), 105.0, 1_000),
    ]
    vp = calculate_volume_profile(bars, num_bins=10)
    assert vp.poc is not None
    assert 99.0 <= vp.poc <= 101.5
    assert vp.val is not None and vp.vah is not None
    assert vp.val <= vp.poc <= vp.vah


def test_calculate_structural_levels_computes_ichimoku_and_vwap() -> None:
    start = datetime(2026, 9, 17, 9, 30, tzinfo=UTC)
    bars = [
        _make_bar(start + timedelta(minutes=15 * i), 100.0 + i * 0.5, 10_000)
        for i in range(60)
    ]
    struct = calculate_structural_levels(bars)
    assert struct.kijun_sen is not None
    assert struct.tenkan_sen is not None
    assert struct.senkou_span_b is not None
    assert struct.session_vwap is not None
    assert struct.session_vwap > 0
    # Continuous Ichimoku series
    assert len(struct.ichimoku_series) > 0
    last_pt = struct.ichimoku_series[-1]
    assert last_pt.tenkan_sen is not None
    assert last_pt.kijun_sen is not None
    assert last_pt.senkou_span_a is not None
    assert last_pt.senkou_span_b is not None
    assert last_pt.chikou_span is not None


def test_calculate_iv_levels_computes_session_move_and_prior_day_pivots() -> None:
    spot = 500.0
    iv = 0.20
    start = datetime(2026, 9, 16, tzinfo=UTC)
    daily_bars = [
        _make_bar(start, 495.0, 100_000, high=502.0, low=490.0),
    ]
    levels = calculate_iv_levels(spot, iv, dte=7, daily_bars=daily_bars)
    assert levels.expected_move is not None
    assert levels.session_expected_move is not None
    assert levels.session_expected_move > 0
    assert levels.session_upper == round(spot + levels.session_expected_move, 2)
    assert levels.session_lower == round(spot - levels.session_expected_move, 2)
    # 7-day expected move must be strictly greater than 1-day session move
    assert levels.expected_move > levels.session_expected_move
    # Prior day pivots
    assert levels.prior_day_high == 502.0
    assert levels.prior_day_low == 490.0
    assert levels.prior_day_close == 495.0

