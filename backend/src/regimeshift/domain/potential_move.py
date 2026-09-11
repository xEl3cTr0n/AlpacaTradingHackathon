import math
from statistics import mean, pstdev

from regimeshift.domain.models import Direction, PotentialMoveThesis, PricePoint


def _true_range(current: PricePoint, previous_close: float) -> float:
    high = current.high if current.high is not None else current.close
    low = current.low if current.low is not None else current.close
    return max(high - low, abs(high - previous_close), abs(low - previous_close))


def build_potential_move_thesis(
    points: list[PricePoint],
    *,
    spot: float,
    direction: Direction,
    conviction: float,
    ema_18: float,
    rsi_14: float,
    relative_strength: float,
    volume_ratio: float,
    market_aligned: bool,
    horizon_sessions: int = 5,
) -> PotentialMoveThesis:
    """Estimate move magnitude independently from directional conviction.

    This uses completed daily bars only. It deliberately does not pretend that
    historical range is an options-implied move; IV/GEX remain council inputs.
    """
    if len(points) < 21:
        raise ValueError("Potential-move estimate requires at least 21 daily bars")

    recent = points[-21:]
    true_ranges = [
        _true_range(recent[index], recent[index - 1].close)
        for index in range(1, len(recent))
    ]
    atr_14 = mean(true_ranges[-14:])
    returns = [
        recent[index].close / recent[index - 1].close - 1
        for index in range(1, len(recent))
    ]
    daily_volatility = pstdev(returns)
    atr_move = atr_14 * math.sqrt(horizon_sessions)
    realized_vol_move = spot * daily_volatility * math.sqrt(horizon_sessions)
    expected_move = max(atr_move, realized_vol_move)
    expected_move_pct = expected_move / spot

    smaller = min(atr_move, realized_vol_move)
    larger = max(atr_move, realized_vol_move)
    estimator_agreement = smaller / larger if larger else 1.0
    move_confidence = min(1.0, 0.55 + 0.30 * estimator_agreement + 0.15 * min(1, len(points) / 120))

    direction_sign = 1 if direction == Direction.BULLISH else -1 if direction == Direction.BEARISH else 0
    direction_score = direction_sign * conviction * 100
    lower_bound = max(0.01, spot - expected_move)
    upper_bound = spot + expected_move

    supporting: list[str] = []
    conflicting: list[str] = []
    if direction == Direction.SIDEWAYS:
        conflicting.append("18/50 EMA trend has no directional agreement")
    else:
        supporting.append(f"18 EMA trend supports {direction.value} direction")
    if market_aligned:
        supporting.append("SPY trend agrees with the symbol direction")
    else:
        conflicting.append("SPY trend does not confirm the symbol direction")
    if relative_strength * direction_sign > 0:
        supporting.append(f"Relative strength vs SPY confirms ({relative_strength:+.1%})")
    elif direction_sign:
        conflicting.append(f"Relative strength vs SPY disagrees ({relative_strength:+.1%})")
    if volume_ratio >= 1:
        supporting.append(f"Volume confirms at {volume_ratio:.2f}x average")
    else:
        conflicting.append(f"Volume is light at {volume_ratio:.2f}x average")
    if direction == Direction.BULLISH and rsi_14 >= 70:
        conflicting.append(f"RSI {rsi_14:.1f} is extended for a bullish entry")
    elif direction == Direction.BEARISH and rsi_14 <= 30:
        conflicting.append(f"RSI {rsi_14:.1f} is extended for a bearish entry")
    elif direction_sign:
        supporting.append(f"RSI {rsi_14:.1f} is not at the directional exhaustion gate")

    if direction == Direction.BULLISH:
        trigger = f"Hold above EMA(18) ${ema_18:.2f} with volume at or above average"
        target = f"${upper_bound:.2f} five-session statistical objective"
        invalidation = f"Close below EMA(18) ${ema_18:.2f} or thesis conflict increases"
    elif direction == Direction.BEARISH:
        trigger = f"Hold below EMA(18) ${ema_18:.2f} with volume at or above average"
        target = f"${lower_bound:.2f} five-session statistical objective"
        invalidation = f"Close above EMA(18) ${ema_18:.2f} or thesis conflict increases"
    else:
        trigger = f"Wait for a confirmed break away from EMA(18) ${ema_18:.2f}"
        target = f"Range ${lower_bound:.2f}–${upper_bound:.2f}"
        invalidation = "No directional thesis exists until trend and crossover agree"

    return PotentialMoveThesis(
        horizon_sessions=horizon_sessions,
        expected_move_dollars=round(expected_move, 2),
        expected_move_pct=round(expected_move_pct, 4),
        lower_bound=round(lower_bound, 2),
        upper_bound=round(upper_bound, 2),
        atr_14=round(atr_14, 2),
        realized_vol_move_pct=round(realized_vol_move / spot, 4),
        direction_score=round(direction_score, 1),
        move_confidence=round(move_confidence, 4),
        trigger=trigger,
        target=target,
        invalidation=invalidation,
        basis="Completed Alpaca daily bars: max of ATR(14) and realized-volatility range; not an options-implied move",
        supporting_evidence=supporting,
        conflicting_evidence=conflicting,
    )
