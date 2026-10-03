from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import regimeshift.main as main
import regimeshift.services.news as news
from regimeshift.config import Settings, get_settings


def _settings(mode="demo"):
    return Settings(
        _env_file=None, market_data_mode=mode, alpaca_api_key="key", alpaca_secret_key="secret"
    )


@pytest.fixture(autouse=True)
def clear_cache():
    with news._lock:
        news._cache.clear()
    yield
    with news._lock:
        news._cache.clear()
    main.app.dependency_overrides.clear()


def _article(**overrides):
    stamp = datetime(2026, 10, 2, 14, 30, tzinfo=UTC)
    raw = dict(
        id=42,
        headline="<b>NVDA</b> beats &amp; raises",
        summary="<p>Guidance above consensus.</p>",
        source="benzinga",
        author="Reporter",
        url="https://example.com/story",
        symbols=["nvda", "AMD"],
        created_at=stamp,
        updated_at=stamp,
    )
    raw.update(overrides)
    return SimpleNamespace(**raw)


def test_demo_news_endpoint_is_labeled_and_read_only():
    main.app.dependency_overrides[get_settings] = lambda: _settings()
    response = TestClient(main.app).get("/api/v1/news?symbols=aapl&limit=5")
    assert response.status_code == 200
    body = response.json()
    assert body["read_only"] is True
    assert body["symbols"] == ["AAPL"]
    assert body["source"] == "deterministic demo headlines"
    assert 0 < len(body["articles"]) <= 5
    assert all(article["symbols"] == ["AAPL"] for article in body["articles"])


def test_news_endpoint_rejects_bad_symbol_lists():
    main.app.dependency_overrides[get_settings] = lambda: _settings()
    client = TestClient(main.app)
    assert client.get("/api/v1/news?symbols=AAPL;DROP").status_code == 422
    eleven = ",".join(f"A{chr(65 + i)}" for i in range(11))
    assert client.get(f"/api/v1/news?symbols={eleven}").status_code == 422
    assert client.get("/api/v1/news?limit=500").status_code == 422


def test_news_endpoint_redacts_upstream_errors():
    main.app.dependency_overrides[get_settings] = lambda: _settings()
    with patch.object(news, "build_news_provider", side_effect=RuntimeError("secret detail")):
        response = TestClient(main.app).get("/api/v1/news")
    assert response.status_code == 502
    assert "secret detail" not in response.text


def test_alpaca_news_strips_markup_and_unsafe_urls():
    provider = news.AlpacaNewsProvider.__new__(news.AlpacaNewsProvider)
    provider.client = MagicMock()
    provider.client.get_news.return_value = SimpleNamespace(
        data={"news": [_article(), _article(id=7, url="javascript:alert(1)")]}
    )
    articles = provider.get_news(["NVDA"], 10)
    request = provider.client.get_news.call_args.args[0]
    assert request.symbols == "NVDA"
    assert request.start is not None  # weekend-safe lookback, not "since midnight"
    assert articles[0].headline == "NVDA beats & raises"
    assert articles[0].summary == "Guidance above consensus."
    assert articles[0].symbols == ["NVDA", "AMD"]
    assert articles[0].url == "https://example.com/story"
    assert articles[1].url is None


def test_news_cache_shares_one_upstream_read():
    calls = []

    class Provider:
        source = "stub"

        def get_news(self, symbols, limit):
            calls.append((tuple(symbols), limit))
            return []

    with patch.object(news, "build_news_provider", return_value=Provider()):
        first = news.get_news(_settings(), ["msft", "AAPL"], 10)
        second = news.get_news(_settings(), ["AAPL", "MSFT"], 10)
        news.get_news(_settings(), [], 10)
    assert first is second
    assert first.symbols == ["AAPL", "MSFT"]
    assert calls == [(("AAPL", "MSFT"), 10), ((), 10)]


def test_alpaca_chart_history_keeps_bar_vwap():
    from regimeshift.services.market_data import AlpacaMarketDataProvider

    stamp = datetime(2026, 10, 2, 14, 30, tzinfo=UTC)
    bar = SimpleNamespace(
        timestamp=stamp, open=1.0, high=2.0, low=0.5, close=1.5, volume=10, vwap=1.25
    )
    provider = AlpacaMarketDataProvider.__new__(AlpacaMarketDataProvider)
    provider.stock_client = MagicMock()
    provider.stock_client.get_stock_bars.return_value = {"SPY": [bar]}
    points = provider.get_chart_history("SPY", "5Min", 50)
    assert points[0].vwap == 1.25
