import pytest

from regimeshift.config import Settings
from regimeshift.services.alpaca_cli import AlpacaCliAdapter


def adapter(pending_roots: list[str]) -> AlpacaCliAdapter:
    instance = AlpacaCliAdapter.__new__(AlpacaCliAdapter)
    instance.settings = Settings(max_open_spreads=3)
    instance._run = lambda args: {
        "equity": "100000", "last_equity": "100000", "trading_blocked": False
    }
    orders = [
        {
            "client_order_id": f"regimeshift-manual-{root}",
            "legs": [{"symbol": f"{root}261016C00200000"}],
        }
        for root in pending_roots
    ]
    instance._run_list = lambda args: orders if args[0] == "order" else []
    return instance


def test_pending_manual_entry_blocks_automatic_entry_in_same_underlying() -> None:
    with pytest.raises(ValueError, match="already uses AAPL"):
        adapter(["AAPL"]).verify_execution_capacity("AAPL")


def test_pending_manual_entries_consume_spread_capacity() -> None:
    with pytest.raises(ValueError, match="concurrent spreads"):
        adapter(["AAPL", "MSFT", "NVDA"]).verify_execution_capacity("AVGO")


def test_different_underlying_can_use_remaining_capacity() -> None:
    result = adapter(["AAPL"]).verify_execution_capacity("AVGO")
    assert result["active_spreads"] == 1
    assert result["same_underlying_clear"] is True
