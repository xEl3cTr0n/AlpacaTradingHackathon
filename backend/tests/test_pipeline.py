from regimeshift.config import Settings
from regimeshift.domain.models import AnalysisControls, StrategyMode, StrategyName
from regimeshift.orchestration.pipeline import DecisionPipeline
from regimeshift.services.market_data import DemoMarketDataProvider


def test_pipeline_returns_complete_audit_record() -> None:
    settings = Settings(
        market_data_mode="demo",
        alpaca_api_key="",
        alpaca_secret_key="",
        alpaca_mcp_enabled=False,
        alpaca_cli_enabled=False,
    )
    result = DecisionPipeline(settings, DemoMarketDataProvider()).analyze("SPY")

    assert result.market.symbol == "SPY"
    assert {agent.agent for agent in result.agents} == {
        "Technical",
        "Microstructure",
        "Swing",
        "Research",
        "Rotation",
        "Bull",
        "Bear",
        "Risk",
    }
    assert result.strategy.name in StrategyName
    assert result.strategy.underlying_symbol == "XSP"
    assert result.strategy.signal_symbol == "SPY"
    assert result.strategy.max_loss_dollars <= result.risk.max_allowed_loss
    assert len(result.council.votes) == 6
    assert result.swing.lookback == 20
    assert len(result.sector_rotation.sectors) == 11
    assert result.sector_rotation.leaders[0] == result.sector_rotation.sectors[0].symbol
    assert {item.provider: item.status for item in result.tool_evidence} == {
        "Alpaca Trading API": "demo",
        "Alpaca Options API": "offline",
        "Alpaca MCP": "configured",
        "Alpaca CLI": "external_runner",
    }
    assert result.mode == "demo"


def test_strategy_controls_change_policy_and_risk_budget() -> None:
    settings = Settings(market_data_mode="demo", account_equity=100_000)
    controls = AnalysisControls(
        strategy_mode=StrategyMode.BEARISH,
        max_risk_pct=0.005,
        min_confidence=0.7,
        target_dte=45,
        max_loss_cap_dollars=200,
    )

    result = DecisionPipeline(settings, DemoMarketDataProvider()).analyze("SPY", controls)

    assert result.strategy.name == StrategyName.BEAR_PUT_SPREAD
    assert result.risk.max_allowed_loss == 200
    assert result.strategy.max_loss_dollars == 200
    assert result.controls.target_dte == 45
