export const WORKSPACE_KEY = "regimeshift.workspace.v1";
export interface WorkspacePreferences {
  symbol: string;
  timeframe: "1Min" | "5Min" | "15Min" | "1Day";
  candleLimit: 100 | 300 | 500 | 1000;
  rsiMode: "off" | "raw" | "quiet" | "reversal";
  lowVolFilter: boolean;
  showLevels: boolean;
  showGex: boolean;
  showIchimoku: boolean;
  showTargets: boolean;
  showVwap: boolean;
  vwapDeviation: 1 | 1.5 | 2 | 2.5 | 3;
  vwapAnchor: "day" | "week" | "month";
  showSmaCross: boolean;
  smaFast: number;
  smaSlow: number;
  showMomentum: boolean;
  momentumLength: number;
  showEma: boolean;
  showRsi: boolean;
  rail: "scanner" | "watchlist" | "sectors";
  dock: "positions" | "orders" | "account" | "options";
  side: "context" | "news";
  newsScope: "ticker" | "market";
  quoteSeconds: 0 | 1 | 5 | 10;
  watchlist: string[];
}
export const DEFAULT_WORKSPACE: WorkspacePreferences = {
  symbol: "SPY", timeframe: "5Min", candleLimit: 500, rsiMode: "quiet", lowVolFilter: false,
  showLevels: true, showGex: true, showIchimoku: false, showTargets: true,
  // thinkorswim study defaults: VWAP ±2σ, MovingAvgCrossover 15/30 SMA, Momentum 12.
  showVwap: true, vwapDeviation: 2, vwapAnchor: "day",
  showSmaCross: true, smaFast: 15, smaSlow: 30,
  showMomentum: true, momentumLength: 12,
  showEma: true, showRsi: false,
  rail: "scanner", dock: "positions", side: "context", newsScope: "ticker", quoteSeconds: 5,
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
  const flag = (key: keyof WorkspacePreferences) =>
    typeof input[key] === "boolean" ? input[key] as boolean : DEFAULT_WORKSPACE[key] as boolean;
  const length = (key: keyof WorkspacePreferences, max: number) => {
    const value = input[key];
    return typeof value === "number" && Number.isInteger(value) && value >= 1 && value <= max
      ? value : DEFAULT_WORKSPACE[key] as number;
  };
  return {
    symbol: normalizeTicker(input.symbol) ?? DEFAULT_WORKSPACE.symbol,
    timeframe: pick("timeframe", ["1Min", "5Min", "15Min", "1Day"], DEFAULT_WORKSPACE.timeframe),
    candleLimit: pick("candleLimit", [100, 300, 500, 1000], DEFAULT_WORKSPACE.candleLimit),
    rsiMode: pick("rsiMode", ["off", "raw", "quiet", "reversal"], DEFAULT_WORKSPACE.rsiMode),
    lowVolFilter: typeof input.lowVolFilter === "boolean" ? input.lowVolFilter : false,
    showLevels: typeof input.showLevels === "boolean" ? input.showLevels : true,
    showGex: typeof input.showGex === "boolean" ? input.showGex : true,
    showIchimoku: typeof input.showIchimoku === "boolean" ? input.showIchimoku : false,
    showTargets: typeof input.showTargets === "boolean" ? input.showTargets : true,
    showVwap: flag("showVwap"),
    vwapDeviation: pick("vwapDeviation", [1, 1.5, 2, 2.5, 3], DEFAULT_WORKSPACE.vwapDeviation),
    vwapAnchor: pick("vwapAnchor", ["day", "week", "month"], DEFAULT_WORKSPACE.vwapAnchor),
    showSmaCross: flag("showSmaCross"),
    smaFast: length("smaFast", 200),
    smaSlow: length("smaSlow", 400),
    showMomentum: flag("showMomentum"),
    momentumLength: length("momentumLength", 200),
    showEma: flag("showEma"),
    showRsi: flag("showRsi"),
    rail: pick("rail", ["scanner", "watchlist", "sectors"], "scanner"),
    dock: pick("dock", ["positions", "orders", "account", "options"], "positions"),
    side: pick("side", ["context", "news"], "context"),
    newsScope: pick("newsScope", ["ticker", "market"], "ticker"),
    quoteSeconds: pick("quoteSeconds", [0, 1, 5, 10], 5),
    watchlist: Array.isArray(input.watchlist)
      ? [...new Set(input.watchlist.map(normalizeTicker).filter((symbol): symbol is string => symbol !== null))].slice(0, 40)
      : [...DEFAULT_WORKSPACE.watchlist],
  };
}
export function mergeWorkspace(raw: string | null, patch: Partial<WorkspacePreferences>) {
  return parseWorkspace(JSON.stringify({ ...parseWorkspace(raw), ...patch }));
}
