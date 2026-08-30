from regimeshift.config import Settings
from regimeshift.domain.models import StrategyName
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
