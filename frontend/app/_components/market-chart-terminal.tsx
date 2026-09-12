"use client";

import { BarChart3, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import type {
  IChartApi,
  ISeriesApi,
  SeriesMarker,
  UTCTimestamp,
} from "lightweight-charts";
import type { ChartSnapshot, DecisionSnapshot, LiveMarketTick, PricePoint } from "@/lib/types";

type Timeframe = ChartSnapshot["timeframe"];
type CandleSeries = ISeriesApi<"Candlestick">;

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

function liveCandleTime(timestamp: string, timeframe: Timeframe): UTCTimestamp {
  const seconds = Math.floor(new Date(timestamp).getTime() / 1000);
  if (timeframe === "1Day") return (Math.floor(seconds / 86_400) * 86_400) as UTCTimestamp;
  const interval = { "1Min": 60, "5Min": 300, "15Min": 900 }[timeframe];
  return (Math.floor(seconds / interval) * interval) as UTCTimestamp;
}

export function MarketChartTerminal({
  snapshot,
  tick,
  quoteRefreshMs = 5000,
}: {
  snapshot: DecisionSnapshot;
  tick: LiveMarketTick;
  quoteRefreshMs?: number;
}) {
  const [timeframe, setTimeframe] = useState<Timeframe>("5Min");
  const [chartSymbol, setChartSymbol] = useState(snapshot.market.symbol);
  const [draftSymbol, setDraftSymbol] = useState(snapshot.market.symbol);
  const [rsiMode, setRsiMode] = useState<"off" | "raw" | "quiet" | "reversal">("quiet");
  const [rsiLowVolFilter, setRsiLowVolFilter] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<CandleSeries | null>(null);
  const latestBarRef = useRef<PricePoint | null>(null);
  const key = `/api/v1/chart?symbol=${encodeURIComponent(chartSymbol)}&timeframe=${timeframe}&limit=300&rsi_low_vol_filter=${rsiLowVolFilter}`;
  const { data, error, isLoading, isValidating } = useSWR(key, fetcher, {
    refreshInterval: timeframe === "1Min" ? 30_000 : 60_000,
    dedupingInterval: 15_000,
    refreshWhenHidden: false,
    refreshWhenOffline: false,
    keepPreviousData: false,
    errorRetryCount: 2,
  });
  const liveKey = chartSymbol === snapshot.market.symbol ? null : `/api/v1/live-tape?symbol=${encodeURIComponent(chartSymbol)}`;
  const { data: chartTick } = useSWR(liveKey, liveFetcher, {
    refreshInterval: quoteRefreshMs,
    dedupingInterval: Math.max(750, quoteRefreshMs * 0.8),
    refreshWhenHidden: false,
    refreshWhenOffline: false,
    revalidateOnFocus: quoteRefreshMs > 0,
    errorRetryCount: 2,
  });
  const activeTick = chartSymbol === snapshot.market.symbol ? tick : chartTick?.symbol === chartSymbol ? chartTick : undefined;
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
    let resizeObserver: ResizeObserver | undefined;

    void import("lightweight-charts").then(
      ({ CandlestickSeries, ColorType, HistogramSeries, LineSeries, LineStyle, createChart, createSeriesMarkers }) => {
        if (disposed || !containerRef.current) return;
        const chart = createChart(containerRef.current, {
          autoSize: true,
          height: 430,
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

        if (chartSymbol === snapshot.market.symbol) {
          const micro = snapshot.options_microstructure;
          const levels = [
            ["Put wall", micro.put_wall, "#ef5350", LineStyle.Solid],
            ["Call wall", micro.call_wall, "#fbbf24", LineStyle.Solid],
            ["Key gamma", micro.key_gamma_strike, "#d946ef", LineStyle.Dashed],
            ["Hedge wall", micro.hedge_wall, "#a78bfa", LineStyle.Dashed],
            ["Swing low", snapshot.swing.swing_low, "#38bdf8", LineStyle.Dotted],
            ["Swing high", snapshot.swing.swing_high, "#35dc7b", LineStyle.Dotted],
          ] as const;
          for (const [title, price, color, lineStyle] of levels) {
            if (price && price > 0) candles.createPriceLine({ price, color, lineStyle, lineWidth: 1, title });
          }
        }
        chart.timeScale().fitContent();
        chartRef.current = chart;
        candleRef.current = candles;
        latestBarRef.current = bars.at(-1) ?? null;
        resizeObserver = new ResizeObserver(() => chart.applyOptions({ width: containerRef.current?.clientWidth }));
        resizeObserver.observe(containerRef.current);
      },
    );
    return () => {
      disposed = true;
      resizeObserver?.disconnect();
      chartRef.current?.remove();
      chartRef.current = null;
      candleRef.current = null;
    };
  }, [bars, chartSymbol, snapshot.market.symbol, snapshot.options_microstructure, snapshot.swing, timeframe, data?.volume_rsi_signals, rsiMode]);

  useEffect(() => {
    const series = candleRef.current;
    const latestBar = latestBarRef.current;
    if (!series || !latestBar || !activeTick) return;
    const time = liveCandleTime(activeTick.as_of, timeframe);
    const latestTime = toTime(latestBar.timestamp);
    const candleTime = time < latestTime ? latestTime : time;
    const startsNewCandle = candleTime > latestTime;
    const nextBar: PricePoint = {
      timestamp: new Date(candleTime * 1000).toISOString(),
      open: startsNewCandle ? latestBar.close : (latestBar.open ?? latestBar.close),
      high: startsNewCandle ? activeTick.price : Math.max(latestBar.high ?? latestBar.close, activeTick.price),
      low: startsNewCandle ? activeTick.price : Math.min(latestBar.low ?? latestBar.close, activeTick.price),
      close: activeTick.price,
      volume: startsNewCandle ? 0 : latestBar.volume,
    };
    series.update({
      time: candleTime,
      open: nextBar.open ?? nextBar.close,
      high: nextBar.high ?? nextBar.close,
      low: nextBar.low ?? nextBar.close,
      close: nextBar.close,
    });
    latestBarRef.current = nextBar;
  }, [activeTick, timeframe]);

  const submitSymbol = () => {
    const normalized = draftSymbol.trim().toUpperCase();
    if (/^[A-Z][A-Z0-9.-]{0,9}$/.test(normalized)) setChartSymbol(normalized);
  };

  return (
    <section className="market-terminal" aria-labelledby="market-chart-title">
      <div className="chart-terminal-toolbar">
        <div>
          <p className="eyebrow">Alpaca market data</p>
          <h3 id="market-chart-title">{chartSymbol} chart terminal</h3>
        </div>
        <div className="chart-quote" aria-live="polite">
          <strong>{activeTick ? `$${activeTick.price.toFixed(2)}` : "Loading quote…"}</strong>
          <span className={(activeTick?.day_change_pct ?? 0) >= 0 ? "positive" : "negative"}>
            {activeTick?.day_change_pct == null ? "—" : `${activeTick.day_change_pct >= 0 ? "+" : ""}${activeTick.day_change_pct.toFixed(2)}%`}
          </span>
        </div>
        <form className="chart-symbol-search" onSubmit={(event) => { event.preventDefault(); submitSymbol(); }}>
          <label htmlFor="chart-symbol">Ticker</label>
          <div><input id="chart-symbol" value={draftSymbol} onChange={(event) => setDraftSymbol(event.target.value.toUpperCase())} maxLength={10} spellCheck={false} aria-label="Search chart ticker" /><button type="submit" aria-label="Load ticker chart"><Search size={15} aria-hidden="true" /></button></div>
        </form>
        <div className="range-tabs" aria-label="Chart timeframe">
          {timeframes.map((item) => (
            <button key={item} type="button" className={timeframe === item ? "active" : ""} aria-pressed={timeframe === item} onClick={() => setTimeframe(item)}>
              {item.replace("Min", "m").replace("Day", "D")}
            </button>
          ))}
        </div>
      </div>
      <div className="chart-rsi-controls"><label>RSI + volume markers<select value={rsiMode} onChange={(event) => setRsiMode(event.target.value as typeof rsiMode)}><option value="off">Off</option><option value="raw">Original · all extremes</option><option value="quiet">Quiet · one per excursion</option><option value="reversal">Price-confirmed reversals</option></select></label><label><input type="checkbox" checked={rsiLowVolFilter} onChange={(event) => setRsiLowVolFilter(event.target.checked)} /> Low-vol filter · ATR/price ≥0.5%</label><p>OB / OS = extreme + volume, not guaranteed tops / bottoms. Closed bars only; research, not orders.</p></div>
      <div className="chart-stat-strip">
        <span>O <b>{latest?.open?.toFixed(2) ?? "—"}</b></span>
        <span>H <b>{latest?.high?.toFixed(2) ?? "—"}</b></span>
        <span>L <b>{latest?.low?.toFixed(2) ?? "—"}</b></span>
        <span>C <b>{latest?.close.toFixed(2) ?? "—"}</b></span>
        <span>Range <b>{range ? `${range.low.toFixed(2)}–${range.high.toFixed(2)}` : "—"}</b></span>
        <span>Bar Δ <b className={(change ?? 0) >= 0 ? "positive" : "negative"}>{change == null ? "—" : `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`}</b></span>
      </div>
      <div className="trading-chart-shell">
        {isLoading && !bars.length && <div className="chart-placeholder"><BarChart3 size={22} aria-hidden="true" /> Loading Alpaca bars…</div>}
        {error && !bars.length && <div className="chart-placeholder negative">Chart feed unavailable.</div>}
        <div ref={containerRef} className="trading-chart" />
      </div>
      <div className="chart-terminal-foot">
        <span>{isValidating ? "Updating bars…" : data?.source ?? snapshot.market.source}</span>
        <span>EMA 18 <i className="legend-cyan" /> EMA 50 <i className="legend-amber" /></span>
        <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">Charts by TradingView</a>
      </div>
      <details className="accessible-data">
        <summary>Recent OHLC data</summary>
        <div className="table-scroll compact-chart-table"><table><thead><tr><th>Time</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Volume</th></tr></thead><tbody>{bars.slice(-10).reverse().map((bar) => <tr key={bar.timestamp}><td>{new Date(bar.timestamp).toLocaleString()}</td><td>{bar.open?.toFixed(2) ?? "—"}</td><td>{bar.high?.toFixed(2) ?? "—"}</td><td>{bar.low?.toFixed(2) ?? "—"}</td><td>{bar.close.toFixed(2)}</td><td>{bar.volume.toLocaleString()}</td></tr>)}</tbody></table></div>
      </details>
    </section>
  );
}
