import type { ChartContextSnapshot } from "./types";

/** Never borrow overlays from a prior symbol or retain them after a failed read. */
export function matchingChartContext(symbol: string, data?: ChartContextSnapshot, failed = false) {
  if (failed || !data || data.symbol !== symbol || data.read_only !== true) return null;
  if (data.options_microstructure && data.options_microstructure.underlying_symbol !== symbol) return null;
  return data;
}

export function chartContextLevels(context: ChartContextSnapshot | null) {
  const micro = context?.options_microstructure;
  const swing = context?.swing;
  const iv = context?.iv_levels;
  const vp = context?.volume_profile;
  const struct = context?.structural_levels;
  const values = [
    { title: "Put wall", price: micro?.put_wall, color: "#ef5350", dashed: false },
    { title: "Call wall", price: micro?.call_wall, color: "#fbbf24", dashed: false },
    { title: "Key gamma", price: micro?.key_gamma_strike, color: "#d946ef", dashed: true },
    { title: "Hedge wall", price: micro?.hedge_wall, color: "#a78bfa", dashed: true },
    { title: "Swing low", price: swing?.swing_low, color: "#38bdf8", dashed: true },
    { title: "Swing high", price: swing?.swing_high, color: "#35dc7b", dashed: true },
    { title: "Session +1σ", price: iv?.session_upper, color: "#38bdf8", dashed: true },
    { title: "Session -1σ", price: iv?.session_lower, color: "#f97316", dashed: true },
    { title: "Weekly +1σ", price: iv?.upper_1s, color: "#06b6d4", dashed: true },
    { title: "Weekly -1σ", price: iv?.lower_1s, color: "#ea580c", dashed: true },
    { title: "Extreme +2σ", price: iv?.upper_2s, color: "#a855f7", dashed: true },
    { title: "Extreme -2σ", price: iv?.lower_2s, color: "#a855f7", dashed: true },
    { title: "Prior Day High", price: iv?.prior_day_high, color: "#84cc16", dashed: true },
    { title: "Prior Day Low", price: iv?.prior_day_low, color: "#fb7185", dashed: true },
    { title: "Volume POC", price: vp?.poc, color: "#eab308", dashed: false },
    { title: "Value Area High", price: vp?.vah, color: "#c084fc", dashed: true },
    { title: "Value Area Low", price: vp?.val, color: "#c084fc", dashed: true },
    { title: "Ichimoku Kijun", price: struct?.kijun_sen, color: "#ec4899", dashed: false },
    { title: "Session VWAP", price: struct?.session_vwap, color: "#06b6d4", dashed: false },
  ];
  return values.flatMap((item) => typeof item.price === "number" && Number.isFinite(item.price) && item.price > 0
    ? [{ ...item, price: item.price }] : []);
}

export interface TargetCorridorSummary {
  spot: number | null;
  dailyExpectedMove: number | null;
  dailyPct: number | null;
  dailyUpper: number | null;
  dailyLower: number | null;
  weeklyExpectedMove: number | null;
  weeklyPct: number | null;
  weeklyUpper: number | null;
  weeklyLower: number | null;
  extremeUpper: number | null;
  extremeLower: number | null;
  callWall: number | null;
  putWall: number | null;
  priorDayHigh: number | null;
  priorDayLow: number | null;
  priorDayClose: number | null;
}

export function targetCorridorSummary(context: ChartContextSnapshot | null): TargetCorridorSummary {
  const spot = context?.underlying_price ?? null;
  const iv = context?.iv_levels;
  const micro = context?.options_microstructure;

  const dailyExpectedMove = iv?.session_expected_move ?? null;
  const dailyPct = spot && dailyExpectedMove && spot > 0 ? +((dailyExpectedMove / spot) * 100).toFixed(2) : null;
  const weeklyExpectedMove = iv?.expected_move ?? null;
  const weeklyPct = spot && weeklyExpectedMove && spot > 0 ? +((weeklyExpectedMove / spot) * 100).toFixed(2) : null;

  return {
    spot,
    dailyExpectedMove,
    dailyPct,
    dailyUpper: iv?.session_upper ?? (spot && dailyExpectedMove ? +(spot + dailyExpectedMove).toFixed(2) : null),
    dailyLower: iv?.session_lower ?? (spot && dailyExpectedMove ? +Math.max(0.01, spot - dailyExpectedMove).toFixed(2) : null),
    weeklyExpectedMove,
    weeklyPct,
    weeklyUpper: iv?.upper_1s ?? (spot && weeklyExpectedMove ? +(spot + weeklyExpectedMove).toFixed(2) : null),
    weeklyLower: iv?.lower_1s ?? (spot && weeklyExpectedMove ? +Math.max(0.01, spot - weeklyExpectedMove).toFixed(2) : null),
    extremeUpper: iv?.upper_2s ?? null,
    extremeLower: iv?.lower_2s ?? null,
    callWall: micro?.call_wall ?? null,
    putWall: micro?.put_wall ?? null,
    priorDayHigh: iv?.prior_day_high ?? null,
    priorDayLow: iv?.prior_day_low ?? null,
    priorDayClose: iv?.prior_day_close ?? null,
  };
}

