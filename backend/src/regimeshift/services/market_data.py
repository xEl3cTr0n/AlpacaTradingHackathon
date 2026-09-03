import math
import random
from datetime import UTC, datetime, timedelta
from typing import Protocol

from regimeshift.config import Settings
from regimeshift.domain.models import MarketContext, PricePoint


class MarketDataProvider(Protocol):
    def get_context(self, symbol: str) -> MarketContext: ...

    def get_price_history(
        self, symbols: list[str], days: int = 180
    ) -> dict[str, list[PricePoint]]: ...

    def get_intraday_history(
        self, symbols: list[str], days: int = 10, bar_minutes: int = 15
    ) -> dict[str, list[PricePoint]]: ...


class DemoMarketDataProvider:
    """Deterministic market tape for demos, tests, and closed-market development."""

    def _get_prices(self, symbol: str, days: int = 180) -> list[PricePoint]:
        symbol = symbol.upper()
        randomizer = random.Random(f"regimeshift:{symbol}")
        now = datetime.now(UTC).replace(hour=20, minute=0, second=0, microsecond=0)
        price = 525.0 if symbol == "SPY" else 460.0
        points: list[PricePoint] = []
        point_count = max(100, int(days * 5 / 7))
        for index in range(point_count):
            drift = 0.0009
            cycle = math.sin(index / 6) * 0.002
            shock = randomizer.gauss(0, 0.006 + (0.002 if index > 85 else 0))
            price *= 1 + drift + cycle + shock
            timestamp = now - timedelta(days=point_count - 1 - index)
            points.append(
                PricePoint(
                    timestamp=timestamp,
                    open=round(price * (1 - shock / 3), 2),
                    high=round(price * (1 + abs(shock) / 2 + 0.002), 2),
                    low=round(price * (1 - abs(shock) / 2 - 0.002), 2),
                    close=round(price, 2),
                    volume=int(61_000_000 + randomizer.random() * 24_000_000),
                )
            )

        return points

    def get_price_history(
        self, symbols: list[str], days: int = 180
    ) -> dict[str, list[PricePoint]]:
        return {symbol.upper(): self._get_prices(symbol, days) for symbol in symbols}

    def get_intraday_history(
        self, symbols: list[str], days: int = 10, bar_minutes: int = 15
    ) -> dict[str, list[PricePoint]]:
        count = max(100, days * 26)
        end = datetime.now(UTC).replace(second=0, microsecond=0)
        output: dict[str, list[PricePoint]] = {}
        for symbol in symbols:
            randomizer = random.Random(f"regimeshift:intraday:{symbol.upper()}")
            price = 525.0 if symbol.upper() == "SPY" else 460.0
            points: list[PricePoint] = []
            for index in range(count):
                shock = randomizer.gauss(0, 0.0025)
                price *= 1 + 0.00008 + math.sin(index / 11) * 0.0007 + shock
                timestamp = end - timedelta(minutes=(count - 1 - index) * bar_minutes)
                points.append(
                    PricePoint(
                        timestamp=timestamp,
                        open=round(price * (1 - shock / 3), 2),
                        high=round(price * (1 + abs(shock) / 2 + 0.0005), 2),
                        low=round(price * (1 - abs(shock) / 2 - 0.0005), 2),
                        close=round(price, 2),
                        volume=int(1_500_000 + randomizer.random() * 900_000),
                    )
                )
            output[symbol.upper()] = points
        return output

    def get_context(self, symbol: str) -> MarketContext:
        symbol = symbol.upper()
        points = self._get_prices(symbol)
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

    def get_price_history(
        self, symbols: list[str], days: int = 180
    ) -> dict[str, list[PricePoint]]:
        from alpaca.data.enums import Adjustment, DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        normalized = [symbol.upper() for symbol in symbols]
        end = datetime.now(UTC)
        request = StockBarsRequest(
            symbol_or_symbols=normalized,
            timeframe=TimeFrame.Day,
            start=end - timedelta(days=days),
            end=end,
            feed=DataFeed.IEX,
            adjustment=Adjustment.ALL,
        )
        bar_set = self.stock_client.get_stock_bars(request)
        histories: dict[str, list[PricePoint]] = {}
        for symbol in normalized:
            bars = bar_set[symbol]
            histories[symbol] = [
                PricePoint(
                    timestamp=bar.timestamp,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=int(bar.volume),
                )
                for bar in bars
            ]
        return histories

    def get_intraday_history(
        self, symbols: list[str], days: int = 10, bar_minutes: int = 15
    ) -> dict[str, list[PricePoint]]:
        from alpaca.data.enums import Adjustment, DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        normalized = [symbol.upper() for symbol in symbols]
        now = datetime.now(UTC)
        current_bucket = now.replace(
            minute=(now.minute // bar_minutes) * bar_minutes,
            second=0,
            microsecond=0,
        )
        end = current_bucket - timedelta(microseconds=1)
        request = StockBarsRequest(
            symbol_or_symbols=normalized,
            timeframe=TimeFrame(bar_minutes, TimeFrameUnit.Minute),
            start=end - timedelta(days=days),
            end=end,
            feed=DataFeed.IEX,
            adjustment=Adjustment.ALL,
        )
        bar_set = self.stock_client.get_stock_bars(request)
        histories: dict[str, list[PricePoint]] = {}
        for symbol in normalized:
            histories[symbol] = [
                PricePoint(
                    timestamp=bar.timestamp,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=int(bar.volume),
                )
                for bar in bar_set[symbol]
            ]
        return histories

    def get_context(self, symbol: str) -> MarketContext:
        from alpaca.data.requests import NewsRequest

        symbol = symbol.upper()
        points = self.get_price_history([symbol])[symbol]
        if len(points) < 55:
            raise ValueError(f"Alpaca returned only {len(points)} daily bars for {symbol}")

        news_set = self.news_client.get_news(NewsRequest(symbols=symbol, limit=5, sort="desc"))
        news_data = getattr(news_set, "data", {})
        news_items = news_data.get("news", []) if isinstance(news_data, dict) else []
        headlines = [article.headline for article in news_items]
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
