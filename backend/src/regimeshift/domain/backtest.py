from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev

from regimeshift.domain.council import BEARISH_SWINGS, BULLISH_SWINGS, VotingCouncil
from regimeshift.domain.models import (
    AgentVerdict,
    Direction,
    PricePoint,
    Stance,
    StrategyName,
    SwingSignal,
)
from regimeshift.domain.regime import RegimeEngine
from regimeshift.domain.sector_rotation import SECTOR_UNIVERSE, SectorRotationEngine
from regimeshift.domain.swing import SwingEngine


@dataclass(frozen=True)
class BacktestParameters:
    swing_lookback: int
    holding_sessions: int
    vote_threshold: float
    signal_family: str = "both"
    max_volatility_percentile: float = 1.0


@dataclass(frozen=True)
class BacktestTrade:
    entry_index: int
    direction: Direction
    net_return: float


def _advocates(
    direction: Direction, regime_confidence: float, high_volatility: bool
) -> tuple[AgentVerdict, AgentVerdict]:
    bull_confidence = min(
        0.9,
        regime_confidence + (0.1 if direction == Direction.BULLISH else -0.14),
    )
    bear_confidence = 0.72 if high_volatility else 0.56
    return (
        AgentVerdict(
            agent="Bull",
            stance=Stance.SUPPORT,
            confidence=max(0.2, bull_confidence),
            summary="Historical bull-case proxy.",
            evidence=[],
        ),
        AgentVerdict(
            agent="Bear",
            stance=Stance.OPPOSE,
            confidence=bear_confidence,
            summary="Historical bear-case proxy.",
            evidence=[],
        ),
    )


def _metrics(trades: list[BacktestTrade], holding_sessions: int) -> dict[str, float | int]:
    if not trades:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "total_return": 0.0,
            "average_return": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
        }

    returns = [trade.net_return for trade in trades]
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for trade_return in returns:
        equity *= 1 + trade_return
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, (equity / peak) - 1)
    deviation = pstdev(returns)
    sharpe = 0.0 if deviation == 0 else mean(returns) / deviation * sqrt(252 / holding_sessions)
    return {
        "trades": len(trades),
        "win_rate": round(sum(value > 0 for value in returns) / len(returns), 4),
        "total_return": round(equity - 1, 4),
        "average_return": round(mean(returns), 4),
        "sharpe": round(sharpe, 3),
        "max_drawdown": round(max_drawdown, 4),
    }


