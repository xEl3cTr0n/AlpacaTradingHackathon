from datetime import UTC, date, datetime

from regimeshift.domain.models import (
    GammaRegime,
    OptionChainContract,
    OptionChainSnapshot,
    OptionsMicrostructureAssessment,
)
from regimeshift.domain.options_thesis import build_options_thesis


def _chain(option_type: str) -> OptionChainSnapshot:
    expiration = date(2026, 10, 16)
    contract = OptionChainContract(
        symbol=f"MSFT261016{'C' if option_type == 'call' else 'P'}00500000",
        option_type=option_type,
        expiration=expiration,
        strike=500,
        moneyness="otm",
        bid=9,
        ask=11,
        midpoint=10,
        spread_percent=0.2,
        open_interest=250,
        implied_volatility=0.30,
        delta=0.5 if option_type == "call" else -0.5,
        gamma=0.02,
    )
    return OptionChainSnapshot(
        underlying_symbol="MSFT",
        underlying_price=500,
        option_type=option_type,
        moneyness="otm",
        expiration=expiration,
        expirations=[expiration],
        contracts=[contract],
        as_of=datetime(2026, 9, 11, tzinfo=UTC),
        source="test",
    )


def test_options_thesis_keeps_context_read_only() -> None:
    microstructure = OptionsMicrostructureAssessment(
        underlying_symbol="MSFT",
        as_of=datetime(2026, 9, 11, tzinfo=UTC),
        source="test",
        status="live",
        contract_count=100,
        net_gex=-1_000_000,
        gross_gex=2_000_000,
        gamma_concentration=0.4,
        call_wall=510,
        put_wall=490,
        key_gamma_strike=500,
        gamma_regime=GammaRegime.AMPLIFYING,
        data_quality=0.9,
        rationale="test",
        evidence=[],
    )

    result = build_options_thesis(
        _chain("call"),
        _chain("put"),
        microstructure,
        now=datetime(2026, 9, 11, tzinfo=UTC),
    )

    assert result.status == "available"
    assert result.dte == 35
    assert result.straddle_cost_dollars == 20
    assert result.iv_expected_move_dollars is not None
    assert result.gamma_regime == GammaRegime.AMPLIFYING
    assert "cannot vote or authorize execution" in result.limitations[0]
