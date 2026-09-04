from datetime import UTC, datetime

from regimeshift.domain.layers import assess_bottom_up, assess_mood_vibe
from regimeshift.domain.models import (
    BottomUpQuad,
    Direction,
    GammaRegime,
    OptionsMicrostructureAssessment,
    RegimeAssessment,
    RegimeMetrics,
    RotationSignal,
    SectorRotationAssessment,
    VibeRegime,
    Volatility,
)


def fixture_regime(*, score: float = 0.5, rsi: float = 60) -> RegimeAssessment:
    return RegimeAssessment(
        direction=Direction.BULLISH,
        volatility=Volatility.NORMAL,
        label="bullish_normal",
        confidence=0.8,
        metrics=RegimeMetrics(
            ema_fast=101,
            ema_slow=100,
            rsi_14=rsi,
            realized_volatility=0.15,
            volatility_percentile=0.5,
            trend_score=score,
        ),
        rationale="fixture",
    )


def fixture_rotation(breadth: float = 0.7) -> SectorRotationAssessment:
    return SectorRotationAssessment(
        as_of=datetime.now(UTC),
        signal=RotationSignal.RISK_ON,
        confidence=0.8,
        breadth=breadth,
        leaders=["XLK"],
        laggards=["XLU"],
        sectors=[],
        rationale="fixture",
    )


def fixture_micro(regime: GammaRegime, gmc: float) -> OptionsMicrostructureAssessment:
    return OptionsMicrostructureAssessment(
        underlying_symbol="SPY",
        as_of=datetime.now(UTC),
        source="fixture",
        status="live",
        contract_count=100,
        net_gex=1,
        gross_gex=2,
        gamma_concentration=gmc,
        gamma_regime=regime,
        data_quality=0.9,
        rationale="fixture",
        evidence=[],
    )


def test_bottom_up_quad_uses_trend_and_etf_breadth() -> None:
    result = assess_bottom_up(fixture_regime(), fixture_rotation())
    assert result.quadrant == BottomUpQuad.QUAD_1
    assert result.label == "Broad risk-on"


def test_negative_gamma_maps_proxy_to_volatility_vibe() -> None:
    bottom = assess_bottom_up(fixture_regime(), fixture_rotation())
    result = assess_mood_vibe(
        fixture_micro(GammaRegime.AMPLIFYING, 0.3), bottom, fixture_regime()
    )
    assert result.vibe == VibeRegime.VOLATILITY
    assert result.status == "research_proxy"
    assert result.input_coverage < 1
