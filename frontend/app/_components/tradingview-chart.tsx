"use client";

import { useMemo } from "react";

function tradingViewSymbol(symbol: string) {
  const normalized = symbol.trim().toUpperCase();
  // SPY's TradingView identifier is AMEX:SPY. Let native search resolve other
  // unqualified symbols instead of incorrectly forcing every stock onto NASDAQ.
  return normalized === "SPY" ? "AMEX:SPY" : normalized;
}

export function TradingViewChart({ symbol }: { symbol: string }) {
  const src = useMemo(() => {
    const params = new URLSearchParams({
      symbol: tradingViewSymbol(symbol),
      interval: "15",
      timezone: "America/Los_Angeles",
      theme: "dark",
      style: "1",
      locale: "en",
      toolbar_bg: "#070c18",
      enable_publishing: "false",
      hide_top_toolbar: "false",
      hide_legend: "false",
      saveimage: "false",
      hideideas: "true",
      allow_symbol_change: "true",
    });
    return `https://www.tradingview.com/widgetembed/?${params.toString()}`;
  }, [symbol]);

  return (
    <section className="tradingview-panel" aria-labelledby="tradingview-chart-title">
      <div className="panel-heading">
        <div><p className="eyebrow">TradingView Advanced Chart</p><h2 id="tradingview-chart-title">Search any ticker</h2></div>
        <span className="source-label">Native symbol search enabled</span>
      </div>
      <p className="tradingview-help">Use TradingView&apos;s symbol box in the chart header to search stocks, ETFs, crypto, forex, and futures without leaving the portfolio.</p>
      <div className="tradingview-frame-wrap">
        <iframe key={src} className="tradingview-frame" src={src} title="TradingView Advanced Chart" loading="lazy" allowFullScreen />
      </div>
    </section>
  );
}
