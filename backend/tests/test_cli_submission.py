"""Exercise the final CLI entry boundary without launching CLI or sending orders."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from regimeshift.config import Settings
from regimeshift.domain.models import StrategyName
from regimeshift.services.alpaca_cli import AlpacaCliAdapter


def fixture():
    expiry = (datetime.now(UTC) + timedelta(days=30)).strftime("%y%m%d")
    long_symbol, short_symbol = (f"AAPL{expiry}C{strike}" for strike in ("00100000", "00105000"))
    plan = {
        "paper_only": True,
        "liquidity_passed": True,
        "maximum_loss": 100,
        "limit_debit": 1.0,
        "quantity": 1,
        "underlying_symbol": "AAPL",
        "legs": [
            {
                "symbol": long_symbol,
                "ratio_qty": "1",
                "side": "buy",
                "position_intent": "buy_to_open",
            },
            {
                "symbol": short_symbol,
                "ratio_qty": "1",
                "side": "sell",
                "position_intent": "sell_to_open",
            },
        ],
    }
    snapshot = SimpleNamespace(
        risk=SimpleNamespace(approved=True, max_allowed_loss=1000),
        council=SimpleNamespace(approved=True),
        decision_id="test-only",
        strategy=SimpleNamespace(name=StrategyName.BULL_CALL_SPREAD, underlying_symbol="AAPL"),
    )
    state = {
        "account": {
            "equity": "100000",
            "last_equity": "100000",
            "status": "ACTIVE",
            "trading_blocked": False,
            "account_blocked": False,
            "trade_suspended_by_user": False,
            "options_buying_power": "50000",
            "options_trading_level": 3,
        },
        "clock": {"is_open": True, "timestamp": datetime.now(UTC).isoformat()},
        "snapshots": {
            symbol: {
                "latestQuote": {
                    "bp": bid,
                    "ap": ask,
                    "bs": 10,
                    "as": 10,
                    "t": datetime.now(UTC).isoformat(),
                }
            }
            for symbol, bid, ask in ((long_symbol, 2.9, 3), (short_symbol, 2, 2.1))
        },
        "calls": [],
    }
    instance = AlpacaCliAdapter.__new__(AlpacaCliAdapter)
    instance.settings = Settings(enable_paper_orders=True, alpaca_paper=True)

    def fake_run(args):
        state["calls"].append(args)
        if args[:3] == ["api", "GET", "/v2/account"]:
            return state["account"]
        if args[0] == "clock":
            return state["clock"]
        if args[:3] == ["data", "option", "snapshot"]:
            return {"snapshots": state["snapshots"]}
        if args[:2] == ["order", "submit"]:
            return {"status": "fake-accepted"}
        raise AssertionError(f"Unexpected command: {args}")

    instance._run = fake_run
    instance._run_list = lambda args: []
    return instance, snapshot, plan, state


def assert_no_order(state):
    assert not any(args[:2] == ["order", "submit"] for args in state["calls"])


def test_valid_entry_requotes_after_account_checks_then_submits_to_fake_cli():
    instance, snapshot, plan, state = fixture()
    result = instance.submit_or_preview(snapshot, plan, execute=True)
    assert [args[0] for args in state["calls"]] == ["api", "clock", "data", "order"]
    assert result["status"] == "submitted" and result["allowed"]
    assert result["execution_capacity"]["risk_budget"] == 1000
    assert all(check["valid"] for check in result["quote_checks"])
    command = state["calls"][-1]
    for flag, value in (
        ("--order-class", "mleg"),
        ("--qty", "1"),
        ("--type", "limit"),
        ("--limit-price", "1.00"),
        ("--time-in-force", "day"),
    ):
        assert command[command.index(flag) + 1] == value


@pytest.mark.parametrize(
    "change",
    [
        {"t": (datetime.now(UTC) - timedelta(minutes=3)).isoformat()},
        {"t": None},
        {"bp": 3.1},
        {"as": 0},
        {"ap": float("nan")},
    ],
)
def test_prepared_liquidity_boolean_cannot_bypass_fresh_quote_check(change):
    instance, snapshot, plan, state = fixture()
    state["snapshots"][plan["legs"][0]["symbol"]]["latestQuote"].update(change)
    with pytest.raises(ValueError):
        instance.submit_or_preview(snapshot, plan, execute=True)
    assert_no_order(state)


@pytest.mark.parametrize(
    "change",
    [
        {"maximum_loss": 1},
        {"quantity": 2},
        {"quantity": True},
        {"limit_debit": 0},
        {"limit_debit": float("nan")},
        {"limit_debit": 5, "maximum_loss": 500},
        {"underlying_symbol": "MSFT"},
    ],
)
def test_forged_plan_rejected_before_broker_submission(change):
    instance, snapshot, plan, state = fixture()
    plan.update(change)
    with pytest.raises(ValueError):
        instance.submit_or_preview(snapshot, plan, execute=True)
    assert_no_order(state)


@pytest.mark.parametrize(
    "field,value",
    [
        ("ratio_qty", "2"),
        ("position_intent", "sell_to_close"),
        ("symbol", "MSFT261016C00105000"),
    ],
)
def test_altered_legs_cannot_bypass_plan_shape(field, value):
    instance, snapshot, plan, state = fixture()
    plan["legs"][1][field] = value
    with pytest.raises(ValueError):
        instance.submit_or_preview(snapshot, plan, execute=True)
    assert_no_order(state)


@pytest.mark.parametrize("gate", ["risk", "council", "closed", "loss", "disabled", "not_paper"])
def test_unapproved_or_unhealthy_entry_never_submits(gate):
    instance, snapshot, plan, state = fixture()
    if gate in {"risk", "council"}:
        getattr(snapshot, gate).approved = False
    elif gate == "closed":
        state["clock"]["is_open"] = False
    elif gate == "loss":
        state["account"]["equity"] = "97000"
    elif gate == "disabled":
        instance.settings.enable_paper_orders = False
    else:
        instance.settings.alpaca_paper = False
    with pytest.raises(ValueError):
        instance.submit_or_preview(snapshot, plan, execute=True)
    assert_no_order(state)


def test_requote_rejects_a_limit_that_is_now_above_market_tolerance():
    instance, snapshot, plan, state = fixture()
    state["snapshots"][plan["legs"][0]["symbol"]]["latestQuote"].update(bp=2.4, ap=2.5)
    with pytest.raises(ValueError, match="Fresh option debit"):
        instance.submit_or_preview(snapshot, plan, execute=True)
    assert_no_order(state)


def test_dry_run_preserves_disabled_execution_and_uses_cli_dry_run_flag():
    instance, snapshot, plan, state = fixture()
    instance.settings.enable_paper_orders = False
    result = instance.submit_or_preview(snapshot, plan, execute=False)
    assert result["status"] == "dry_run"
    assert state["calls"][0][:3] == ["order", "submit", "--dry-run"]
