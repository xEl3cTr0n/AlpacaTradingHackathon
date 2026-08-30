from regimeshift.domain.models import Direction
from regimeshift.domain.regime import RegimeEngine
from regimeshift.services.market_data import DemoMarketDataProvider


def test_regime_assessment_is_bounded_and_explainable() -> None:
    market = DemoMarketDataProvider().get_context("SPY")
    assessment = RegimeEngine().assess(market.prices)

    assert assessment.direction in Direction
    assert 0 <= assessment.confidence <= 1
    assert -1 <= assessment.metrics.trend_score <= 1
    assert 0 <= assessment.metrics.volatility_percentile <= 1
    assert "realized volatility" in assessment.rationale


def test_regime_requires_enough_history() -> None:
    market = DemoMarketDataProvider().get_context("SPY")

    try:
        RegimeEngine().assess(market.prices[:20])
    except ValueError as error:
        assert "55" in str(error)
    else:
        raise AssertionError("Expected insufficient history to fail")
