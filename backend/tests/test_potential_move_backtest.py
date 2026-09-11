from datetime import UTC, datetime, timedelta

from regimeshift.domain.models import PricePoint
from regimeshift.domain.potential_move_backtest import PotentialMoveBacktester


def _history(multiplier: float = 1.0) -> list[PricePoint]:
    start = datetime(2024, 1, 2, tzinfo=UTC)
    points: list[PricePoint] = []
    price = 100 * multiplier
    for index in range(220):
        change = 0.003 if index % 9 < 5 else -0.002
        price *= 1 + change
        points.append(
            PricePoint(
                timestamp=start + timedelta(days=index),
                open=price * 0.998,
                high=price * 1.012,
                low=price * 0.988,
                close=price,
                volume=2_000_000,
            )
        )
    return points


def test_move_backtest_is_chronological_and_never_execution_eligible() -> None:
    report = PotentialMoveBacktester().evaluate({"SPY": _history(), "AAPL": _history(1.5)})

    assert report["split_date"]
    assert report["train"]["observations"] > 0
    assert report["holdout"]["observations"] > 0
    assert 0 <= report["holdout"]["terminal_coverage"] <= 1
    research = report["indicator_research"]["holdout"]
    assert "directional_efficiency" in research
    assert "volatility_expansion" in research
    assert "overnight_gap_risk" in research
    assert research["execution_eligible"] is False
    assert report["execution_eligible"] is False
    assert "available at each close" in report["methodology"]
