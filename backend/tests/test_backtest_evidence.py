from pathlib import Path

from regimeshift.domain.backtest_evidence import (
    load_scanner_backtest_evidence,
    scanner_tier_execution_allowed,
    validate_scanner_backtest_evidence,
)


def _reports() -> tuple[dict[str, object], dict[str, object]]:
    intraday = {
        "generated_at": "2026-09-05T11:29:33+00:00",
        "parameters": {
            "timeframe": "15Min",
            "ema_period": 18,
            "trend_ema_period": 50,
            "production_conviction": 0.6,
            "exploration_conviction": 0.55,
            "friction": 0.002,
        },
        "universe_size": 24,
        "production_gate_passed": False,
        "exploration_gate_passed": True,
    }
    daily = {
        "generated_at": "2026-09-02T10:56:18+00:00",
        "parameters": {
            "ema_period": 18,
            "trend_ema_period": 50,
            "minimum_conviction": 0.6,
            "minimum_average_dollar_volume": 100_000_000,
        },
        "production_gate_passed": True,
    }
    return intraday, daily


def test_structured_gate_evidence_matches_worker_policy() -> None:
    intraday, daily = _reports()
    gates = validate_scanner_backtest_evidence(intraday, daily)

    assert gates.evidence_valid is True
    assert gates.intraday_production_backtest_passed is False
    assert gates.intraday_exploration_backtest_passed is True
    assert gates.daily_production_backtest_passed is True


def test_policy_change_invalidates_every_execution_gate() -> None:
    intraday, daily = _reports()
    intraday["parameters"]["exploration_conviction"] = 0.50
    gates = validate_scanner_backtest_evidence(intraday, daily)

    assert gates.evidence_valid is False
    assert gates.intraday_exploration_backtest_passed is False
    assert gates.daily_production_backtest_passed is False
    assert "expected 0.55" in gates.details[0]


def test_packaged_deployment_evidence_is_valid() -> None:
    packaged = load_scanner_backtest_evidence()
    repository_root = Path(__file__).resolve().parents[2]
    committed = load_scanner_backtest_evidence(repository_root)

    assert packaged.evidence_valid is True
    assert packaged.intraday_production_backtest_passed is False
    assert packaged.intraday_exploration_backtest_passed is True
    assert packaged.daily_production_backtest_passed is True
    assert packaged.source.startswith("Packaged")
    assert packaged.model_dump(exclude={"source"}) == committed.model_dump(exclude={"source"})


def test_scanner_tier_gate_is_fail_closed_and_timeframe_specific() -> None:
    gates = load_scanner_backtest_evidence()

    assert scanner_tier_execution_allowed(
        gates,
        timeframe="15Min",
        signal_tier="production",
        exploration_enabled=True,
    ) == (False, "Intraday production holdout gate is locked")
    assert scanner_tier_execution_allowed(
        gates,
        timeframe="15Min",
        signal_tier="exploration",
        exploration_enabled=True,
    )[0]
    assert scanner_tier_execution_allowed(
        gates,
        timeframe="1Day",
        signal_tier="production",
        exploration_enabled=False,
    )[0]

    invalid = gates.model_copy(update={"evidence_valid": False})
    assert not scanner_tier_execution_allowed(
        invalid,
        timeframe="1Day",
        signal_tier="production",
        exploration_enabled=True,
    )[0]
