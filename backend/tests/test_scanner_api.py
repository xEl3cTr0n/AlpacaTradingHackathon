from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

import regimeshift.main as main_module
from regimeshift.config import Settings, get_settings
from regimeshift.domain.backtest_evidence import load_scanner_backtest_evidence
from regimeshift.domain.models import PricePoint
from regimeshift.domain.scanner import LargeCapScanner


def test_api_exposes_paper_experiment_without_changing_holdout_evidence():
    main_module.app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        market_data_mode="demo",
        alpaca_api_key="",
        alpaca_secret_key="",
        paper_experiment_mode=True,
        alpaca_paper=True,
    )
    try:
        response = TestClient(main_module.app).get("/api/v1/scanner?limit=24")
    finally:
        main_module.app.dependency_overrides.clear()
    assert response.status_code == 200
    gates = response.json()["execution_gates"]
    assert gates["paper_experiment_enabled"] is True
    assert gates["intraday_production_backtest_passed"] is False
    assert gates["evidence_valid"] is True


def _points(closes: list[float], volume: int) -> list[PricePoint]:
    start = datetime(2025, 1, 2, tzinfo=UTC)
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


def test_scanner_evaluation_recomputes_signal_and_applies_tier_gate(monkeypatch) -> None:
    benchmark = _points([400 + index * 0.5 for index in range(80)], 5_000_000)
    closes = [100 + index * 0.8 for index in range(80)]
    closes[-2] = 145
    closes[-1] = 180
    points = _points(closes, 2_000_000)
    snapshot = LargeCapScanner().scan(
        {"SPY": benchmark, "CRM": points},
        timeframe="15Min",
        source="deterministic test tape",
    )
    candidate = snapshot.candidates[0].model_copy(
        update={
            "signal_tier": "production",
            "conviction": 0.65,
            "risk_cap_dollars": 1_000,
        }
    )
    snapshot = snapshot.model_copy(
        update={
            "candidates": [candidate],
            "execution_gates": load_scanner_backtest_evidence(),
        }
    )
    monkeypatch.setattr(
        main_module,
        "_build_scanner_snapshot",
        lambda settings, provider, limit: snapshot,
    )
    main_module.app.dependency_overrides[get_settings] = lambda: Settings(
        market_data_mode="demo",
        enable_exploration_orders=True,
    )
    try:
        response = TestClient(main_module.app).get("/api/v1/scanner/evaluate?symbol=CRM")
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["scanner_signal"]["symbol"] == "CRM"
    assert payload["strategy"]["status"] == "backtest locked"
    assert payload["risk"]["approved"] is False
    assert payload["tool_evidence"][-1] == {
        "provider": "RegimeShift evidence registry",
        "capability": "scanner tier authorization",
        "status": "locked",
        "summary": "Intraday production holdout gate is locked",
    }
