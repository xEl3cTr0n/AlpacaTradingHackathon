from datetime import UTC, datetime
from typing import Any

from regimeshift.domain.gamma_profile import calculate_gamma_profile_levels
from regimeshift.domain.models import (
    GammaRegime,
    OptionsMicrostructureAssessment,
)


def unavailable_microstructure(
    symbol: str, source: str, reason: str
) -> OptionsMicrostructureAssessment:
    return OptionsMicrostructureAssessment(
        underlying_symbol=symbol,
        as_of=datetime.now(UTC),
        source=source,
        status="unavailable",
        contract_count=0,
        net_gex=0,
        gross_gex=0,
        gamma_regime=GammaRegime.UNAVAILABLE,
        data_quality=0,
        rationale=reason,
        evidence=[reason, "Microstructure abstains; missing data is never synthesized."],
    )


def assess_microstructure(
    symbol: str,
    spot: float,
    contracts: list[dict[str, float | str | int | None]],
    *,
    source: str,
) -> OptionsMicrostructureAssessment:
    """Compute auditable near-term GEX metrics from a joined option chain.

    GEX follows Nguyen's paper convention: +calls, -puts, gamma * OI * 100 * spot.
    It is a positioning proxy, not observed dealer inventory.
    """
    usable = [
        item
        for item in contracts
        if item.get("gamma") is not None
        and item.get("open_interest") is not None
        and float(item.get("open_interest") or 0) > 0
    ]
    if len(usable) < 20:
        return unavailable_microstructure(
            symbol,
            source,
            f"Only {len(usable)} contracts had both Greeks and open interest; 20 required.",
        )

    net_gex = gross_gex = total_gamma_oi = atm_gamma_oi = 0.0
    call_delta_volume = put_delta_volume = total_volume = 0.0
    put_vega_volume = total_vega_volume = 0.0
    profile: dict[float, dict[str, Any]] = {}

    for item in usable:
        option_type = str(item["option_type"]).lower()
        strike = float(item["strike"])
        gamma = max(0.0, float(item["gamma"]))
        oi = int(float(item.get("open_interest") or 0))
        volume = int(max(0.0, float(item.get("volume") or 0)))
        delta = abs(float(item.get("delta") or 0))
        vega = abs(float(item.get("vega") or 0))
        iv = float(item["implied_volatility"]) if item.get("implied_volatility") is not None else None
        unsigned = gamma * oi * 100 * spot
        signed = unsigned if option_type == "call" else -unsigned
        row = profile.setdefault(
            strike,
            {
                "call_gex": 0.0,
                "put_gex": 0.0,
                "call_oi": 0,
                "put_oi": 0,
                "call_volume": 0,
                "put_volume": 0,
                "call_iv": None,
                "put_iv": None,
            },
        )
        if option_type == "call":
            row["call_gex"] += signed
            row["call_oi"] += oi
            row["call_volume"] += volume
            if iv is not None:
                row["call_iv"] = iv
            call_delta_volume += delta * volume
        else:
            row["put_gex"] += signed
            row["put_oi"] += oi
            row["put_volume"] += volume
            if iv is not None:
                row["put_iv"] = iv
            put_delta_volume += delta * volume
            put_vega_volume += vega * volume
        net_gex += signed
        gross_gex += unsigned
        total_volume += volume
        total_vega_volume += vega * volume
        total_gamma_oi += gamma * oi
        if 0.98 <= strike / spot <= 1.02:
            atm_gamma_oi += gamma * oi

    gmc = atm_gamma_oi / total_gamma_oi if total_gamma_oi else None
    nope = (
        (call_delta_volume - put_delta_volume) / total_volume if total_volume else None
    )
    pvi = put_vega_volume / total_vega_volume if total_vega_volume else None
    levels = calculate_gamma_profile_levels(usable, spot)
    call_wall = levels.call_wall
    put_wall = levels.put_wall
    normalized = net_gex / gross_gex if gross_gex else 0.0
    if normalized >= 0.08:
        gamma_regime = GammaRegime.STABILIZING
    elif normalized <= -0.08:
        gamma_regime = GammaRegime.AMPLIFYING
    else:
        gamma_regime = GammaRegime.MIXED

    atm_ivs = [
        float(item["implied_volatility"])
        for item in usable
        if item.get("implied_volatility") and 0.97 <= float(item["strike"]) / spot <= 1.03
    ]
    average_iv = sum(atm_ivs) / len(atm_ivs) if atm_ivs else None

    completeness = len(usable) / max(1, len(contracts))
    breadth = min(1.0, len(usable) / 100)
    data_quality = min(1.0, 0.65 * completeness + 0.35 * breadth)
    gmc_text = f"{gmc:.0%}" if gmc is not None else "unavailable"
    rationale = (
        f"Near-term {symbol} gamma is {gamma_regime.value}; "
        f"{gmc_text} of gamma-OI sits within ±2% of spot."
    )
    return OptionsMicrostructureAssessment(
        underlying_symbol=symbol,
        as_of=datetime.now(UTC),
        source=source,
        status="live",
        contract_count=len(usable),
        net_gex=round(net_gex, 2),
        gross_gex=round(gross_gex, 2),
        gamma_concentration=round(gmc, 4) if gmc is not None else None,
        nope_options=round(nope, 4) if nope is not None else None,
        put_vega_intensity=round(pvi, 4) if pvi is not None else None,
        call_wall=call_wall,
        put_wall=put_wall,
        call_directional_bias=levels.call_directional_bias,
        put_directional_bias=levels.put_directional_bias,
        key_gamma_strike=levels.key_gamma_strike,
        key_delta_strike=levels.key_delta_strike,
        hedge_wall=levels.hedge_wall,
        gamma_regime=gamma_regime,
        average_iv=round(average_iv, 4) if average_iv is not None else None,
        data_quality=round(data_quality, 3),
        gex_by_strike=[
            {
                "strike": strike,
                "call_gex": round(row["call_gex"], 2),
                "put_gex": round(row["put_gex"], 2),
                "net_gex": round(row["call_gex"] + row["put_gex"], 2),
                "call_oi": row["call_oi"],
                "put_oi": row["put_oi"],
                "total_oi": row["call_oi"] + row["put_oi"],
                "call_volume": row["call_volume"],
                "put_volume": row["put_volume"],
                "total_volume": row["call_volume"] + row["put_volume"],
                "call_iv": round(row["call_iv"], 4) if row["call_iv"] is not None else None,
                "put_iv": round(row["put_iv"], 4) if row["put_iv"] is not None else None,
                "average_iv": round((row["call_iv"] + row["put_iv"]) / 2, 4)
                if row["call_iv"] is not None and row["put_iv"] is not None
                else (round(row["call_iv"], 4) if row["call_iv"] is not None else (round(row["put_iv"], 4) if row["put_iv"] is not None else None)),
            }
            for strike, row in sorted(profile.items())
        ],
        rationale=rationale,
        evidence=[
            f"Net GEX {net_gex:,.0f}; gross GEX {gross_gex:,.0f}",
            f"Call wall {call_wall or 0:g}; put wall {put_wall or 0:g}",
            (
                f"Key gamma {levels.key_gamma_strike or 0:g}; "
                f"key delta {levels.key_delta_strike or 0:g}; "
                f"hedge wall {levels.hedge_wall or 0:g}"
            ),
            f"NOPE-options {nope:+.3f}" if nope is not None else "NOPE-options unavailable",
            (
                f"Put vega intensity {pvi:.0%}"
                if pvi is not None
                else "Put vega intensity unavailable"
            ),
            "GEX sign assumes dealers long calls and short puts; it is a transparent proxy.",
        ],
    )
