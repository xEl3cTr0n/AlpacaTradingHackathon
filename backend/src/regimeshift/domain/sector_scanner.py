"""Read-only, synchronized sector confirmation. Never a broker execution gate."""

from datetime import datetime, time, timedelta
from math import sqrt
from statistics import mean
from typing import Literal

from pydantic import BaseModel, Field

from regimeshift.domain.models import PricePoint, UnderlyingTradePlan
from regimeshift.domain.scanner_diagnostics import (
    NEW_YORK,
    aware,
    breakout_plans,
    choppiness,
    valid_ohlc,
)
from regimeshift.domain.sector_rotation import SECTOR_UNIVERSE

# Curated liquid-name research samples, not complete ETF holdings or index weights.
SECTOR_SAMPLES = {
    "XLK": ["AAPL", "MSFT", "NVDA", "AVGO", "AMD"],
    "XLC": ["META", "GOOGL", "NFLX", "DIS", "TMUS"],
    "XLY": ["AMZN", "TSLA", "HD", "MCD", "LOW"],
    "XLP": ["WMT", "COST", "PG", "KO", "PEP"],
    "XLE": ["XOM", "CVX", "COP", "SLB", "EOG"],
    "XLF": ["JPM", "BAC", "GS", "V", "MA"],
    "XLV": ["LLY", "JNJ", "ABBV", "MRK", "UNH"],
    "XLI": ["GE", "CAT", "RTX", "HON", "UPS"],
    "XLB": ["LIN", "SHW", "FCX", "NEM", "APD"],
    "XLRE": ["PLD", "AMT", "EQIX", "WELL", "SPG"],
    "XLU": ["NEE", "SO", "DUK", "CEG", "AEP"],
}


class SectorMember(BaseModel):
    symbol: str
    as_of: datetime | None = None
    available: bool = False
    price: float | None = None
    session_return: float | None = None
    relative_to_sector: float | None = None
    trend: Literal["bullish", "bearish", "mixed", "unavailable"] = "unavailable"
    above_vwap: bool | None = None
    correlation: float | None = None
    correlation_pairs: int = 0
    confirms: bool = False
    plans: list[UnderlyingTradePlan] = Field(default_factory=list)


class SectorScanRow(BaseModel):
    symbol: str
    name: str
    as_of: datetime | None = None
    available: bool = False
    stale: bool = True
    price: float | None = None
    session_return: float | None = None
    relative_to_spy: float | None = None
    trend: Literal["bullish", "bearish", "mixed", "unavailable"] = "unavailable"
    session_vwap: float | None = None
    chop: float | None = None
    sample_coverage: float = 0
    bullish_breadth: float | None = None
    bearish_breadth: float | None = None
    agreement: float | None = None
    score: float | None = None
    signal: Literal[
        "confirmed_bullish", "confirmed_bearish", "watch", "historical", "unavailable"
    ] = "unavailable"
    daily_returns: dict[str, float | None] = Field(default_factory=dict)
    daily_as_of: datetime | None = None
    plans: list[UnderlyingTradePlan] = Field(default_factory=list)
    members: list[SectorMember] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class SectorScanSnapshot(BaseModel):
    generated_at: datetime
    as_of: datetime | None
    source: str
    read_only: Literal[True] = True
    timeframe: Literal["15Min"] = "15Min"
    sectors: list[SectorScanRow]
    notes: list[str]


def _ema(values: list[float], period: int) -> float:
    result = values[0]
    for value in values[1:]:
        result += 2 / (period + 1) * (value - result)
    return result


def completed_session_bars(points: list[PricePoint], now: datetime) -> list[PricePoint]:
    """Regular-hours completed bars only; do not fill gaps or infer missing prints."""
    result = {}
    for point in points:
        stamp = aware(point.timestamp)
        local = stamp.astimezone(NEW_YORK)
        if (
            stamp + timedelta(minutes=15) <= aware(now)
            and local.weekday() < 5
            and time(9, 30) <= local.time() < time(16)
            and valid_ohlc(point)
        ):
            result[stamp] = point
    return [result[key] for key in sorted(result)]


