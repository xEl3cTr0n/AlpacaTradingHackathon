import type { ScannerCandidate } from "./types";

export interface ScannerFilters {
  chop: "all" | "trend" | "transition" | "chop" | "not_chop";
  chopTimeframe: "intraday" | "daily";
  rFactor: "all" | "bullish" | "bearish";
  dailyBar: "completed" | "provisional";
  threshold: number;
  minRvol: number;
  rsiSignal: "all" | "raw" | "quiet" | "reversal" | "continuation";
  lowVolFilter: boolean;
  freshOnly: boolean;
  sort: "rank" | "r_factor" | "chop";
}

export const DEFAULT_FILTERS: ScannerFilters = {
  chop: "all", chopTimeframe: "intraday", rFactor: "all", dailyBar: "completed",
  threshold: 150, minRvol: 0, rsiSignal: "all", lowVolFilter: false,
  freshOnly: false, sort: "rank",
};

export const BUILTIN_PRESETS: Array<{ name: string; filters: ScannerFilters }> = [
  { name: "All names", filters: DEFAULT_FILTERS },
  { name: "Trending tape", filters: { ...DEFAULT_FILTERS, chop: "trend", sort: "chop" } },
  { name: "R-Factor calls", filters: { ...DEFAULT_FILTERS, rFactor: "bullish", sort: "r_factor" } },
  { name: "R-Factor puts (mirror)", filters: { ...DEFAULT_FILTERS, rFactor: "bearish", sort: "r_factor" } },
  { name: "Quiet reversals", filters: { ...DEFAULT_FILTERS, rsiSignal: "reversal" } },
];

export function filterCandidates(candidates: ScannerCandidate[], filters: ScannerFilters) {
  const reading = (c: ScannerCandidate) => filters.dailyBar === "completed"
    ? c.diagnostics?.daily_r_factor : c.diagnostics?.provisional_r_factor;
  const chop = (c: ScannerCandidate) => filters.chopTimeframe === "daily"
    ? c.diagnostics?.daily_chop : c.diagnostics?.chop;
  return candidates.filter((c) => {
    const d = c.diagnostics;
    if (filters.freshOnly && (!d || d.stale)) return false;
    const state = chop(c)?.state;
    if (filters.chop !== "all" && (!state || state === "unavailable" || (
      filters.chop === "not_chop" ? state === "chop" : state !== filters.chop
    ))) return false;
    const r = reading(c);
    if (filters.rFactor !== "all" && (!r || (filters.rFactor === "bullish"
      ? r.score <= filters.threshold : r.score >= -filters.threshold))) return false;
    if (filters.minRvol > 0 && (!r || r.relative_volume < filters.minRvol)) return false;
    const v = filters.lowVolFilter ? d?.volume_rsi_low_vol_filtered : d?.volume_rsi;
    if (filters.rsiSignal !== "all" && !v) return false;
    if (filters.rsiSignal === "raw" && v?.raw_signal === "none") return false;
    if (filters.rsiSignal === "quiet" && v?.quiet_signal === "none") return false;
    if (filters.rsiSignal === "reversal" && !v?.context.startsWith("reversal_")) return false;
    if (filters.rsiSignal === "continuation" && !v?.context.endsWith("_continuation")) return false;
    return true;
  }).sort((a, b) => {
    if (filters.sort === "r_factor") return Math.abs(reading(b)?.score ?? 0) - Math.abs(reading(a)?.score ?? 0) || a.rank - b.rank;
    if (filters.sort === "chop") return (chop(a)?.value ?? 101) - (chop(b)?.value ?? 101) || a.rank - b.rank;
    return a.rank - b.rank;
  });
}

export function parsePresets(raw: string): Array<{ name: string; filters: ScannerFilters }> {
  try {
    const items: unknown = JSON.parse(raw);
    if (!Array.isArray(items)) return [];
    return items.slice(0, 10).flatMap((item) => {
      if (!item || typeof item.name !== "string" || !item.name.trim() || item.name.length > 32) return [];
      const f = item.filters;
      if (!f || !["all", "trend", "transition", "chop", "not_chop"].includes(f.chop)
        || !["intraday", "daily"].includes(f.chopTimeframe)
        || !["all", "bullish", "bearish"].includes(f.rFactor)
        || !["completed", "provisional"].includes(f.dailyBar)
        || !["all", "raw", "quiet", "reversal", "continuation"].includes(f.rsiSignal)
        || !["rank", "r_factor", "chop"].includes(f.sort)
        || typeof f.lowVolFilter !== "boolean" || typeof f.freshOnly !== "boolean"
        || !Number.isFinite(f.threshold) || f.threshold < 0 || f.threshold > 1000
        || !Number.isFinite(f.minRvol) || f.minRvol < 0 || f.minRvol > 14) return [];
      return [{ name: item.name.trim(), filters: f as ScannerFilters }];
    });
  } catch { return []; }
}
