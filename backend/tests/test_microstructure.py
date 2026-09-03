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
    assert result.call_wall == 100


def test_sparse_chain_abstains_instead_of_inventing_data() -> None:
    result = assess_microstructure("TEST", 100, [], source="fixture")
    assert result.status == "unavailable"
    assert result.data_quality == 0
    assert result.gamma_regime == GammaRegime.UNAVAILABLE