def _metrics(points: list[PricePoint]) -> tuple[str, float | None, float | None]:
    closes = [p.close for p in points]
    fast, slow = _ema(closes, 18), _ema(closes, 50)
    trend = (
        "bullish"
        if closes[-1] > fast > slow
        else "bearish"
        if closes[-1] < fast < slow
        else "mixed"
    )
    session = aware(points[-1].timestamp).astimezone(NEW_YORK).date()
    today = [p for p in points if aware(p.timestamp).astimezone(NEW_YORK).date() == session]
    has_open = aware(today[0].timestamp).astimezone(NEW_YORK).time() == time(9, 30)
    change = today[-1].close / today[0].open - 1 if has_open else None
    volume = sum(p.volume for p in today)
    # Typical-price × volume is an approximation, not trade-level consolidated VWAP.
    vwap = (
        sum((p.high + p.low + p.close) / 3 * p.volume for p in today) / volume
        if has_open and volume
        else None
    )
    return trend, change, vwap


def correlation(left: list[PricePoint], right: list[PricePoint]) -> tuple[float | None, int]:
    def returns(points):
        return {
            aware(b.timestamp): b.close / a.close - 1
            for a, b in zip(points, points[1:], strict=False)
            if aware(b.timestamp) - aware(a.timestamp) == timedelta(minutes=15)
        }

    a, b = returns(left), returns(right)
    stamps = sorted(a.keys() & b.keys())[-26:]
    if len(stamps) < 10:
        return None, len(stamps)
    x, y = [a[t] for t in stamps], [b[t] for t in stamps]
    mx, my = mean(x), mean(y)
    denominator = sqrt(sum((v - mx) ** 2 for v in x) * sum((v - my) ** 2 for v in y))
    value = (
        sum((u - mx) * (v - my) for u, v in zip(x, y, strict=True)) / denominator
        if denominator > 1e-15
        else None
    )
    return max(-1.0, min(1.0, value)) if value is not None else None, len(stamps)


def is_stale_as_of(as_of: datetime, now: datetime) -> bool:
    local_now = aware(now).astimezone(NEW_YORK)
    return (
        aware(now) - aware(as_of) > timedelta(minutes=45)
        or local_now.weekday() >= 5
        or not time(9, 30) <= local_now.time() < time(16)
    )


def recompute_sector_snapshot_status(
    snapshot: SectorScanSnapshot, now: datetime
) -> SectorScanSnapshot:
    """Recompute time-dependent status (stale, signal, breakout plans) for a cached snapshot."""
    updated_sectors = []
    for orig_row in snapshot.sectors:
        row = orig_row.model_copy(deep=True)
        if row.available and row.as_of:
            is_stale = is_stale_as_of(row.as_of, now)
            if is_stale and not row.stale:
                row.stale = True
                row.signal = "historical"
                if not any("Historical/session closed" in r for r in row.reasons):
                    row.reasons.insert(
                        0,
                        "Historical/session closed: not a current entry; check feed timestamps.",
                    )
                row.plans = [p.model_copy(update={"status": "stale"}) for p in row.plans]
                for member in row.members:
                    member.plans = [
                        p.model_copy(update={"status": "stale"}) for p in member.plans
                    ]
        updated_sectors.append(row)
    return snapshot.model_copy(update={"sectors": updated_sectors})


