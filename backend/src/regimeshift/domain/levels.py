"""Pure calculations for IV expected move walls, volume profile (POC/VAH/VAL), and Ichimoku/VWAP equilibrium."""

import math
from regimeshift.domain.models import (
    IchimokuCloudPoint,
    IvLevels,
    PricePoint,
    StructuralLevels,
    VolumeProfileLevels,
)


def calculate_iv_levels(
    spot: float,
    average_iv: float | None,
    dte: int = 7,
    daily_bars: list[PricePoint] | None = None,
) -> IvLevels:
    prior_high = prior_low = prior_close = None
    if daily_bars:
        last_bar = daily_bars[-1]
        prior_high = round(last_bar.high, 2) if last_bar.high is not None else round(last_bar.close, 2)
        prior_low = round(last_bar.low, 2) if last_bar.low is not None else round(last_bar.close, 2)
        prior_close = round(last_bar.close, 2)

    if spot <= 0 or average_iv is None or average_iv <= 0:
        return IvLevels(
            average_iv=average_iv,
            prior_day_high=prior_high,
            prior_day_low=prior_low,
            prior_day_close=prior_close,
        )

    valid_dte = max(1, dte)
    expected_move = round(spot * average_iv * math.sqrt(valid_dte / 365.0), 2)
    session_expected_move = round(spot * average_iv * math.sqrt(1.0 / 365.0), 2)

    return IvLevels(
        upper_1s=round(spot + expected_move, 2),
        lower_1s=round(max(0.01, spot - expected_move), 2),
        upper_2s=round(spot + 2 * expected_move, 2),
        lower_2s=round(max(0.01, spot - 2 * expected_move), 2),
        average_iv=round(average_iv, 4),
        expected_move=expected_move,
        session_expected_move=session_expected_move,
        session_upper=round(spot + session_expected_move, 2),
        session_lower=round(max(0.01, spot - session_expected_move), 2),
        prior_day_high=prior_high,
        prior_day_low=prior_low,
        prior_day_close=prior_close,
    )


def calculate_volume_profile(
    bars: list[PricePoint], num_bins: int = 24
) -> VolumeProfileLevels:
    if not bars:
        return VolumeProfileLevels()
    prices_with_volume: list[tuple[float, int]] = []
    for bar in bars:
        price = (
            (bar.high + bar.low + bar.close) / 3.0
            if bar.high is not None and bar.low is not None
            else bar.close
        )
        if price > 0 and bar.volume > 0:
            prices_with_volume.append((price, bar.volume))

    if not prices_with_volume:
        return VolumeProfileLevels()

    min_p = min(p for p, _ in prices_with_volume)
    max_p = max(p for p, _ in prices_with_volume)
    if min_p == max_p or num_bins <= 1:
        return VolumeProfileLevels(poc=round(min_p, 2))

    bin_width = (max_p - min_p) / num_bins
    bin_volumes = [0.0] * num_bins

    for p, v in prices_with_volume:
        idx = min(num_bins - 1, int((p - min_p) / bin_width))
        bin_volumes[idx] += v

    max_idx = max(range(num_bins), key=lambda i: bin_volumes[i])
    poc = min_p + (max_idx + 0.5) * bin_width

    # 70% Value Area around POC
    total_vol = sum(bin_volumes)
    target_vol = 0.70 * total_vol
    low_idx, high_idx = max_idx, max_idx
    acc_vol = bin_volumes[max_idx]

    while acc_vol < target_vol and (low_idx > 0 or high_idx < num_bins - 1):
        next_low = bin_volumes[low_idx - 1] if low_idx > 0 else 0
        next_high = bin_volumes[high_idx + 1] if high_idx < num_bins - 1 else 0
        if next_high >= next_low and high_idx < num_bins - 1:
            high_idx += 1
            acc_vol += next_high
        elif low_idx > 0:
            low_idx -= 1
            acc_vol += next_low
        else:
            high_idx += 1
            acc_vol += next_high

    val = min_p + low_idx * bin_width
    vah = min_p + (high_idx + 1) * bin_width

    return VolumeProfileLevels(
        poc=round(poc, 2),
        vah=round(vah, 2),
        val=round(val, 2),
    )


def calculate_structural_levels(
    bars: list[PricePoint],
) -> StructuralLevels:
    if not bars:
        return StructuralLevels()

    # Session VWAP from today's bars
    last_date = bars[-1].timestamp.date()
    today_bars = [b for b in bars if b.timestamp.date() == last_date]
    session_vwap = None
    if today_bars:
        vol_sum = sum(b.volume for b in today_bars)
        if vol_sum > 0:
            pv_sum = sum(
                (
                    (b.high + b.low + b.close) / 3.0
                    if b.high is not None and b.low is not None
                    else b.close
                )
                * b.volume
                for b in today_bars
            )
            session_vwap = round(pv_sum / vol_sum, 2)

    highs = [b.high if b.high is not None else b.close for b in bars]
    lows = [b.low if b.low is not None else b.close for b in bars]
    closes = [b.close for b in bars]

    tenkan_sen = (
        round((max(highs[-9:]) + min(lows[-9:])) / 2.0, 2)
        if len(bars) >= 9
        else None
    )
    kijun_sen = (
        round((max(highs[-26:]) + min(lows[-26:])) / 2.0, 2)
        if len(bars) >= 26
        else None
    )
    senkou_span_b = (
        round((max(highs[-52:]) + min(lows[-52:])) / 2.0, 2)
        if len(bars) >= 52
        else None
    )

    # Continuous Ichimoku series
    ichimoku_series: list[IchimokuCloudPoint] = []
    n = len(bars)
    for i in range(n):
        t_val = (
            round((max(highs[max(0, i - 8) : i + 1]) + min(lows[max(0, i - 8) : i + 1])) / 2.0, 2)
            if i >= 8
            else None
        )
        k_val = (
            round((max(highs[max(0, i - 25) : i + 1]) + min(lows[max(0, i - 25) : i + 1])) / 2.0, 2)
            if i >= 25
            else None
        )
        span_a = round((t_val + k_val) / 2.0, 2) if t_val is not None and k_val is not None else None
        span_b = (
            round((max(highs[max(0, i - 51) : i + 1]) + min(lows[max(0, i - 51) : i + 1])) / 2.0, 2)
            if i >= 51
            else None
        )
        chikou = round(closes[i], 2)

        if i >= 8:
            ichimoku_series.append(
                IchimokuCloudPoint(
                    timestamp=bars[i].timestamp,
                    tenkan_sen=t_val,
                    kijun_sen=k_val,
                    senkou_span_a=span_a,
                    senkou_span_b=span_b,
                    chikou_span=chikou,
                )
            )

    return StructuralLevels(
        kijun_sen=kijun_sen,
        tenkan_sen=tenkan_sen,
        senkou_span_b=senkou_span_b,
        session_vwap=session_vwap,
        ichimoku_series=ichimoku_series,
    )

