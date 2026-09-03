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

const syntheticSource = /demo|synthetic|fallback/i;

async function responseJson<T>(response: Response, label: string): Promise<T> {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${label} returned ${response.status}: ${detail.slice(0, 180)}`);
  }
  return (await response.json()) as T;
}

function requireLiveSource(label: string, source: string): void {
  if (syntheticSource.test(source)) throw new Error(`${label} returned non-live data.`);
}

export async function fetchSnapshot(symbol = "SPY"): Promise<DecisionSnapshot> {
  const response = await fetch(`${apiUrl}/api/v1/snapshot?symbol=${encodeURIComponent(symbol)}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
  const snapshot = await responseJson<DecisionSnapshot>(response, "Regime API");
  requireLiveSource("Regime API", snapshot.market.source);
  return snapshot;
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
  const snapshot = await responseJson<DecisionSnapshot>(response, "Analysis API");
  requireLiveSource("Analysis API", snapshot.market.source);
  return snapshot;
}

export async function fetchPlatform(): Promise<PlatformSnapshot> {
  const response = await fetch(`${apiUrl}/api/v1/platform`, {
    cache: "no-store",
    signal: AbortSignal.timeout(10_000),
  });
  const platform = await responseJson<PlatformSnapshot>(response, "Platform API");
  requireLiveSource("Platform API", platform.mode);
  return platform;
}

export async function fetchScanner(limit = 12): Promise<ScannerSnapshot> {
  const response = await fetch(`${apiUrl}/api/v1/scanner?limit=${limit}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(15_000),
  });
  const scanner = await responseJson<ScannerSnapshot>(response, "Scanner API");
  requireLiveSource("Scanner API", scanner.source);
  return scanner;
}
