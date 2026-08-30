"use server";

import { analyzeSnapshot } from "@/lib/api";
import type { AnalysisControls, DecisionSnapshot } from "@/lib/types";

export async function runAnalysis(
  symbol: string,
  controls: AnalysisControls,
): Promise<DecisionSnapshot> {
  const normalized = symbol.trim().toUpperCase();
  if (!/^[A-Z.]{1,10}$/.test(normalized)) {
    throw new Error("Use a valid ticker containing letters or a period.");
  }
  return analyzeSnapshot(normalized, controls);
}
