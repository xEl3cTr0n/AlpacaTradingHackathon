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
  const values = [
    { title: "Put wall", price: micro?.put_wall, color: "#ef5350", dashed: false },
    { title: "Call wall", price: micro?.call_wall, color: "#fbbf24", dashed: false },
    { title: "Key gamma", price: micro?.key_gamma_strike, color: "#d946ef", dashed: true },
    { title: "Hedge wall", price: micro?.hedge_wall, color: "#a78bfa", dashed: true },
    { title: "Swing low", price: swing?.swing_low, color: "#38bdf8", dashed: true },
    { title: "Swing high", price: swing?.swing_high, color: "#35dc7b", dashed: true },
  ];
  return values.flatMap((item) => typeof item.price === "number" && Number.isFinite(item.price) && item.price > 0
    ? [{ ...item, price: item.price }] : []);
}

export function nearbyGexRows(context: ChartContextSnapshot | null, limit = 21) {
  const spot = context?.underlying_price;
  if (!spot || !Number.isFinite(spot)) return [];
  return [...(context?.options_microstructure?.gex_by_strike ?? [])]
    .filter((row) => [row.strike, row.call_gex, row.put_gex, row.net_gex].every(Number.isFinite))
    .sort((a, b) => Math.abs(a.strike - spot) - Math.abs(b.strike - spot))
    .slice(0, limit).sort((a, b) => a.strike - b.strike);
}
