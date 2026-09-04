def select_contracts_by_moneyness(
    contracts: list[dict[str, object]],
    *,
    spot: float,
    option_type: str,
    moneyness: str,
    limit: int = 10,
) -> list[dict[str, object]]:
    """Return the nearest contracts on one requested side of spot."""
    if option_type not in {"call", "put"}:
        raise ValueError("Option type must be call or put")
    if moneyness not in {"itm", "otm"}:
        raise ValueError("Moneyness must be itm or otm")

    def matches(strike: float) -> bool:
        is_itm = strike < spot if option_type == "call" else strike > spot
        return is_itm if moneyness == "itm" else not is_itm

    filtered = [item for item in contracts if matches(float(item["strike"]))]
    filtered.sort(key=lambda item: (abs(float(item["strike"]) - spot), float(item["strike"])))
    return filtered[:limit]
