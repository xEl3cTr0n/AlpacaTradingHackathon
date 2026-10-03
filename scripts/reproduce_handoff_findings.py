"""Offline bug witnesses for docs/gemini-handoff.md (2026-09-17).

These assertions describe existing bugs, NOT desired regression-test behavior.
After fixing a finding, convert its witness into a test of the desired behavior.
No broker commands, external requests, credentials, or order submissions.
Run from repo root: backend/.venv/bin/python scripts/reproduce_handoff_findings.py
"""

import runpy
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/src"))

from fastapi.testclient import TestClient

from regimeshift.config import Settings, get_settings
from regimeshift.domain.models import LiveMarketTick
from regimeshift.domain.exits import managed_exit_plan
import regimeshift.main as main
import regimeshift.services.live_tape as live
import regimeshift.services.sector_scanner as sectors


def config(mode="demo"):
    return Settings(_env_file=None, market_data_mode=mode,
                    alpaca_api_key="", alpaca_secret_key="")


def cache_scope():
    calls = []

    def provider(settings):
        calls.append(settings.market_data_mode)
        return SimpleNamespace(get_live_tick=lambda symbol: LiveMarketTick(
            symbol=symbol, as_of=datetime(2026, 9, 17, 14, tzinfo=UTC),
            price=100 if settings.market_data_mode == "demo" else 200,
            source=settings.market_data_mode))

    live._cache.clear()
    with patch.object(live, "build_market_data_provider", provider), \
            patch.object(live, "monotonic", return_value=100):
        live.get_live_tick(config("demo"), "SPY")
        second = live.get_live_tick(config("alpaca"), "SPY")
    live._cache.clear()
    assert calls == ["demo", "alpaca"] and second.source == "alpaca" and second.price == 200
    print("B1 verified fixed: Alpaca-mode request is isolated from demo cache.")


def exception_disclosure():
    marker = "SYNTHETIC_PRIVATE_UPSTREAM_DETAIL"
    main.app.dependency_overrides[get_settings] = lambda: config()
    try:
        with patch.object(main, "get_live_tick", side_effect=RuntimeError(marker)):
            response = TestClient(main.app).get("/api/v1/live-tape?symbol=SPY")
        assert response.status_code == 502 and marker not in response.json()["detail"]
        assert response.json()["detail"] == "Live tape request failed; retry shortly"
    finally:
        main.app.dependency_overrides.clear()
    print("B2 verified fixed: upstream exception detail is sanitized in public GET.")


def sector_close_cache():
    fixtures = runpy.run_path(str(ROOT / "backend/tests/test_sector_scanner.py"))
    histories, _ = fixtures["fixture"]()
    before = datetime(2026, 9, 11, 19, 59, 30, tzinfo=UTC)
    after = before + timedelta(seconds=40)
    now = [before]

    class Clock:
        @staticmethod
        def now(_tz):
            return now[0]

    provider = SimpleNamespace(get_intraday_history=lambda *a, **k: histories,
                               get_price_history=lambda *a, **k: {})
    sectors._cache.clear()
    sectors._inflight.clear()
    with patch.object(sectors, "build_market_data_provider", return_value=provider), \
            patch.object(sectors, "datetime", Clock), \
            patch.object(sectors, "monotonic", side_effect=lambda: (now[0] - before).total_seconds()):
        sectors.get_sector_scan(config())
        now[0] = after
        cached = sectors.get_sector_scan(config())
    direct = fixtures["tech"](histories, after)
    row = next(r for r in cached.sectors if r.symbol == "XLK")
    sectors._cache.clear()
    assert row.signal == "historical" and row.stale
    assert direct.signal == "historical" and direct.stale
    print("B3 verified fixed: 16:00:10 ET cache correctly returns historical signal and stale status.")


def weekly_exit_conflict():
    fixtures = runpy.run_path(str(ROOT / "backend/tests/test_exits.py"))
    entry = fixtures["_entry"]()
    entry["submitted_at"] = "2026-12-11T14:30:00Z"
    positions = {
        leg["symbol"]: {"qty": "1" if leg["side"] == "buy" else "-1",
                        "qty_available": "1", "unrealized_pl": "0"}
        for leg in entry["legs"]
    }
    plan = managed_exit_plan(entry, positions, now=datetime(2026, 12, 11, 15, tzinfo=UTC))
    assert plan is None
    exit_plan = managed_exit_plan(entry, positions, now=datetime(2026, 12, 17, 15, tzinfo=UTC))
    assert exit_plan is not None and "expiration is within 1 day" in exit_plan["reasons"]
    print("G1 verified fixed: seven-DTE spread is not immediately closed on entry; exits at horizon cutoff.")


if __name__ == "__main__":
    cache_scope()
    exception_disclosure()
    sector_close_cache()
    weekly_exit_conflict()