export function nearbyGexRows(context: ChartContextSnapshot | null, limit = 21) {
  const spot = context?.underlying_price;
  if (!spot || !Number.isFinite(spot)) return [];
  return [...(context?.options_microstructure?.gex_by_strike ?? [])]
    .filter((row) => [row.strike, row.call_gex, row.put_gex, row.net_gex].every(Number.isFinite))
    .sort((a, b) => Math.abs(a.strike - spot) - Math.abs(b.strike - spot))
    .slice(0, limit).sort((a, b) => a.strike - b.strike);
}

export function formatSessionDate(dateString?: string | null): string {
  if (!dateString) return "unavailable";
  const date = new Date(dateString);
  if (Number.isNaN(date.getTime())) return "unavailable";
  return date.toLocaleDateString("en-US", { timeZone: "America/New_York" });
}

export interface HeatmapRow {
  strike: number;
  call_gex: number;
  put_gex: number;
  net_gex: number;
  call_oi: number;
  put_oi: number;
  total_oi: number;
  call_volume: number;
  put_volume: number;
  total_volume: number;
  call_iv: number | null;
  put_iv: number | null;
  average_iv: number | null;
  isAtm: boolean;
  callOiIntensity: number;
  putOiIntensity: number;
  callVolIntensity: number;
  putVolIntensity: number;
  gexIntensity: number;
  ivIntensity: number;
}

export interface HeatmapSummary {
  totalCallOi: number;
  totalPutOi: number;
  totalOi: number;
  pcOiRatio: number | null;
  totalCallVol: number;
  totalPutVol: number;
  totalVolume: number;
  pcVolRatio: number | null;
  atmStrike: number | null;
  atmIv: number | null;
}

