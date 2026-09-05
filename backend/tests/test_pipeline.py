from datetime import UTC, datetime, timedelta

from regimeshift.config import Settings
from regimeshift.domain.models import AnalysisControls, PricePoint, StrategyMode, StrategyName
from regimeshift.domain.scanner import LargeCapScanner
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
        "Macro",
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
    assert result.strategy.max_loss_dollars <= 1_000
    assert result.strategy.stop_loss_dollars == result.strategy.max_loss_dollars * 0.5
    assert len(result.council.votes) == 6
    assert result.swing.lookback == 20
    assert len(result.sector_rotation.sectors) == 11
    assert result.sector_rotation.leaders[0] == result.sector_rotation.sectors[0].symbol
    assert {item.provider: item.status for item in result.tool_evidence} == {
        "Alpaca Trading API": "demo",
        "Alpaca Options API": "offline",
        "FRED": "offline",
        "Alpaca MCP": "configured",
        "Alpaca CLI": "external_runner",
    }
    assert result.market_layers.macro.status == "unavailable"
    assert result.market_layers.bottom_up.quadrant.value.startswith("quad_")
    assert result.market_layers.mood_vibe.status == "insufficient_inputs"
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
    assert result.strategy.stop_loss_dollars == 100
    assert result.controls.target_dte == 45


def test_default_position_budget_is_one_percent_with_half_loss_trigger() -> None:
    settings = Settings(market_data_mode="demo", account_equity=100_000)
    controls = AnalysisControls(
        strategy_mode=StrategyMode.BEARISH,
        instrument_mode="equity_option",
        max_risk_pct=0.01,
    )

    result = DecisionPipeline(settings, DemoMarketDataProvider()).analyze("AAPL", controls)

    assert result.strategy.max_loss_dollars == 1_000
    assert result.strategy.stop_loss_dollars == 500
    assert result.risk.max_allowed_loss == 1_000


def test_scanner_signal_is_a_structured_council_vote_and_sets_direction() -> None:
    start = datetime(2025, 1, 2, tzinfo=UTC)

    def points(closes: list[float], volume: int) -> list[PricePoint]:
        return [
            PricePoint(
                timestamp=start + timedelta(days=index),
                open=close,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                volume=volume * (2 if index == len(closes) - 1 else 1),
            )
            for index, close in enumerate(closes)
        ]

    benchmark = points([400 + index * 0.5 for index in range(80)], 5_000_000)
    closes = [100 + index * 0.8 for index in range(80)]
    closes[-2] = 145
    closes[-1] = 180
    signal = LargeCapScanner().score("AAPL", "Apple", points(closes, 2_000_000), benchmark, 79)
    assert signal is not None and signal.actionable

    result = DecisionPipeline(Settings(market_data_mode="demo"), DemoMarketDataProvider()).analyze(
        "AAPL",
        AnalysisControls(min_confidence=signal.conviction),
        scanner_signal=signal,
    )

    assert result.strategy.name == StrategyName.BULL_CALL_SPREAD
    assert result.scanner_signal == signal
    assert any(vote.agent == "Scanner" for vote in result.council.votes)
    assert any(agent.agent == "Scanner" for agent in result.agents)
    assert result.council.required_support == 3

    exploration = signal.model_copy(
        update={
            "conviction": 0.57,
            "signal_tier": "exploration",
            "risk_cap_dollars": 500,
        }
    )
    exploration_result = DecisionPipeline(
        Settings(market_data_mode="demo"), DemoMarketDataProvider()
    ).analyze(
        "AAPL",
        AnalysisControls(min_confidence=exploration.conviction, max_loss_cap_dollars=500),
        scanner_signal=exploration,
    )
    assert exploration_result.council.required_support == 2
    assert exploration_result.strategy.max_loss_dollars == 500


def test_missing_gex_keeps_only_half_size_exploration_eligible() -> None:
    start = datetime(2025, 1, 2, tzinfo=UTC)

    def points(closes: list[float], volume: int) -> list[PricePoint]:
        return [
            PricePoint(
                timestamp=start + timedelta(days=index),
                open=close,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                volume=volume * (2 if index == len(closes) - 1 else 1),
            )
            for index, close in enumerate(closes)
        ]

    benchmark = points([400 + index * 0.5 for index in range(80)], 5_000_000)
    closes = [100 + index * 0.8 for index in range(80)]
    closes[-2] = 145
    closes[-1] = 180
    signal = LargeCapScanner().score("AAPL", "Apple", points(closes, 2_000_000), benchmark, 79)
    assert signal is not None
    signal = signal.model_copy(
        update={
            "conviction": 0.57,
            "signal_tier": "exploration",
            "risk_cap_dollars": 500,
        }
    )
    pipeline = DecisionPipeline(Settings(market_data_mode="demo"), DemoMarketDataProvider())
    result = pipeline.analyze(
        "AAPL",
        AnalysisControls(min_confidence=0.57, max_loss_cap_dollars=500),
        scanner_signal=signal,
    )
    pipeline.settings.market_data_mode = "alpaca"
    bull = next(agent for agent in result.agents if agent.agent == "Bull").model_copy(
        update={"confidence": 0.8}
    )
    bear = next(agent for agent in result.agents if agent.agent == "Bear").model_copy(
        update={"confidence": 0.4}
    )

    risk = pipeline._risk_gate(
        result.regime.model_copy(update={"direction": signal.direction, "confidence": 0.8}),
        result.swing,
        result.options_microstructure,
        result.strategy,
        bull,
        bear,
        result.council.model_copy(update={"approved": True}),
        result.controls,
        signal,
    )

    assert risk.approved is True
    assert risk.max_allowed_loss == 500
    assert any("Live GEX unavailable" in reason for reason in risk.reasons)
