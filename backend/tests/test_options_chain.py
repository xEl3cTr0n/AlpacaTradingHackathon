from regimeshift.domain.options_chain import select_contracts_by_moneyness


def rows() -> list[dict[str, object]]:
    return [{"strike": strike, "symbol": f"OPT{strike}"} for strike in range(90, 111)]


def test_call_chain_orders_nearest_itm_and_otm_strikes() -> None:
    itm = select_contracts_by_moneyness(
        rows(), spot=100.5, option_type="call", moneyness="itm", limit=3
    )
    otm = select_contracts_by_moneyness(
        rows(), spot=100.5, option_type="call", moneyness="otm", limit=3
    )
    assert [item["strike"] for item in itm] == [100, 99, 98]
    assert [item["strike"] for item in otm] == [101, 102, 103]


def test_put_chain_orders_nearest_itm_and_otm_strikes() -> None:
    itm = select_contracts_by_moneyness(
        rows(), spot=100.5, option_type="put", moneyness="itm", limit=3
    )
    otm = select_contracts_by_moneyness(
        rows(), spot=100.5, option_type="put", moneyness="otm", limit=3
    )
    assert [item["strike"] for item in itm] == [101, 102, 103]
    assert [item["strike"] for item in otm] == [100, 99, 98]
