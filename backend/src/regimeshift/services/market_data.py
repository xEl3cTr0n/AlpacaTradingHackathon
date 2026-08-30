import math
import random
from datetime import UTC, datetime, timedelta
from typing import Protocol

from regimeshift.config import Settings
from regimeshift.domain.models import MarketContext, PricePoint


class MarketDataProvider(Protocol):
    def get_context(self, symbol: str) -> MarketContext: ...


class DemoMarketDataProvider:
    """Deterministic market tape for demos, tests, and closed-market development."""

    def get_context(self, symbol: str) -> MarketContext:
        symbol = symbol.upper()
        randomizer = random.Random(f"regimeshift:{symbol}")
        now = datetime.now(UTC).replace(hour=20, minute=0, second=0, microsecond=0)
        price = 525.0 if symbol == "SPY" else 460.0
        points: list[PricePoint] = []
        for index in range(100):
            drift = 0.0009
            cycle = math.sin(index / 6) * 0.002
            shock = randomizer.gauss(0, 0.006 + (0.002 if index > 85 else 0))
            price *= 1 + drift + cycle + shock
            timestamp = now - timedelta(days=99 - index)
            points.append(
                PricePoint(
                    timestamp=timestamp,
                    close=round(price, 2),
                    volume=int(61_000_000 + randomizer.random() * 24_000_000),
                )
            )

        change = ((points[-1].close / points[-2].close) - 1) * 100
        return MarketContext(
            symbol=symbol,
            as_of=points[-1].timestamp,
            source="deterministic demo tape",
            current_price=points[-1].close,
            price_change_pct=round(change, 2),
            prices=points,
            headlines=[
                f"{symbol} liquidity remains firm as investors assess the next macro catalyst",
                "Options markets price a wider range of outcomes into the coming sessions",
                "Large-cap momentum holds while traders monitor volatility",
            ],
        )


class AlpacaMarketDataProvider:
    def __init__(self, settings: Settings):
        if not settings.alpaca_configured:
            raise ValueError("Alpaca credentials are not configured")
        from alpaca.data.historical import NewsClient, StockHistoricalDataClient

        secret = settings.alpaca_secret_key.get_secret_value()
        self.stock_client = StockHistoricalDataClient(settings.alpaca_api_key, secret)
        self.news_client = NewsClient(settings.alpaca_api_key, secret)

    def get_context(self, symbol: str) -> MarketContext:
        from alpaca.data.requests import NewsRequest, StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        symbol = symbol.upper()
        end = datetime.now(UTC)
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=end - timedelta(days=180),
            end=end,
        )
        bars = self.stock_client.get_stock_bars(request)[symbol]
        points = [
            PricePoint(timestamp=bar.timestamp, close=float(bar.close), volume=int(bar.volume))
            for bar in bars
        ]
        if len(points) < 55:
            raise ValueError(f"Alpaca returned only {len(points)} daily bars for {symbol}")

        news = self.news_client.get_news(NewsRequest(symbols=symbol, limit=5, sort="desc"))
        headlines = [article.headline for article in news.news]
        change = ((points[-1].close / points[-2].close) - 1) * 100
        return MarketContext(
            symbol=symbol,
            as_of=points[-1].timestamp,
            source="Alpaca Market Data API",
            current_price=round(points[-1].close, 2),
            price_change_pct=round(change, 2),
            prices=points[-100:],
            headlines=headlines,
        )


def build_market_data_provider(settings: Settings) -> MarketDataProvider:
    if settings.market_data_mode.lower() == "alpaca":
        return AlpacaMarketDataProvider(settings)
    return DemoMarketDataProvider()
