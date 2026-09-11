from regimeshift.domain.backtest_evidence import validate_scanner_backtest_evidence


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
