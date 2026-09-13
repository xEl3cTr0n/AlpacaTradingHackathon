from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import regimeshift.main as main
import regimeshift.services.chart_context as context
from regimeshift.config import Settings, get_settings
from regimeshift.domain.microstructure import assess_microstructure, unavailable_microstructure
from regimeshift.domain.models import ChartContextSnapshot, LiveMarketTick, PricePoint


@pytest.fixture(autouse=True)
def empty_context_cache():
    context._cache.clear()
    context._inflight.clear()
    yield
    context._cache.clear()
    context._inflight.clear()
    main.app.dependency_overrides.clear()


def settings(**kwargs):
    return Settings(
        _env_file=None, market_data_mode="demo", alpaca_api_key="", alpaca_secret_key="", **kwargs
    )


def providers(
    monkeypatch, *, missing_options=False, missing_history=False, wrong_symbol=False, stale=False
):
    now = datetime.now(UTC)
    bars = [
        PricePoint(
            timestamp=now - timedelta(days=61 - i),
            close=100 + i,
            high=102 + i,
            low=99 + i,
            volume=1000,
        )
        for i in range(60)
    ]
    if stale:
        bars = [
            bar.model_copy(update={"timestamp": bar.timestamp - timedelta(days=30)}) for bar in bars
        ]
    market = SimpleNamespace(
        get_chart_history=lambda *args: [] if missing_history else bars,
        get_live_tick=lambda symbol: LiveMarketTick(
            symbol=symbol, as_of=now, price=160, source="fixture"
        ),
    )

    def assessment(symbol, spot):
        if missing_options:
            return unavailable_microstructure(symbol, "fixture", "Missing Greeks")
        return assess_microstructure(
            "OTHER" if wrong_symbol else symbol,
            spot,
            [
                {
                    "option_type": "call" if i % 2 else "put",
                    "strike": 150 + i,
                    "gamma": 0.02,
                    "open_interest": 100,
                }
                for i in range(30)
            ],
            source="fixture",
        )

    monkeypatch.setattr(context, "build_market_data_provider", lambda _: market)
    monkeypatch.setattr(
        context, "build_options_provider", lambda _: SimpleNamespace(get_assessment=assessment)
    )


def test_ticker_context_loads_without_council_or_order_adapter(monkeypatch):
    providers(monkeypatch)

    def forbidden(*args, **kwargs):
        raise AssertionError("The council must not run for chart context")

    monkeypatch.setattr(main, "DecisionPipeline", forbidden)
    main.app.dependency_overrides[get_settings] = lambda: settings()
    client = TestClient(main.app)
    for symbol in ("aapl", "MSFT"):
        response = client.get(f"/api/v1/chart-context?symbol={symbol}")
        assert response.status_code == 200
        data = response.json()
        assert data["read_only"] and data["symbol"] == symbol.upper()
        assert data["status"] == "available"
        assert data["options_microstructure"]["underlying_symbol"] == symbol.upper()
        assert data["options_microstructure"]["gex_by_strike"]
        assert data["swing"]["swing_high"] > data["swing"]["swing_low"]
        assert "council" not in data and "risk" not in data and "orders" not in data


@pytest.mark.parametrize(
    "options,history,wrong,stale,expected",
    [
        (True, False, False, False, "partial"),
        (False, True, False, False, "partial"),
        (True, True, False, False, "unavailable"),
        (False, False, True, False, "partial"),
        (False, False, False, True, "partial"),
    ],
)
def test_partial_failure_never_substitutes_old_or_wrong_ticker(
    monkeypatch, options, history, wrong, stale, expected
):
    providers(
        monkeypatch,
        missing_options=options,
        missing_history=history,
        wrong_symbol=wrong,
        stale=stale,
    )
    result = context.get_chart_context(settings(), "AAPL")
    assert result.status == expected
    assert (result.options_microstructure is None) == (options or wrong)
    assert (result.swing is None) == (history or stale)


def test_cache_scopes_by_symbol_credentials_and_expires(monkeypatch):
    calls = []

    def build(config, symbol):
        calls.append(symbol)
        return ChartContextSnapshot(
            symbol=symbol, generated_at=datetime.now(UTC), status="unavailable"
        )

    monkeypatch.setattr(context, "build_chart_context", build)
    monkeypatch.setattr(context, "monotonic", lambda: 100)
    config = settings()
    result = context.get_chart_context(config, "aapl")
    result.notes.append("caller mutation")
    assert context.get_chart_context(config, "AAPL").notes == []
    context.get_chart_context(config, "MSFT")
    context.get_chart_context(
        config.model_copy(update={"alpaca_api_key": "different-test-account"}), "AAPL"
    )
    assert calls == ["AAPL", "MSFT", "AAPL"]
    monkeypatch.setattr(context, "monotonic", lambda: 161)
    context.get_chart_context(config, "AAPL")
    assert len(calls) == 4


def test_same_ticker_requests_coalesce_without_blocking_other_tickers(monkeypatch):
    entered, release = Event(), Event()
    calls = []

    def build(config, symbol):
        calls.append(symbol)
        if symbol == "AAPL":
            entered.set()
            assert release.wait(timeout=5)
        return ChartContextSnapshot(
            symbol=symbol, generated_at=datetime.now(UTC), status="unavailable"
        )

    monkeypatch.setattr(context, "build_chart_context", build)
    config = settings()
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(context.get_chart_context, config, "AAPL")
        assert entered.wait(timeout=5)
        second = pool.submit(context.get_chart_context, config, "AAPL")
        other = pool.submit(context.get_chart_context, config, "MSFT")
        try:
            assert other.result(timeout=5).symbol == "MSFT"
        finally:
            release.set()
        assert first.result().symbol == second.result().symbol == "AAPL"
    assert calls.count("AAPL") == 1


def test_chart_context_rejects_invalid_ticker_before_upstream(monkeypatch):
    main.app.dependency_overrides[get_settings] = lambda: settings()
    monkeypatch.setattr(main, "get_chart_context", lambda *args: pytest.fail("No upstream call"))
    assert TestClient(main.app).get("/api/v1/chart-context?symbol=../../bad").status_code == 422