class SwingVoteBacktester:
    """Walk-forward directional proxy test with no future data in signal generation."""

    warmup_sessions = 100
    friction = 0.0015

    def __init__(self) -> None:
        self.regime_engine = RegimeEngine()
        self.rotation_engine = SectorRotationEngine()
        self.council = VotingCouncil()

    def run(
        self,
        histories: dict[str, list[PricePoint]],
        parameters: BacktestParameters,
        signal_symbol: str = "SPY",
    ) -> list[BacktestTrade]:
        signal_symbol = signal_symbol.upper()
        required = {self.rotation_engine.benchmark_symbol, signal_symbol, *SECTOR_UNIVERSE}
        missing = sorted(required - histories.keys())
        if missing:
            raise ValueError(f"Backtest is missing history for: {', '.join(missing)}")

        benchmark = histories[self.rotation_engine.benchmark_symbol]
        by_date = {
            symbol: {point.timestamp.date(): point for point in points}
            for symbol, points in histories.items()
        }
        aligned_dates = [
            point.timestamp.date()
            for point in benchmark
            if all(point.timestamp.date() in by_date[symbol] for symbol in required)
        ]
        aligned = {
            symbol: [by_date[symbol][date] for date in aligned_dates]
            for symbol in required
        }
        signal_points = aligned[signal_symbol]
        swing_engine = SwingEngine(parameters.swing_lookback)
        trades: list[BacktestTrade] = []
        next_entry = self.warmup_sessions

        for index in range(
            self.warmup_sessions,
            len(signal_points) - parameters.holding_sessions,
        ):
            if index < next_entry:
                continue
            window = signal_points[: index + 1]
            regime = self.regime_engine.assess(window[-120:])
            swing = swing_engine.assess(window[-120:])
            if regime.metrics.volatility_percentile > parameters.max_volatility_percentile:
                continue
            if parameters.signal_family == "breakout" and swing.signal not in {
                SwingSignal.BULLISH_BREAKOUT,
                SwingSignal.BEARISH_BREAKDOWN,
            }:
                continue
            if parameters.signal_family == "reversal" and swing.signal not in {
                SwingSignal.BULLISH_REVERSAL,
                SwingSignal.BEARISH_REVERSAL,
            }:
                continue
            rotation = self.rotation_engine.assess(
                {symbol: points[: index + 1] for symbol, points in aligned.items()}
            )
            direction = self._candidate_direction(regime.direction, swing.signal)
            if direction == Direction.SIDEWAYS:
                continue

            strategy = (
                StrategyName.BULL_CALL_SPREAD
                if direction == Direction.BULLISH
                else StrategyName.BEAR_PUT_SPREAD
            )
            research = AgentVerdict(
                agent="Research",
                stance=Stance.NEUTRAL,
                confidence=0.35,
                summary="Historical news was unavailable and abstained.",
                evidence=[],
            )
            bull, bear = _advocates(
                regime.direction,
                regime.confidence,
                regime.volatility.value == "high",
            )
            decision = self.council.evaluate(
                strategy,
                regime,
                swing,
                rotation,
                research,
                bull,
                bear,
                threshold=parameters.vote_threshold,
            )
            if not decision.approved:
                continue

            raw_return = (
                signal_points[index + parameters.holding_sessions].close
                / signal_points[index].close
            ) - 1
            signed_return = raw_return if direction == Direction.BULLISH else -raw_return
            trades.append(
                BacktestTrade(
                    entry_index=index,
                    direction=direction,
                    net_return=signed_return - self.friction,
                )
            )
            next_entry = index + parameters.holding_sessions
        return trades

    def evaluate(
        self,
        histories: dict[str, list[PricePoint]],
        parameters: BacktestParameters,
        signal_symbol: str,
    ) -> dict[str, float | int]:
        return _metrics(
            self.run(histories, parameters, signal_symbol),
            parameters.holding_sessions,
        )

    def tune(self, histories: dict[str, list[PricePoint]]) -> dict[str, object]:
        benchmark_length = len(histories[self.rotation_engine.benchmark_symbol])
        split_index = int(benchmark_length * 0.7)
        candidates: list[tuple[BacktestParameters, list[BacktestTrade]]] = []
        for lookback in (10, 20, 30):
            for holding in (5, 10):
                for threshold in (0.52, 0.56):
                    for signal_family in ("breakout", "reversal"):
                        for max_volatility in (0.7, 1.0):
                            parameters = BacktestParameters(
                                lookback,
                                holding,
                                threshold,
                                signal_family,
                                max_volatility,
                            )
                            candidates.append((parameters, self.run(histories, parameters)))

        def rank(
            candidate: tuple[BacktestParameters, list[BacktestTrade]],
        ) -> tuple[float, float, int]:
            parameters, trades = candidate
            train = [trade for trade in trades if trade.entry_index < split_index]
            metrics = _metrics(train, parameters.holding_sessions)
            enough_trades = int(metrics["trades"]) >= 8
            return (
                float(metrics["sharpe"]) if enough_trades else -99.0,
                float(metrics["total_return"]),
                int(metrics["trades"]),
            )

        parameters, trades = max(candidates, key=rank)
        train = [trade for trade in trades if trade.entry_index < split_index]
        validation = [trade for trade in trades if trade.entry_index >= split_index]
        validation_metrics = _metrics(validation, parameters.holding_sessions)
        passed = (
            int(validation_metrics["trades"]) >= 3
            and float(validation_metrics["average_return"]) > 0
            and float(validation_metrics["total_return"]) > 0
            and float(validation_metrics["max_drawdown"]) >= -0.12
        )
        return {
            "methodology": (
                "70/30 chronological train/holdout; non-overlapping trades; "
                "15 bps proxy friction"
            ),
            "instrument": "SPY directional proxy for XSP/SPXW defined-risk spreads",
            "parameters": {
                "swing_lookback": parameters.swing_lookback,
                "holding_sessions": parameters.holding_sessions,
                "vote_threshold": parameters.vote_threshold,
                "signal_family": parameters.signal_family,
                "max_volatility_percentile": parameters.max_volatility_percentile,
            },
            "train": _metrics(train, parameters.holding_sessions),
            "holdout": validation_metrics,
            "production_gate_passed": passed,
            "limitations": [
                "Measures signal direction, not historical option-spread fills.",
                "Index-level market data is unavailable, so SPY proxies XSP/SPXW.",
                "Past paper-proxy performance does not predict future results.",
            ],
        }

    @staticmethod
    def _candidate_direction(regime: Direction, swing: SwingSignal) -> Direction:
        if swing in BULLISH_SWINGS and regime != Direction.BEARISH:
            return Direction.BULLISH
        if swing in BEARISH_SWINGS and regime != Direction.BULLISH:
            return Direction.BEARISH
        return Direction.SIDEWAYS
