from collections import defaultdict
from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev

from regimeshift.domain.models import Direction, PricePoint
from regimeshift.domain.scanner import (
    LARGE_CAP_UNIVERSE,
    LargeCapScanner,
    exponential_moving_average,
    relative_strength_index,
)


@dataclass(frozen=True)
class ScannerBacktestTrade:
    signal_date: object
    symbol: str
    direction: Direction
    conviction: float
    net_return: float


def _metrics(trades: list[ScannerBacktestTrade], holding_sessions: int) -> dict[str, object]:
    if not trades:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "total_return": 0.0,
            "average_return": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "calls": 0,
            "puts": 0,
        }
    returns = [trade.net_return for trade in trades]
    equity = 1.0
    peak = 1.0
    maximum_drawdown = 0.0
    for value in returns:
        equity *= 1 + value
        peak = max(peak, equity)
        maximum_drawdown = min(maximum_drawdown, equity / peak - 1)
    deviation = pstdev(returns)
    sharpe = 0.0 if deviation == 0 else mean(returns) / deviation * sqrt(252 / holding_sessions)
    return {
        "trades": len(trades),
        "win_rate": round(sum(value > 0 for value in returns) / len(returns), 4),
        "total_return": round(equity - 1, 4),
        "average_return": round(mean(returns), 4),
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(maximum_drawdown, 4),
        "calls": sum(trade.direction == Direction.BULLISH for trade in trades),
        "puts": sum(trade.direction == Direction.BEARISH for trade in trades),
    }


