/**
 * Pure chart-study math. Every output array is index-aligned with the input
 * bars (null = not enough history), so the chart, legend and signal readout
 * can all look values up by bar index. Formulas follow the thinkorswim
 * built-ins they are named after so levels match what traders see there.
 */

export interface Bar {
  timestamp: string;
  close: number;
  volume: number;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  vwap?: number | null;
}

export type Series = (number | null)[];
export type VwapAnchor = "day" | "week" | "month";
export interface Cross { index: number; direction: "up" | "down" }

export function sma(values: number[], length: number): Series {
  const out: Series = new Array(values.length).fill(null);
  if (length < 1) return out;
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= length) sum -= values[i - length];
    if (i >= length - 1) out[i] = sum / length;
  }
  return out;
}

/** thinkorswim ExpAverage: seeded with the first value, plotted from bar one. */
export function ema(values: number[], length: number): Series {
  const k = 2 / (length + 1);
  let value = values[0];
  return values.map((close, i) => (value = i === 0 ? close : close * k + value * (1 - k)));
}

/** thinkorswim Momentum: close minus the close `length` bars earlier. */
export function momentum(values: number[], length: number): Series {
  return values.map((value, i) => (i >= length ? value - values[i - length] : null));
}

/** Wilder RSI, matching thinkorswim RSI(14) with Wilder's average. */
export function rsi(values: number[], length = 14): Series {
  const out: Series = new Array(values.length).fill(null);
  if (values.length <= length) return out;
  let gain = 0, loss = 0;
  for (let i = 1; i <= length; i++) {
    const change = values[i] - values[i - 1];
    gain += Math.max(change, 0); loss += Math.max(-change, 0);
  }
  gain /= length; loss /= length;
  out[length] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  for (let i = length + 1; i < values.length; i++) {
    const change = values[i] - values[i - 1];
    gain = (gain * (length - 1) + Math.max(change, 0)) / length;
    loss = (loss * (length - 1) + Math.max(-change, 0)) / length;
    out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  }
  return out;
}

/**
 * thinkorswim `Crosses(a, b, above)`: a > b on this bar and a <= b on the prior
 * bar (mirror for below). Bars where either side is missing never cross.
 */
export function crosses(a: Series, b: Series | number): Cross[] {
  const at = (i: number) => (typeof b === "number" ? b : b[i]);
  const out: Cross[] = [];
  for (let i = 1; i < a.length; i++) {
    const [a0, a1, b0, b1] = [a[i - 1], a[i], at(i - 1), at(i)];
    if (a0 == null || a1 == null || b0 == null || b1 == null) continue;
    if (a1 > b1 && a0 <= b0) out.push({ index: i, direction: "up" });
    else if (a1 < b1 && a0 >= b0) out.push({ index: i, direction: "down" });
  }
  return out;
}

const etDate = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
});

/** Trading-period id in New York time, like thinkorswim's GetYYYYMMDD roll. */
export function periodKey(timestamp: string, anchor: VwapAnchor): number {
  const [year, month, day] = etDate.format(new Date(timestamp)).split("-").map(Number);
  if (anchor === "month") return year * 12 + month;
  const days = Math.floor(Date.UTC(year, month - 1, day) / 86_400_000);
  // 1970-01-01 was a Thursday; +4 makes weeks roll on Sunday as in thinkorswim.
  return anchor === "week" ? Math.floor((days + 4) / 7) : days;
}

export interface VwapBands { vwap: Series; deviation: Series; upper: Series; lower: Series }

/**
 * thinkorswim VWAP study: volume-weighted mean of each bar's VWAP since the
 * period rolled, with bands at ±`deviations` volume-weighted standard
 * deviations. Bars without a feed VWAP fall back to HLC/3.
 */
export function vwapBands(bars: Bar[], deviations = 2, anchor: VwapAnchor = "day"): VwapBands {
  const n = bars.length;
  const result: VwapBands = { vwap: new Array(n).fill(null), deviation: new Array(n).fill(null), upper: new Array(n).fill(null), lower: new Array(n).fill(null) };
  let period: number | null = null, volume = 0, pv = 0, pv2 = 0;
  for (let i = 0; i < n; i++) {
    const bar = bars[i];
    const key = periodKey(bar.timestamp, anchor);
    if (key !== period) { period = key; volume = 0; pv = 0; pv2 = 0; }
    const price = bar.vwap ?? ((bar.high ?? bar.close) + (bar.low ?? bar.close) + bar.close) / 3;
    volume += bar.volume; pv += bar.volume * price; pv2 += bar.volume * price * price;
    if (volume <= 0) continue;
    const mean = pv / volume;
    const deviation = Math.sqrt(Math.max(pv2 / volume - mean * mean, 0));
    result.vwap[i] = mean;
    result.deviation[i] = deviation;
    result.upper[i] = mean + deviations * deviation;
    result.lower[i] = mean - deviations * deviation;
  }
  return result;
}

const minutes: Record<string, number> = { "1Min": 1, "5Min": 5, "15Min": 15 };

