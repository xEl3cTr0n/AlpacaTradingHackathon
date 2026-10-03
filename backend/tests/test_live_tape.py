import time
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from regimeshift.config import Settings
from regimeshift.domain.models import LiveMarketTick
import regimeshift.services.live_tape as live_tape


def _settings(mode="demo", api_key="key-1", secret="sec-1"):
    return Settings(
        _env_file=None,
        market_data_mode=mode,
        alpaca_api_key=api_key,
        alpaca_secret_key=secret,
    )


@pytest.fixture(autouse=True)
def clear_cache():
    with live_tape._lock:
        live_tape._cache.clear()
        live_tape._inflight.clear()
    yield
    with live_tape._lock:
        live_tape._cache.clear()
        live_tape._inflight.clear()


def test_live_tape_isolates_by_mode():
    provider_calls = []

    def mock_builder(s: Settings):
        provider_calls.append(s.market_data_mode)
        price = 100.0 if s.market_data_mode == "demo" else 200.0
        return SimpleNamespace(
            get_live_tick=lambda sym: LiveMarketTick(
                symbol=sym,
                price=price,
                as_of=datetime(2026, 9, 17, 12, 0, tzinfo=UTC),
                source=s.market_data_mode,
            )
        )

    with patch.object(live_tape, "build_market_data_provider", side_effect=mock_builder):
        demo_tick = live_tape.get_live_tick(_settings(mode="demo"), "SPY")
        alpaca_tick = live_tape.get_live_tick(_settings(mode="alpaca"), "SPY")

    assert provider_calls == ["demo", "alpaca"]
    assert demo_tick.source == "demo"
    assert demo_tick.price == 100.0
    assert alpaca_tick.source == "alpaca"
    assert alpaca_tick.price == 200.0


def test_live_tape_isolates_by_credentials():
    provider_calls = []

    def mock_builder(s: Settings):
        provider_calls.append(s.alpaca_api_key)
        return SimpleNamespace(
            get_live_tick=lambda sym: LiveMarketTick(
                symbol=sym,
                price=150.0 if s.alpaca_api_key == "user-a" else 160.0,
                as_of=datetime(2026, 9, 17, 12, 0, tzinfo=UTC),
                source="alpaca",
            )
        )

    with patch.object(live_tape, "build_market_data_provider", side_effect=mock_builder):
        user_a = live_tape.get_live_tick(_settings(mode="alpaca", api_key="user-a"), "AAPL")
        user_b = live_tape.get_live_tick(_settings(mode="alpaca", api_key="user-b"), "AAPL")

    assert provider_calls == ["user-a", "user-b"]
    assert user_a.price == 150.0
    assert user_b.price == 160.0


def test_live_tape_caches_within_ttl():
    mock_provider = SimpleNamespace(
        get_live_tick=MagicMock(
            return_value=LiveMarketTick(
                symbol="SPY",
                price=500.0,
                as_of=datetime(2026, 9, 17, 12, 0, tzinfo=UTC),
                source="demo",
            )
        )
    )

    with patch.object(live_tape, "build_market_data_provider", return_value=mock_provider):
        t1 = live_tape.get_live_tick(_settings(), "SPY")
        t2 = live_tape.get_live_tick(_settings(), "SPY")

    assert mock_provider.get_live_tick.call_count == 1
    assert t1.price == t2.price == 500.0


def test_live_tape_expires_after_ttl():
    mock_provider = SimpleNamespace(
        get_live_tick=MagicMock(
            return_value=LiveMarketTick(
                symbol="SPY",
                price=500.0,
                as_of=datetime(2026, 9, 17, 12, 0, tzinfo=UTC),
                source="demo",
            )
        )
    )

    clock = [100.0]

    with patch.object(live_tape, "build_market_data_provider", return_value=mock_provider), \
         patch.object(live_tape, "monotonic", side_effect=lambda: clock[0]):
        live_tape.get_live_tick(_settings(), "SPY")
        clock[0] = 100.2
        live_tape.get_live_tick(_settings(), "SPY")  # 100.2 -> cached
        clock[0] = 101.5
        live_tape.get_live_tick(_settings(), "SPY")  # 101.5 -> expired (> 0.8s)

    assert mock_provider.get_live_tick.call_count == 2


def test_live_tape_returns_deep_copy():
    mock_provider = SimpleNamespace(
        get_live_tick=MagicMock(
            return_value=LiveMarketTick(
                symbol="SPY",
                price=500.0,
                as_of=datetime(2026, 9, 17, 12, 0, tzinfo=UTC),
                source="demo",
            )
        )
    )

    with patch.object(live_tape, "build_market_data_provider", return_value=mock_provider):
        tick1 = live_tape.get_live_tick(_settings(), "SPY")
        tick1.price = 999.0
        tick2 = live_tape.get_live_tick(_settings(), "SPY")

    assert tick2.price == 500.0
