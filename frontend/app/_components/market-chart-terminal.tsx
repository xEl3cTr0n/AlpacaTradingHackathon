"use client";

import { BarChart3, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import type {
  IChartApi,
  LogicalRange,
  SeriesMarker,
  UTCTimestamp,
} from "lightweight-charts";
import type { ChartContextSnapshot, ChartSnapshot, DecisionSnapshot, LiveMarketTick, PricePoint } from "@/lib/types";
import { chartContextLevels, matchingChartContext, targetCorridorSummary } from "@/lib/chart-context";
import { ChartContextPanel } from "./chart-context-panel";
import { ChartFreshness } from "./chart-freshness";
import { useWorkspacePreferences } from "@/lib/use-workspace-preferences";
import { IchimokuCloudPrimitive } from "@/lib/ichimoku-cloud-plugin";

type Timeframe = ChartSnapshot["timeframe"];

const timeframes: Timeframe[] = ["1Min", "5Min", "15Min", "1Day"];

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

const contextFetcher = async (url: string): Promise<ChartContextSnapshot> => {
  const response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(35_000) });
  if (!response.ok) throw new Error("Chart overlays unavailable");
  return response.json() as Promise<ChartContextSnapshot>;
};

const toTime = (timestamp: string): UTCTimestamp =>
  Math.floor(new Date(timestamp).getTime() / 1000) as UTCTimestamp;

function ema(points: PricePoint[], period: number) {
  const multiplier = 2 / (period + 1);
  let value = points[0]?.close ?? 0;
  return points.map((point) => {
    value = point.close * multiplier + value * (1 - multiplier);
    return { time: toTime(point.timestamp), value };
  });
}

