"use client";

import { ExternalLink, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import useSWR from "swr";
import type { NewsSnapshot } from "@/lib/types";
import { useWorkspacePreferences } from "@/lib/use-workspace-preferences";

async function newsFetcher(url: string): Promise<NewsSnapshot> {
  const response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(15_000) });
  if (!response.ok) throw new Error("News feed unavailable");
  return response.json() as Promise<NewsSnapshot>;
}

function age(timestamp: string, now: number | null) {
  if (now == null) return "";
  const minutes = Math.max(0, Math.round((now - new Date(timestamp).getTime()) / 60_000));
  if (minutes < 60) return `${minutes}m`;
  if (minutes < 60 * 24) return `${Math.floor(minutes / 60)}h`;
  return `${Math.floor(minutes / 1440)}d`;
}

const safeLink = (url?: string | null) => (url && /^https?:\/\//i.test(url) ? url : null);

/** Read-only headline tape. Ticker chips re-point the workspace; nothing here trades. */
export function NewsFeed({ symbol, onSymbolChange }: { symbol: string; onSymbolChange: (symbol: string) => void }) {
  const [preferences, updatePreferences] = useWorkspacePreferences();
  const scope = preferences.newsScope;
  const [now, setNow] = useState<number | null>(null);
  const [seen, setSeen] = useState<{ url: string; newest: string } | null>(null);
  const url = `/api/v1/news?limit=30${scope === "ticker" ? `&symbols=${encodeURIComponent(symbol)}` : ""}`;
  const { data, error, isValidating, mutate } = useSWR(url, newsFetcher, {
    refreshInterval: 60_000, dedupingInterval: 25_000, keepPreviousData: false,
    refreshWhenHidden: false, refreshWhenOffline: false, errorRetryCount: 1,
  });
  useEffect(() => {
    const initial = setTimeout(() => setNow(Date.now()), 0);
    const timer = setInterval(() => setNow(Date.now()), 30_000);
    return () => { clearTimeout(initial); clearInterval(timer); };
  }, []);
  const articles = data?.articles ?? [];
  const newestLoaded = articles.reduce((max, article) => (article.created_at > max ? article.created_at : max), "");
  // Remember the newest headline from the first load of this feed; later
  // arrivals get a NEW mark until the operator refreshes.
  if (newestLoaded && seen?.url !== url) setSeen({ url, newest: newestLoaded });
  const newestSeen = seen?.url === url ? seen.newest : null;
  const demo = data?.source.includes("demo");

  return <section className="side-card news-feed" aria-label="News headlines" aria-busy={isValidating}>
    <div className="side-card-heading">
      <div className="segmented-mini" role="group" aria-label="News scope">
        {(["ticker", "market"] as const).map((item) => <button key={item} type="button" aria-pressed={scope === item} className={scope === item ? "active" : ""} onClick={() => updatePreferences({ newsScope: item })}>{item === "ticker" ? symbol : "Market"}</button>)}
      </div>
      <button type="button" className="icon-action" onClick={() => { if (newestLoaded) setSeen({ url, newest: newestLoaded }); void mutate(); }} disabled={isValidating} aria-label="Refresh headlines"><RefreshCw size={13} className={isValidating ? "spinning" : ""} aria-hidden="true" /></button>
    </div>
    {error && <p className="workspace-warning" role="alert">Headline refresh failed. Showing nothing rather than stale news.</p>}
    {demo && <p className="workspace-warning">Demo headlines — connect Alpaca for the real feed.</p>}
    {!data && !error && <p className="rail-note" role="status">Loading headlines…</p>}
    {data && !articles.length && <p className="rail-note">No headlines in the last few days{scope === "ticker" ? ` for ${symbol}` : ""}.</p>}
    <ol className="news-list">
      {!error && articles.map((article) => {
        const link = safeLink(article.url);
        const fresh = newestSeen != null && article.created_at > newestSeen;
        return <li key={article.id} className={fresh ? "fresh" : ""}>
          <div className="news-meta"><time dateTime={article.created_at} title={new Date(article.created_at).toLocaleString()}>{age(article.created_at, now)}</time><span>{article.source}</span>{fresh && <b>NEW</b>}</div>
          {link ? <a href={link} target="_blank" rel="noreferrer noopener">{article.headline}<ExternalLink size={11} aria-hidden="true" /></a> : <p>{article.headline}</p>}
          {article.symbols.length > 0 && <div className="news-tickers">{article.symbols.slice(0, 6).map((ticker) => <button key={ticker} type="button" className={ticker === symbol ? "active" : ""} onClick={() => onSymbolChange(ticker)} aria-label={`Chart ${ticker}`}>{ticker}</button>)}</div>}
        </li>;
      })}
    </ol>
    <p className="rail-note">{data?.source ?? "Alpaca News API"} · polls 60s · headlines are context, never trade signals.</p>
  </section>;
}
