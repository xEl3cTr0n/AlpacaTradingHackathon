"""Fixed-rule daily underlying proxies. No historical option fills or execution approval."""

from datetime import datetime
from statistics import mean

from regimeshift.domain.models import PricePoint, UnderlyingTradePlan
from regimeshift.domain.scanner_diagnostics import (
    NEW_YORK,
    aware,
    breakout_plans,
    choppiness,
    r_factor,
    valid_ohlc,
)
from regimeshift.domain.volume_rsi import volume_rsi_series


def simulate_breakout(
    points: list[PricePoint],
    signal_index: int,
    plan: UnderlyingTradePlan,
) -> dict | None:
    sign = 1 if plan.side == "call" else -1
    for entry_index in range(signal_index + 1, min(signal_index + 4, len(points))):
        bar = points[entry_index]
        if not valid_ohlc(bar):
            return None
        touched = bar.high >= plan.entry if sign == 1 else bar.low <= plan.entry
        if not touched:
            continue
        fill = max(bar.open, plan.entry) if sign == 1 else min(bar.open, plan.entry)
        # A gap >0.5R beyond the trigger is not chased.
        if sign * (fill - plan.entry) > 0.5 * plan.risk_per_share:
            return None
        end = entry_index + plan.time_exit_bars - 1
        if end >= len(points):
            return None
        risk = abs(fill - plan.invalidation)
        for j in range(entry_index, end + 1):
            bar = points[j]
            if not valid_ohlc(bar):
                return None
            stopped = bar.low <= plan.invalidation if sign == 1 else bar.high >= plan.invalidation
            targeted = bar.high >= plan.target_2 if sign == 1 else bar.low <= plan.target_2
            # Stop first even on the entry bar when OHLC cannot establish event ordering.
            if stopped:
                # Entry-bar open precedes the breakout, so it cannot be an exit fill.
                exit_price = (
                    plan.invalidation
                    if j == entry_index
                    else (
                        min(bar.open, plan.invalidation)
                        if sign == 1
                        else max(bar.open, plan.invalidation)
                    )
                )
                reason = "stop"
            elif targeted:
                exit_price, reason = plan.target_2, "target_2"
            elif j == end:
                exit_price, reason = bar.close, "time"
            else:
                continue
            net = sign * (exit_price - fill) - fill * 0.001
            return {
                "entry_index": entry_index,
                "exit_index": j,
                "reason": reason,
                "return": net / fill,
                "r_multiple": net / risk,
            }
    return None


def summarize(trades: list[dict]) -> dict:
    returns = [trade["return"] for trade in trades]
    gains = sum(max(value, 0) for value in returns)
    losses = sum(max(-value, 0) for value in returns)
    return {
        "trades": len(trades),
        "win_rate": (
            round(sum(value > 0 for value in returns) / len(returns), 4) if returns else None
        ),
        "mean_underlying_return": round(mean(returns), 6) if returns else None,
        "profit_factor": round(gains / losses, 4) if losses else None,
        "mean_r": round(mean(t["r_multiple"] for t in trades), 4) if trades else None,
    }