def build_sector_scan(
    histories: dict[str, list[PricePoint]],
    daily: dict[str, list[PricePoint]],
    now: datetime,
    source: str,
) -> SectorScanSnapshot:
    clean = {symbol: completed_session_bars(points, now) for symbol, points in histories.items()}
    benchmark = clean.get("SPY", [])
    as_of = aware(benchmark[-1].timestamp) if len(benchmark) >= 50 else None
    # All names evaluated at the SPY reference bar, not a mixture of latest timestamps.
    clean = {
        s: [p for p in bars if as_of and aware(p.timestamp) <= as_of] for s, bars in clean.items()
    }
    spy_return = _metrics(benchmark)[1] if as_of else None
    rows = []
    for symbol, name in SECTOR_UNIVERSE.items():
        row = SectorScanRow(symbol=symbol, name=name)
        points = clean.get(symbol, [])
        if as_of is None or len(points) < 50 or aware(points[-1].timestamp) != as_of:
            row.reasons.append("Missing synchronized ETF/SPY history (50 completed bars required).")
            row.members = [SectorMember(symbol=s) for s in SECTOR_SAMPLES[symbol]]
            rows.append(row)
            continue
        row.available, row.as_of, row.price = True, as_of, points[-1].close
        row.stale = is_stale_as_of(as_of, now)
        row.trend, row.session_return, row.session_vwap = _metrics(points)
        row.relative_to_spy = (
            row.session_return - spy_return
            if row.session_return is not None and spy_return is not None
            else None
        )
        chop = choppiness(points, "15Min")
        row.chop = chop.value
        row.plans = breakout_plans(points, chop, stale=row.stale)
        for member in SECTOR_SAMPLES[symbol]:
            bars = clean.get(member, [])
            item = SectorMember(symbol=member, as_of=bars[-1].timestamp if bars else None)
            if len(bars) >= 50 and aware(bars[-1].timestamp) == as_of:
                item.available, item.price = True, bars[-1].close
                item.trend, item.session_return, vwap = _metrics(bars)
                item.above_vwap = item.price > vwap if vwap is not None else None
                item.relative_to_sector = (
                    item.session_return - row.session_return
                    if item.session_return is not None and row.session_return is not None
                    else None
                )
                item.correlation, item.correlation_pairs = correlation(bars, points)
                item.confirms = (
                    row.trend in ("bullish", "bearish")
                    and item.trend == row.trend
                    and item.above_vwap is not None
                    and item.above_vwap == (row.trend == "bullish")
                    and item.correlation is not None
                    and item.correlation >= 0.3
                )
                item.plans = breakout_plans(bars, choppiness(bars, "15Min"), stale=row.stale)
            row.members.append(item)
        available = [m for m in row.members if m.available]
        row.sample_coverage = len(available) / len(row.members)
        if available:
            row.bullish_breadth = sum(m.trend == "bullish" for m in available) / len(available)
            row.bearish_breadth = sum(m.trend == "bearish" for m in available) / len(available)
            row.agreement = sum(m.confirms for m in available) / len(available)
            direction = 1 if row.trend == "bullish" else -1 if row.trend == "bearish" else 0
            rs = max(-1, min(1, (row.relative_to_spy or 0) / 0.01))
            row.score = round(
                direction * 40 + (row.bullish_breadth - row.bearish_breadth) * 40 + rs * 20, 1
            )
        conditions = {
            "ETF has 18/50 EMA directional alignment": row.trend in ("bullish", "bearish"),
            "At least 60% of the curated sample has synchronized data": row.sample_coverage >= 0.6,
            "Sample agreement ≥60% (trend + VWAP + correlation ≥0.30)": row.agreement is not None
            and row.agreement >= 0.6,
            "ETF is not choppy (CHOP ≤61.8)": row.chop is not None and row.chop <= 61.8,
            "ETF VWAP and relative-to-SPY direction agree": row.session_vwap is not None
            and row.relative_to_spy is not None
            and (
                (
                    row.trend == "bullish"
                    and row.price > row.session_vwap
                    and row.relative_to_spy > 0
                )
                or (
                    row.trend == "bearish"
                    and row.price < row.session_vwap
                    and row.relative_to_spy < 0
                )
            ),
        }
        row.reasons = [
            ("PASS: " if passed else "WAIT: ") + label for label, passed in conditions.items()
        ]
        row.signal = (
            "historical"
            if row.stale
            else f"confirmed_{row.trend}"
            if all(conditions.values())
            else "watch"
        )
        if row.stale:
            row.reasons.insert(
                0,
                "Historical/session closed: not a current entry; check feed timestamps.",
            )
        completed_daily = sorted(
            [
                p
                for p in daily.get(symbol, [])
                if valid_ohlc(p)
                and aware(p.timestamp).astimezone(NEW_YORK).date()
                < aware(now).astimezone(NEW_YORK).date()
            ],
            key=lambda p: p.timestamp,
        )
        for label, period in (("1D", 1), ("5D", 5), ("20D", 20)):
            row.daily_returns[label] = (
                completed_daily[-1].close / completed_daily[-period - 1].close - 1
                if len(completed_daily) > period
                else None
            )
        row.daily_as_of = completed_daily[-1].timestamp if completed_daily else None
        rows.append(row)
    rows.sort(key=lambda r: (r.score is not None, abs(r.score or 0)), reverse=True)
    return SectorScanSnapshot(
        generated_at=now,
        as_of=as_of,
        source=source,
        sectors=rows,
        notes=[
            "Research only. No council or orders. Agreement does not guarantee profit.",
            "11 ETFs; five curated names each, not full holdings or cap-weighted breadth.",
            "Completed regular-session 15m bars synchronized to SPY. Missing names are excluded.",
            "Since 09:30 ET open; unavailable if opening bar missing. VWAP is a bar-based proxy.",
            "Correlation: up to 26 matched consecutive 15m returns, minimum 10, no overnight gaps.",
            "Rank: trend ±40 + net breadth ×40 + capped relative-SPY return ×20; not probability.",
            "1D/5D/20D end on last completed daily bar, separate from intraday session return.",
            "Future triggers/stops use underlying prices, not options. Check option liquidity.",
        ],
    )