function ichimoku(points: PricePoint[]) {
  const tenkanData: { time: UTCTimestamp; value: number }[] = [];
  const kijunData: { time: UTCTimestamp; value: number }[] = [];
  const spanAData: { time: UTCTimestamp; value: number }[] = [];
  const spanBData: { time: UTCTimestamp; value: number }[] = [];
  const chikouData: { time: UTCTimestamp; value: number }[] = [];
  const cloudData: { time: UTCTimestamp; spanA: number; spanB: number }[] = [];

  for (let i = 0; i < points.length; i++) {
    const t = toTime(points[i].timestamp);
    chikouData.push({ time: t, value: points[i].close });

    if (i >= 8) {
      let high9 = -Infinity;
      let low9 = Infinity;
      for (let j = i - 8; j <= i; j++) {
        const h = points[j].high ?? points[j].close;
        const l = points[j].low ?? points[j].close;
        if (h > high9) high9 = h;
        if (l < low9) low9 = l;
      }
      const tVal = +((high9 + low9) / 2).toFixed(2);
      tenkanData.push({ time: t, value: tVal });

      if (i >= 25) {
        let high26 = -Infinity;
        let low26 = Infinity;
        for (let j = i - 25; j <= i; j++) {
          const h = points[j].high ?? points[j].close;
          const l = points[j].low ?? points[j].close;
          if (h > high26) high26 = h;
          if (l < low26) low26 = l;
        }
        const kVal = +((high26 + low26) / 2).toFixed(2);
        kijunData.push({ time: t, value: kVal });
        const aVal = +((tVal + kVal) / 2).toFixed(2);
        spanAData.push({ time: t, value: aVal });

        // Span B: 52 period midpoint (or maximum window up to 52 once past Kijun 26)
        const bLookback = Math.min(i, 51);
        let high52 = -Infinity;
        let low52 = Infinity;
        for (let j = i - bLookback; j <= i; j++) {
          const h = points[j].high ?? points[j].close;
          const l = points[j].low ?? points[j].close;
          if (h > high52) high52 = h;
          if (l < low52) low52 = l;
        }
        const bVal = +((high52 + low52) / 2).toFixed(2);
        if (i >= 51) {
          spanBData.push({ time: t, value: bVal });
        }
        cloudData.push({ time: t, spanA: aVal, spanB: bVal });
      }
    }
  }

  return { tenkanData, kijunData, spanAData, spanBData, chikouData, cloudData };
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
  compact?: boolean;
}) {
  const [preferences, updatePreferences] = useWorkspacePreferences();
  const timeframe = preferences.timeframe;
  const setTimeframe = (value: Timeframe) => updatePreferences({ timeframe: value });
  const [localSymbol, setLocalSymbol] = useState(snapshot.market.symbol);
  const chartSymbol = symbol ?? localSymbol;
  const [renderError, setRenderError] = useState(false);
  const [renderAttempt, setRenderAttempt] = useState(0);
  const rsiMode = preferences.rsiMode;
  const setRsiMode = (value: typeof rsiMode) => updatePreferences({ rsiMode: value });
  const rsiLowVolFilter = preferences.lowVolFilter;
  const setRsiLowVolFilter = (value: boolean) => updatePreferences({ lowVolFilter: value });
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const visibleRangeRef = useRef<{ key: string; range: LogicalRange } | null>(null);
  const candleLimit = preferences.candleLimit ?? 500;
  const setCandleLimit = (value: typeof candleLimit) => updatePreferences({ candleLimit: value });
  const key = `/api/v1/chart?symbol=${encodeURIComponent(chartSymbol)}&timeframe=${timeframe}&limit=${candleLimit}&rsi_low_vol_filter=${rsiLowVolFilter}`;
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
  const { data: contextData, error: contextError, isValidating: contextLoading, mutate: refreshContext } = useSWR(
    `/api/v1/chart-context?symbol=${encodeURIComponent(chartSymbol)}`, contextFetcher,
    { refreshInterval: 60_000, dedupingInterval: 30_000, keepPreviousData: false,
      refreshWhenHidden: false, refreshWhenOffline: false, errorRetryCount: 1 },
  );
  const context = matchingChartContext(chartSymbol, contextData, Boolean(contextError));
  const targets = useMemo(() => targetCorridorSummary(context), [context]);
  const overlayLevels = useMemo(() => {
    if (!preferences.showLevels) return [];
    const allLevels = chartContextLevels(context);
    if (!preferences.showTargets) {
      return allLevels.filter((lvl) => !lvl.title.includes("Session") && !lvl.title.includes("Weekly") && !lvl.title.includes("Extreme") && !lvl.title.includes("Prior Day"));
    }
    return allLevels;
  }, [context, preferences.showLevels, preferences.showTargets]);

  const bars = useMemo(
    () => data?.bars ?? (timeframe === "1Day" && chartSymbol === snapshot.market.symbol ? snapshot.market.prices : []),
    [data?.bars, snapshot.market.prices, snapshot.market.symbol, timeframe, chartSymbol],
  );
  const latest = bars.at(-1);
  const previous = bars.at(-2);
  const change = latest && previous ? (latest.close / previous.close - 1) * 100 : null;
  const range = useMemo(() => {
    if (!bars.length) return null;
    return {
      high: Math.max(...bars.map((bar) => bar.high ?? bar.close)),
      low: Math.min(...bars.map((bar) => bar.low ?? bar.close)),
    };
  }, [bars]);

  useEffect(() => {
    if (!containerRef.current || !bars.length) return;
    let disposed = false;
    let ownedChart: IChartApi | undefined;
    let resizeObserver: ResizeObserver | undefined;
    const viewKey = `${chartSymbol}:${timeframe}`;

    void import("lightweight-charts").then(
      ({ CandlestickSeries, ColorType, HistogramSeries, LineSeries, LineStyle, createChart, createSeriesMarkers }) => {
        if (disposed || !containerRef.current) return;
        setRenderError(false);
        const chart = createChart(containerRef.current, {
          autoSize: false,
          height: containerRef.current.clientHeight || 430,
          layout: {
            attributionLogo: true,
            background: { type: ColorType.Solid, color: "#070c18" },
            textColor: "#94a3b8",
            fontFamily: "var(--font-mono), monospace",
          },
          grid: {
            vertLines: { color: "rgba(38, 51, 76, .42)" },
            horzLines: { color: "rgba(38, 51, 76, .42)" },
          },
          rightPriceScale: { borderColor: "#26334c" },
          timeScale: {
            borderColor: "#26334c",
            timeVisible: timeframe !== "1Day",
            secondsVisible: false,
            rightOffset: 3,
          },
          crosshair: {
            vertLine: { color: "rgba(148, 163, 184, .45)", labelBackgroundColor: "#26334c" },
            horzLine: { color: "rgba(148, 163, 184, .45)", labelBackgroundColor: "#26334c" },
          },
        });
        ownedChart = chart;
        const candles = chart.addSeries(CandlestickSeries, {
          upColor: "#26a69a",
          downColor: "#ef5350",
          borderUpColor: "#26a69a",
          borderDownColor: "#ef5350",
          wickUpColor: "#26a69a",
          wickDownColor: "#ef5350",
        });
        candles.setData(
          bars.map((bar) => ({
            time: toTime(bar.timestamp),
            open: bar.open ?? bar.close,
            high: bar.high ?? bar.close,
            low: bar.low ?? bar.close,
            close: bar.close,
          })),
        );
        const markers: SeriesMarker<UTCTimestamp>[] = (data?.volume_rsi_signals ?? []).flatMap((signal) => {
          const side = rsiMode === "raw" ? signal.raw_signal : rsiMode === "quiet" ? signal.quiet_signal
            : rsiMode === "reversal" ? (signal.context === "reversal_down" ? "overbought" : signal.context === "reversal_up" ? "oversold" : "none") : "none";
          if (side === "none") return [];
          const high = side === "overbought";
          return [{ time: toTime(signal.as_of), position: high ? "aboveBar" : "belowBar",
            color: high ? "#fb7185" : "#35dc7b", shape: high ? "arrowDown" : "arrowUp",
            text: rsiMode === "reversal" ? (high ? "Rev ↓" : "Rev ↑") : high ? "OB" : "OS" }];
        });
        createSeriesMarkers(candles, markers);
        const volume = chart.addSeries(HistogramSeries, {
          priceFormat: { type: "volume" },
          priceScaleId: "volume",
        });
        volume.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
        volume.setData(
          bars.map((bar) => ({
            time: toTime(bar.timestamp),
            value: bar.volume,
            color: (bar.close >= (bar.open ?? bar.close) ? "#26a69a" : "#ef5350") + "66",
          })),
        );
        const ema18 = chart.addSeries(LineSeries, {
          color: "#38bdf8",
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          title: "EMA 18",
        });
        const ema50 = chart.addSeries(LineSeries, {
          color: "#fbbf24",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
          title: "EMA 50",
        });
        ema18.setData(ema(bars, 18));
        ema50.setData(ema(bars, 50));

        // Full 5-Line Ichimoku Suite
        if (preferences.showIchimoku) {
          const cloud = bars.length >= 9 ? ichimoku(bars) : null;
          const backendSeries = context?.structural_levels?.ichimoku_series;
          const hasCloud = cloud && cloud.tenkanData.length > 0;
          const hasBackend = (backendSeries?.length ?? 0) > 0;

          if (hasCloud || hasBackend) {
            const tenkan = chart.addSeries(LineSeries, {
              color: "#38bdf8",
              lineWidth: 1,
              priceLineVisible: false,
              lastValueVisible: false,
              title: "Tenkan (9)",
            });
            const kijun = chart.addSeries(LineSeries, {
              color: "#ec4899",
              lineWidth: 2,
              priceLineVisible: false,
              lastValueVisible: false,
              title: "Kijun (26)",
            });
            const spanA = chart.addSeries(LineSeries, {
              color: "#34d399",
              lineWidth: 1,
              lineStyle: LineStyle.Dotted,
              priceLineVisible: false,
              lastValueVisible: false,
              title: "Span A",
            });
            const spanB = chart.addSeries(LineSeries, {
              color: "#f43f5e",
              lineWidth: 1,
              lineStyle: LineStyle.Dotted,
              priceLineVisible: false,
              lastValueVisible: false,
              title: "Span B",
            });
            const chikou = chart.addSeries(LineSeries, {
              color: "#c084fc",
              lineWidth: 1,
              lineStyle: LineStyle.Dashed,
              priceLineVisible: false,
              lastValueVisible: false,
              title: "Chikou",
            });

            if (hasCloud) {
              if (cloud.cloudData.length > 1) {
                const cloudPrimitive = new IchimokuCloudPrimitive(cloud.cloudData);
                candles.attachPrimitive(cloudPrimitive);
              }
              tenkan.setData(cloud.tenkanData);
              kijun.setData(cloud.kijunData);
              spanA.setData(cloud.spanAData);
              spanB.setData(cloud.spanBData);
              chikou.setData(cloud.chikouData);
            } else if (hasBackend && backendSeries) {
              const backendCloud = backendSeries
                .filter((pt) => pt.senkou_span_a != null && pt.senkou_span_b != null)
                .map((pt) => ({ time: toTime(pt.timestamp), spanA: pt.senkou_span_a!, spanB: pt.senkou_span_b! }));
              if (backendCloud.length > 1) {
                const cloudPrimitive = new IchimokuCloudPrimitive(backendCloud);
                candles.attachPrimitive(cloudPrimitive);
              }
              tenkan.setData(
                backendSeries
                  .filter((pt) => pt.tenkan_sen != null)
                  .map((pt) => ({ time: toTime(pt.timestamp), value: pt.tenkan_sen! }))
              );
              kijun.setData(
                backendSeries
                  .filter((pt) => pt.kijun_sen != null)
                  .map((pt) => ({ time: toTime(pt.timestamp), value: pt.kijun_sen! }))
              );
              spanA.setData(
                backendSeries
                  .filter((pt) => pt.senkou_span_a != null)
                  .map((pt) => ({ time: toTime(pt.timestamp), value: pt.senkou_span_a! }))
              );
              spanB.setData(
                backendSeries
                  .filter((pt) => pt.senkou_span_b != null)
                  .map((pt) => ({ time: toTime(pt.timestamp), value: pt.senkou_span_b! }))
              );
              chikou.setData(
                backendSeries
                  .filter((pt) => pt.chikou_span != null)
                  .map((pt) => ({ time: toTime(pt.timestamp), value: pt.chikou_span! }))
              );
            }
          }
        }

        for (const { title, price, color, dashed } of overlayLevels) {
          candles.createPriceLine({ price, color, lineStyle: dashed ? LineStyle.Dashed : LineStyle.Solid, lineWidth: 1, title });
        }
        const previousView = visibleRangeRef.current;
        if (previousView?.key === viewKey) {
          chart.timeScale().setVisibleLogicalRange(previousView.range);
        } else {
          if (bars.length > 120) {
            chart.timeScale().setVisibleLogicalRange({
              from: bars.length - 120,
              to: bars.length + 5,
            });
          } else {
            chart.timeScale().fitContent();
          }
        }
        chartRef.current = chart;
        resizeObserver = new ResizeObserver(() => chart.applyOptions({ width: containerRef.current?.clientWidth, height: containerRef.current?.clientHeight }));
        resizeObserver.observe(containerRef.current);
      },
    ).catch(() => { if (!disposed) setRenderError(true); });
    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      const range = ownedChart?.timeScale().getVisibleLogicalRange();
      if (range) visibleRangeRef.current = { key: viewKey, range };
      ownedChart?.remove();
      if (chartRef.current === ownedChart) chartRef.current = null;
    };
  }, [bars, chartSymbol, overlayLevels, timeframe, data?.volume_rsi_signals, rsiMode, renderAttempt, preferences.showIchimoku, context]);

  // Display tape independently: quotes are not OHLC bars, and an old trade
  // must never rewrite newer history or fabricate a daily/session candle.
  const submitSymbol = (value: string) => {
    const normalized = value.trim().toUpperCase();
    if (/^[A-Z.]{1,10}$/.test(normalized)) {
      setLocalSymbol(normalized);
      onSymbolChange?.(normalized);
    }
  };

  const handleFitAll = () => {
    chartRef.current?.timeScale().fitContent();
  };

  const handleResetRecent = () => {
    if (!chartRef.current || !bars.length) return;
    if (bars.length > 120) {
      chartRef.current.timeScale().setVisibleLogicalRange({
        from: bars.length - 120,
        to: bars.length + 5,
      });
    } else {
      chartRef.current.timeScale().fitContent();
    }
  };

  return (
    <section className={compact ? "market-terminal compact-chart" : "market-terminal"} aria-labelledby="market-chart-title">
      <div className="chart-terminal-toolbar">
        <div>
          {!compact && <p className="eyebrow">Alpaca market data</p>}
          <h2 id="market-chart-title">{chartSymbol}{compact ? "" : " chart terminal"}</h2>
        </div>
        <div className="chart-quote">
          <strong>{activeTick ? `$${activeTick.price.toFixed(2)}` : "Loading quote…"}</strong>
          <span className={(activeTick?.day_change_pct ?? 0) >= 0 ? "positive" : "negative"}>
            {activeTick?.day_change_pct == null ? "—" : `${activeTick.day_change_pct >= 0 ? "+" : ""}${activeTick.day_change_pct.toFixed(2)}%`}
          </span>
        </div>
        {!compact && <form key={chartSymbol} className="chart-symbol-search" onSubmit={(event) => { event.preventDefault(); submitSymbol(String(new FormData(event.currentTarget).get("ticker") ?? "")); }}>
          <label htmlFor="chart-symbol">Ticker</label>
          <div><input id="chart-symbol" name="ticker" defaultValue={chartSymbol} pattern="[A-Za-z.]{1,10}" required maxLength={10} spellCheck={false} aria-label="Search chart ticker" /><button type="submit" aria-label="Load ticker chart"><Search size={15} aria-hidden="true" /></button></div>
        </form>}
        <div className="range-tabs" aria-label="Chart timeframe">
          {timeframes.map((item) => (
            <button key={item} type="button" className={timeframe === item ? "active" : ""} aria-pressed={timeframe === item} onClick={() => setTimeframe(item)}>
              {item.replace("Min", "m").replace("Day", "D")}
            </button>
          ))}
        </div>
        <div className="range-tabs candle-depth-tabs" aria-label="Candle count history">
          {([100, 300, 500, 1000] as const).map((count) => (
            <button
              key={count}
              type="button"
              className={candleLimit === count ? "active" : ""}
              aria-pressed={candleLimit === count}
              title={`Load ${count} candles of history`}
              onClick={() => setCandleLimit(count)}
            >
              {count}b
            </button>
          ))}
        </div>
        <div className="chart-view-actions">
          <button
            type="button"
            className={`chart-toggle-btn ${preferences.showTargets ? "active" : ""}`}
            onClick={() => updatePreferences({ showTargets: !preferences.showTargets })}
            title="Toggle Implied Move Targets & Corridors"
          >
            🎯 Targets
          </button>
          <button
            type="button"
            className={`chart-toggle-btn ${preferences.showIchimoku ? "active" : ""}`}
            onClick={() => updatePreferences({ showIchimoku: !preferences.showIchimoku })}
            title="Toggle Full 5-Line Ichimoku Cloud"
          >
            ☁️ Ichimoku
          </button>
          <button type="button" onClick={handleResetRecent} title="Focus on most recent candles">Recent</button>
          <button type="button" onClick={handleFitAll} title="Fit entire historical dataset on screen">Fit All</button>
        </div>
        {compact && <label className="quote-refresh-control">Quotes<select value={preferences.quoteSeconds} onChange={(event) => updatePreferences({ quoteSeconds: Number(event.target.value) as 0 | 1 | 5 | 10 })}><option value={0}>Paused</option><option value={1}>1s</option><option value={5}>5s</option><option value={10}>10s</option></select></label>}
      </div>
      <ChartFreshness tradeAt={activeTick?.as_of} barAt={latest?.timestamp} timeframe={timeframe} quoteSeconds={quoteRefreshMs / 1000} failed={Boolean(tickError)} />
      <details className="chart-indicators">
        <summary>Indicators · EMA 18 / 50 · RSI {rsiMode} · {overlayLevels.length} automatic levels</summary>
        <div className="chart-rsi-controls">
          <label><input type="checkbox" checked={preferences.showTargets} onChange={(event) => updatePreferences({ showTargets: event.target.checked })} /> 🎯 Implied move targets</label>
          <label><input type="checkbox" checked={preferences.showIchimoku} onChange={(event) => updatePreferences({ showIchimoku: event.target.checked })} /> ☁️ Ichimoku Cloud (Tenkan, Kijun, Spans A/B)</label>
          <label><input type="checkbox" checked={preferences.showLevels} onChange={(event) => updatePreferences({ showLevels: event.target.checked })} /> GEX &amp; swing levels</label>
          <label><input type="checkbox" checked={preferences.showGex} onChange={(event) => updatePreferences({ showGex: event.target.checked })} /> GEX profile</label>
          <label>RSI + volume markers<select value={rsiMode} onChange={(event) => setRsiMode(event.target.value as typeof rsiMode)}><option value="off">Off</option><option value="raw">Original · all extremes</option><option value="quiet">Quiet · one per excursion</option><option value="reversal">Price-confirmed reversals</option></select></label>
          <label><input type="checkbox" checked={rsiLowVolFilter} onChange={(event) => setRsiLowVolFilter(event.target.checked)} /> Low-vol filter · ATR/price ≥0.5%</label>
          <p>OB / OS = extreme + volume, not guaranteed tops / bottoms. Closed bars only; research, not orders.</p>
        </div>
      </details>
      <div className="chart-stat-strip">
        <span>O <b>{latest?.open?.toFixed(2) ?? "—"}</b></span>
        <span>H <b>{latest?.high?.toFixed(2) ?? "—"}</b></span>
        <span>L <b>{latest?.low?.toFixed(2) ?? "—"}</b></span>
        <span>C <b>{latest?.close.toFixed(2) ?? "—"}</b></span>
        <span>Range <b>{range ? `${range.low.toFixed(2)}–${range.high.toFixed(2)}` : "—"}</b></span>
        <span>Bar Δ <b className={(change ?? 0) >= 0 ? "positive" : "negative"}>{change == null ? "—" : `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`}</b></span>
        <span>Bars <b>{bars.length}</b></span>
        {bars.length > 0 && (
          <span>Span <b>{new Date(bars[0].timestamp).toLocaleDateString()} → {new Date(bars.at(-1)!.timestamp).toLocaleDateString()}</b></span>
        )}
      </div>
      <div className="trading-chart-shell">
        {isLoading && !bars.length && <div className="chart-placeholder"><BarChart3 size={22} aria-hidden="true" /> Loading Alpaca bars…</div>}
        {(error || renderError) && <div className="chart-feed-error" role="alert">{renderError ? "Chart renderer unavailable." : "Bar refresh failed; displayed history may be stale."} <button type="button" onClick={() => { if (renderError) setRenderAttempt((value) => value + 1); void mutate(); }}>Retry chart</button></div>}
        {!isLoading && !error && !bars.length && <div className="chart-placeholder">No bars returned. Choose another ticker or timeframe.</div>}
        <div ref={containerRef} className="trading-chart" />

        {preferences.showTargets && targets.spot != null && (
          <div className="chart-target-hud" aria-label="Implied Move and Targets HUD">
            <div className="target-hud-header">
              <div className="hud-title">
                <span>🎯 TARGET CORRIDOR</span>
                <strong>${targets.spot.toFixed(2)}</strong>
              </div>
              <div className="hud-moves">
                {targets.dailyExpectedMove != null && (
                  <span className="move-chip daily">1D: ±${targets.dailyExpectedMove.toFixed(2)} ({targets.dailyPct}%)</span>
                )}
                {targets.weeklyExpectedMove != null && (
                  <span className="move-chip weekly">7D: ±${targets.weeklyExpectedMove.toFixed(2)} ({targets.weeklyPct}%)</span>
                )}
              </div>
            </div>
            <div className="target-hud-levels">
              {targets.dailyUpper != null && (
                <div className="hud-level-item bull">
                  <span>Bull Target</span>
                  <strong>${targets.dailyUpper.toFixed(2)}</strong>
                  <small>+{targets.dailyPct}%</small>
                </div>
              )}
              {targets.dailyLower != null && (
                <div className="hud-level-item bear">
                  <span>Bear Target</span>
                  <strong>${targets.dailyLower.toFixed(2)}</strong>
                  <small>-{targets.dailyPct}%</small>
                </div>
              )}
              {targets.callWall != null && (
                <div className="hud-level-item call-wall">
                  <span>Call Wall</span>
                  <strong>${targets.callWall.toFixed(2)}</strong>
                  <small>Resistance</small>
                </div>
              )}
              {targets.putWall != null && (
                <div className="hud-level-item put-wall">
                  <span>Put Wall</span>
                  <strong>${targets.putWall.toFixed(2)}</strong>
                  <small>Support</small>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
      <div className="chart-terminal-foot">
        <span>{isValidating ? "Updating bars…" : data?.source ?? snapshot.market.source}</span>
        <span>{bars.length} {timeframe} candles · Drag or scroll to inspect history</span>
        <span>{tickError ? "Tape unavailable" : activeTick ? `Tape as of ${new Date(activeTick.as_of).toLocaleString()}` : "No tape yet"}</span>
        <span>Quotes {quoteRefreshMs > 0 ? `${quoteRefreshMs / 1000}s` : "paused"} · bars {timeframe === "1Min" ? "30s" : "60s"}</span>
        <span>EMA 18 <i className="legend-cyan" /> EMA 50 <i className="legend-amber" /></span>
        <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">Charts by TradingView</a>
      </div>
      <details className="accessible-data">
        <summary>Recent OHLC data</summary>
        <div className="table-scroll compact-chart-table"><table><thead><tr><th>Time</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th></tr></thead><tbody>{bars.slice(-10).reverse().map((bar) => <tr key={bar.timestamp}><td>{new Date(bar.timestamp).toLocaleString()}</td><td>{bar.open?.toFixed(2) ?? "—"}</td><td>{bar.high?.toFixed(2) ?? "—"}</td><td>{bar.low?.toFixed(2) ?? "—"}</td><td>{bar.close.toFixed(2)}</td><td>{bar.volume.toLocaleString()}</td></tr>)}</tbody></table></div>
      </details>
      <ChartContextPanel symbol={chartSymbol} context={context} loading={contextLoading} failed={Boolean(contextError)} onRetry={() => void refreshContext()} />
    </section>
  );
}
