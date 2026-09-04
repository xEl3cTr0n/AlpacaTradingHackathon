"use client";

import { Activity, ChevronDown, Pause, Play, Radio, RefreshCw } from "lucide-react";
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import useSWR from "swr";
import type { DecisionSnapshot, LiveMarketTick } from "@/lib/types";

const fetcher = async (url: string): Promise<LiveMarketTick> => {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Live tape returned ${response.status}`);
  return response.json() as Promise<LiveMarketTick>;
};

const pct = (value?: number | null) => value == null ? "N/A" : `${(value * 100).toFixed(1)}%`;
const quad = (value: string) => value.replace("quad_", "Q").replace("unavailable", "N/A").toUpperCase();
const MarketChartTerminal = dynamic(
  () => import("@/app/_components/market-chart-terminal").then((module) => module.MarketChartTerminal),
  { ssr: false, loading: () => <div className="chart-placeholder">Loading chart terminal…</div> },
);

export function MarketLayers({ snapshot }: { snapshot: DecisionSnapshot }) {
  const [seconds, setSeconds] = useState(5);
  const [playing, setPlaying] = useState(true);
  const key = `/api/v1/live-tape?symbol=${encodeURIComponent(snapshot.market.symbol)}`;
  const { data, error, isValidating, mutate } = useSWR(key, fetcher, {
    fallbackData: {
      symbol: snapshot.market.symbol,
      as_of: snapshot.market.as_of,
      price: snapshot.market.current_price,
      day_change_pct: snapshot.market.price_change_pct,
      source: snapshot.market.source,
    },
    refreshInterval: playing ? seconds * 1000 : 0,
    dedupingInterval: Math.max(750, seconds * 800),
    refreshWhenHidden: false,
    refreshWhenOffline: false,
    revalidateOnFocus: true,
    errorRetryCount: 2,
  });
  const lastUpdate = useMemo(
    () => new Date(data.as_of).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    [data.as_of],
  );
  const macro = snapshot.market_layers.macro;
  const bottom = snapshot.market_layers.bottom_up;
  const micro = snapshot.options_microstructure;
  const mood = snapshot.market_layers.mood_vibe;

  return (
    <section className="panel layered-market" aria-labelledby="market-layers-title">
      <div className="layers-toolbar">
        <div><p className="eyebrow">Three-layer regime stack</p><h2 id="market-layers-title">Market state engine</h2></div>
        <div className="live-tape" role="status" aria-atomic="true">
          <span className={`live-indicator ${playing ? "running" : "paused"}`}><Radio size={13} aria-hidden="true" />{playing ? "Live" : "Paused"}</span>
          <strong>${data.price.toFixed(2)}</strong>
          <small className={(data.day_change_pct ?? 0) >= 0 ? "positive" : "negative"}>{data.day_change_pct == null ? "" : `${data.day_change_pct >= 0 ? "+" : ""}${data.day_change_pct.toFixed(2)}%`}</small>
        </div>
        <div className="refresh-controls">
          <label><span>Refresh</span><select aria-label="Live price refresh interval" value={seconds} onChange={(event) => setSeconds(Number(event.target.value))}><option value={1}>1 sec</option><option value={5}>5 sec</option><option value={10}>10 sec</option></select><ChevronDown size={13} aria-hidden="true" /></label>
          <button type="button" className="secondary-action icon-action" aria-label={playing ? "Pause live updates" : "Resume live updates"} onClick={() => setPlaying(!playing)}>{playing ? <Pause size={15} aria-hidden="true" /> : <Play size={15} aria-hidden="true" />}</button>
          <button type="button" className="secondary-action icon-action" aria-label="Refresh now" onClick={() => void mutate()}><RefreshCw size={15} className={isValidating ? "spinning" : ""} aria-hidden="true" /></button>
        </div>
      </div>
      <div className="tape-meta"><span>Last tick {lastUpdate}</span><span>{data.bid && data.ask ? `Bid ${data.bid.toFixed(2)} · Ask ${data.ask.toFixed(2)}` : "Quote unavailable"}</span><span>{data.spread_bps == null ? "Spread N/A" : `Spread ${data.spread_bps.toFixed(1)} bps`}</span><span>{error ? "Feed retrying" : data.source}</span></div>
      <MarketChartTerminal snapshot={snapshot} tick={data} />
      <div className="layer-stack">
        <article className="market-layer macro-layer"><div className="layer-index">01</div><div className="layer-copy"><span>Top-down · GDP / CPI</span><h3>Macro {quad(macro.quadrant)}</h3><strong>{macro.label}</strong><p>{macro.rationale}</p></div><dl><div><dt>Real GDP YoY</dt><dd>{pct(macro.real_gdp_yoy)}</dd></div><div><dt>CPI YoY</dt><dd>{pct(macro.cpi_yoy)}</dd></div><div><dt>Cadence</dt><dd>6 hours</dd></div></dl></article>
        <div className="layer-connector" aria-hidden="true"><span /></div>
        <article className="market-layer bottom-layer"><div className="layer-index">02</div><div className="layer-copy"><span>Bottom-up · ETFs / securities</span><h3>Market {quad(bottom.quadrant)}</h3><strong>{bottom.label}</strong><p>{bottom.rationale}</p></div><dl><div><dt>Trend</dt><dd>{bottom.trend_positive ? "Positive" : "Non-positive"}</dd></div><div><dt>Breadth</dt><dd>{pct(snapshot.sector_rotation.breadth)}</dd></div><div><dt>Cadence</dt><dd>Agent run</dd></div></dl></article>
        <div className="layer-connector" aria-hidden="true"><span /></div>
        <article className="market-layer micro-layer"><div className="layer-index">03</div><div className="layer-copy"><span>Microstructure of Options Order Dynamics</span><h3>MOOD {mood.mood.toUpperCase()}</h3><strong>VIBE · {mood.vibe.toUpperCase()}</strong><p>{mood.rationale}</p></div><dl><div><dt>Key gamma</dt><dd>{micro.key_gamma_strike?.toFixed(0) ?? "N/A"}</dd></div><div><dt>Hedge wall</dt><dd>{micro.hedge_wall?.toFixed(0) ?? "N/A"}</dd></div><div><dt>Trapdoor</dt><dd>{micro.put_directional_bias?.toFixed(0) ?? "N/A"}</dd></div></dl></article>
      </div>
      <div className="layers-footnote"><Activity size={14} aria-hidden="true" /><span>The 1/5/10-second control refreshes only Alpaca tape data. Macro refreshes every six hours; bottom-up and options layers refresh on a full agent run to avoid rate-limit noise. The Volatility-Informed Behavioral Engine is marked as a research proxy until contract volume, vanna, charm, and REPH are available.</span></div>
    </section>
  );
}
