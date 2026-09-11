import math
from datetime import UTC, datetime

from regimeshift.domain.models import (
    OptionChainContract,
    OptionChainSnapshot,
    OptionsMicrostructureAssessment,
    OptionsThesisSnapshot,
)


def _closest_contract(chain: OptionChainSnapshot) -> OptionChainContract:
    if not chain.contracts:
        raise ValueError(f"No {chain.option_type} contracts available for options thesis")
    return min(
        chain.contracts,
        key=lambda contract: abs(contract.strike - chain.underlying_price),
    )


def build_options_thesis(
    call_chain: OptionChainSnapshot,
    put_chain: OptionChainSnapshot,
    microstructure: OptionsMicrostructureAssessment,
    *,
    now: datetime | None = None,
) -> OptionsThesisSnapshot:
    """Build read-only options confirmation without granting trade authority."""
    if call_chain.underlying_symbol != put_chain.underlying_symbol:
        raise ValueError("Call and put chains must share an underlying")
    if call_chain.expiration != put_chain.expiration:
        raise ValueError("Call and put chains must share an expiration")
    if call_chain.option_type != "call" or put_chain.option_type != "put":
        raise ValueError("Options thesis requires one call chain and one put chain")

    current_time = now or datetime.now(UTC)
    spot = call_chain.underlying_price
    call = _closest_contract(call_chain)
    put = _closest_contract(put_chain)
    dte = max(0, (call_chain.expiration - current_time.date()).days)

    iv_values = [
        value
        for value in (call.implied_volatility, put.implied_volatility)
        if value is not None
    ]
    average_iv = sum(iv_values) / len(iv_values) if iv_values else None
    iv_move = spot * average_iv * math.sqrt(dte / 365) if average_iv is not None else None

    midpoint_values = (call.midpoint, put.midpoint)
    straddle_cost = (
        sum(value for value in midpoint_values if value is not None)
        if all(value is not None for value in midpoint_values)
        else None
    )
    agreement = None
    if iv_move is not None and straddle_cost is not None and max(iv_move, straddle_cost) > 0:
        agreement = min(iv_move, straddle_cost) / max(iv_move, straddle_cost)

    spreads = [
        value
        for value in (call.spread_percent, put.spread_percent)
        if value is not None
    ]
    open_interests = [
        value for value in (call.open_interest, put.open_interest) if value is not None
    ]
    max_spread = max(spreads) if spreads else None
    min_open_interest = min(open_interests) if open_interests else None

    evidence: list[str] = []
    if iv_move is not None:
        evidence.append(
            f"Average near-ATM IV {average_iv:.1%} implies ±${iv_move:.2f} through expiry"
        )
    else:
        evidence.append("Near-ATM implied volatility is unavailable")
    if straddle_cost is not None:
        evidence.append(
            f"Near-ATM call + put midpoint costs ${straddle_cost:.2f} per share"
        )
    else:
        evidence.append("A complete call + put midpoint is unavailable")
    if max_spread is not None:
        evidence.append(f"Wider leg quote is {max_spread:.1%} of midpoint")
    if min_open_interest is not None:
        evidence.append(f"Thinner near-ATM leg has {min_open_interest:,} open contracts")
    evidence.append(
        f"GEX regime is {microstructure.gamma_regime.value}; net GEX {microstructure.net_gex:,.0f}"
    )
    if microstructure.call_wall is not None or microstructure.put_wall is not None:
        evidence.append(
            "Gamma walls: "
            f"put {microstructure.put_wall or 0:.2f} / call {microstructure.call_wall or 0:.2f}"
        )

    complete_inputs = sum(
        value is not None
        for value in (average_iv, straddle_cost, max_spread, min_open_interest)
    )
    status = (
        "available"
        if complete_inputs == 4 and microstructure.status in {"available", "live"}
        else "partial"
    )
    return OptionsThesisSnapshot(
        underlying_symbol=call_chain.underlying_symbol,
        underlying_price=spot,
        expiration=call_chain.expiration,
        dte=dte,
        as_of=max(call_chain.as_of, put_chain.as_of, microstructure.as_of),
        source="Alpaca option-chain snapshots + contract open interest",
        status=status,
        call_symbol=call.symbol,
        put_symbol=put.symbol,
        call_strike=call.strike,
        put_strike=put.strike,
        average_implied_volatility=(round(average_iv, 4) if average_iv is not None else None),
        iv_expected_move_dollars=(round(iv_move, 2) if iv_move is not None else None),
        iv_expected_move_pct=(round(iv_move / spot, 4) if iv_move is not None else None),
        straddle_cost_dollars=(
            round(straddle_cost, 2) if straddle_cost is not None else None
        ),
        straddle_cost_pct=(
            round(straddle_cost / spot, 4) if straddle_cost is not None else None
        ),
        estimator_agreement=(round(agreement, 4) if agreement is not None else None),
        maximum_quote_spread_pct=(round(max_spread, 4) if max_spread is not None else None),
        minimum_open_interest=min_open_interest,
        gamma_regime=microstructure.gamma_regime,
        net_gex=microstructure.net_gex,
        gamma_concentration=microstructure.gamma_concentration,
        call_wall=microstructure.call_wall,
        put_wall=microstructure.put_wall,
        key_gamma_strike=microstructure.key_gamma_strike,
        data_quality=microstructure.data_quality,
        evidence=evidence,
        limitations=[
            "Read-only context: this snapshot cannot vote or authorize execution.",
            "Alpaca may return indicative rather than OPRA quotes for unsubscribed accounts.",
            "The call-plus-put midpoint is a cost reference, not a probability bound.",
            "IV is annualized and converted to an expiry move with sqrt(DTE/365).",
        ],
    )
