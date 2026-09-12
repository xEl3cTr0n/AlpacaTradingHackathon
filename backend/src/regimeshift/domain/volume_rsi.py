"""User's RSI/volume defaults, plus explicitly separate debounced context."""

from statistics import mean

from regimeshift.domain.models import PricePoint, VolumeRsiReading


def volume_rsi_series(
    points: list[PricePoint],
    *,
    use_low_vol_filter: bool = False,
) -> list[VolumeRsiReading | None]:
    # Local import avoids the diagnostics/indicator import cycle.
    from regimeshift.domain.scanner_diagnostics import valid_ohlc

    output: list[VolumeRsiReading | None] = []
    gains: list[float] = []
    losses: list[float] = []
    ranges: list[float] = []
    volumes: list[int] = []
    avg_gain = avg_loss = atr = None
    previous = None
    latched_zone = "none"
    last_alert = -100
    event: tuple[int, str, PricePoint] | None = None
    for i, p in enumerate(points):
        if not valid_ohlc(p):
            # A data hole invalidates both smoothing history and pending confirmations.
            gains, losses, ranges, volumes = [], [], [], []
            avg_gain = avg_loss = atr = previous = event = None
            latched_zone = "none"
            output.append(None)
            continue
        tr = (
            p.high - p.low
            if previous is None
            else max(
                p.high - p.low,
                abs(p.high - previous.close),
                abs(p.low - previous.close),
            )
        )
        ranges.append(tr)
        volumes.append(p.volume)
        if atr is None and len(ranges) == 14:
            atr = mean(ranges)
        elif atr is not None:
            atr = (atr * 13 + tr) / 14
        if previous is not None:
            change = p.close - previous.close
            gain, loss = max(change, 0), max(-change, 0)
            gains.append(gain)
            losses.append(loss)
            if avg_gain is None and len(gains) == 14:
                avg_gain, avg_loss = mean(gains), mean(losses)
            elif avg_gain is not None:
                avg_gain, avg_loss = (avg_gain * 13 + gain) / 14, (avg_loss * 13 + loss) / 14
        previous = p
        if avg_gain is None or atr is None or len(volumes) < 20:
            output.append(None)
            continue
        # Pine's RSI yields no signal for the undefined all-flat 0/0 case.
        if avg_gain == avg_loss == 0:
            output.append(None)
            continue
        rsi = 100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
        average_volume = mean(volumes[-20:])
        ratio = p.volume / average_volume if average_volume > 0 else 0.0
        low_vol = atr / p.close < 0.005
        zone = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "none"
        raw = zone if ratio > 1.2 and (not use_low_vol_filter or not low_vol) else "none"
        if zone == "none":
            latched_zone = "none"
        quiet = "none"
        context = "none"
        event_at = None
        age = None
        if event is not None and i - event[0] <= 5:
            event_index, event_zone, anchor = event
            event_at, age = anchor.timestamp, i - event_index
            context = "extreme_watch"
            valid = not use_low_vol_filter or not low_vol
            if age > 0 and valid:
                if event_zone == "overbought" and rsi < 70 and p.close < anchor.low:
                    context, event = "reversal_down", None
                elif event_zone == "oversold" and rsi > 30 and p.close > anchor.high:
                    context, event = "reversal_up", None
                elif event_zone == "overbought" and rsi > 70 and p.close > anchor.high:
                    context = "up_continuation"
                elif event_zone == "oversold" and rsi < 30 and p.close < anchor.low:
                    context = "down_continuation"
        elif event is not None:
            event = None
        if raw != "none" and raw != latched_zone and i - last_alert >= 5:
            quiet, latched_zone, last_alert = raw, raw, i
            event = (i, raw, p)
            # A new opposite extreme must not erase a just-confirmed reversal.
            if not context.startswith("reversal_"):
                context, event_at, age = "extreme_watch", p.timestamp, 0
        output.append(
            VolumeRsiReading(
                as_of=p.timestamp,
                rsi=rsi,
                volume_ratio=ratio,
                atr_fraction=atr / p.close,
                low_volatility=low_vol,
                low_vol_filter_enabled=use_low_vol_filter,
                raw_signal=raw,
                quiet_signal=quiet,
                context=context,
                event_at=event_at,
                event_age_bars=age,
            )
        )
    return output
