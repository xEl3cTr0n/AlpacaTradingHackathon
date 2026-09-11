from datetime import UTC, datetime, timedelta

from regimeshift.domain.models import Direction, PricePoint
from regimeshift.domain.potential_move import build_potential_move_thesis


def _daily_points() -> list[PricePoint]:
    start = datetime(2026, 1, 2, tzinfo=UTC)
    return [
        PricePoint(
            timestamp=start + timedelta(days=index),
            open=100 + index * 0.4,
            high=102 + index * 0.4,
            low=98 + index * 0.4,
            close=100 + index * 0.4,
            volume=2_000_000,
        )
        for index in range(80)
    ]


def test_move_magnitude_is_independent_from_direction() -> None:
    points = _daily_points()
    common = dict(
        points=points,
        spot=points[-1].close,
        conviction=0.72,
        ema_18=points[-1].close - 1,
        rsi_14=58,
        relative_strength=0.03,
        volume_ratio=1.2,
        market_aligned=True,
    )

    bullish = build_potential_move_thesis(direction=Direction.BULLISH, **common)
    bearish = build_potential_move_thesis(direction=Direction.BEARISH, **common)

    assert bullish.expected_move_dollars == bearish.expected_move_dollars
    assert bullish.direction_score == 72
    assert bearish.direction_score == -72
    assert bullish.lower_bound < common["spot"] < bullish.upper_bound
    assert bullish.directional_efficiency_20d == 1
    assert bullish.research_only is True


def test_move_thesis_exposes_trigger_target_invalidation_and_conflict() -> None:
    thesis = build_potential_move_thesis(
        _daily_points(),
        spot=131.6,
        direction=Direction.BULLISH,
        conviction=0.64,
        ema_18=130,
        rsi_14=74,
        relative_strength=-0.02,
        volume_ratio=0.7,
        market_aligned=False,
    )

    assert thesis.trigger
    assert thesis.target
    assert thesis.invalidation
    assert thesis.conflicting_evidence
    assert "not an options-implied move" in thesis.basis


def test_move_thesis_surfaces_chop_expansion_and_gap_risk_without_changing_direction() -> None:
    points = _daily_points()
    points[-1] = points[-1].model_copy(
        update={
            "open": points[-2].close * 1.03,
            "high": points[-2].close * 1.05,
            "low": points[-2].close * 0.98,
            "close": points[-2].close * 0.99,
        }
    )
    thesis = build_potential_move_thesis(
        points,
        spot=points[-1].close,
        direction=Direction.BULLISH,
        conviction=0.6,
        ema_18=points[-1].close - 1,
        rsi_14=55,
        relative_strength=0.01,
        volume_ratio=1.1,
        market_aligned=True,
    )

    assert -1 <= thesis.directional_efficiency_20d <= 1
    assert thesis.volatility_expansion_ratio > 0
    assert thesis.average_gap_pct_20d > 0
    assert thesis.direction_score == 60
    assert thesis.research_only is True
