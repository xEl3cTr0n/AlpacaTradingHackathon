from regimeshift.domain.microstructure import assess_microstructure
from regimeshift.domain.models import GammaRegime


def test_gex_and_concentration_follow_published_formulas() -> None:
    rows = []
    for index in range(30):
        rows.append(
            {
                "option_type": "call",
                "strike": 100 + (index % 3),
                "gamma": 0.02,
                "open_interest": 100,
                "delta": 0.5,
                "vega": 0.2,
                "volume": 10,
            }
        )
    for index in range(10):
        rows.append(
            {
                "option_type": "put",
                "strike": 90 + index,
                "gamma": 0.01,
                "open_interest": 100,
                "delta": -0.4,
                "vega": 0.3,
                "volume": 10,
            }
        )

    result = assess_microstructure("TEST", 100, rows, source="fixture")

    assert result.status == "live"
    assert result.gamma_regime == GammaRegime.STABILIZING
    assert result.net_gex == 500_000
    assert result.gamma_concentration is not None
    assert result.gamma_concentration > 0.8
    assert result.call_wall == 101
    assert result.key_gamma_strike == 100
    assert result.hedge_wall == 100


def test_sparse_chain_abstains_instead_of_inventing_data() -> None:
    result = assess_microstructure("TEST", 100, [], source="fixture")
    assert result.status == "unavailable"
    assert result.data_quality == 0
    assert result.gamma_regime == GammaRegime.UNAVAILABLE


def test_nguyen_profile_exposes_directional_strike_levels() -> None:
    rows = []
    for strike in (90, 95, 105, 110):
        rows.extend(
            [
                {
                    "option_type": "call",
                    "strike": strike,
                    "gamma": 0.01 if strike != 105 else 0.05,
                    "open_interest": 50 if strike != 105 else 400,
                    "delta": 0.5,
                    "vega": 0.2,
                    "volume": 1,
                },
                {
                    "option_type": "put",
                    "strike": strike,
                    "gamma": 0.04 if strike == 95 else 0.005,
                    "open_interest": 500 if strike == 95 else 25,
                    "delta": -0.5,
                    "vega": 0.2,
                    "volume": 1,
                },
            ]
            * 3
        )
    result = assess_microstructure("TEST", 100, rows, source="fixture")
    assert result.put_wall == 95
    assert result.put_directional_bias == 95
    assert result.call_wall == 105
    assert result.call_directional_bias == 105
    assert result.key_gamma_strike == 105
    assert result.hedge_wall == 95
