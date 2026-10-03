"use client";

import { BarChart3, RotateCcw, Search, SlidersHorizontal } from "lucide-react";
import {
  BaselineSeries,
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineStyle,
  TickMarkType,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type LogicalRange,
  type MouseEventParams,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import useSWR from "swr";
import type { ChartSnapshot, DecisionSnapshot, LiveMarketTick, PricePoint } from "@/lib/types";
import { chartContextLevels } from "@/lib/chart-context";
import {
  computeStudies,
  formingBarIndex,
  signalReadout,
  type Series,
  type StudySettings,
  type StudyValues,
} from "@/lib/indicators";
import { IchimokuCloudPrimitive } from "@/lib/ichimoku-cloud-plugin";
import { useChartContext } from "@/lib/use-chart-context";
import { DEFAULT_WORKSPACE, type WorkspacePreferences } from "@/lib/workspace-preferences";
import { useWorkspacePreferences } from "@/lib/use-workspace-preferences";
import { ChartContextPanel } from "./chart-context-panel";
import { ChartFreshness } from "./chart-freshness";

type Timeframe = ChartSnapshot["timeframe"];
type Line = ISeriesApi<"Line">;

const timeframes: Timeframe[] = ["1Min", "5Min", "15Min", "1Day"];

/** Study palette. Shared by series, legend swatches and the studies menu. */
const COLORS = {
  up: "#26a69a", down: "#ef5350",
  vwap: "#e879f9", vwapBand: "rgba(232, 121, 249, .55)",
  smaFast: "#facc15", smaSlow: "#f97316",
  ema18: "#38bdf8", ema50: "#a78bfa",
  rsi: "#c084fc", last: "#e2e8f0",
};

const fetcher = async (url: string): Promise<ChartSnapshot> => {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Chart data returned ${response.status}`);
  return response.json() as Promise<ChartSnapshot>;
};

const liveFetcher = async (url: string): Promise<LiveMarketTick> => {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Live tape returned ${response.status}`);
  return response.json() as Promise<LiveMarketTick>;
};

const toTime = (timestamp: string): UTCTimestamp =>
  Math.floor(new Date(timestamp).getTime() / 1000) as UTCTimestamp;