class ScannerBacktester:
    """Fixed-rule chronological validation for the large-cap 18 EMA scanner."""

    holding_sessions = 3
    friction = 0.002

    def __init__(self) -> None:
        self.scanner = LargeCapScanner()

    def evaluate(self, histories: dict[str, list[PricePoint]]) -> dict[str, object]:
        benchmark = histories.get(self.scanner.benchmark_symbol, [])
        if len(benchmark) < 100:
            raise ValueError("Scanner backtest requires at least 100 SPY sessions")
        benchmark_by_date = {
            point.timestamp.date(): index for index, point in enumerate(benchmark)
        }
        benchmark_closes = [point.close for point in benchmark]
        benchmark_ema_50 = exponential_moving_average(
            benchmark_closes, self.scanner.trend_period
        )
        candidates_by_date: dict[object, list[tuple[float, str, Direction, int]]] = (
            defaultdict(list)
        )

        for symbol in LARGE_CAP_UNIVERSE:
            points = histories.get(symbol, [])
            if len(points) < 100:
                continue
            closes = [point.close for point in points]
            ema_18 = exponential_moving_average(closes, self.scanner.ema_period)
            ema_50 = exponential_moving_average(closes, self.scanner.trend_period)
            rsi_14 = relative_strength_index(closes)
            for index in range(60, len(points) - self.holding_sessions):
                signal_date = points[index].timestamp.date()
                old_date = points[index - 20].timestamp.date()
                benchmark_index = benchmark_by_date.get(signal_date)
                old_benchmark_index = benchmark_by_date.get(old_date)
                if (
                    benchmark_index is None
                    or old_benchmark_index is None
                    or benchmark_index < 55
                ):
                    continue

                bullish = (
                    closes[index - 1] <= ema_18[index - 1]
                    and closes[index] > ema_18[index]
                    and ema_18[index] > ema_50[index]
                    and ema_18[index] > ema_18[index - 5]
                )
                bearish = (
                    closes[index - 1] >= ema_18[index - 1]
                    and closes[index] < ema_18[index]
                    and ema_18[index] < ema_50[index]
                    and ema_18[index] < ema_18[index - 5]
                )
                direction = (
                    Direction.BULLISH
                    if bullish
                    else Direction.BEARISH
                    if bearish
                    else Direction.SIDEWAYS
                )
                if direction == Direction.SIDEWAYS:
                    continue

                market_aligned = (
                    direction == Direction.BULLISH
                    and benchmark_closes[benchmark_index] > benchmark_ema_50[benchmark_index]
                    and benchmark_ema_50[benchmark_index]
                    > benchmark_ema_50[benchmark_index - 5]
                ) or (
                    direction == Direction.BEARISH
                    and benchmark_closes[benchmark_index] < benchmark_ema_50[benchmark_index]
                    and benchmark_ema_50[benchmark_index]
                    < benchmark_ema_50[benchmark_index - 5]
                )
                if not market_aligned:
                    continue

                average_volume = mean(
                    point.volume for point in points[index - 20 : index]
                )
                average_dollar_volume = mean(
                    point.close * point.volume for point in points[index - 20 : index]
                )
                if average_dollar_volume < self.scanner.minimum_average_dollar_volume:
                    continue
                direction_sign = 1 if direction == Direction.BULLISH else -1
                volume_ratio = points[index].volume / max(1, average_volume)
                relative_strength = (closes[index] / closes[index - 20] - 1) - (
                    benchmark_closes[benchmark_index]
                    / benchmark_closes[old_benchmark_index]
                    - 1
                )
                slope = ema_18[index] / ema_18[index - 5] - 1
                conviction = (
                    0.45
                    + 0.20 * min(1.0, abs(slope) / 0.04)
                    + 0.15
                    * max(0.0, min(1.0, relative_strength * direction_sign / 0.08))
                    + 0.10 * max(0.0, min(1.0, (volume_ratio - 0.8) / 0.8))
                    + 0.10
                    * max(
                        0.0,
                        min(1.0, (rsi_14[index] - 50) * direction_sign / 20),
                    )
                )
                if conviction >= self.scanner.minimum_conviction:
                    candidates_by_date[signal_date].append(
                        (conviction, symbol, direction, index)
                    )

        trades: list[ScannerBacktestTrade] = []
        next_entry_date = None
        for signal_date in sorted(candidates_by_date):
            if next_entry_date is not None and signal_date < next_entry_date:
                continue
            conviction, symbol, direction, index = max(candidates_by_date[signal_date])
            points = histories[symbol]
            entry_price = points[index + 1].open or points[index + 1].close
            exit_price = points[index + self.holding_sessions].close
            direction_sign = 1 if direction == Direction.BULLISH else -1
            net_return = direction_sign * (exit_price / entry_price - 1) - self.friction
            trades.append(
                ScannerBacktestTrade(
                    signal_date=signal_date,
                    symbol=symbol,
                    direction=direction,
                    conviction=conviction,
                    net_return=net_return,
                )
            )
            next_entry_date = points[index + self.holding_sessions].timestamp.date()

        split_date = benchmark[int(len(benchmark) * 0.7)].timestamp.date()
        train = [trade for trade in trades if trade.signal_date < split_date]
        holdout = [trade for trade in trades if trade.signal_date >= split_date]
        holdout_metrics = _metrics(holdout, self.holding_sessions)
        passed = (
            int(holdout_metrics["trades"]) >= 10
            and float(holdout_metrics["average_return"]) > 0
            and float(holdout_metrics["total_return"]) > 0
            and float(holdout_metrics["max_drawdown"]) >= -0.30
        )
        return {
            "methodology": (
                "Fixed 18 EMA price-cross rule; next-session open entry; one top-ranked "
                "portfolio candidate at a time; 70/30 chronological split; 20 bps friction"
            ),
            "parameters": {
                "ema_period": self.scanner.ema_period,
                "trend_ema_period": self.scanner.trend_period,
                "minimum_conviction": self.scanner.minimum_conviction,
                "minimum_average_dollar_volume": (
                    self.scanner.minimum_average_dollar_volume
                ),
                "holding_sessions": self.holding_sessions,
            },
            "universe_size": len(LARGE_CAP_UNIVERSE),
            "split_date": split_date.isoformat(),
            "train": _metrics(train, self.holding_sessions),
            "holdout": holdout_metrics,
            "production_gate_passed": passed,
            "limitations": [
                "Measures underlying direction, not historical option-spread fills.",
                "Average dollar volume is a first-stage proxy; live option quotes and "
                "open interest must pass before execution.",
                "A moving average is lagging and can whipsaw in range-bound markets.",
                "Past paper-proxy performance does not predict future results.",
            ],
        }
