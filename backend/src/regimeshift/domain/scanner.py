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
    """Ranks liquid large caps using daily or intraday 18 EMA crosses."""

    benchmark_symbol = "SPY"
    ema_period = 18
    trend_period = 50
    minimum_conviction = 0.60
    exploration_conviction = 0.55
    exploration_risk_cap = 500.0
    production_risk_cap = 1_000.0
    minimum_average_dollar_volume = 100_000_000
    interval_minutes = 15

    def scan(
        self,
        histories: dict[str, list[PricePoint]],
        *,
        limit: int = 12,
        source: str = "market data",
        timeframe: str = "1Day",
        liquidity_histories: dict[str, list[PricePoint]] | None = None,
        annualization_periods: int = 252,
    ) -> ScannerSnapshot:
        benchmark = histories.get(self.benchmark_symbol, [])
        if len(benchmark) < 60:
            raise ValueError("Scanner requires at least 60 SPY sessions")

        candidates: list[ScannerCandidate] = []
        for symbol, name in LARGE_CAP_UNIVERSE.items():
            points = histories.get(symbol, [])
            if len(points) < 60:
                continue
            candidate = None
            newest_candidate = None
            detection_bars = 4 if timeframe == "15Min" else 1
            for index in range(len(points) - 1, max(59, len(points) - detection_bars - 1), -1):
                scored = self.score(
                    symbol,
                    name,
                    points,
                    benchmark,
                    index,
                    liquidity_points=(liquidity_histories or histories).get(symbol),
                    trend_points=(liquidity_histories or {}).get(symbol),
                    benchmark_trend_points=(liquidity_histories or {}).get(
                        self.benchmark_symbol
                    ),
                    annualization_periods=annualization_periods,
                )
                newest_candidate = newest_candidate or scored
                if scored is not None and scored.actionable:
                    candidate = scored
                    break
            candidate = candidate or newest_candidate
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
            timeframe=timeframe,
            universe_size=len(LARGE_CAP_UNIVERSE),
            scanned_count=len(candidates),
            actionable_count=sum(candidate.actionable for candidate in candidates),
            minimum_conviction=self.minimum_conviction,
            ema_period=self.ema_period,
            methodology=(
                "15-minute 18 EMA crossover and 18/50 trend alignment, confirmed by SPY; "
                "the latest four completed bars are checked to tolerate worker delay. "
                "Daily $100M average dollar volume is the first liquidity gate; contract "
                "quotes and open interest are checked before execution. Production starts "
                "at 60% conviction. The 55–60% exploration tier uses a $500 half-size cap."
                if timeframe == "15Min"
                else "Two-stage liquidity screen: large-cap universe and $100M 20-session "
                "average dollar volume, followed by contract bid/ask and open-interest "
                "checks before execution. Production signals require a price/18 EMA cross, "
                "trend and SPY confirmation, and 60% conviction; 55–60% exploration "
                "signals use a $500 half-size cap."
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
        *,
        liquidity_points: list[PricePoint] | None = None,
        trend_points: list[PricePoint] | None = None,
        benchmark_trend_points: list[PricePoint] | None = None,
        annualization_periods: int = 252,
    ) -> ScannerCandidate | None:
        if index < 60 or index >= len(points):
            return None
        closes = [point.close for point in points[: index + 1]]
        ema_18 = exponential_moving_average(closes, self.ema_period)
        ema_50 = exponential_moving_average(closes, self.trend_period)
        rsi_14 = relative_strength_index(closes)
        current = points[index]

        benchmark_by_timestamp = {
            point.timestamp: position for position, point in enumerate(benchmark)
        }
        benchmark_index = benchmark_by_timestamp.get(current.timestamp)
        historical_benchmark_index = benchmark_by_timestamp.get(
            points[index - 20].timestamp
        )
        if benchmark_index is None or historical_benchmark_index is None:
            return None
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
        if trend_points and benchmark_trend_points:
            available_trend = [
                point for point in trend_points if point.timestamp.date() < current.timestamp.date()
            ]
            available_benchmark_trend = [
                point
                for point in benchmark_trend_points
                if point.timestamp.date() < current.timestamp.date()
            ]
            if len(available_trend) < 55 or len(available_benchmark_trend) < 55:
                return None
            trend_closes = [point.close for point in available_trend]
            trend_18 = exponential_moving_average(trend_closes, self.ema_period)
            trend_50 = exponential_moving_average(trend_closes, self.trend_period)
            daily_benchmark_closes = [point.close for point in available_benchmark_trend]
            daily_benchmark_50 = exponential_moving_average(
                daily_benchmark_closes, self.trend_period
            )
            bullish_trend = trend_18[-1] > trend_50[-1] and trend_18[-1] > trend_18[-6]
            bearish_trend = trend_18[-1] < trend_50[-1] and trend_18[-1] < trend_18[-6]
            benchmark_bullish = (
                daily_benchmark_closes[-1] > daily_benchmark_50[-1]
                and daily_benchmark_50[-1] > daily_benchmark_50[-6]
            )
            benchmark_bearish = (
                daily_benchmark_closes[-1] < daily_benchmark_50[-1]
                and daily_benchmark_50[-1] < daily_benchmark_50[-6]
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
        liquidity_points = liquidity_points or points
        completed_liquidity = [
            point
            for point in liquidity_points
            if point.timestamp.date() < current.timestamp.date()
        ]
        if completed_liquidity:
            liquidity_points = completed_liquidity
        if len(liquidity_points) < 20:
            return None
        average_dollar_volume = mean(
            point.close * point.volume for point in liquidity_points[-20:]
        )
        volume_ratio = current.volume / max(1, average_volume)
        benchmark_current = benchmark[benchmark_index].close
        benchmark_old = benchmark[historical_benchmark_index].close
        relative_strength = (closes[-1] / closes[-21] - 1) - (
            benchmark_current / benchmark_old - 1
        )
        slope = ema_18[-1] / ema_18[-6] - 1
        daily_returns = [
            closes[position] / closes[position - 1] - 1
            for position in range(len(closes) - 20, len(closes))
        ]
        realized_volatility = pstdev(daily_returns) * math.sqrt(annualization_periods)
        # A cross is actionable only when it agrees with the higher-timeframe
        # trend.  The old unqualified OR could mark a bearish cross inside a
        # bullish trend (or vice versa) as an actionable signal.
        exact_cross = (
            direction == Direction.BULLISH and bullish_cross
        ) or (
            direction == Direction.BEARISH and bearish_cross
        )

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
        qualified_signal = bool(
            exact_cross
            and direction != Direction.SIDEWAYS
            and market_aligned
            and liquidity_qualified
            and conviction >= self.exploration_conviction
        )
        signal_tier = (
            "production"
            if qualified_signal and conviction >= self.minimum_conviction
            else "exploration"
            if qualified_signal
            else "watch"
        )
        actionable = signal_tier != "watch"
        risk_cap_dollars = (
            self.exploration_risk_cap
            if signal_tier == "exploration"
            else self.production_risk_cap
            if signal_tier == "production"
            else 0.0
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
            signal_tier=signal_tier,
            risk_cap_dollars=risk_cap_dollars,
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
