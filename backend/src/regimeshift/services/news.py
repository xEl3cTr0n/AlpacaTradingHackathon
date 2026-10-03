"""Read-only headline feed for the terminal news panel.

Alpaca's news API (Benzinga-sourced) is included with market-data credentials,
so the terminal gets a real feed without another vendor or a paywalled squawk.
Headlines are display context only: they never vote, size or authorize orders.
"""

import hashlib
import html
import re
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from threading import Lock
from time import monotonic
from typing import Protocol

from regimeshift.config import Settings
from regimeshift.domain.models import NewsArticle, NewsSnapshot

CACHE_SECONDS = 30.0
MAX_CACHE_KEYS = 64
MARKET_LOOKBACK = timedelta(days=4)
_TAG = re.compile(r"<[^>]+>")

_cache: OrderedDict[tuple[str, str, str, int], tuple[float, NewsSnapshot]] = OrderedDict()
_lock = Lock()


class NewsProvider(Protocol):
    source: str

    def get_news(self, symbols: list[str], limit: int) -> list[NewsArticle]: ...


def _clean(text: str | None, limit: int) -> str:
    plain = html.unescape(_TAG.sub(" ", text or ""))
    plain = " ".join(plain.split())
    return plain if len(plain) <= limit else plain[: limit - 1].rstrip() + "…"


def _safe_url(url: str | None) -> str | None:
    # The UI renders this as a link; only plain web URLs are allowed through.
    return url if url and url.lower().startswith(("https://", "http://")) else None


class AlpacaNewsProvider:
    source = "Alpaca News API (Benzinga)"

    def __init__(self, settings: Settings):
        if not settings.alpaca_configured:
            raise ValueError("Alpaca credentials are not configured")
        from alpaca.data.historical import NewsClient

        self.client = NewsClient(
            settings.alpaca_api_key, settings.alpaca_secret_key.get_secret_value()
        )

    def get_news(self, symbols: list[str], limit: int) -> list[NewsArticle]:
        from alpaca.data.requests import NewsRequest

        request = NewsRequest(
            symbols=",".join(symbols) if symbols else None,
            # Alpaca defaults to "since midnight", which is empty on weekends.
            start=datetime.now(UTC) - MARKET_LOOKBACK,
            limit=limit,
            sort="desc",
            include_content=False,
        )
        news_set = self.client.get_news(request)
        data = getattr(news_set, "data", {})
        items = data.get("news", []) if isinstance(data, dict) else []
        # Alpaca's sort key is updated_at; edited stories would jump the queue.
        items = sorted(items, key=lambda item: item.created_at, reverse=True)
        return [
            NewsArticle(
                id=str(item.id),
                headline=_clean(item.headline, 300),
                summary=_clean(item.summary, 400),
                source=item.source or "unknown",
                author=item.author or "",
                url=_safe_url(item.url),
                symbols=[s.upper() for s in (item.symbols or [])][:12],
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items[:limit]
        ]


class DemoNewsProvider:
    source = "deterministic demo headlines"

    def get_news(self, symbols: list[str], limit: int) -> list[NewsArticle]:
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        tickers = symbols or ["SPY", "QQQ", "NVDA", "AAPL"]
        templates = [
            "{s} options volume rises into the close as traders weigh the next catalyst",
            "Analysts revisit {s} targets after the latest guidance update",
            "{s} holds near session VWAP while broader indices consolidate",
            "Sector rotation lifts {s} relative strength versus SPY",
        ]
        articles = []
        for index in range(min(limit, 12)):
            symbol = tickers[index % len(tickers)]
            stamp = now - timedelta(minutes=17 * index + 3)
            articles.append(
                NewsArticle(
                    id=f"demo-{symbol}-{index}",
                    headline=templates[index % len(templates)].format(s=symbol),
                    summary="Demo headline for offline development. Not real news.",
                    source="demo",
                    symbols=[symbol],
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
        return articles


def build_news_provider(settings: Settings) -> NewsProvider:
    if settings.market_data_mode.lower() == "alpaca":
        return AlpacaNewsProvider(settings)
    return DemoNewsProvider()


def _cache_key(settings: Settings, symbols: list[str], limit: int) -> tuple[str, str, str, int]:
    identity = hashlib.sha256(
        f"{settings.alpaca_api_key}:{settings.alpaca_secret_key.get_secret_value()}".encode()
    ).hexdigest()
    return (settings.market_data_mode.lower(), identity, ",".join(symbols), limit)


def get_news(settings: Settings, symbols: list[str], limit: int = 25) -> NewsSnapshot:
    """Return recent headlines, sharing one upstream read per key for 30 seconds."""
    normalized = sorted({symbol.upper() for symbol in symbols})
    key = _cache_key(settings, normalized, limit)
    with _lock:
        cached = _cache.get(key)
        if cached and monotonic() - cached[0] < CACHE_SECONDS:
            _cache.move_to_end(key)
            return cached[1]
    provider = build_news_provider(settings)
    snapshot = NewsSnapshot(
        generated_at=datetime.now(UTC),
        source=provider.source,
        symbols=normalized,
        articles=provider.get_news(normalized, limit),
    )
    with _lock:
        _cache[key] = (monotonic(), snapshot)
        _cache.move_to_end(key)
        while len(_cache) > MAX_CACHE_KEYS:
            _cache.popitem(last=False)
    return snapshot
