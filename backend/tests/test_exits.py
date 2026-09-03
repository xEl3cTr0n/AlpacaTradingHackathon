from datetime import UTC, datetime

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
            {"symbol": "AAPL261218C00200000", "ratio_qty": "1", "position_intent": "buy_to_open"},
            {"symbol": "AAPL261218C00205000", "ratio_qty": "1", "position_intent": "sell_to_open"},
        ],
    }


def test_managed_exit_closes_spread_atomically_on_profit() -> None:
    positions = {
        "AAPL261218C00200000": {"qty_available": "1", "unrealized_pl": "140"},
        "AAPL261218C00205000": {"qty_available": "1", "unrealized_pl": "40"},
    }
    plan = managed_exit_plan(
        _entry(), positions, now=datetime(2026, 9, 3, tzinfo=UTC)
    )

    assert plan is not None
    assert plan["reasons"] == ["50% profit target reached"]
    assert [leg["position_intent"] for leg in plan["legs"]] == [
        "sell_to_close",
        "buy_to_close",
    ]


def test_managed_exit_detects_regime_reversal() -> None:
    positions = {
        "AAPL261218C00200000": {"qty_available": "1", "unrealized_pl": "0"},
        "AAPL261218C00205000": {"qty_available": "1", "unrealized_pl": "0"},
    }
    plan = managed_exit_plan(
        _entry(),
        positions,
        current_direction=Direction.BEARISH,
        now=datetime(2026, 9, 3, tzinfo=UTC),
    )

    assert plan is not None
    assert "detected trend reversed against the position" in plan["reasons"]
