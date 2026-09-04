from dataclasses import dataclass


@dataclass(frozen=True)
class GammaProfileLevels:
    put_wall: float | None
    call_wall: float | None
    call_directional_bias: float | None
    put_directional_bias: float | None
    key_gamma_strike: float | None
    key_delta_strike: float | None
    hedge_wall: float | None


def calculate_gamma_profile_levels(
    contracts: list[dict[str, float | str | int | None]], spot: float
) -> GammaProfileLevels:
    """Port the supplied Nguyen strike-level scoring into a pure research calculation.

    Gamma signs remain a positioning convention, not observed dealer inventory. The
    function is intentionally isolated so historical option-chain tests can validate it
    before any new level is permitted to alter the execution policy.
    """
    strikes: dict[float, dict[str, float]] = {}
    for item in contracts:
        gamma = max(0.0, float(item.get("gamma") or 0))
        open_interest = max(0.0, float(item.get("open_interest") or 0))
        strike = float(item.get("strike") or 0)
        if gamma <= 0 or open_interest <= 0 or strike <= 0:
            continue
        row = strikes.setdefault(
            strike,
            {
                "call_gex": 0.0,
                "put_gex": 0.0,
                "call_oi": 0.0,
                "put_oi": 0.0,
                "net_delta": 0.0,
            },
        )
        option_type = str(item.get("option_type") or "").lower()
        gex = gamma * open_interest * 100 * spot
        delta_exposure = float(item.get("delta") or 0) * open_interest * 100
        if option_type == "call":
            row["call_gex"] += gex
            row["call_oi"] += open_interest
        elif option_type == "put":
            row["put_gex"] += gex
            row["put_oi"] += open_interest
        row["net_delta"] += delta_exposure

    nearby = {
        strike: row
        for strike, row in strikes.items()
        if spot * 0.85 <= strike <= spot * 1.15
    }

    def best(candidates: list[tuple[float, float]]) -> float | None:
        return max(candidates, key=lambda item: item[1])[0] if candidates else None

    put_wall_scores: list[tuple[float, float]] = []
    call_wall_scores: list[tuple[float, float]] = []
    call_bias_scores: list[tuple[float, float]] = []
    put_bias_scores: list[tuple[float, float]] = []
    for strike, row in nearby.items():
        call_gex = row["call_gex"]
        put_gex = row["put_gex"]
        if strike < spot and put_gex > call_gex:
            put_wall_scores.append(
                (strike, put_gex * row["put_oi"] / max(row["call_oi"], 1))
            )
        if strike > spot:
            call_wall_scores.append(
                (
                    strike,
                    (row["call_oi"] + row["put_oi"]) * (call_gex + put_gex),
                )
            )
            if call_gex > put_gex:
                call_bias_scores.append(
                    (strike, call_gex * row["call_oi"] / max(row["put_oi"], 1))
                )
        if strike < spot and call_gex > 0 and put_gex / call_gex > 2:
            skew_ratio = put_gex / call_gex
            put_bias_scores.append(
                (
                    strike,
                    put_gex
                    * skew_ratio
                    * row["put_oi"]
                    / max(row["call_oi"], 1),
                )
            )

    key_gamma = best(
        [(strike, abs(row["call_gex"] - row["put_gex"])) for strike, row in nearby.items()]
    )
    hedge_wall = best(
        [(strike, row["call_gex"] + row["put_gex"]) for strike, row in nearby.items()]
    )
    key_delta = best(
        [(strike, abs(row["net_delta"])) for strike, row in strikes.items()]
    )
    return GammaProfileLevels(
        put_wall=best(put_wall_scores),
        call_wall=best(call_wall_scores),
        call_directional_bias=best(call_bias_scores),
        put_directional_bias=best(put_bias_scores),
        key_gamma_strike=key_gamma,
        key_delta_strike=key_delta,
        hedge_wall=hedge_wall,
    )
