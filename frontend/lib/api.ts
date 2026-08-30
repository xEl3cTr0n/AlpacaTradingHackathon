import { getDemoPlatform, getDemoSnapshot } from "@/lib/demo";
import type { AnalysisControls, DecisionSnapshot, PlatformSnapshot } from "@/lib/types";

const apiUrl = process.env.REGIMESHIFT_API_URL ?? "http://127.0.0.1:8000";

export async function fetchSnapshot(symbol = "SPY"): Promise<DecisionSnapshot> {
  try {
    const response = await fetch(`${apiUrl}/api/v1/snapshot?symbol=${encodeURIComponent(symbol)}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) throw new Error(`Regime API returned ${response.status}`);
    return (await response.json()) as DecisionSnapshot;
  } catch (error) {
    console.warn("Regime API unreachable, serving offline demo snapshot:", error);
    const demo = getDemoSnapshot();
    demo.market.symbol = symbol;
    return demo;
  }
}

export async function analyzeSnapshot(
  symbol: string,
  controls: AnalysisControls,
): Promise<DecisionSnapshot> {
  const response = await fetch(`${apiUrl}/api/v1/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, ...controls }),
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Analysis API returned ${response.status}: ${body.slice(0, 180)}`);
  }
  return (await response.json()) as DecisionSnapshot;
}

export async function fetchPlatform(): Promise<PlatformSnapshot> {
  try {
    const response = await fetch(`${apiUrl}/api/v1/platform`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) throw new Error(`Platform API returned ${response.status}`);
    return (await response.json()) as PlatformSnapshot;
  } catch (error) {
    console.warn("Platform API unreachable, serving offline demo telemetry:", error);
    return getDemoPlatform();
  }
}
