from datetime import UTC, datetime, timedelta

import pytest
from regimeshift.config import Settings
from regimeshift.domain.execution_checks import (
    check_option_quote,
    verify_entry_capacity,
    verify_open_clock,
)

NOW = datetime(2026, 9, 11, 15, tzinfo=UTC)
ACCOUNT = {
    "equity": "100000",
    "last_equity": "100000",
    "status": "ACTIVE",
    "trading_blocked": False,
    "account_blocked": False,
    "trade_suspended_by_user": False,
    "options_trading_level": 3,
    "options_buying_power": "50000",
}


def quote(**overrides):
    args = dict(bid=2.9, ask=3, bid_size=10, ask_size=10, timestamp=NOW, now=NOW)
    args.update(overrides)
    return check_option_quote("AAPL261016C00200000", **args)


@pytest.mark.parametrize(
    "overrides",
    [
        {"timestamp": None},
        {"timestamp": "yesterday"},
        {"timestamp": NOW.replace(tzinfo=None)},
        {"timestamp": NOW - timedelta(seconds=121)},
        {"timestamp": NOW + timedelta(seconds=6)},
        {"bid": float("nan")},
        {"ask": float("inf")},
        {"bid": 3.1},
        {"ask": 0},
        {"bid_size": 0},
        {"ask_size": None},
        {"ask_size": float("nan")},
        {"bid": True},
        {"ask": 5},
    ],
)
def test_bad_quote_is_inspectable_and_fail_closed(overrides):
    result = quote(**overrides)
    assert not result.valid and result.reasons
    assert "NaN" not in result.model_dump_json() and "Infinity" not in result.model_dump_json()


def test_quote_age_boundaries_and_equal_sided_prices():
    assert quote(timestamp=NOW - timedelta(seconds=120)).valid
    assert quote(timestamp=NOW + timedelta(seconds=5)).valid
    assert quote(bid=3, ask=3).valid


@pytest.mark.parametrize(
    "clock",
    [
        {"timestamp": NOW.isoformat(), "is_open": False},
        {"timestamp": NOW.isoformat(), "is_open": "true"},
        {"timestamp": (NOW - timedelta(seconds=61)).isoformat(), "is_open": True},
        {"is_open": True},
    ],
)
def test_unverified_clock_cannot_authorize_entry(clock):
    with pytest.raises(ValueError):
        verify_open_clock(clock, now=NOW)


def test_capacity_uses_actual_equity_not_configured_demo_equity():
    account = {**ACCOUNT, "equity": "50000", "last_equity": "50000"}
    settings = Settings(account_equity=100000)
    with pytest.raises(ValueError, match=r"\$500"):
        verify_entry_capacity(settings, "AAPL", account, [], [], maximum_loss=600)
    result = verify_entry_capacity(settings, "AAPL", account, [], [], maximum_loss=400)
    assert result["risk_budget"] == 500


def test_capacity_counts_external_entries_and_rejects_truncated_lists():
    orders = [
        {"symbol": f"{symbol}261016C00200000", "position_intent": "buy_to_open"}
        for symbol in ("MSFT", "NVDA", "AVGO")
    ]
    with pytest.raises(ValueError, match="concurrent spreads"):
        verify_entry_capacity(Settings(), "AAPL", ACCOUNT, [], orders)
    with pytest.raises(ValueError, match="truncated"):
        verify_entry_capacity(Settings(), "AAPL", ACCOUNT, [], [{}] * 500)


def test_closing_order_is_not_an_additional_entry_but_position_still_counts():
    position = {"symbol": "AAPL261016C00200000", "asset_class": "us_option", "qty": "1"}
    closing = {"symbol": position["symbol"], "position_intent": "sell_to_close"}
    result = verify_entry_capacity(Settings(), "MSFT", ACCOUNT, [position], [closing])
    assert result["active_spreads"] == 1
    with pytest.raises(ValueError, match="already uses AAPL"):
        verify_entry_capacity(Settings(), "AAPL", ACCOUNT, [position], [closing])


def test_unrecognized_option_order_cannot_be_mistaken_for_stock_exposure():
    order = {"symbol": "MALFORMED", "asset_class": "us_option", "position_intent": "buy_to_open"}
    with pytest.raises(ValueError, match="unrecognized contract"):
        verify_entry_capacity(Settings(), "AAPL", ACCOUNT, [], [order])


@pytest.mark.parametrize(
    "change",
    [
        {"equity": "NaN"},
        {"last_equity": "Infinity"},
        {"options_buying_power": None},
        {"options_trading_level": 2},
        {"account_blocked": None},
        {"trading_blocked": "false"},
        {"status": "DISABLED"},
        {"equity": "97000"},
    ],
)
def test_unknown_or_unhealthy_account_never_authorizes(change):
    with pytest.raises(ValueError):
        verify_entry_capacity(Settings(), "AAPL", {**ACCOUNT, **change}, [], [], maximum_loss=100)
