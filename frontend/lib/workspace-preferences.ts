export const WORKSPACE_KEY = "regimeshift.workspace.v1";
export interface WorkspacePreferences {
  symbol: string;
  timeframe: "1Min" | "5Min" | "15Min" | "1Day";
  rsiMode: "off" | "raw" | "quiet" | "reversal";
  lowVolFilter: boolean;
  showLevels: boolean;
  showGex: boolean;
  rail: "scanner" | "watchlist";
  dock: "positions" | "orders" | "options";
  quoteSeconds: 0 | 1 | 5 | 10;
  watchlist: string[];
}
export const DEFAULT_WORKSPACE: WorkspacePreferences = {
  symbol: "SPY", timeframe: "5Min", rsiMode: "quiet", lowVolFilter: false,
  showLevels: true, showGex: true, rail: "scanner", dock: "positions", quoteSeconds: 5,
  watchlist: ["SPY", "QQQ", "IWM", "AAPL", "MSFT", "NVDA"],
};
export function normalizeTicker(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const symbol = value.trim().toUpperCase();
  return /^[A-Z][A-Z.]{0,9}$/.test(symbol) ? symbol : null;
}
/** Whitelist display preferences. Never deserialize execution state or secrets. */
export function parseWorkspace(raw: string | null): WorkspacePreferences {
  let input: Record<string, unknown> = {};
  try {
    const parsed: unknown = JSON.parse(raw ?? "{}");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) input = parsed as Record<string, unknown>;
  } catch { /* Corrupt storage falls back to safe display defaults. */ }
  const pick = <T extends string | number>(key: string, allowed: readonly T[], fallback: T): T =>
    allowed.includes(input[key] as T) ? input[key] as T : fallback;
  return {
    symbol: normalizeTicker(input.symbol) ?? DEFAULT_WORKSPACE.symbol,
    timeframe: pick("timeframe", ["1Min", "5Min", "15Min", "1Day"], DEFAULT_WORKSPACE.timeframe),
    rsiMode: pick("rsiMode", ["off", "raw", "quiet", "reversal"], DEFAULT_WORKSPACE.rsiMode),
    lowVolFilter: typeof input.lowVolFilter === "boolean" ? input.lowVolFilter : false,
    showLevels: typeof input.showLevels === "boolean" ? input.showLevels : true,
    showGex: typeof input.showGex === "boolean" ? input.showGex : true,
    rail: pick("rail", ["scanner", "watchlist"], "scanner"),
    dock: pick("dock", ["positions", "orders", "options"], "positions"),
    quoteSeconds: pick("quoteSeconds", [0, 1, 5, 10], 5),
    watchlist: Array.isArray(input.watchlist)
      ? [...new Set(input.watchlist.map(normalizeTicker).filter((symbol): symbol is string => symbol !== null))].slice(0, 40)
      : [...DEFAULT_WORKSPACE.watchlist],
  };
}
export function mergeWorkspace(raw: string | null, patch: Partial<WorkspacePreferences>) {
  return parseWorkspace(JSON.stringify({ ...parseWorkspace(raw), ...patch }));
}
