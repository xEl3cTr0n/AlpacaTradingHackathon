from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from regimeshift.config import Settings
from regimeshift.services.alpaca_cli import AlpacaCliAdapter


def fixture():
    expiry = (datetime.now(UTC) + timedelta(days=30)).strftime("%y%m%d")
    symbols = [f"AAPL{expiry}C00200000", f"AAPL{expiry}C00205000"]
    entry = {
        "id": "test-entry",
        "client_order_id": "regimeshift-manual-test",
        "status": "filled",
        "order_class": "mleg",
        "filled_qty": "1",
        "filled_avg_price": "1.5",
        "legs": [
            {
                "symbol": symbols[0],
                "side": "buy",
                "position_intent": "buy_to_open",
                "ratio_qty": "1",
            },
            {
                "symbol": symbols[1],
                "side": "sell",
                "position_intent": "sell_to_open",
                "ratio_qty": "1",
            },
        ],
    }
    state = {
        "entries": [entry],
        "open_orders": [],
        "clock_open": True,
        "existing": None,
        "positions": [
            {
                "symbol": symbols[0],
                "asset_class": "us_option",
                "qty": "1",
                "qty_available": "1",
                "unrealized_pl": "-60",
            },
            {
                "symbol": symbols[1],
                "asset_class": "us_option",
                "qty": "-1",
                "qty_available": "1",
                "unrealized_pl": "-20",
            },
        ],
        "submitted": [],
    }
    cli = AlpacaCliAdapter.__new__(AlpacaCliAdapter)
    cli.settings = Settings(enable_paper_orders=True, alpaca_paper=True)

    def fake_list(args):
        if args[0] == "position":
            return state["positions"]
        return state["entries"] if "closed" in args else state["open_orders"]

    def fake_run(args):
        if args[0] == "clock":
            return {"timestamp": datetime.now(UTC).isoformat(), "is_open": state["clock_open"]}
        assert args[:2] == ["order", "submit"]
        state["submitted"].append(args)
        return {"status": "fake-accepted"}

    cli._run_list = fake_list
    cli._run = fake_run
    cli.existing_order = lambda client_id: state["existing"]
    return cli, state


def test_valid_exit_rechecks_broker_then_closes_only_verified_legs():
    cli, state = fixture()
    plan = cli.managed_exit_plans()[0]
    assert cli.submit_exit(plan, execute=True)["status"] == "submitted"
    command = state["submitted"][0]
    assert command[command.index("--order-class") + 1] == "mleg"
    assert command[command.index("--type") + 1] == "market"
    assert [leg["position_intent"] for leg in plan["legs"]] == ["sell_to_close", "buy_to_close"]


@pytest.mark.parametrize(
    "change",
    [
        "missing_leg",
        "wrong_side",
        "pending",
        "no_longer_stopped",
        "closed",
        "duplicate",
        "forged_legs",
        "non_paper",
    ],
)
def test_plan_cannot_outlive_holdings_or_skip_final_exit_checks(change):
    cli, state = fixture()
    plan = cli.managed_exit_plans()[0]
    if change == "missing_leg":
        state["positions"].pop()
    elif change == "wrong_side":
        state["positions"][1]["qty"] = "1"
    elif change == "pending":
        state["open_orders"] = [
            {"symbol": plan["legs"][0]["symbol"], "position_intent": "sell_to_close"}
        ]
    elif change == "no_longer_stopped":
        for position in state["positions"]:
            position["unrealized_pl"] = "0"
    elif change == "closed":
        state["clock_open"] = False
    elif change == "duplicate":
        state["existing"] = {"status": "accepted"}
    elif change == "forged_legs":
        plan["legs"][0]["position_intent"] = "buy_to_open"
    else:
        cli.settings.alpaca_paper = False
    with pytest.raises(ValueError):
        cli.submit_exit(plan, execute=True)
    assert not state["submitted"]


def test_missing_intent_produces_reconciliation_receipt_instead_of_guess():
    cli, state = fixture()
    del state["entries"][0]["legs"][0]["position_intent"]
    result = cli.assess_managed_exits()
    assert not result["plans"]
    assert result["checks"][0]["status"] == "reconciliation_required"
    assert "cannot infer closing sides" in result["checks"][0]["reasons"][0]


def test_conflicting_opening_history_is_not_attributed_to_two_spreads():
    cli, state = fixture()
    other = deepcopy(state["entries"][0])
    other["id"] = "second-entry"
    state["entries"].append(other)
    result = cli.assess_managed_exits()
    assert not result["plans"]
    assert all(check["status"] == "reconciliation_required" for check in result["checks"])


@pytest.mark.parametrize("status", ["filled", "canceled", "rejected", "expired"])
def test_previous_exit_is_never_blindly_resubmitted(status):
    cli, state = fixture()
    state["entries"].append(
        {"client_order_id": cli.exit_client_order_id("test-entry"), "status": status}
    )
    result = cli.assess_managed_exits()
    assert not result["plans"]
    assert not state["submitted"]


def test_unmanaged_option_is_visible_but_not_closed():
    cli, state = fixture()
    state["entries"] = []
    result = cli.assess_managed_exits()
    assert not result["plans"] and result["checks"][0]["status"] == "unmanaged_positions"


def test_closed_entry_circuit_breaker_does_not_block_risk_reducing_exit():
    cli, state = fixture()
    cli.verify_execution_capacity = lambda *args, **kwargs: pytest.fail(
        "Entry capacity must not gate exits"
    )
    cli.submit_exit(cli.managed_exit_plans()[0], execute=True)
    assert len(state["submitted"]) == 1