def evaluate_research(histories: dict[str, list[PricePoint]], now: datetime) -> dict:
    session = aware(now).astimezone(NEW_YORK).date()
    histories = {
        symbol: sorted(
            (p for p in bars if aware(p.timestamp).astimezone(NEW_YORK).date() < session),
            key=lambda p: p.timestamp,
        )
        for symbol, bars in histories.items()
    }
    dates = sorted({p.timestamp for bars in histories.values() for p in bars})
    if len(dates) < 100:
        raise ValueError("At least 100 completed daily sessions required")
    split = dates[int(len(dates) * 0.7)]
    names = [
        "r_factor",
        "r_factor_exclude_chop",
        "r_factor_trend_only",
        "rsi_raw_fade",
        "rsi_quiet_fade",
        "rsi_confirmed_reversal",
    ]
    results = {name: {"train": [], "holdout": []} for name in names}
    counts = {"raw_rsi_alerts": 0, "quiet_rsi_alerts": 0, "confirmed_reversals": 0}
    for bars in histories.values():
        rsi = volume_rsi_series(bars)
        next_allowed = {name: 0 for name in names}
        for i in range(59, len(bars) - 11):
            # Purge every possible entry+holding window that crosses the split.
            if bars[i].timestamp < split <= bars[i + 11].timestamp:
                continue
            partition = "train" if bars[i].timestamp < split else "holdout"
            window = bars[max(0, i - 59) : i + 1]
            r = r_factor(window)
            chop = choppiness(window)
            plans = breakout_plans(window, chop)
            if r and (r.bullish_match or r.bearish_match):
                side = "call" if r.bullish_match else "put"
                plan = next((p for p in plans if p.side == side), None)
                for name in names[:3]:
                    eligible = name == "r_factor" or (
                        chop.state != "unavailable"
                        and (
                            chop.state != "chop"
                            if name == "r_factor_exclude_chop"
                            else chop.state == "trend"
                        )
                    )
                    if not eligible or i < next_allowed[name] or plan is None:
                        continue
                    trade = simulate_breakout(bars, i, plan)
                    if trade:
                        results[name][partition].append(trade)
                        next_allowed[name] = trade["exit_index"] + 1
            v = rsi[i]
            if v is None:
                continue
            counts["raw_rsi_alerts"] += v.raw_signal != "none"
            counts["quiet_rsi_alerts"] += v.quiet_signal != "none"
            counts["confirmed_reversals"] += v.context.startswith("reversal_")
            for name, signal in (
                ("rsi_raw_fade", v.raw_signal),
                ("rsi_quiet_fade", v.quiet_signal),
                (
                    "rsi_confirmed_reversal",
                    "overbought"
                    if v.context == "reversal_down"
                    else "oversold"
                    if v.context == "reversal_up"
                    else "none",
                ),
            ):
                if signal == "none" or i < next_allowed[name]:
                    continue
                if not all(valid_ohlc(p) for p in bars[i + 1 : i + 6]):
                    continue
                entry, exit_price = bars[i + 1].open, bars[i + 5].close
                sign = -1 if signal == "overbought" else 1
                net_return = sign * (exit_price - entry) / entry - 0.001
                results[name][partition].append({"return": net_return, "r_multiple": 0})
                next_allowed[name] = i + 6
    variants = {
        name: {part: summarize(trades) for part, trades in partitions.items()}
        for name, partitions in results.items()
    }
    for name in names[3:]:
        for partition in variants[name].values():
            partition["mean_r"] = None  # Five-day event study has no stop-based risk unit.
    return {
        "research_only": True,
        "execution_authorized": False,
        "source": "Alpaca IEX fully adjusted daily bars",
        "start": dates[0].isoformat(),
        "end": dates[-1].isoformat(),
        "holdout_start": split.isoformat(),
        "symbols": len(histories),
        "session_count": len(dates),
        "signal_counts": counts,
        "variants": variants,
        "methodology": [
            "Fixed thresholds before the run. Chronological 70/30 split; purge 11-bar "
            "cross-boundary windows. No overlapping observations per symbol per variant.",
            "R-Factor: original >150 and mirrored <-150. Next 3 sessions may trigger "
            "20-bar high/low +0.1 ATR breakout; initial stop capped to 2 ATR; full exit "
            "at 2R or after 8 bars. 1R is a displayed reference, not a partial fill. "
            "No gap chasing beyond 0.5R. Stop-first ambiguity; adverse stop gaps respected.",
            "RSI event study: original, debounced and price-confirmed reversal events; "
            "contrarian entry at next open, exit on fifth session close. Low-vol filter OFF. "
            "Raw extrema are not claimed to be tops/bottoms. Reversal has up to 5-bar latency.",
            "All returns deduct 10bps round trip underlying cost. No option chains, "
            "Greeks, IV decay, options spreads, portfolio allocation or borrow fees modelled. "
            "Not options P&L. Daily evidence cannot validate 15-minute entries.",
            "Current large-cap universe has survivorship bias; IEX partial-market volume "
            "differs from consolidated feeds. This exploratory comparison is not a promotion gate.",
        ],
    }
