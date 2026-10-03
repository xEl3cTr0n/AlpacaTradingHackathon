from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import regimeshift.main as main
import regimeshift.services.sector_scanner as service
from regimeshift.config import Settings, get_settings
from regimeshift.domain.models import PricePoint
from regimeshift.domain.sector_scanner import (
    SECTOR_SAMPLES,
    build_sector_scan,
    completed_session_bars,
    correlation,
)
from regimeshift.services.market_data import AlpacaMarketDataProvider


def tape(factor=1):
    points, price = [], 100.0
    for day in range(3):
        for bar in range(26):
            i = day * 26 + bar
            opening = price
            price *= 1 + factor * (0.001 + i % 7 * 0.0003)
            points.append(
                PricePoint(
                    timestamp=datetime(2026, 9, 9 + day, 13, 30, tzinfo=UTC)
                    + timedelta(minutes=bar * 15),
                    open=opening,
                    close=price,
                    high=max(opening, price) + 0.01,
                    low=min(opening, price) - 0.01,
                    volume=1000 + i * 10,
                )
            )
    return points


def fixture(factor=1):
    histories = {"SPY": tape(factor * 0.3), "XLK": tape(factor)}
    histories.update({s: tape(factor * (1 + i * 0.1)) for i, s in enumerate(SECTOR_SAMPLES["XLK"])})
    histories = {s: bars[:-1] for s, bars in histories.items()}
    now = histories["SPY"][-1].timestamp + timedelta(minutes=20)
    return histories, now


def tech(histories, now):
    return next(
        r for r in build_sector_scan(histories, {}, now, "fixture").sectors if r.symbol == "XLK"
    )


@pytest.mark.parametrize("factor,signal", [(1, "confirmed_bullish"), (-1, "confirmed_bearish")])
def test_sector_confirmation_is_symmetric_and_inspectable(factor, signal):
    histories, now = fixture(factor)
    row = tech(histories, now)
    assert row.signal == signal
    assert row.sample_coverage == row.agreement == 1
    assert all(m.confirms and m.correlation > 0.99 for m in row.members)
    assert len(row.reasons) == 5
    assert row.plans and all(m.plans for m in row.members)
    for plan in row.plans:
        assert (
            plan.entry > plan.invalidation
            if plan.side == "call"
            else plan.entry < plan.invalidation
        )


def test_missing_and_out_of_sync_members_not_counted_as_bears():
    histories, now = fixture()
    del histories["AAPL"]
    histories["MSFT"] = histories["MSFT"][:-1]
    row = tech(histories, now)
    assert row.sample_coverage == 0.6
    assert row.bullish_breadth == 1 and row.bearish_breadth == 0
    assert sum(m.available for m in row.members) == 3
    histories["NVDA"] = []
    assert tech(histories, now).signal == "watch"


def test_old_data_cannot_confirm_current_entry():
    histories, now = fixture()
    row = tech(histories, now + timedelta(days=3))
    assert row.stale and row.signal == "historical"
    assert all(p.state == "stale" for p in row.plans)


def test_missing_benchmark_never_substitutes_another_sector():
    histories, now = fixture()
    del histories["SPY"]
    result = build_sector_scan(histories, {}, now, "fixture")
    assert result.as_of is None
    assert all(not row.available and row.signal == "unavailable" for row in result.sectors)


def test_unfinished_future_and_extended_hours_bars_excluded():
    points = tape()
    now = points[-1].timestamp + timedelta(minutes=5)
    extras = [
        points[-1].model_copy(update={"timestamp": now + timedelta(days=1)}),
        points[-1].model_copy(update={"timestamp": now.replace(hour=12)}),
    ]
    result = completed_session_bars(points + extras, now)
    assert result == points[:-1]


def test_missing_open_disables_session_comparison_and_confirmation():
    histories, now = fixture()
    histories["XLK"] = [
        p
        for p in histories["XLK"]
        if not (p.timestamp.day == 11 and p.timestamp.hour == 13 and p.timestamp.minute == 30)
    ]
    row = tech(histories, now)
    assert row.session_return is None and row.session_vwap is None
    assert row.relative_to_spy is None and row.signal == "watch"


def test_correlation_uses_matched_returns_and_rejects_zero_variance():
    points = tape()
    assert correlation(points, points)[0] == pytest.approx(1)
    assert correlation(points[:5], points[:5]) == (None, 4)
    flat = [p.model_copy(update={"close": 100}) for p in points]
    assert correlation(points, flat) == (None, 26)
    sparse = points[::2]
    assert correlation(points, sparse) == (None, 0)


def test_daily_returns_exclude_today_and_future_bars():
    histories, now = fixture()
    daily = [
        PricePoint(
            timestamp=now - timedelta(days=25 - i),
            open=100 + i,
            high=101 + i,
            low=99 + i,
            close=100 + i,
            volume=1000,
        )
        for i in range(28)
    ]
    result = build_sector_scan(histories, {"XLK": daily}, now, "fixture")
    row = next(r for r in result.sectors if r.symbol == "XLK")
    assert row.daily_returns["1D"] == pytest.approx(124 / 123 - 1)
    assert row.daily_returns["20D"] == pytest.approx(124 / 104 - 1)


def test_market_adapter_retains_available_symbols_when_one_has_no_bars():
    provider = AlpacaMarketDataProvider.__new__(AlpacaMarketDataProvider)
    provider.stock_client = SimpleNamespace(get_stock_bars=lambda _: {"SPY": tape()})
    result = provider.get_intraday_history(["SPY", "MISSING"])
    assert len(result["SPY"]) == 78 and result["MISSING"] == []


@pytest.fixture
def isolated_service():
    service._cache.clear()
    service._inflight.clear()
    yield
    service._cache.clear()
    service._inflight.clear()
    main.app.dependency_overrides.clear()


def settings(**kwargs):
    return Settings(
        _env_file=None, market_data_mode="demo", alpaca_api_key="", alpaca_secret_key="", **kwargs
    )


def test_service_caches_copies_and_api_is_read_only(monkeypatch, isolated_service):
    histories, _ = fixture()
    calls = []

    def fetch(*args, **kwargs):
        calls.append(1)
        return histories

    monkeypatch.setattr(
        service,
        "build_market_data_provider",
        lambda _: SimpleNamespace(
            get_intraday_history=fetch, get_price_history=lambda *args, **kwargs: {}
        ),
    )
    config = settings()
    first = service.get_sector_scan(config)
    first.sectors.clear()
    main.app.dependency_overrides[get_settings] = lambda: config
    response = TestClient(main.app).get("/api/v1/sector-scanner")
    assert response.status_code == 200 and response.json()["read_only"] is True
    assert len(response.json()["sectors"]) == 11 and len(calls) == 1
    assert TestClient(main.app).post("/api/v1/sector-scanner").status_code == 405


def test_api_errors_are_redacted(monkeypatch, isolated_service):
    monkeypatch.setattr(
        main, "get_sector_scan", lambda _: (_ for _ in ()).throw(ValueError("sensitive upstream"))
    )
    main.app.dependency_overrides[get_settings] = lambda: settings()
    response = TestClient(main.app).get("/api/v1/sector-scanner")
    assert response.status_code == 502 and "sensitive" not in response.text
