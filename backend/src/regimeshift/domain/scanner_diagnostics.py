"""Read-only R-Factor, CHOP and future breakout plans; never execution gates."""

import math
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from statistics import mean
from zoneinfo import ZoneInfo

from regimeshift.domain.models import (
    ChopReading,
    PricePoint,
    RFactorReading,
    ScannerDiagnostics,
    UnderlyingTradePlan,
)
from regimeshift.domain.volume_rsi import volume_rsi_series

NEW_YORK = ZoneInfo("America/New_York")


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def valid_ohlc(point: PricePoint) -> bool:
    values = (point.open, point.high, point.low, point.close)
    return (
        all(v is not None and math.isfinite(v) and v > 0 for v in values)
        and point.low <= min(point.open, point.close) <= max(point.open, point.close) <= point.high
        and point.volume >= 0
    )


def r_factor(points: list[PricePoint], *, provisional: bool = False) -> RFactorReading | None:
    """Exact supplied DAY equation. Current bar participates in Average(volume,14).

    RVOL is deliberately uncapped. The final ThinkScript plot is a boolean; expose
    its rounded numeric input as well. Bearish <-150 is our explicit extension.
    Invalid/missing OHLC fails unavailable rather than creating a false signal.
    """
    if len(points) < 14 or not all(valid_ohlc(p) for p in points[-14:]):
        return None
    p = points[-1]
    avg_volume = mean(p.volume for p in points[-14:])
    relative_volume = p.volume / avg_volume if avg_volume > 0 else 1.0
    green = p.close >= p.open
    directional_volume = relative_volume if green else -relative_volume
    open_change = (p.close - p.open) / p.open * 100
    momentum = (p.close - (p.low if green else p.high)) / p.open * 100
    typical = (p.high + p.low + p.close) / 3
    distance = (p.close - typical) / typical * 100
    raw = 100 * (0.5 * directional_volume + 0.25 * open_change + 0.15 * momentum + 0.1 * distance)
    score = float(Decimal(str(raw)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    return RFactorReading(
        as_of=p.timestamp,
        provisional=provisional,
        score=score,
        relative_volume=relative_volume,
        directional_volume=directional_volume,
        open_change_pct=open_change,
        momentum_pct=momentum,
        typical_price_distance_pct=distance,
        bullish_match=score > 150,
        bearish_match=score < -150,
    )


def true_ranges(points: list[PricePoint], period: int = 14) -> list[float]:
    if len(points) < period + 1 or not all(valid_ohlc(p) for p in points[-period - 1 :]):
        return []
    return [
        max(p.high - p.low, abs(p.high - previous.close), abs(p.low - previous.close))
        for previous, p in zip(points[-period - 1 : -1], points[-period:], strict=True)
    ]


def choppiness(points: list[PricePoint], timeframe: str = "1Day") -> ChopReading:
    result = ChopReading(as_of=points[-1].timestamp if points else None, timeframe=timeframe)
    ranges = true_ranges(points)
    if not ranges:
        return result
    width = max(p.high for p in points[-14:]) - min(p.low for p in points[-14:])
    # Flat tape is maximally choppy; bound occasional window-edge gap effects.
    value = 100.0 if width == 0 else 100 * math.log10(sum(ranges) / width) / math.log10(14)
    value = min(100.0, max(0.0, value))
    return result.model_copy(
        update={
            "value": value,
            "state": "chop" if value > 61.8 else "trend" if value < 38.2 else "transition",
        }
    )


def breakout_plans(
    points: list[PricePoint],
    chop: ChopReading,
    *,
    stale: bool = False,
) -> list[UnderlyingTradePlan]:
    """Levels fixed after the latest completed bar; eligible only on later bars."""
    if len(points) < 20 or not all(valid_ohlc(p) for p in points[-20:]):
        return []
    ranges = true_ranges(points)
    atr = mean(ranges) if ranges else 0.0
    if atr <= 0 or chop.value is None:
        return []
    high = max(p.high for p in points[-20:])
    low = min(p.low for p in points[-20:])
    state = "stale" if stale else "wait_chop" if chop.state == "chop" else "wait_breakout"
    plans = []
    for side, sign in (("call", 1), ("put", -1)):
        entry = high + 0.1 * atr if sign == 1 else low - 0.1 * atr
        stop = (
            max(low - 0.1 * atr, entry - 2 * atr)
            if sign == 1
            else min(
                high + 0.1 * atr,
                entry + 2 * atr,
            )
        )
        risk = abs(entry - stop)
        target_1, target_2 = entry + sign * risk, entry + sign * 2 * risk
        if min(entry, stop, target_1, target_2) <= 0 or risk <= 0:
            continue
        plans.append(
            UnderlyingTradePlan(
                side=side,
                entry=entry,
                invalidation=stop,
                target_1=target_1,
                target_2=target_2,
                risk_per_share=risk,
                state=state,
            )
        )
    return plans


def build_scanner_diagnostics(
    points: list[PricePoint],
    daily_points: list[PricePoint],
    *,
    timeframe: str,
    evaluation_time: datetime,
) -> ScannerDiagnostics:
    now = aware(evaluation_time)
    session = now.astimezone(NEW_YORK).date()
    # Conservative completion: today's DAY bar remains provisional even after close.
    daily = sorted(
        (p for p in daily_points if aware(p.timestamp) <= now), key=lambda p: p.timestamp
    )
    completed = [p for p in daily if aware(p.timestamp).astimezone(NEW_YORK).date() < session]
    current = [p for p in daily if aware(p.timestamp).astimezone(NEW_YORK).date() == session]
    tape = (
        completed
        if timeframe == "1Day"
        else sorted(
            (p for p in points if aware(p.timestamp) + timedelta(minutes=15) <= now),
            key=lambda p: p.timestamp,
        )
    )
    latest = tape[-1] if tape else None
    max_age = timedelta(minutes=90) if timeframe == "15Min" else timedelta(days=4)
    stale = latest is None or now - aware(latest.timestamp) > max_age
    chop = choppiness(tape, timeframe)
    rsi_readings = volume_rsi_series(tape)
    filtered_rsi = volume_rsi_series(tape, use_low_vol_filter=True)
    return ScannerDiagnostics(
        evaluated_at=now,
        levels_as_of=latest.timestamp if latest else None,
        levels_price=latest.close if latest else None,
        timeframe=timeframe,
        stale=stale,
        daily_r_factor=r_factor(completed),
        provisional_r_factor=(
            r_factor([*completed, current[-1]], provisional=True) if current else None
        ),
        chop=chop,
        daily_chop=choppiness(completed),
        volume_rsi=rsi_readings[-1] if rsi_readings else None,
        volume_rsi_low_vol_filtered=filtered_rsi[-1] if filtered_rsi else None,
        recent_rsi_events=[
            r
            for r in rsi_readings[-40:]
            if r is not None and (r.quiet_signal != "none" or r.context.startswith("reversal_"))
        ][-6:],
        plans=breakout_plans(tape, chop, stale=stale),
        notes=[
            "Research filters only; these readings cannot approve, vote for or size orders.",
            "R-Factor uses DAY bars, uncapped 14-bar RVOL and typical price, not actual VWAP. "
            "Today's reading is provisional; completed readings exclude today's session.",
            "CHOP(14): <38.2 trend, >61.8 chop, otherwise transition; direction is separate.",
            "RSI/volume: Wilder RSI14, current-inclusive SMA20 volume >1.2x, RSI >70/<30. "
            "Optional Wilder ATR14/price <0.5% suppresses low-volatility signals, not CHOP. "
            "Quiet mode emits once per extreme excursion with 5-bar cooldown. A reversal "
            "requires RSI to leave the extreme and price to close beyond the signal candle "
            "in the opposite direction within 5 bars. Continuation is not a reversal. "
            "These are context / profit-review cues, never automatic entry or exit orders.",
            "Plans: next 3 bars may break a 20-bar extreme + 0.1 ATR; stop at opposite "
            "extreme capped to 2 ATR; targets 1R / 2R; time exit after 8 bars from entry. "
            "ATR is the arithmetic mean of 14 true ranges. Re-scan after entry window expires.",
            "Levels are underlying prices, not option premiums. No orders or stops are placed. "
            "Check option quotes, spread, OI, IV, expiry and Risk Agent before a paper order. "
            "Configured debit cap and 50% premium loss policy remain separate; "
            "a stop is not guaranteed.",
            "IEX volume is partial-market; R-Factor can differ from Thinkorswim's feed. "
            "Missing OHLC is unavailable, never a manufactured signal.",
        ],
    )
