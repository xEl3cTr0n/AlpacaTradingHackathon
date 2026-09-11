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
    directional_efficiency_20d: float
    volatility_expansion_ratio: float
    average_gap_pct_20d: float
    future_return_pct: float
    future_max_gap_pct: float


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
        (item.realized_move_pct - item.expected_move_pct) ** 2 for item in observations
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


def _cohort_metrics(observations: list[MoveObservation]) -> dict[str, object]:
    if not observations:
        return {
            "observations": 0,
            "terminal_coverage": 0.0,
            "path_coverage": 0.0,
            "mean_realized_move_pct": 0.0,
            "mean_future_max_gap_pct": 0.0,
        }
    count = len(observations)
    return {
        "observations": count,
        "terminal_coverage": round(sum(item.terminal_covered for item in observations) / count, 4),
        "path_coverage": round(sum(item.path_covered for item in observations) / count, 4),
        "mean_realized_move_pct": round(mean(item.realized_move_pct for item in observations), 4),
        "mean_future_max_gap_pct": round(mean(item.future_max_gap_pct for item in observations), 4),
    }


def _directional_cohort(observations: list[MoveObservation]) -> dict[str, object]:
    directional = [item for item in observations if item.directional_efficiency_20d != 0]
    if not directional:
        return {
            "observations": 0,
            "directional_hit_rate": 0.0,
            "mean_signed_return_pct": 0.0,
            "mean_absolute_return_pct": 0.0,
        }
    signed_returns = [
        item.future_return_pct * (1 if item.directional_efficiency_20d > 0 else -1)
        for item in directional
    ]
    return {
        "observations": len(directional),
        "directional_hit_rate": round(
            sum(value > 0 for value in signed_returns) / len(signed_returns), 4
        ),
        "mean_signed_return_pct": round(mean(signed_returns), 4),
        "mean_absolute_return_pct": round(
            mean(abs(item.future_return_pct) for item in directional), 4
        ),
    }


def _indicator_research(observations: list[MoveObservation]) -> dict[str, object]:
    high_efficiency = [
        item for item in observations if abs(item.directional_efficiency_20d) >= 0.25
    ]
    weak_efficiency = [item for item in observations if abs(item.directional_efficiency_20d) < 0.25]
    expanded = [item for item in observations if item.volatility_expansion_ratio >= 1.20]
    normal_volatility = [
        item for item in observations if 0.80 < item.volatility_expansion_ratio < 1.20
    ]
    compressed = [item for item in observations if item.volatility_expansion_ratio <= 0.80]
    elevated_gap = [item for item in observations if item.average_gap_pct_20d >= 0.015]
    ordinary_gap = [item for item in observations if item.average_gap_pct_20d < 0.015]

    high_efficiency_metrics = _directional_cohort(high_efficiency)
    weak_efficiency_metrics = _directional_cohort(weak_efficiency)
    expanded_metrics = _cohort_metrics(expanded)
    compressed_metrics = _cohort_metrics(compressed)
    elevated_gap_metrics = _cohort_metrics(elevated_gap)
    ordinary_gap_metrics = _cohort_metrics(ordinary_gap)

    efficiency_gate = (
        int(high_efficiency_metrics["observations"]) >= 200
        and float(high_efficiency_metrics["directional_hit_rate"]) >= 0.52
        and float(high_efficiency_metrics["mean_signed_return_pct"]) > 0
    )
    expansion_gate = (
        int(expanded_metrics["observations"]) >= 100
        and int(compressed_metrics["observations"]) >= 100
        and float(expanded_metrics["mean_realized_move_pct"])
        > float(compressed_metrics["mean_realized_move_pct"])
    )
    gap_gate = (
        int(elevated_gap_metrics["observations"]) >= 50
        and int(ordinary_gap_metrics["observations"]) >= 500
        and float(elevated_gap_metrics["mean_future_max_gap_pct"])
        > float(ordinary_gap_metrics["mean_future_max_gap_pct"]) * 1.15
    )
    return {
        "thresholds": {
            "high_directional_efficiency": 0.25,
            "expanded_volatility_ratio": 1.20,
            "compressed_volatility_ratio": 0.80,
            "elevated_average_gap_pct": 0.015,
        },
        "directional_efficiency": {
            "high": high_efficiency_metrics,
            "weak_or_choppy": weak_efficiency_metrics,
            "research_gate_passed": efficiency_gate,
        },
        "volatility_expansion": {
            "expanded": expanded_metrics,
            "normal": _cohort_metrics(normal_volatility),
            "compressed": compressed_metrics,
            "research_gate_passed": expansion_gate,
        },
        "overnight_gap_risk": {
            "elevated": elevated_gap_metrics,
            "ordinary": ordinary_gap_metrics,
            "research_gate_passed": gap_gate,
        },
        "promotion_gate_passed": efficiency_gate and expansion_gate and gap_gate,
        "execution_eligible": False,
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
                prior_closes = [current.close, *(point.close for point in future[:-1])]
                future_gaps = [
                    abs(point.open / previous_close - 1)
                    for point, previous_close in zip(future, prior_closes, strict=True)
                    if point.open is not None and previous_close
                ]
                observations.append(
                    MoveObservation(
                        signal_date=current.timestamp.date(),
                        symbol=symbol,
                        expected_move_pct=thesis.expected_move_pct,
                        realized_move_pct=abs(final / spot - 1),
                        terminal_covered=thesis.lower_bound <= final <= thesis.upper_bound,
                        path_covered=(
                            future_low >= thesis.lower_bound and future_high <= thesis.upper_bound
                        ),
                        upper_breached=future_high > thesis.upper_bound,
                        lower_breached=future_low < thesis.lower_bound,
                        directional_efficiency_20d=(thesis.directional_efficiency_20d),
                        volatility_expansion_ratio=(thesis.volatility_expansion_ratio),
                        average_gap_pct_20d=thesis.average_gap_pct_20d,
                        future_return_pct=final / spot - 1,
                        future_max_gap_pct=max(future_gaps, default=0.0),
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
            "indicator_research": {
                "train": _indicator_research(train),
                "holdout": _indicator_research(holdout),
            },
            "calibration_gate_passed": calibration_gate_passed,
            "execution_eligible": False,
            "limitations": [
                "Validates an underlying statistical range, not an options-implied move.",
                "Cross-sectional observations share market regimes and are not independent.",
                "Corporate events are not separated from ordinary sessions.",
                "The range remains display-only; it cannot authorize paper execution.",
                "Indicator cohorts are observational research and do not change scanner "
                "conviction, council votes, risk approval, or order eligibility.",
                "Past calibration does not predict future coverage.",
            ],
        }