export function strikeHeatmapRows(
  context: ChartContextSnapshot | null,
  limit = 25,
  sortBy: "strike" | "net_gex" | "volume" | "oi" = "strike",
  sortDir: "asc" | "desc" = "asc"
): HeatmapRow[] {
  const spot = context?.underlying_price;
  const rawRows = context?.options_microstructure?.gex_by_strike ?? [];
  if (rawRows.length === 0) return [];

  const validRows = rawRows.filter(
    (row) => typeof row.strike === "number" && Number.isFinite(row.strike) && row.strike > 0
  );
  if (validRows.length === 0) return [];

  // Determine closest ATM strike
  let atmStrike: number | null = null;
  if (spot && Number.isFinite(spot)) {
    let closestDist = Infinity;
    for (const r of validRows) {
      const dist = Math.abs(r.strike - spot);
      if (dist < closestDist) {
        closestDist = dist;
        atmStrike = r.strike;
      }
    }
  }

  // Window to limit nearest strikes around spot if limit is provided and spot exists
  let workingRows = validRows;
  if (limit > 0 && validRows.length > limit && spot && Number.isFinite(spot)) {
    workingRows = [...validRows]
      .sort((a, b) => Math.abs(a.strike - spot) - Math.abs(b.strike - spot))
      .slice(0, limit);
  }

  // Calculate intensity ceilings
  const maxCallOi = Math.max(...workingRows.map((r) => r.call_oi ?? 0), 1);
  const maxPutOi = Math.max(...workingRows.map((r) => r.put_oi ?? 0), 1);
  const maxCallVol = Math.max(...workingRows.map((r) => r.call_volume ?? 0), 1);
  const maxPutVol = Math.max(...workingRows.map((r) => r.put_volume ?? 0), 1);
  const maxAbsGex = Math.max(...workingRows.map((r) => Math.abs(r.net_gex ?? 0)), 1);

  const ivValues = workingRows
    .map((r) => r.average_iv)
    .filter((iv): iv is number => typeof iv === "number" && Number.isFinite(iv) && iv > 0);
  const minIv = ivValues.length > 0 ? Math.min(...ivValues) : 0;
  const maxIv = ivValues.length > 0 ? Math.max(...ivValues) : 1;
  const ivRange = Math.max(maxIv - minIv, 0.001);

  const mapped: HeatmapRow[] = workingRows.map((r) => {
    const call_oi = r.call_oi ?? 0;
    const put_oi = r.put_oi ?? 0;
    const total_oi = r.total_oi ?? (call_oi + put_oi);
    const call_volume = r.call_volume ?? 0;
    const put_volume = r.put_volume ?? 0;
    const total_volume = r.total_volume ?? (call_volume + put_volume);
    const avgIv = r.average_iv ?? null;

    return {
      strike: r.strike,
      call_gex: r.call_gex ?? 0,
      put_gex: r.put_gex ?? 0,
      net_gex: r.net_gex ?? 0,
      call_oi,
      put_oi,
      total_oi,
      call_volume,
      put_volume,
      total_volume,
      call_iv: r.call_iv ?? null,
      put_iv: r.put_iv ?? null,
      average_iv: avgIv,
      isAtm: r.strike === atmStrike,
      callOiIntensity: Math.min(1, Math.max(0, call_oi / maxCallOi)),
      putOiIntensity: Math.min(1, Math.max(0, put_oi / maxPutOi)),
      callVolIntensity: Math.min(1, Math.max(0, call_volume / maxCallVol)),
      putVolIntensity: Math.min(1, Math.max(0, put_volume / maxPutVol)),
      gexIntensity: Math.min(1, Math.max(0, Math.abs(r.net_gex ?? 0) / maxAbsGex)),
      ivIntensity: avgIv != null ? Math.min(1, Math.max(0, (avgIv - minIv) / ivRange)) : 0,
    };
  });

  return mapped.sort((a, b) => {
    let diff = 0;
    if (sortBy === "strike") diff = a.strike - b.strike;
    else if (sortBy === "net_gex") diff = b.net_gex - a.net_gex;
    else if (sortBy === "volume") diff = b.total_volume - a.total_volume;
    else if (sortBy === "oi") diff = b.total_oi - a.total_oi;

    return sortDir === "desc" ? -diff : diff;
  });
}

export function heatmapSummary(context: ChartContextSnapshot | null): HeatmapSummary {
  const rawRows = context?.options_microstructure?.gex_by_strike ?? [];
  const spot = context?.underlying_price;

  let totalCallOi = 0;
  let totalPutOi = 0;
  let totalCallVol = 0;
  let totalPutVol = 0;
  let atmStrike: number | null = null;
  let atmIv: number | null = null;
  let closestDist = Infinity;

  for (const r of rawRows) {
    totalCallOi += r.call_oi ?? 0;
    totalPutOi += r.put_oi ?? 0;
    totalCallVol += r.call_volume ?? 0;
    totalPutVol += r.put_volume ?? 0;

    if (spot && Number.isFinite(spot) && Number.isFinite(r.strike)) {
      const dist = Math.abs(r.strike - spot);
      if (dist < closestDist) {
        closestDist = dist;
        atmStrike = r.strike;
        atmIv = r.average_iv ?? null;
      }
    }
  }

  const totalOi = totalCallOi + totalPutOi;
  const totalVolume = totalCallVol + totalPutVol;
  const pcOiRatio = totalCallOi > 0 ? +(totalPutOi / totalCallOi).toFixed(2) : null;
  const pcVolRatio = totalCallVol > 0 ? +(totalPutVol / totalCallVol).toFixed(2) : null;

  return {
    totalCallOi,
    totalPutOi,
    totalOi,
    pcOiRatio,
    totalCallVol,
    totalPutVol,
    totalVolume,
    pcVolRatio,
    atmStrike,
    atmIv,
  };
}


