import { getDemoSnapshot } from "@/lib/demo";
import type { DecisionSnapshot } from "@/lib/types";

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

