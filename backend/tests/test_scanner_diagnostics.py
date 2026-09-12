from datetime import UTC, datetime, timedelta

import pytest
from regimeshift.domain.models import PricePoint, UnderlyingTradePlan
from regimeshift.domain.scanner_diagnostics import (
    breakout_plans,
    build_scanner_diagnostics,
    choppiness,
    r_factor,
)
from regimeshift.domain.scanner_research_backtest import evaluate_research, simulate_breakout
from regimeshift.domain.volume_rsi import volume_rsi_series


def bars(closes: list[float], volume: int = 100) -> list[PricePoint]:
    return [
        PricePoint(
            timestamp=datetime(2025, 1, 1, 5, tzinfo=UTC) + timedelta(days=i),
            open=c,
            high=c + 0.5,
            low=c - 0.5,
            close=c,
            volume=volume,
        )
        for i, c in enumerate(closes)
    ]


def test_r_factor_hand_calculated_original_and_strict_threshold():
    tape = bars([100.0] * 14)
    tape[-1] = tape[-1].model_copy(
        update={"open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0, "volume": 300}
    )
    reading = r_factor(tape)
    # Average volume = 1600/14; RVOL = 2.625; momentum = 5%; proxy = 102.666...
    assert reading.relative_volume == 2.625
    assert reading.score == 319.2
    assert reading.bullish_match and not reading.bearish_match
    tape = bars([100.0] * 14)
    for p in tape[:-1]:
        p.volume = 11
    tape[-1].volume = 39  # 39/(182/14) = 3 -> exactly 150, not a match
    tape[-1].high = tape[-1].low = tape[-1].close
    reading = r_factor(tape)
    assert reading.score == 150
    assert not reading.bullish_match
    tape[-1].volume = 40
    assert r_factor(tape).bullish_match


def test_r_factor_red_day_and_missing_data():
    tape = bars([100.0] * 14)
    tape[-1] = tape[-1].model_copy(
        update={"open": 100.0, "high": 101.0, "low": 95.0, "close": 96.0, "volume": 300}
    )
    reading = r_factor(tape)
    assert reading.bearish_match and reading.score < -300
    assert reading.directional_volume == -2.625
    assert r_factor(tape[:13]) is None
    tape[-1].open = None
    assert r_factor(tape) is None
    zero = bars([100.0] * 14, volume=0)
    assert r_factor(zero).relative_volume == 1  # Original fallback


def test_chop_distinguishes_trend_range_flat_and_unavailable():
    trending = bars([100.0 + i for i in range(30)])
    choppy = bars([100.0 + i % 2 for i in range(30)])
    assert choppiness(trending).state == "trend"
    assert choppiness(choppy).state == "chop"
    flat = bars([100.0] * 30)
    for p in flat:
        p.high = p.low = p.close
    assert choppiness(flat).value == 100
    assert choppiness(flat[:14]).state == "unavailable"
    flat[-1].high = None
    assert choppiness(flat).state == "unavailable"


def test_completed_daily_and_intraday_exclude_unfinished_and_future_bars():
    daily = bars([100.0 + i for i in range(30)])
    now = daily[-1].timestamp + timedelta(hours=9, minutes=37)
    intraday = [
        p.model_copy(update={"timestamp": now - timedelta(minutes=15 * (30 - i))})
        for i, p in enumerate(daily)
    ]
    future = intraday[-1].model_copy(update={"timestamp": now, "close": 9000.0})
    result = build_scanner_diagnostics(
        [*intraday, future], daily, timeframe="15Min", evaluation_time=now
    )
    assert result.levels_as_of == intraday[-1].timestamp
    assert result.daily_r_factor.as_of == daily[-2].timestamp
    assert result.provisional_r_factor.as_of == daily[-1].timestamp
    assert result.provisional_r_factor.provisional
    assert result.daily_r_factor.provisional is False
    assert not result.stale
    later = build_scanner_diagnostics(
        intraday, daily, timeframe="15Min", evaluation_time=now + timedelta(hours=2)
    )
    assert later.stale
    assert all(p.state == "stale" for p in later.plans)


def test_call_put_plan_ordering_and_no_auto_permission():
    tape = bars([100.0 + i for i in range(30)])
    call, put = breakout_plans(tape, choppiness(tape))
    assert call.invalidation < call.entry < call.target_1 < call.target_2
    assert put.invalidation > put.entry > put.target_1 > put.target_2
    assert call.entry > max(p.high for p in tape[-20:])
    assert put.entry < min(p.low for p in tape[-20:])
    assert call.time_exit_bars == put.time_exit_bars == 8


def test_volume_rsi_smoothing_raw_repeats_quiet_deduplicates():
    tape = bars([100.0 + i for i in range(40)])
    tape[30].volume, tape[31].volume = 300, 300
    readings = volume_rsi_series(tape)
    assert readings[30].rsi == 100
    assert readings[30].volume_ratio == pytest.approx(300 / 110)
    assert readings[30].raw_signal == readings[31].raw_signal == "overbought"
    assert readings[30].quiet_signal == "overbought"
    assert readings[31].quiet_signal == "none"
    assert readings[31].context == "up_continuation"
    assert readings[36].context == "none"  # confirmation window expired
    # Future input must not repaint any previous reading.
    assert volume_rsi_series(tape[:32]) == readings[:32]


def test_volume_rsi_reversal_needs_price_and_rsi_confirmation():
    tape = bars([100.0 + i for i in range(31)] + [125.0, 115.0])
    tape[30].volume = 300
    readings = volume_rsi_series(tape)
    assert readings[30].quiet_signal == "overbought"
    assert readings[31].context != "reversal_down"  # RSI still above 70
    assert readings[32].context == "reversal_down"
    assert readings[32].event_at == tape[30].timestamp
    assert readings[32].event_age_bars == 2


def test_new_opposite_extreme_does_not_erase_reversal_on_fifth_bar():
    tape = bars([100.0 + i for i in range(31)] + [130.0, 130.0, 130.0, 130.0, 80.0])
    tape[30].volume = tape[35].volume = 300
    reading = volume_rsi_series(tape)[-1]
    assert reading.quiet_signal == "oversold"
    assert reading.context == "reversal_down"
    assert reading.event_at == tape[30].timestamp


def test_low_volatility_filter_is_optional_and_not_chop():
    tape = bars([100.0 + i * 0.01 for i in range(31)])
    for p in tape:
        p.high, p.low = p.close + 0.01, p.close - 0.01
    tape[-1].volume = 300
    original = volume_rsi_series(tape)[-1]
    filtered = volume_rsi_series(tape, use_low_vol_filter=True)[-1]
    assert original.raw_signal == "overbought" and original.low_volatility
    assert filtered.raw_signal == "none"
    assert choppiness(tape).state == "trend"


def test_rsi_strict_volume_threshold_and_missing_ohlc_reset():
    tape = bars([100.0 + i for i in range(30)], volume=94)
    tape[-1].volume = 114  # 114/95 == 1.2; strict > means no signal
    assert volume_rsi_series(tape)[-1].raw_signal == "none"
    tape[-1].volume = 115
    assert volume_rsi_series(tape)[-1].raw_signal == "overbought"
    tape[-2].high = None
    assert volume_rsi_series(tape)[-1] is None


def test_backtest_next_bar_only_stop_first_and_gap_cost():
    tape = bars([100.0] * 12)
    plan = UnderlyingTradePlan(
        side="call",
        entry=101,
        invalidation=99,
        target_1=103,
        target_2=105,
        risk_per_share=2,
        state="wait_breakout",
    )
    tape[0].high = 500  # Signal bar must never fill.
    assert simulate_breakout(tape, 0, plan) is None
    tape[1].high, tape[1].low = 106, 98
    trade = simulate_breakout(tape, 0, plan)
    assert trade["entry_index"] == 1 and trade["reason"] == "stop"
    assert trade["return"] == pytest.approx((99 - 101) / 101 - 0.001)
    tape[1].low = 100
    tape[1].high = 102
    tape[2].open, tape[2].high, tape[2].low, tape[2].close = 95, 97, 94, 96
    trade = simulate_breakout(tape, 0, plan)
    assert trade["return"] == pytest.approx((95 - 101) / 101 - 0.001)


def test_backtest_entry_bar_prior_gap_is_not_used_as_exit_price():
    tape = bars([100.0] * 12)
    plan = UnderlyingTradePlan(
        side="call",
        entry=101,
        invalidation=99,
        target_1=103,
        target_2=105,
        risk_per_share=2,
        state="wait_breakout",
    )
    tape[1].open, tape[1].low, tape[1].high = 95, 94, 102
    trade = simulate_breakout(tape, 0, plan)
    assert trade["return"] == pytest.approx((99 - 101) / 101 - 0.001)


def test_backtest_purges_boundary_windows(monkeypatch):
    import regimeshift.domain.scanner_research_backtest as module

    tape = bars([100.0 + i for i in range(200)])
    now = tape[-1].timestamp + timedelta(days=1)
    split = tape[140].timestamp
    checked = []
    monkeypatch.setattr(
        module,
        "r_factor",
        lambda _points: type(
            "R",
            (),
            {
                "bullish_match": True,
                "bearish_match": False,
            },
        )(),
    )

    def simulate(points, index, plan):
        assert not (points[index].timestamp < split <= points[index + 11].timestamp)
        checked.append(index)
        return None

    monkeypatch.setattr(module, "simulate_breakout", simulate)
    module.evaluate_research({"TEST": tape}, now)
    assert checked and any(index >= 140 for index in checked)


def test_backtest_honest_empty_results_and_today_excluded():
    tape = bars([100.0] * 200)
    result = evaluate_research({"TEST": tape}, tape[-1].timestamp + timedelta(hours=8))
    assert result["end"] == tape[-2].timestamp.isoformat()
    assert result["execution_authorized"] is False
    assert result["variants"]["rsi_raw_fade"]["holdout"]["trades"] == 0
    assert result["variants"]["rsi_raw_fade"]["holdout"]["win_rate"] is None


def test_chart_api_does_not_emit_unfinished_bar_markers(monkeypatch):
    from types import SimpleNamespace

    import regimeshift.main as module
    from fastapi.testclient import TestClient
    from regimeshift.config import Settings, get_settings

    now = datetime(2026, 9, 11, 17, 37, tzinfo=UTC)
    tape = bars([100.0 + i for i in range(40)])
    for i, p in enumerate(tape):
        p.timestamp = now - timedelta(minutes=(39 - i) * 15 + 7)
    tape[30].volume = tape[39].volume = 300

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setattr(
        module,
        "build_market_data_provider",
        lambda _settings: SimpleNamespace(
            get_chart_history=lambda *args: tape,
        ),
    )
    module.app.dependency_overrides[get_settings] = lambda: Settings(market_data_mode="demo")
    try:
        response = TestClient(module.app).get("/api/v1/chart?symbol=TEST&timeframe=15Min")
    finally:
        module.app.dependency_overrides.clear()
    assert response.status_code == 200
    events = response.json()["volume_rsi_signals"]
    assert events
    assert all(datetime.fromisoformat(e["as_of"]) + timedelta(minutes=15) <= now for e in events)
