import math
from statistics import mean, pstdev

from regimeshift.domain.models import (
    Direction,
    PricePoint,
    ScannerCandidate,
    ScannerPattern,
    ScannerSnapshot,
)

LARGE_CAP_UNIVERSE: dict[str, str] = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "META": "Meta Platforms",
    "TSLA": "Tesla",
    "AVGO": "Broadcom",
    "BRK.B": "Berkshire Hathaway",
    "JPM": "JPMorgan Chase",
    "LLY": "Eli Lilly",
    "V": "Visa",
    "MA": "Mastercard",
    "WMT": "Walmart",
    "XOM": "Exxon Mobil",
    "COST": "Costco",
    "NFLX": "Netflix",
    "AMD": "Advanced Micro Devices",
    "CRM": "Salesforce",
    "ORCL": "Oracle",
    "BAC": "Bank of America",
    "HD": "Home Depot",
    "KO": "Coca-Cola",
    "PEP": "PepsiCo",
}


def exponential_moving_average(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    current = values[0]
    output: list[float] = []
    for value in values:
        current = alpha * value + (1 - alpha) * current
        output.append(current)
    return output


def relative_strength_index(values: list[float], period: int = 14) -> list[float]:
    output = [50.0] * len(values)
    average_gain = 0.0
    average_loss = 0.0
    for index in range(1, len(values)):
        change = values[index] - values[index - 1]
        gain = max(change, 0)
        loss = max(-change, 0)
        if index <= period:
            average_gain += gain / period
            average_loss += loss / period
        else:
            average_gain = (average_gain * (period - 1) + gain) / period
            average_loss = (average_loss * (period - 1) + loss) / period
        if index >= period:
            output[index] = (
                100.0
                if average_loss == 0
                else 100 - 100 / (1 + average_gain / average_loss)
            )
    return output


class LargeCapScanner:
    """Ranks liquid large caps; only validated 18 EMA crosses are actionable."""

    benchmark_symbol = "SPY"
    ema_period = 18
    trend_period = 50
    minimum_conviction = 0.60
    minimum_average_dollar_volume = 100_000_000
    interval_minutes = 15

    def scan(
        self,
        histories: dict[str, list[PricePoint]],
        *,
        limit: int = 12,
        source: str = "market data",
    ) -> ScannerSnapshot:
        benchmark = histories.get(self.benchmark_symbol, [])
        if len(benchmark) < 60:
            raise ValueError("Scanner requires at least 60 SPY sessions")

        candidates: list[ScannerCandidate] = []
        for symbol, name in LARGE_CAP_UNIVERSE.items():
            points = histories.get(symbol, [])
            if len(points) < 60:
                continue
            candidate = self.score(symbol, name, points, benchmark, len(points) - 1)
            if candidate is not None:
                candidates.append(candidate)

        candidates.sort(
            key=lambda candidate: (
                candidate.actionable,
                candidate.conviction,
                candidate.average_dollar_volume,
            ),
            reverse=True,
        )
        ranked = [
            candidate.model_copy(update={"rank": rank})
            for rank, candidate in enumerate(candidates[:limit], start=1)
        ]
        return ScannerSnapshot(
            generated_at=max(point.timestamp for point in benchmark),
            source=source,
            interval_minutes=self.interval_minutes,
            universe_size=len(LARGE_CAP_UNIVERSE),
            scanned_count=len(candidates),
            actionable_count=sum(candidate.actionable for candidate in candidates),
            minimum_conviction=self.minimum_conviction,
            ema_period=self.ema_period,
            methodology=(
                "Two-stage liquidity screen: large-cap universe and $100M 20-session "
                "average dollar volume, followed by contract bid/ask and open-interest "
                "checks before execution. Actionable signals require a price/18 EMA cross, "
                "18/50 EMA trend alignment, SPY trend confirmation, and 60% conviction."
            ),
            candidates=ranked,
        )

    def score(
        self,
        symbol: str,
        name: str,
        points: list[PricePoint],
        benchmark: list[PricePoint],
        index: int,
    ) -> ScannerCandidate | None:
        if index < 60 or index >= len(points):
            return None
        closes = [point.close for point in points[: index + 1]]
        ema_18 = exponential_moving_average(closes, self.ema_period)
        ema_50 = exponential_moving_average(closes, self.trend_period)
        rsi_14 = relative_strength_index(closes)
        current = points[index]

        benchmark_by_date = {point.timestamp.date(): point for point in benchmark}
        benchmark_dates = [point.timestamp.date() for point in benchmark]
        current_date = current.timestamp.date()
        if current_date not in benchmark_by_date:
            return None
        historical_date = points[index - 20].timestamp.date()
        if historical_date not in benchmark_by_date:
            return None
        benchmark_index = benchmark_dates.index(current_date)
        if benchmark_index < 55:
            return None
        benchmark_closes = [point.close for point in benchmark[: benchmark_index + 1]]
        benchmark_ema_50 = exponential_moving_average(benchmark_closes, self.trend_period)

        bullish_cross = closes[-2] <= ema_18[-2] and closes[-1] > ema_18[-1]
        bearish_cross = closes[-2] >= ema_18[-2] and closes[-1] < ema_18[-1]
        bullish_trend = ema_18[-1] > ema_50[-1] and ema_18[-1] > ema_18[-6]
        bearish_trend = ema_18[-1] < ema_50[-1] and ema_18[-1] < ema_18[-6]
        benchmark_bullish = (
            benchmark_closes[-1] > benchmark_ema_50[-1]
            and benchmark_ema_50[-1] > benchmark_ema_50[-6]
        )
        benchmark_bearish = (
            benchmark_closes[-1] < benchmark_ema_50[-1]
            and benchmark_ema_50[-1] < benchmark_ema_50[-6]
        )

        if bullish_trend:
            direction = Direction.BULLISH
            pattern = (
                ScannerPattern.BULLISH_18EMA_CROSS
                if bullish_cross
                else ScannerPattern.BULLISH_TREND_WATCH
            )
            market_aligned = benchmark_bullish
        elif bearish_trend:
            direction = Direction.BEARISH
            pattern = (
                ScannerPattern.BEARISH_18EMA_CROSS
                if bearish_cross
                else ScannerPattern.BEARISH_TREND_WATCH
            )
            market_aligned = benchmark_bearish
        else:
            direction = Direction.SIDEWAYS
            pattern = ScannerPattern.NO_SETUP
            market_aligned = False

        direction_sign = 1 if direction == Direction.BULLISH else -1
        average_volume = mean(point.volume for point in points[index - 20 : index])
        average_dollar_volume = mean(
            point.close * point.volume for point in points[index - 20 : index]
        )
        volume_ratio = current.volume / max(1, average_volume)
        benchmark_current = benchmark_by_date[current_date].close
        benchmark_old = benchmark_by_date[historical_date].close
        relative_strength = (closes[-1] / closes[-21] - 1) - (
            benchmark_current / benchmark_old - 1
        )
        slope = ema_18[-1] / ema_18[-6] - 1
        daily_returns = [
            closes[position] / closes[position - 1] - 1
            for position in range(len(closes) - 20, len(closes))
        ]
        realized_volatility = pstdev(daily_returns) * math.sqrt(252)
        exact_cross = bullish_cross or bearish_cross

        slope_score = min(1.0, abs(slope) / 0.04)
        relative_strength_score = max(
            0.0, min(1.0, relative_strength * direction_sign / 0.08)
        )
        volume_score = max(0.0, min(1.0, (volume_ratio - 0.8) / 0.8))
        rsi_score = max(0.0, min(1.0, (rsi_14[-1] - 50) * direction_sign / 20))
        conviction = (
            (0.45 if exact_cross else 0.15)
            + 0.20 * slope_score
            + 0.15 * relative_strength_score
            + 0.10 * volume_score
            + 0.10 * rsi_score
        )
        conviction = round(min(1.0, conviction), 4)
        liquidity_qualified = average_dollar_volume >= self.minimum_average_dollar_volume
        actionable = bool(
            exact_cross
            and direction != Direction.SIDEWAYS
            and market_aligned
            and liquidity_qualified
            and conviction >= self.minimum_conviction
        )
        liquidity_tier = (
            "very_high"
            if average_dollar_volume >= 5_000_000_000
            else "high"
            if average_dollar_volume >= 1_000_000_000
            else "qualified"
            if liquidity_qualified
            else "below_floor"
        )
        option_bias = (
            "call_debit_spread"
            if direction == Direction.BULLISH
            else "put_debit_spread"
            if direction == Direction.BEARISH
            else "no_trade"
        )
        return ScannerCandidate(
            rank=1,
            symbol=symbol,
            name=name,
            as_of=current.timestamp,
            pattern=pattern,
            direction=direction,
            option_bias=option_bias,
            conviction=conviction,
            actionable=actionable,
            current_price=round(current.close, 2),
            ema_18=round(ema_18[-1], 2),
            ema_50=round(ema_50[-1], 2),
            ema_18_slope_5d=round(slope, 4),
            rsi_14=round(rsi_14[-1], 1),
            volume_ratio=round(volume_ratio, 2),
            relative_strength_20d=round(relative_strength, 4),
            realized_volatility=round(realized_volatility, 4),
            average_dollar_volume=round(average_dollar_volume, 2),
            market_aligned=market_aligned,
            liquidity_tier=liquidity_tier,
            evidence=[
                f"Price {current.close:.2f} vs EMA(18) {ema_18[-1]:.2f}",
                f"EMA(18) five-session slope {slope:+.2%}",
                f"20-session relative strength vs SPY {relative_strength:+.2%}",
                f"Volume is {volume_ratio:.2f}x its 20-session average",
                "Option-chain liquidity is verified only after council approval",
            ],
        )
