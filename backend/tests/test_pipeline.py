from regimeshift.config import Settings
from regimeshift.domain.models import AnalysisControls, StrategyMode, StrategyName
from regimeshift.orchestration.pipeline import DecisionPipeline
from regimeshift.services.market_data import DemoMarketDataProvider


def test_pipeline_returns_complete_audit_record() -> None:
    settings = Settings(market_data_mode="demo")
    result = DecisionPipeline(settings, DemoMarketDataProvider()).analyze("SPY")

    assert result.market.symbol == "SPY"
    assert {agent.agent for agent in result.agents} == {
        "Technical",
        "Research",
        "Bull",
        "Bear",
        "Risk",
    }
    assert result.strategy.name in StrategyName
    assert result.strategy.max_loss_dollars <= result.risk.max_allowed_loss
    assert result.mode == "demo"


def test_strategy_controls_change_policy_and_risk_budget() -> None:
    settings = Settings(market_data_mode="demo", account_equity=100_000)
    controls = AnalysisControls(
        strategy_mode=StrategyMode.BEARISH,
        max_risk_pct=0.005,
        min_confidence=0.7,
        target_dte=45,
    )

    result = DecisionPipeline(settings, DemoMarketDataProvider()).analyze("SPY", controls)

    assert result.strategy.name == StrategyName.BEAR_PUT_SPREAD
    assert result.risk.max_allowed_loss == 500
    assert result.controls.target_dte == 45
