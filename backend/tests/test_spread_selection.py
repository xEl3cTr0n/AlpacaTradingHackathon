from datetime import UTC, datetime, timedelta

import pytest
from regimeshift.services.alpaca_cli import AlpacaCliAdapter


def chain(rows):
    contracts = []
    snapshots = {}
    for strike, bid, ask, interest in rows:
        symbol = str(strike)
        contracts.append(
            {
                "symbol": symbol,
                "strike_price": str(strike),
                "expiration_date": "2026-10-16",
                "open_interest": interest,
            }
        )
        snapshots[symbol] = {
            "latestQuote": {
                "bp": bid,
                "ap": ask,
                "bs": 10,
                "as": 10,
                "t": datetime.now(UTC).isoformat(),
            }
        }
    return contracts, snapshots


def select(rows, *, cap=500, option_type="call"):
    return AlpacaCliAdapter.select_spread_contracts(
        *chain(rows), spot=100, option_type=option_type, risk_cap=cap
    )


def test_illiquid_atm_contract_does_not_hide_valid_nearby_pair():
    long, short = select([(100, 3, 3.1, 0), (101, 2, 2.1, 100), (103, 1, 1.1, 100)])
    assert (long["symbol"], short["symbol"]) == ("101", "103")


def test_selects_affordable_width_instead_of_rejecting_entire_signal():
    long, short = select([(100, 3, 3.1, 100), (101, 2.4, 2.5, 100), (102, 1.5, 1.6, 100)], cap=100)
    assert (long["symbol"], short["symbol"]) == ("100", "101")


def test_rejects_when_no_pair_fits_risk_cap():
    with pytest.raises(ValueError, match="Risk Agent budget"):
        select([(100, 3, 3.1, 100), (102, 1.5, 1.6, 100)], cap=50)


def test_put_spread_has_lower_strike_short_leg():
    long, short = select([(100, 3, 3.1, 100), (98, 1.5, 1.6, 100)], option_type="put")
    assert (long["symbol"], short["symbol"]) == ("100", "98")


def test_crossed_quotes_cannot_supply_an_alternative_pair():
    with pytest.raises(ValueError, match="Fewer than two"):
        select([(100, 4, 3, 100), (102, 1.5, 1.6, 100)])


def test_stale_atm_quote_is_skipped_in_favor_of_fresh_nearby_pair():
    contracts, snapshots = chain([(100, 3, 3.1, 100), (101, 2, 2.1, 100), (103, 1, 1.1, 100)])
    now = datetime.now(UTC)
    snapshots["100"]["latestQuote"]["t"] = (now - timedelta(minutes=5)).isoformat()
    long, short = AlpacaCliAdapter.select_spread_contracts(
        contracts,
        snapshots,
        spot=100,
        option_type="call",
        risk_cap=500,
        now=now,
    )
    assert (long["symbol"], short["symbol"]) == ("101", "103")
