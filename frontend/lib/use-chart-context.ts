"use client";
import useSWR from "swr";
import { matchingChartContext } from "./chart-context";
import type { ChartContextSnapshot } from "./types";

async function contextFetcher(url: string): Promise<ChartContextSnapshot> {
  const response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(35_000) });
  if (!response.ok) throw new Error("Chart overlays unavailable");
  return response.json() as Promise<ChartContextSnapshot>;
}

/** One cached options/levels read per ticker, shared by the chart and side panels. */
export function useChartContext(symbol: string) {
  const { data, error, isValidating, mutate } = useSWR(
    `/api/v1/chart-context?symbol=${encodeURIComponent(symbol)}`, contextFetcher,
    { refreshInterval: 60_000, dedupingInterval: 30_000, keepPreviousData: false,
      refreshWhenHidden: false, refreshWhenOffline: false, errorRetryCount: 1 },
  );
  return {
    context: matchingChartContext(symbol, data, Boolean(error)),
    failed: Boolean(error),
    loading: isValidating,
    refresh: () => void mutate(),
  };
}
