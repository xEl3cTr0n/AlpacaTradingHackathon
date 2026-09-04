from regimeshift.domain.models import (
    BottomUpQuad,
    BottomUpQuadAssessment,
    GammaRegime,
    MoodVibeAssessment,
    OptionsMicrostructureAssessment,
    RegimeAssessment,
    SectorRotationAssessment,
    VibeRegime,
)


def assess_bottom_up(
    regime: RegimeAssessment, rotation: SectorRotationAssessment
) -> BottomUpQuadAssessment:
    trend_positive = regime.metrics.trend_score >= 0.18
    breadth_positive = rotation.breadth >= 0.55
    if trend_positive and breadth_positive:
        quadrant, label = BottomUpQuad.QUAD_1, "Broad risk-on"
    elif trend_positive:
        quadrant, label = BottomUpQuad.QUAD_2, "Narrow advance"
    elif not breadth_positive and rotation.breadth <= 0.45:
        quadrant, label = BottomUpQuad.QUAD_3, "Broad risk-off"
    else:
        quadrant, label = BottomUpQuad.QUAD_4, "Rotation / repair"
    confidence = min(
        0.95,
        0.5 + abs(regime.metrics.trend_score) * 0.25 + abs(rotation.breadth - 0.5) * 0.5,
    )
    return BottomUpQuadAssessment(
        quadrant=quadrant,
        label=label,
        trend_positive=trend_positive,
        breadth_positive=breadth_positive,
        confidence=round(confidence, 3),
        rationale=(
            f"Security trend score is {regime.metrics.trend_score:+.2f}; "
            f"{rotation.breadth:.0%} of sector ETFs outperform SPY."
        ),
    )


def assess_mood_vibe(
    micro: OptionsMicrostructureAssessment,
    bottom_up: BottomUpQuadAssessment,
    regime: RegimeAssessment,
) -> MoodVibeAssessment:
    if micro.status != "live":
        return MoodVibeAssessment(
            mood="unavailable",
            vibe=VibeRegime.UNAVAILABLE,
            status="insufficient_inputs",
            confidence=0,
            input_coverage=0,
            rationale="Live option Greeks and open interest are required.",
            missing_inputs=["GEX", "GMC", "options volume", "vanna", "charm"],
        )

    gmc = micro.gamma_concentration
    if micro.gamma_regime == GammaRegime.AMPLIFYING or (gmc is not None and gmc < 0.35):
        mood, vibe = "fragile", VibeRegime.VOLATILITY
    elif (
        bottom_up.quadrant == BottomUpQuad.QUAD_1
        and micro.gamma_regime == GammaRegime.STABILIZING
        and regime.metrics.rsi_14 >= 65
    ):
        mood, vibe = "extended", VibeRegime.EUPHORIA
    elif (
        bottom_up.quadrant == BottomUpQuad.QUAD_4
        and micro.gamma_regime == GammaRegime.STABILIZING
    ):
        mood, vibe = "supported", VibeRegime.BTFD
    else:
        mood, vibe = "balanced", VibeRegime.INDIFFERENCE

    available = 2 + int(micro.nope_options is not None) + int(
        micro.put_vega_intensity is not None
    )
    coverage = available / 6
    confidence = min(0.7, micro.data_quality * (0.45 + coverage * 0.35))
    return MoodVibeAssessment(
        mood=mood,
        vibe=vibe,
        status="research_proxy",
        confidence=round(confidence, 3),
        input_coverage=round(coverage, 3),
        rationale=(
            f"Proxy combines {micro.gamma_regime.value} gamma, "
            f"{gmc:.0%} GMC, {bottom_up.quadrant.value}, and RSI."
            if gmc is not None
            else "Proxy has insufficient gamma concentration data."
        ),
        missing_inputs=["contract volume / NOPE", "vanna / GEX+", "charm / CHR", "REPH"],
    )
