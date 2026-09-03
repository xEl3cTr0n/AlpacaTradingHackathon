import { getDemoPlatform, getDemoScanner, getDemoSnapshot } from "@/lib/demo";
import type {
  AnalysisControls,
  DecisionSnapshot,
  PlatformSnapshot,
  ScannerSnapshot,
} from "@/lib/types";

// Vercel Services injects BACKEND_URL for server-to-server requests. The
// explicit override remains useful when the frontend and API run separately.
const apiUrl =
  process.env.BACKEND_URL ?? process.env.REGIMESHIFT_API_URL ?? "http://127.0.0.1:8000";

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

export async function fetchScanner(limit = 12): Promise<ScannerSnapshot> {
  try {
    const response = await fetch(`${apiUrl}/api/v1/scanner?limit=${limit}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(12_000),
    });
    if (!response.ok) throw new Error(`Scanner API returned ${response.status}`);
    return (await response.json()) as ScannerSnapshot;
  } catch (error) {
    console.warn("Scanner API unreachable, serving offline scanner preview:", error);
    return getDemoScanner();
  }
}
