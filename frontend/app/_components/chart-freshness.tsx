"use client";
import { useEffect, useState } from "react";
import { tradeAge } from "@/lib/feed-freshness";

export function ChartFreshness({ tradeAt, barAt, timeframe, quoteSeconds, failed }: {
  tradeAt?: string; barAt?: string; timeframe: string; quoteSeconds: number; failed: boolean;
}) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    const initial = setTimeout(() => setNow(Date.now()), 0);
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => { clearTimeout(initial); clearInterval(timer); };
  }, []);
  const age = now == null ? null : tradeAge(tradeAt, now);
  return <div className="chart-freshness">
    <span className={failed || age?.stale ? "negative" : ""}>{failed ? "Trade refresh failed" : age?.label ?? "Checking trade time…"}{age?.stale ? " · not current" : ""}</span>
    <span>{timeframe === "1Day" ? "Candle session (ET)" : "Candle starts"} {barAt ? timeframe === "1Day" ? new Date(barAt).toLocaleDateString(undefined, { timeZone: "America/New_York" }) : new Date(barAt).toLocaleString(undefined, { timeZoneName: "short" }) : "—"} · chart axis UTC</span>
    <details><summary>Why different speeds?</summary><p>TradingView draws the chart; Alpaca supplies the data. Latest trade polls {quoteSeconds ? `every ${quoteSeconds}s` : "are paused"}; {timeframe} candles refresh every {timeframe === "1Min" ? "30" : "60"}s. Polling is not streaming. Changing quote speed does not change candle speed.</p><p>IEX is a single-exchange feed, not the full US market. Sparse trading or a closed session can leave the last trade unchanged. Free indicative options data is separate from this stock chart. Faster polling cannot create newer exchange data.</p></details>
  </div>;
}
