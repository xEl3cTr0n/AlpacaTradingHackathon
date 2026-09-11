from dataclasses import dataclass
from math import sqrt
from statistics import mean, median

from regimeshift.domain.models import Direction, PricePoint
from regimeshift.domain.potential_move import build_potential_move_thesis


@dataclass(frozen=True)
class MoveObservation:
    signal_date: object
    symbol: str
    expected_move_pct: float
    realized_move_pct: float
    terminal_covered: bool
    path_covered: bool
    upper_breached: bool
    lower_breached: bool


def _metrics(observations: list[MoveObservation]) -> dict[str, object]:
    if not observations:
        return {
            "observations": 0,
            "terminal_coverage": 0.0,
            "path_coverage": 0.0,
            "mean_expected_move_pct": 0.0,
            "mean_realized_move_pct": 0.0,
            "median_realized_to_expected": 0.0,
            "upper_breach_rate": 0.0,
            "lower_breach_rate": 0.0,
            "range_rmse_pct": 0.0,
        }
    ratios = [
        item.realized_move_pct / item.expected_move_pct
        for item in observations
        if item.expected_move_pct > 0
    ]
    squared_errors = [
        (item.realized_move_pct - item.expected_move_pct) ** 2
        for item in observations
    ]
    count = len(observations)
    return {
        "observations": count,
        "terminal_coverage": round(sum(item.terminal_covered for item in observations) / count, 4),
        "path_coverage": round(sum(item.path_covered for item in observations) / count, 4),
        "mean_expected_move_pct": round(mean(item.expected_move_pct for item in observations), 4),
        "mean_realized_move_pct": round(mean(item.realized_move_pct for item in observations), 4),
        "median_realized_to_expected": round(median(ratios), 4),
        "upper_breach_rate": round(sum(item.upper_breached for item in observations) / count, 4),
        "lower_breach_rate": round(sum(item.lower_breached for item in observations) / count, 4),
        "range_rmse_pct": round(sqrt(mean(squared_errors)), 4),
    }


class PotentialMoveBacktester:
    """Walk-forward calibration for the historical five-session range."""

    horizon_sessions = 5
    warmup_sessions = 60

    def evaluate(self, histories: dict[str, list[PricePoint]]) -> dict[str, object]:
        benchmark = histories.get("SPY", [])
        if len(benchmark) < 100:
            raise ValueError("Potential-move backtest requires at least 100 SPY sessions")
        split_date = benchmark[int(len(benchmark) * 0.7)].timestamp.date()
        observations: list[MoveObservation] = []

        for symbol, points in histories.items():
            if len(points) < self.warmup_sessions + self.horizon_sessions:
                continue
            for index in range(
                self.warmup_sessions,
                len(points) - self.horizon_sessions,
                self.horizon_sessions,
            ):
                current = points[index]
                spot = current.close
                thesis = build_potential_move_thesis(
                    points[: index + 1],
                    spot=spot,
                    direction=Direction.SIDEWAYS,
                    conviction=0,
                    ema_18=spot,
                    rsi_14=50,
                    relative_strength=0,
                    volume_ratio=1,
                    market_aligned=False,
                    horizon_sessions=self.horizon_sessions,
                )
                future = points[index + 1 : index + self.horizon_sessions + 1]
                final = future[-1].close
                future_high = max(
                    point.high if point.high is not None else point.close for point in future
                )
                future_low = min(
                    point.low if point.low is not None else point.close for point in future
                )
                observations.append(
                    MoveObservation(
                        signal_date=current.timestamp.date(),
                        symbol=symbol,
                        expected_move_pct=thesis.expected_move_pct,
                        realized_move_pct=abs(final / spot - 1),
                        terminal_covered=thesis.lower_bound <= final <= thesis.upper_bound,
                        path_covered=(
                            future_low >= thesis.lower_bound
                            and future_high <= thesis.upper_bound
                        ),
                        upper_breached=future_high > thesis.upper_bound,
                        lower_breached=future_low < thesis.lower_bound,
                    )
                )

        train = [item for item in observations if item.signal_date < split_date]
        holdout = [item for item in observations if item.signal_date >= split_date]
        holdout_metrics = _metrics(holdout)
        calibration_gate_passed = (
            int(holdout_metrics["observations"]) >= 1_000
            and 0.65 <= float(holdout_metrics["terminal_coverage"]) <= 0.95
            and float(holdout_metrics["path_coverage"]) >= 0.45
            and 0.35 <= float(holdout_metrics["median_realized_to_expected"]) <= 1.0
        )
        return {
            "methodology": (
                "Walk-forward non-overlapping five-session windows; estimate uses only bars "
                "available at each close; 70/30 chronological train/holdout split"
            ),
            "parameters": {
                "horizon_sessions": self.horizon_sessions,
                "warmup_sessions": self.warmup_sessions,
                "range_estimator": "max(ATR(14) × sqrt(5), daily realized volatility × sqrt(5))",
            },
            "split_date": split_date.isoformat(),
            "train": _metrics(train),
            "holdout": holdout_metrics,
            "calibration_gate_passed": calibration_gate_passed,
            "execution_eligible": False,
            "limitations": [
                "Validates an underlying statistical range, not an options-implied move.",
                "Cross-sectional observations share market regimes and are not independent.",
                "Corporate events are not separated from ordinary sessions.",
                "The range remains display-only; it cannot authorize paper execution.",
                "Past calibration does not predict future coverage.",
            ],
        }