// Axis and crosshair labels in exchange time, not UTC.
const zone = { timeZone: "America/New_York" } as const;
const etClock = new Intl.DateTimeFormat("en-US", { ...zone, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const etDay = new Intl.DateTimeFormat("en-US", { ...zone, month: "short", day: "numeric" });
const etMonth = new Intl.DateTimeFormat("en-US", { ...zone, month: "short" });
const etYear = new Intl.DateTimeFormat("en-US", { ...zone, year: "numeric" });
const etStamp = new Intl.DateTimeFormat("en-US", { ...zone, month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const etDate = new Intl.DateTimeFormat("en-US", { ...zone, month: "short", day: "numeric", year: "numeric" });
const asDate = (time: Time) => new Date((time as number) * 1000);

function ichimoku(points: PricePoint[]) {
  const tenkanData: { time: UTCTimestamp; value: number }[] = [];
  const kijunData: { time: UTCTimestamp; value: number }[] = [];
  const spanAData: { time: UTCTimestamp; value: number }[] = [];
  const spanBData: { time: UTCTimestamp; value: number }[] = [];
  const chikouData: { time: UTCTimestamp; value: number }[] = [];
  const cloudData: { time: UTCTimestamp; spanA: number; spanB: number }[] = [];
  const midpoint = (from: number, to: number) => {
    let high = -Infinity, low = Infinity;
    for (let j = from; j <= to; j++) {
      high = Math.max(high, points[j].high ?? points[j].close);
      low = Math.min(low, points[j].low ?? points[j].close);
    }
    return +((high + low) / 2).toFixed(2);
  };
  for (let i = 0; i < points.length; i++) {
    const t = toTime(points[i].timestamp);
    chikouData.push({ time: t, value: points[i].close });
    if (i < 8) continue;
    const tenkan = midpoint(i - 8, i);
    tenkanData.push({ time: t, value: tenkan });
    if (i < 25) continue;
    const kijun = midpoint(i - 25, i);
    kijunData.push({ time: t, value: kijun });
    const spanA = +((tenkan + kijun) / 2).toFixed(2);
    spanAData.push({ time: t, value: spanA });
    // Span B: 52-bar midpoint, or the longest available window before 52 bars exist.
    const spanB = midpoint(i - Math.min(i, 51), i);
    if (i >= 51) spanBData.push({ time: t, value: spanB });
    cloudData.push({ time: t, spanA, spanB });
  }
  return { tenkanData, kijunData, spanAData, spanBData, chikouData, cloudData };
}

/** Crosshair bar index, kept outside React state so mouse moves only re-render the legend. */
function createHoverStore() {
  let index: number | null = null;
  const listeners = new Set<() => void>();
  return {
    get: () => index,
    set(next: number | null) {
      if (next === index) return;
      index = next;
      listeners.forEach((listener) => listener());
    },
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    },
  };
}
type HoverStore = ReturnType<typeof createHoverStore>;

interface ChartHandles {
  chart: IChartApi;
  candles: ISeriesApi<"Candlestick">;
  volume: ISeriesApi<"Histogram">;
  candleMarkers: ISeriesMarkersPluginApi<Time>;
  lines: Partial<Record<"vwap" | "vwapUpper" | "vwapLower" | "smaFast" | "smaSlow" | "ema18" | "ema50" | "tenkan" | "kijun" | "spanA" | "spanB" | "chikou" | "rsi", Line>>;
  momentum?: ISeriesApi<"Baseline">;
  momentumMarkers?: ISeriesMarkersPluginApi<Time>;
  cloud?: IchimokuCloudPrimitive;
  times: Map<number, number>;
  needsRange: boolean;
}

const fmt = (value: number | null | undefined, digits = 2) => (value == null ? "—" : value.toFixed(digits));
const volumeLabel = (value: number) => Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(value);

function ChartLegend({ store, bars, studies, settings, symbol, timeframe }: {
  store: HoverStore; bars: PricePoint[]; studies: StudyValues; settings: StudySettings; symbol: string; timeframe: Timeframe;
}) {
  const hovered = useSyncExternalStore(store.subscribe, store.get, store.get);
  const index = hovered ?? bars.length - 1;
  const bar = bars[index];
  if (!bar) return null;
  const previous = bars[index - 1];
  const change = previous ? (bar.close / previous.close - 1) * 100 : null;
  const at = (series: Series | null | undefined) => series?.[index];
  const vwap = studies.vwap;
  const items: { label: string; value: string; color: string }[] = [];
  if (vwap) items.push({ label: `VWAP ±${settings.vwapDeviation}σ`, value: `${fmt(at(vwap.vwap))} (${fmt(at(vwap.lower))}–${fmt(at(vwap.upper))})`, color: COLORS.vwap });
  if (studies.smaFast) items.push({ label: `SMA ${settings.smaFast}`, value: fmt(at(studies.smaFast)), color: COLORS.smaFast });
  if (studies.smaSlow) items.push({ label: `SMA ${settings.smaSlow}`, value: fmt(at(studies.smaSlow)), color: COLORS.smaSlow });
  if (studies.ema18) items.push({ label: "EMA 18", value: fmt(at(studies.ema18)), color: COLORS.ema18 });
  if (studies.ema50) items.push({ label: "EMA 50", value: fmt(at(studies.ema50)), color: COLORS.ema50 });
  if (studies.momentum) items.push({ label: `MOM ${settings.momentumLength}`, value: fmt(at(studies.momentum)), color: (at(studies.momentum) ?? 0) >= 0 ? COLORS.up : COLORS.down });
  if (studies.rsi) items.push({ label: "RSI 14", value: fmt(at(studies.rsi), 1), color: COLORS.rsi });
  const up = bar.close >= (bar.open ?? bar.close);
  return <div className="chart-legend" aria-hidden="true">
    <div className="legend-ohlc">
      <strong>{symbol} · {timeframe.replace("Min", "m").replace("Day", "D")}</strong>
      <span>{timeframe === "1Day" ? etDate.format(new Date(bar.timestamp)) : etStamp.format(new Date(bar.timestamp))} ET</span>
      <span>O <b className={up ? "positive" : "negative"}>{fmt(bar.open)}</b></span>
      <span>H <b className={up ? "positive" : "negative"}>{fmt(bar.high)}</b></span>
      <span>L <b className={up ? "positive" : "negative"}>{fmt(bar.low)}</b></span>
      <span>C <b className={up ? "positive" : "negative"}>{fmt(bar.close)}</b></span>
      <span>V <b>{volumeLabel(bar.volume)}</b></span>
      {change != null && <span className={change >= 0 ? "positive" : "negative"}>{change >= 0 ? "+" : ""}{change.toFixed(2)}%</span>}
    </div>
    {items.length > 0 && <div className="legend-studies">{items.map((item) => <span key={item.label}><i style={{ background: item.color }} />{item.label} <b>{item.value}</b></span>)}</div>}
  </div>;
}

function LengthField({ label, value, max, onCommit }: { label: string; value: number; max: number; onCommit: (value: number) => void }) {
  const [draft, setDraft] = useState(String(value));
  const [synced, setSynced] = useState(value);
  if (synced !== value) { setSynced(value); setDraft(String(value)); }
  return <label className="study-length">{label}<input type="number" inputMode="numeric" min={1} max={max} step={1} value={draft}
    onChange={(event) => {
      setDraft(event.target.value);
      const next = Number(event.target.value);
      if (Number.isInteger(next) && next >= 1 && next <= max) onCommit(next);
    }}
    onBlur={() => setDraft(String(value))} /></label>;
}

function StudiesMenu({ preferences, update }: { preferences: WorkspacePreferences; update: (patch: Partial<WorkspacePreferences>) => void }) {
  const menu = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const close = (event: Event) => {
      const element = menu.current;
      if (!element?.open) return;
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !element.contains(event.target as Node)) element.open = false;
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", close); };
  }, []);
  const p = preferences;
  const swatch = (color: string) => <i className="study-swatch" style={{ background: color }} />;
  return <details className="study-menu" ref={menu}>
    <summary><SlidersHorizontal size={13} aria-hidden="true" />Studies</summary>
    <div className="study-panel" role="group" aria-label="Chart studies">
      <div className="study-row">
        <label><input type="checkbox" checked={p.showVwap} onChange={(e) => update({ showVwap: e.target.checked })} />{swatch(COLORS.vwap)}VWAP bands</label>
        <label className="study-length">σ<select value={p.vwapDeviation} onChange={(e) => update({ vwapDeviation: Number(e.target.value) as WorkspacePreferences["vwapDeviation"] })}>{[1, 1.5, 2, 2.5, 3].map((v) => <option key={v} value={v}>±{v}</option>)}</select></label>
        <label className="study-length">Reset<select value={p.vwapAnchor} onChange={(e) => update({ vwapAnchor: e.target.value as WorkspacePreferences["vwapAnchor"] })}><option value="day">Day</option><option value="week">Week</option><option value="month">Month</option></select></label>
      </div>
      <div className="study-row">
        <label><input type="checkbox" checked={p.showSmaCross} onChange={(e) => update({ showSmaCross: e.target.checked })} />{swatch(COLORS.smaFast)}{swatch(COLORS.smaSlow)}SMA crossover</label>
        <LengthField label="Fast" value={p.smaFast} max={200} onCommit={(v) => update({ smaFast: v })} />
        <LengthField label="Slow" value={p.smaSlow} max={400} onCommit={(v) => update({ smaSlow: v })} />
      </div>
      <div className="study-row">
        <label><input type="checkbox" checked={p.showMomentum} onChange={(e) => update({ showMomentum: e.target.checked })} />{swatch(COLORS.up)}Momentum pane</label>
        <LengthField label="Length" value={p.momentumLength} max={200} onCommit={(v) => update({ momentumLength: v })} />
      </div>
      <div className="study-row">
        <label><input type="checkbox" checked={p.showRsi} onChange={(e) => update({ showRsi: e.target.checked })} />{swatch(COLORS.rsi)}RSI 14 pane</label>
        <label><input type="checkbox" checked={p.showEma} onChange={(e) => update({ showEma: e.target.checked })} />{swatch(COLORS.ema18)}{swatch(COLORS.ema50)}EMA 18/50 · scanner basis</label>
      </div>
      <div className="study-row">
        <label><input type="checkbox" checked={p.showIchimoku} onChange={(e) => update({ showIchimoku: e.target.checked })} />Ichimoku cloud</label>
        <label><input type="checkbox" checked={p.showLevels} onChange={(e) => update({ showLevels: e.target.checked })} />Options &amp; swing levels</label>
        <label><input type="checkbox" checked={p.showTargets} onChange={(e) => update({ showTargets: e.target.checked })} />Implied-move targets</label>
      </div>
      <div className="study-row">
        <label className="study-length">RSI + volume marks<select value={p.rsiMode} onChange={(e) => update({ rsiMode: e.target.value as WorkspacePreferences["rsiMode"] })}><option value="off">Off</option><option value="raw">All extremes</option><option value="quiet">One per excursion</option><option value="reversal">Price-confirmed reversals</option></select></label>
        <label><input type="checkbox" checked={p.lowVolFilter} onChange={(e) => update({ lowVolFilter: e.target.checked })} />Low-vol filter (ATR/price ≥0.5%)</label>
      </div>
      <p>Defaults mirror thinkorswim: VWAP ±2σ (daily reset, ET), MovingAvgCrossover SMA 15/30, Momentum 12. Arrows mark completed bars only. Studies are research context, not orders.</p>
      <button type="button" className="secondary-action" onClick={() => update({
        showVwap: DEFAULT_WORKSPACE.showVwap, vwapDeviation: DEFAULT_WORKSPACE.vwapDeviation, vwapAnchor: DEFAULT_WORKSPACE.vwapAnchor,
        showSmaCross: DEFAULT_WORKSPACE.showSmaCross, smaFast: DEFAULT_WORKSPACE.smaFast, smaSlow: DEFAULT_WORKSPACE.smaSlow,
        showMomentum: DEFAULT_WORKSPACE.showMomentum, momentumLength: DEFAULT_WORKSPACE.momentumLength,
        showEma: DEFAULT_WORKSPACE.showEma, showRsi: DEFAULT_WORKSPACE.showRsi, showIchimoku: DEFAULT_WORKSPACE.showIchimoku,
      })}><RotateCcw size={12} aria-hidden="true" />Reset studies</button>
    </div>
  </details>;
}

export function MarketChartTerminal({
  snapshot,
  tick,
  quoteRefreshMs = 5000,
  symbol,
  onSymbolChange,
  compact = false,
}: {
  snapshot: DecisionSnapshot;
  tick?: LiveMarketTick;
  quoteRefreshMs?: number;
  symbol?: string;
  onSymbolChange?: (symbol: string) => void;
  /** Compact workspace mode: the host renders options context in its own side panel. */
  compact?: boolean;
}) {
  const [preferences, updatePreferences] = useWorkspacePreferences();
  const timeframe = preferences.timeframe;
  const [localSymbol, setLocalSymbol] = useState(snapshot.market.symbol);
  const chartSymbol = symbol ?? localSymbol;
  const [renderError, setRenderError] = useState(false);
  const [renderAttempt, setRenderAttempt] = useState(0);
  const [now, setNow] = useState<number | null>(null);
  const rsiMode = preferences.rsiMode;
  const containerRef = useRef<HTMLDivElement>(null);
  const handlesRef = useRef<ChartHandles | null>(null);
  const savedRangeRef = useRef<{ key: string; range: LogicalRange } | null>(null);
  const [hover] = useState(createHoverStore);
  const candleLimit = preferences.candleLimit ?? 500;
  const key = `/api/v1/chart?symbol=${encodeURIComponent(chartSymbol)}&timeframe=${timeframe}&limit=${candleLimit}&rsi_low_vol_filter=${preferences.lowVolFilter}`;
  const { data, error, isLoading, isValidating, mutate } = useSWR(key, fetcher, {
    refreshInterval: timeframe === "1Min" ? 30_000 : 60_000,
    dedupingInterval: 15_000,
    refreshWhenHidden: false,
    refreshWhenOffline: false,
    keepPreviousData: false,
    errorRetryCount: 2,
  });
  const liveKey = tick?.symbol === chartSymbol ? null : `/api/v1/live-tape?symbol=${encodeURIComponent(chartSymbol)}`;
  const { data: chartTick, error: tickError } = useSWR(liveKey, liveFetcher, {
    refreshInterval: quoteRefreshMs,
    dedupingInterval: Math.max(750, quoteRefreshMs * 0.8),
    refreshWhenHidden: false,
    refreshWhenOffline: false,
    revalidateOnFocus: quoteRefreshMs > 0,
    errorRetryCount: 2,
  });
  const activeTick = tick?.symbol === chartSymbol ? tick : chartTick?.symbol === chartSymbol ? chartTick : undefined;
  const { context, failed: contextFailed, loading: contextLoading, refresh: refreshContext } = useChartContext(chartSymbol);

  const studySettings = useMemo<StudySettings>(() => ({
    showVwap: preferences.showVwap, vwapDeviation: preferences.vwapDeviation, vwapAnchor: preferences.vwapAnchor,
    showSmaCross: preferences.showSmaCross, smaFast: preferences.smaFast, smaSlow: preferences.smaSlow,
    showMomentum: preferences.showMomentum, momentumLength: preferences.momentumLength,
    showEma: preferences.showEma, showRsi: preferences.showRsi,
  }), [preferences.showVwap, preferences.vwapDeviation, preferences.vwapAnchor, preferences.showSmaCross, preferences.smaFast,
    preferences.smaSlow, preferences.showMomentum, preferences.momentumLength, preferences.showEma, preferences.showRsi]);

  const overlayLevels = useMemo(() => {
    if (!preferences.showLevels && !preferences.showTargets) return [];
    const isTarget = (title: string) => /Session|Weekly|Extreme|Prior Day/.test(title);
    return chartContextLevels(context).filter((level) =>
      // The VWAP study already draws the session VWAP with its bands.
      !(preferences.showVwap && level.title === "Session VWAP")
      && (isTarget(level.title) ? preferences.showTargets : preferences.showLevels));
  }, [context, preferences.showLevels, preferences.showTargets, preferences.showVwap]);

  const bars = useMemo(
    () => data?.bars ?? (timeframe === "1Day" && chartSymbol === snapshot.market.symbol ? snapshot.market.prices : []),
    [data?.bars, snapshot.market.prices, snapshot.market.symbol, timeframe, chartSymbol],
  );
  const studies = useMemo(() => computeStudies(bars, studySettings, timeframe), [bars, studySettings, timeframe]);
  // Until the clock is known, treat the newest bar as possibly unfinished.
  const forming = now == null ? (bars.length ? bars.length - 1 : null) : formingBarIndex(bars, timeframe, now);
  const chips = useMemo(() => signalReadout(bars, studies, studySettings, forming), [bars, studies, studySettings, forming]);
  const latest = bars.at(-1);

  useEffect(() => {
    const initial = setTimeout(() => setNow(Date.now()), 0);
    const timer = setInterval(() => setNow(Date.now()), 15_000);
    return () => { clearTimeout(initial); clearInterval(timer); };
  }, []);

  // Chart structure: rebuilt only when the ticker, timeframe or set of panes
  // changes. Bar refreshes reuse it, so the view and crosshair do not reset.
  const layoutKey = [preferences.showVwap, preferences.showSmaCross, preferences.showEma, preferences.showMomentum,
    preferences.showRsi, preferences.showIchimoku].map(Number).join("");
  const viewKey = `${chartSymbol}:${timeframe}:${candleLimit}`;
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let chart: IChartApi;
    try {
      chart = createChart(container, {
        autoSize: false,
        width: container.clientWidth,
        height: container.clientHeight || 520,
        layout: {
          attributionLogo: true,
          background: { type: ColorType.Solid, color: "#070c18" },
          textColor: "#94a3b8",
          fontFamily: "var(--font-mono), monospace",
          panes: { separatorColor: "#26334c", separatorHoverColor: "rgba(56, 189, 248, .25)", enableResize: true },
        },
        grid: { vertLines: { color: "rgba(38, 51, 76, .42)" }, horzLines: { color: "rgba(38, 51, 76, .42)" } },
        rightPriceScale: { borderColor: "#26334c" },
        crosshair: {
          mode: CrosshairMode.Normal,
          vertLine: { color: "rgba(148, 163, 184, .45)", labelBackgroundColor: "#26334c" },
          horzLine: { color: "rgba(148, 163, 184, .45)", labelBackgroundColor: "#26334c" },
        },
        localization: { timeFormatter: (time: Time) => (timeframe === "1Day" ? etDate : etStamp).format(asDate(time)) },
        timeScale: {
          borderColor: "#26334c",
          timeVisible: timeframe !== "1Day",
          secondsVisible: false,
          rightOffset: 4,
          tickMarkFormatter: (time: Time, type: TickMarkType) => {
            const date = asDate(time);
            if (type === TickMarkType.Year) return etYear.format(date);
            if (type === TickMarkType.Month) return etMonth.format(date);
            if (type === TickMarkType.DayOfMonth || timeframe === "1Day") return etDay.format(date);
            return etClock.format(date);
          },
        },
      });
    } catch {
      const timer = setTimeout(() => setRenderError(true), 0);
      return () => clearTimeout(timer);
    }
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: COLORS.up, downColor: COLORS.down, borderUpColor: COLORS.up, borderDownColor: COLORS.down,
      wickUpColor: COLORS.up, wickDownColor: COLORS.down, priceLineVisible: false,
    });
    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" }, priceScaleId: "volume", lastValueVisible: false, priceLineVisible: false,
    });
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    const line = (color: string, width: 1 | 2, style: LineStyle = LineStyle.Solid, pane = 0) => chart.addSeries(LineSeries, {
      color, lineWidth: width, lineStyle: style, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
    }, pane);
    const handles: ChartHandles = {
      chart, candles, volume, candleMarkers: createSeriesMarkers(candles, []), lines: {}, times: new Map(), needsRange: true,
    };
    if (preferences.showVwap) {
      handles.lines.vwapUpper = line(COLORS.vwapBand, 1, LineStyle.Dashed);
      handles.lines.vwapLower = line(COLORS.vwapBand, 1, LineStyle.Dashed);
      handles.lines.vwap = line(COLORS.vwap, 2);
    }
    if (preferences.showEma) {
      handles.lines.ema50 = line(COLORS.ema50, 1);
      handles.lines.ema18 = line(COLORS.ema18, 1);
    }
    if (preferences.showSmaCross) {
      handles.lines.smaSlow = line(COLORS.smaSlow, 2);
      handles.lines.smaFast = line(COLORS.smaFast, 2);
    }
    if (preferences.showIchimoku) {
      handles.cloud = new IchimokuCloudPrimitive([]);
      candles.attachPrimitive(handles.cloud);
      handles.lines.tenkan = line("#38bdf8", 1);
      handles.lines.kijun = line("#ec4899", 2);
      handles.lines.spanA = line("#34d399", 1, LineStyle.Dotted);
      handles.lines.spanB = line("#f43f5e", 1, LineStyle.Dotted);
      handles.lines.chikou = line("#c084fc", 1, LineStyle.Dashed);
    }
    let pane = 1;
    if (preferences.showMomentum) {
      handles.momentum = chart.addSeries(BaselineSeries, {
        baseValue: { type: "price", price: 0 }, lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
        topLineColor: COLORS.up, topFillColor1: "rgba(38, 166, 154, .32)", topFillColor2: "rgba(38, 166, 154, .04)",
        bottomLineColor: COLORS.down, bottomFillColor1: "rgba(239, 83, 80, .04)", bottomFillColor2: "rgba(239, 83, 80, .32)",
      }, pane++);
      handles.momentum.createPriceLine({ price: 0, color: "#475569", lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: false, title: "" });
      handles.momentumMarkers = createSeriesMarkers(handles.momentum, []);
    }
    if (preferences.showRsi) {
      const rsi = line(COLORS.rsi, 1, LineStyle.Solid, pane++);
      rsi.applyOptions({ lastValueVisible: true });
      for (const price of [70, 30]) rsi.createPriceLine({ price, color: "#475569", lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: true, title: "" });
      handles.lines.rsi = rsi;
    }
    const paneList = chart.panes();
    paneList[0]?.setStretchFactor(paneList.length > 2 ? 3.2 : 3.6);
    const onCrosshair = (param: MouseEventParams<Time>) => {
      hover.set(param.time == null ? null : handles.times.get(param.time as number) ?? null);
    };
    chart.subscribeCrosshairMove(onCrosshair);
    const resizeObserver = new ResizeObserver(() => chart.applyOptions({ width: container.clientWidth, height: container.clientHeight }));
    resizeObserver.observe(container);
    handlesRef.current = handles;
    return () => {
      const range = chart.timeScale().getVisibleLogicalRange();
      if (range) savedRangeRef.current = { key: viewKey, range };
      chart.unsubscribeCrosshairMove(onCrosshair);
      resizeObserver.disconnect();
      handlesRef.current = null;
      hover.set(null);
      chart.remove();
    };
    // layoutKey captures every structural preference read above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartSymbol, timeframe, layoutKey, renderAttempt, hover]);

  // Data: setData on the existing series for every bar or study refresh.
  useEffect(() => {
    const handles = handlesRef.current;
    if (!handles) return;
    const times = bars.map((bar) => toTime(bar.timestamp));
    handles.times = new Map(times.map((time, index) => [time as number, index]));
    handles.candles.setData(bars.map((bar, i) => ({
      time: times[i], open: bar.open ?? bar.close, high: bar.high ?? bar.close, low: bar.low ?? bar.close, close: bar.close,
    })));
    handles.volume.setData(bars.map((bar, i) => ({
      time: times[i], value: bar.volume, color: (bar.close >= (bar.open ?? bar.close) ? COLORS.up : COLORS.down) + "55",
    })));
    const plot = (series: Line | ISeriesApi<"Baseline"> | undefined, values: Series | null | undefined) => {
      series?.setData((values ?? []).flatMap((value, i) => (value == null ? [] : [{ time: times[i], value }])));
    };
    const { lines } = handles;
    plot(lines.vwap, studies.vwap?.vwap);
    plot(lines.vwapUpper, studies.vwap?.upper);
    plot(lines.vwapLower, studies.vwap?.lower);
    plot(lines.smaFast, studies.smaFast);
    plot(lines.smaSlow, studies.smaSlow);
    plot(lines.ema18, studies.ema18);
    plot(lines.ema50, studies.ema50);
    plot(handles.momentum, studies.momentum);
    plot(lines.rsi, studies.rsi);
    if (handles.cloud) {
      const cloud = ichimoku(bars);
      handles.cloud.setData(cloud.cloudData);
      lines.tenkan?.setData(cloud.tenkanData);
      lines.kijun?.setData(cloud.kijunData);
      lines.spanA?.setData(cloud.spanAData);
      lines.spanB?.setData(cloud.spanBData);
      lines.chikou?.setData(cloud.chikouData);
    }

    const markers: SeriesMarker<Time>[] = (data?.volume_rsi_signals ?? []).flatMap((signal) => {
      const side = rsiMode === "raw" ? signal.raw_signal : rsiMode === "quiet" ? signal.quiet_signal
        : rsiMode === "reversal" ? (signal.context === "reversal_down" ? "overbought" : signal.context === "reversal_up" ? "oversold" : "none") : "none";
      if (side === "none") return [];
      const high = side === "overbought";
      return [{ time: toTime(signal.as_of), position: high ? "aboveBar" : "belowBar",
        color: high ? "#fb7185" : "#35dc7b", shape: high ? "arrowDown" : "arrowUp",
        text: rsiMode === "reversal" ? (high ? "Rev ↓" : "Rev ↑") : high ? "OB" : "OS" }] as SeriesMarker<Time>[];
    });
    // Crossovers on a still-forming bar can undo themselves, so only completed bars get arrows.
    for (const cross of studies.smaCrosses) {
      if (cross.index === forming) continue;
      const up = cross.direction === "up";
      markers.push({ time: times[cross.index], position: up ? "belowBar" : "aboveBar", shape: up ? "arrowUp" : "arrowDown",
        color: up ? COLORS.smaFast : COLORS.smaSlow, text: up ? "MA↑" : "MA↓" });
    }
    handles.candleMarkers.setMarkers(markers.sort((a, b) => (a.time as number) - (b.time as number)));
    handles.momentumMarkers?.setMarkers(studies.momentumCrosses.filter((cross) => cross.index !== forming).map((cross) => {
      const up = cross.direction === "up";
      return { time: times[cross.index], position: up ? "belowBar" : "aboveBar", shape: up ? "arrowUp" : "arrowDown", color: up ? COLORS.up : COLORS.down };
    }));

    if (handles.needsRange && bars.length) {
      handles.needsRange = false;
      const saved = savedRangeRef.current;
      if (saved?.key === viewKey) handles.chart.timeScale().setVisibleLogicalRange(saved.range);
      else if (bars.length > 120) handles.chart.timeScale().setVisibleLogicalRange({ from: bars.length - 120, to: bars.length + 4 });
      else handles.chart.timeScale().fitContent();
    }
  }, [bars, studies, forming, data?.volume_rsi_signals, rsiMode, viewKey, chartSymbol, timeframe, layoutKey, renderAttempt]);

  // Context levels as price lines; replaced only when the levels change.
  useEffect(() => {
    const handles = handlesRef.current;
    if (!handles) return;
    const lines = overlayLevels.map(({ title, price, color, dashed }) =>
      handles.candles.createPriceLine({ price, color, lineStyle: dashed ? LineStyle.Dashed : LineStyle.Solid, lineWidth: 1, title }));
    return () => { if (handlesRef.current === handles) lines.forEach((line) => handles.candles.removePriceLine(line)); };
  }, [overlayLevels, chartSymbol, timeframe, layoutKey, renderAttempt]);

  // Latest trade as its own line. Quotes never rewrite or fabricate candles.
  const lastPrice = activeTick?.price;
  useEffect(() => {
    const handles = handlesRef.current;
    if (!handles || lastPrice == null) return;
    const line = handles.candles.createPriceLine({ price: lastPrice, color: COLORS.last, lineWidth: 1, lineStyle: LineStyle.Dotted, axisLabelVisible: true, title: "LAST" });
    return () => { if (handlesRef.current === handles) handles.candles.removePriceLine(line); };
  }, [lastPrice, chartSymbol, timeframe, layoutKey, renderAttempt]);

  const submitSymbol = (value: string) => {
    const normalized = value.trim().toUpperCase();
    if (/^[A-Z.]{1,10}$/.test(normalized)) {
      setLocalSymbol(normalized);
      onSymbolChange?.(normalized);
    }
  };
  const focusRecent = () => {
    const chart = handlesRef.current?.chart;
    if (!chart || !bars.length) return;
    if (bars.length > 120) chart.timeScale().setVisibleLogicalRange({ from: bars.length - 120, to: bars.length + 4 });
    else chart.timeScale().fitContent();
  };
  const paneCount = Number(preferences.showMomentum) + Number(preferences.showRsi);

  return (
    <section className={compact ? "market-terminal compact-chart" : "market-terminal"} aria-labelledby="market-chart-title">
      <div className="chart-terminal-toolbar">
        <div className="chart-title">
          {!compact && <p className="eyebrow">Alpaca market data</p>}
          <h2 id="market-chart-title">{chartSymbol}{compact ? "" : " chart terminal"}</h2>
          <div className="chart-quote">
            <strong>{activeTick ? `$${activeTick.price.toFixed(2)}` : "—"}</strong>
            <span className={(activeTick?.day_change_pct ?? 0) >= 0 ? "positive" : "negative"}>
              {activeTick?.day_change_pct == null ? "—" : `${activeTick.day_change_pct >= 0 ? "+" : ""}${activeTick.day_change_pct.toFixed(2)}%`}
            </span>
          </div>
        </div>
        {!compact && <form key={chartSymbol} className="chart-symbol-search" onSubmit={(event) => { event.preventDefault(); submitSymbol(String(new FormData(event.currentTarget).get("ticker") ?? "")); }}>
          <label htmlFor="chart-symbol">Ticker</label>
          <div><input id="chart-symbol" name="ticker" defaultValue={chartSymbol} pattern="[A-Za-z.]{1,10}" required maxLength={10} spellCheck={false} aria-label="Search chart ticker" /><button type="submit" aria-label="Load ticker chart"><Search size={15} aria-hidden="true" /></button></div>
        </form>}
        <div className="range-tabs" role="group" aria-label="Chart timeframe">
          {timeframes.map((item) => (
            <button key={item} type="button" className={timeframe === item ? "active" : ""} aria-pressed={timeframe === item} onClick={() => updatePreferences({ timeframe: item })}>
              {item.replace("Min", "m").replace("Day", "D")}
            </button>
          ))}
        </div>
        <div className="chart-view-actions">
          <StudiesMenu preferences={preferences} update={updatePreferences} />
          <label className="chart-select" title="Candles of history to load">Bars<select value={candleLimit} onChange={(event) => updatePreferences({ candleLimit: Number(event.target.value) as typeof candleLimit })}>{([100, 300, 500, 1000] as const).map((count) => <option key={count} value={count}>{count}</option>)}</select></label>
          <button type="button" onClick={focusRecent} title="Focus on the most recent 120 candles">Recent</button>
          <button type="button" onClick={() => handlesRef.current?.chart.timeScale().fitContent()} title="Fit all loaded candles">Fit</button>
          <label className="chart-select" title="Latest-trade polling interval">Quotes<select value={preferences.quoteSeconds} onChange={(event) => updatePreferences({ quoteSeconds: Number(event.target.value) as 0 | 1 | 5 | 10 })}><option value={0}>Paused</option><option value={1}>1s</option><option value={5}>5s</option><option value={10}>10s</option></select></label>
        </div>
      </div>
      {chips.length > 0 && <ul className="signal-strip" aria-label="Study readout on the latest bar">
        {chips.map((chip) => <li key={chip.id} className={`signal-chip ${chip.tone}`} title={chip.detail}><b>{chip.label}</b><span>{chip.detail}</span></li>)}
      </ul>}
      <ChartFreshness tradeAt={activeTick?.as_of} barAt={latest?.timestamp} timeframe={timeframe} quoteSeconds={quoteRefreshMs / 1000} failed={Boolean(tickError)} />
      <div className="trading-chart-shell" style={{ "--chart-panes": paneCount } as React.CSSProperties}>
        {isLoading && !bars.length && <div className="chart-placeholder"><BarChart3 size={22} aria-hidden="true" /> Loading Alpaca bars…</div>}
        {(error || renderError) && <div className="chart-feed-error" role="alert">{renderError ? "Chart renderer unavailable." : "Bar refresh failed; displayed history may be stale."} <button type="button" onClick={() => { if (renderError) { setRenderError(false); setRenderAttempt((value) => value + 1); } void mutate(); }}>Retry chart</button></div>}
        {!isLoading && !error && !bars.length && <div className="chart-placeholder">No bars returned. Choose another ticker or timeframe.</div>}
        <ChartLegend store={hover} bars={bars} studies={studies} settings={studySettings} symbol={chartSymbol} timeframe={timeframe} />
        <div ref={containerRef} className="trading-chart" />
      </div>
      <div className="chart-terminal-foot">
        <span>{isValidating ? "Updating bars…" : data?.source ?? snapshot.market.source}</span>
        <span>{bars.length} {timeframe} candles{bars.length > 0 && ` · ${etDate.format(new Date(bars[0].timestamp))} → ${etDate.format(new Date(bars.at(-1)!.timestamp))}`} · axis ET</span>
        <span>{tickError ? "Tape unavailable" : activeTick ? `Tape ${etStamp.format(new Date(activeTick.as_of))} ET` : "No tape yet"}</span>
        <span>Quotes {quoteRefreshMs > 0 ? `${quoteRefreshMs / 1000}s` : "paused"} · bars {timeframe === "1Min" ? "30s" : "60s"}</span>
        <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">Charts by TradingView</a>
      </div>
      <details className="accessible-data">
        <summary>Recent OHLC data</summary>
        <div className="table-scroll compact-chart-table"><table><thead><tr><th>Time (ET)</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th></tr></thead><tbody>{bars.slice(-10).reverse().map((bar) => <tr key={bar.timestamp}><td>{etStamp.format(new Date(bar.timestamp))}</td><td>{bar.open?.toFixed(2) ?? "—"}</td><td>{bar.high?.toFixed(2) ?? "—"}</td><td>{bar.low?.toFixed(2) ?? "—"}</td><td>{bar.close.toFixed(2)}</td><td>{bar.volume.toLocaleString()}</td></tr>)}</tbody></table></div>
      </details>
      {!compact && <ChartContextPanel symbol={chartSymbol} context={context} loading={contextLoading} failed={contextFailed} onRetry={refreshContext} />}
    </section>
  );
}