/** Index of the still-forming bar (if any). Daily bars form until the ET date changes. */
export function formingBarIndex(bars: Bar[], timeframe: string, now: number): number | null {
  const last = bars.at(-1);
  if (!last) return null;
  if (timeframe === "1Day") {
    return periodKey(last.timestamp, "day") >= periodKey(new Date(now).toISOString(), "day") ? bars.length - 1 : null;
  }
  const length = minutes[timeframe];
  if (!length) return null;
  return new Date(last.timestamp).getTime() + length * 60_000 > now ? bars.length - 1 : null;
}

export interface StudySettings {
  showVwap: boolean; vwapDeviation: number; vwapAnchor: VwapAnchor;
  showSmaCross: boolean; smaFast: number; smaSlow: number;
  showMomentum: boolean; momentumLength: number;
  showEma: boolean; showRsi: boolean;
}

export interface StudyValues {
  vwap: VwapBands | null; vwapAnchor: VwapAnchor;
  smaFast: Series | null; smaSlow: Series | null; smaCrosses: Cross[];
  ema18: Series | null; ema50: Series | null;
  momentum: Series | null; momentumCrosses: Cross[];
  rsi: Series | null;
}

/** Daily VWAP on a daily chart is just each bar's own VWAP, so it rolls monthly there. */
export function effectiveVwapAnchor(anchor: VwapAnchor, timeframe: string): VwapAnchor {
  return timeframe === "1Day" && anchor === "day" ? "month" : anchor;
}

export function computeStudies(bars: Bar[], settings: StudySettings, timeframe: string): StudyValues {
  const closes = bars.map((bar) => bar.close);
  const vwapAnchor = effectiveVwapAnchor(settings.vwapAnchor, timeframe);
  const smaFast = settings.showSmaCross ? sma(closes, settings.smaFast) : null;
  const smaSlow = settings.showSmaCross ? sma(closes, settings.smaSlow) : null;
  const mom = settings.showMomentum ? momentum(closes, settings.momentumLength) : null;
  return {
    vwap: settings.showVwap ? vwapBands(bars, settings.vwapDeviation, vwapAnchor) : null,
    vwapAnchor,
    smaFast, smaSlow,
    smaCrosses: smaFast && smaSlow ? crosses(smaFast, smaSlow) : [],
    ema18: settings.showEma ? ema(closes, 18) : null,
    ema50: settings.showEma ? ema(closes, 50) : null,
    momentum: mom,
    momentumCrosses: mom ? crosses(mom, 0) : [],
    rsi: settings.showRsi ? rsi(closes, 14) : null,
  };
}

export interface SignalChip { id: string; label: string; detail: string; tone: "bull" | "bear" | "neutral" }

/**
 * Plain-language state of each enabled study on the latest bar. A cross on a
 * still-forming bar is reported as unconfirmed, never as a completed signal.
 */
export function signalReadout(bars: Bar[], studies: StudyValues, settings: StudySettings, forming: number | null): SignalChip[] {
  const last = bars.length - 1;
  if (last < 0) return [];
  const chips: SignalChip[] = [];
  const ago = (cross?: Cross) => cross == null ? "no cross in view"
    : cross.index === forming ? "crossing on forming bar · unconfirmed"
    : `crossed ${last - cross.index === 0 ? "this bar" : `${last - cross.index} bars ago`}`;
  const vwap = studies.vwap?.vwap[last], dev = studies.vwap?.deviation[last];
  if (vwap != null && dev != null) {
    const z = dev > 0 ? (bars[last].close - vwap) / dev : 0;
    const stretched = Math.abs(z) >= settings.vwapDeviation;
    chips.push({
      id: "vwap", label: `VWAP ${z >= 0 ? "+" : ""}${z.toFixed(1)}σ`,
      detail: `${stretched ? "Outside" : "Inside"} ±${settings.vwapDeviation}σ band · ${studies.vwapAnchor} anchor · VWAP ${vwap.toFixed(2)}`,
      tone: stretched ? "neutral" : z >= 0 ? "bull" : "bear",
    });
  }
  const fast = studies.smaFast?.[last], slow = studies.smaSlow?.[last];
  if (fast != null && slow != null) {
    const bull = fast > slow;
    chips.push({
      id: "sma", label: `SMA ${settings.smaFast}/${settings.smaSlow} ${bull ? "▲" : "▼"}`,
      detail: `${settings.smaFast} ${bull ? "above" : "below"} ${settings.smaSlow} · ${ago(studies.smaCrosses.at(-1))}`,
      tone: bull ? "bull" : "bear",
    });
  }
  const mom = studies.momentum?.[last];
  if (mom != null) {
    chips.push({
      id: "momentum", label: `MOM(${settings.momentumLength}) ${mom >= 0 ? "+" : ""}${mom.toFixed(2)}`,
      detail: `${mom >= 0 ? "Above" : "Below"} zero · ${ago(studies.momentumCrosses.at(-1))}`,
      tone: mom > 0 ? "bull" : mom < 0 ? "bear" : "neutral",
    });
  }
  const r = studies.rsi?.[last];
  if (r != null) {
    // Zones are context, not reversal calls, so RSI never colors as a direction.
    chips.push({ id: "rsi", label: `RSI ${r.toFixed(0)}`, detail: r >= 70 ? "Overbought zone" : r <= 30 ? "Oversold zone" : "Neutral zone", tone: "neutral" });
  }
  return chips;
}
