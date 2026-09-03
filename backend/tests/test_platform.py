from regimeshift.config import Settings
from regimeshift.services.alpaca_cli import AlpacaCliAdapter
from regimeshift.services.platform import DemoPlatformProvider


def test_demo_platform_exposes_judge_visible_telemetry() -> None:
    snapshot = DemoPlatformProvider(Settings(market_data_mode="demo")).get_snapshot()

    assert snapshot.account.equity > 0
    assert len(snapshot.equity_curve) == 31
    assert snapshot.positions
    assert snapshot.orders
    assert {integration.id for integration in snapshot.integrations} == {
        "trading-api",
        "mcp",
        "cli",
    }


def test_signal_client_order_id_is_stable_and_alpaca_safe() -> None:
    signal_key = "AAPL:2026-09-02:bullish_18ema_cross"

    first = AlpacaCliAdapter.signal_client_order_id(signal_key)
    second = AlpacaCliAdapter.signal_client_order_id(signal_key)

    assert first == second
    assert first.startswith("regimeshift-signal-")
    assert len(first) <= 48
    assert first != AlpacaCliAdapter.signal_client_order_id(signal_key.replace("AAPL", "MSFT"))
