from datetime import UTC, datetime, timedelta

from regimeshift.domain.models import PricePoint, RotationPhase, RotationSignal
from regimeshift.domain.sector_rotation import SECTOR_UNIVERSE, SectorRotationEngine


def _history(daily_return: float) -> list[PricePoint]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    price = 100.0
    points: list[PricePoint] = []
    for index in range(80):
        price *= 1 + daily_return
        points.append(
            PricePoint(timestamp=start + timedelta(days=index), close=price, volume=1_000_000)
        )
    return points


def test_sector_rotation_ranks_relative_strength_and_detects_risk_on() -> None:
    histories = {"SPY": _history(0.001)}
    for symbol in SECTOR_UNIVERSE:
        if symbol in {"XLC", "XLY", "XLE", "XLF", "XLI", "XLB", "XLK"}:
            histories[symbol] = _history(0.002)
        else:
            histories[symbol] = _history(0.0004)

    assessment = SectorRotationEngine().assess(histories)

    assert assessment.signal == RotationSignal.RISK_ON
    assert assessment.breadth > 0.55
    assert len(assessment.sectors) == 11
    assert assessment.sectors[0].phase == RotationPhase.LEADING
    assert assessment.sectors[-1].phase == RotationPhase.LAGGING
    assert assessment.sectors[0].rotation_score >= assessment.sectors[-1].rotation_score


def test_sector_rotation_requires_complete_history() -> None:
    try:
        SectorRotationEngine().assess({"SPY": _history(0.001)})
    except ValueError as error:
        assert "missing history" in str(error)
    else:
        raise AssertionError("Expected missing sector history to fail")
