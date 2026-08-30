from regimeshift.config import Settings
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
