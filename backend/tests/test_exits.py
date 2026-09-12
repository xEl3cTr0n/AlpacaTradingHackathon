from datetime import UTC, datetime

import pytest
from regimeshift.domain.exits import managed_exit_plan
from regimeshift.domain.models import Direction


def _entry() -> dict:
    return {
        "id": "entry-123",
        "client_order_id": "regimeshift-signal-abc",
        "status": "filled",
        "order_class": "mleg",
        "qty": "1",
        "filled_qty": "1",
        "filled_avg_price": "1.50",
        "legs": [
            {
                "symbol": "AAPL261218C00200000",
                "ratio_qty": "1",
                "position_intent": "buy_to_open",
                "side": "buy",
            },
            {
                "symbol": "AAPL261218C00205000",
                "ratio_qty": "1",
                "position_intent": "sell_to_open",
                "side": "sell",
            },
        ],
    }


def test_managed_exit_closes_spread_atomically_on_profit() -> None:
    positions = {
        "AAPL261218C00200000": {"qty": "1", "qty_available": "1", "unrealized_pl": "140"},
        "AAPL261218C00205000": {"qty": "-1", "qty_available": "1", "unrealized_pl": "40"},
    }
    plan = managed_exit_plan(_entry(), positions, now=datetime(2026, 9, 3, tzinfo=UTC))

    assert plan is not None
    assert plan["reasons"] == ["50% profit target reached"]
    assert [leg["position_intent"] for leg in plan["legs"]] == [
        "sell_to_close",
        "buy_to_close",
    ]


def test_managed_exit_detects_regime_reversal() -> None:
    positions = {
        "AAPL261218C00200000": {"qty": "1", "qty_available": "1", "unrealized_pl": "0"},
        "AAPL261218C00205000": {"qty": "-1", "qty_available": "1", "unrealized_pl": "0"},
    }
    plan = managed_exit_plan(
        _entry(),
        positions,
        current_direction=Direction.BEARISH,
        now=datetime(2026, 9, 3, tzinfo=UTC),
    )

    assert plan is not None
    assert "detected trend reversed against the position" in plan["reasons"]


def test_managed_exit_stops_manual_spread_at_half_the_debit() -> None:
    entry = _entry()
    entry["client_order_id"] = "regimeshift-manual-abc"
    positions = {
        "AAPL261218C00200000": {"qty": "1", "qty_available": "1", "unrealized_pl": "-60"},
        "AAPL261218C00205000": {"qty": "-1", "qty_available": "1", "unrealized_pl": "-20"},
    }

    plan = managed_exit_plan(entry, positions, now=datetime(2026, 9, 3, tzinfo=UTC))

    assert plan is not None
    assert plan["stop_loss_dollars"] == 75
    assert plan["reasons"] == ["50% maximum-loss stop reached"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("qty", "-1"),
        ("qty", "2"),
        ("qty", None),
        ("qty_available", "0"),
        ("qty_available", "NaN"),
        ("unrealized_pl", "NaN"),
        ("unrealized_pl", None),
    ],
)
def test_uncertain_holdings_cannot_authorize_exit(field, value):
    positions = {
        "AAPL261218C00200000": {"qty": "1", "qty_available": "1", "unrealized_pl": "-60"},
        "AAPL261218C00205000": {"qty": "-1", "qty_available": "1", "unrealized_pl": "-20"},
    }
    positions["AAPL261218C00200000"][field] = value
    with pytest.raises(ValueError):
        managed_exit_plan(_entry(), positions)


@pytest.mark.parametrize(
    "field,value",
    [
        ("position_intent", None),
        ("position_intent", "sell_to_close"),
        ("side", "sell"),
        ("ratio_qty", "2"),
    ],
)
def test_ambiguous_opening_intents_and_ratios_do_not_default_to_buy_to_close(field, value):
    entry = _entry()
    entry["legs"][0][field] = value
    positions = {
        "AAPL261218C00200000": {"qty": "1", "qty_available": "1", "unrealized_pl": "-60"},
        "AAPL261218C00205000": {"qty": "-1", "qty_available": "1", "unrealized_pl": "-20"},
    }
    with pytest.raises(ValueError):
        managed_exit_plan(entry, positions)


def test_partial_spread_requires_explicit_reconciliation():
    with pytest.raises(ValueError, match="Incomplete held spread"):
        managed_exit_plan(_entry(), {"AAPL261218C00200000": {}})
