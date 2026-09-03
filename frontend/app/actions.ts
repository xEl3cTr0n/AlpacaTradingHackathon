"use server";

import { analyzeSnapshot, executeManualTrade, fetchScanner, previewManualTrade } from "@/lib/api";
import type { AnalysisControls, DecisionSnapshot, ManualTradePreview, ManualTradeRequest, ManualTradeResult, ScannerSnapshot } from "@/lib/types";

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

export async function refreshScanner(): Promise<ScannerSnapshot> {
  return fetchScanner(12);
}

export async function runManualPreview(
  request: ManualTradeRequest,
): Promise<ManualTradePreview> {
  return previewManualTrade(request);
}

export async function submitManualPaperTrade(
  request: ManualTradeRequest,
  operatorToken: string,
  confirmation: string,
): Promise<ManualTradeResult> {
  if (confirmation !== "PAPER") throw new Error("Type PAPER to confirm the paper order.");
  if (operatorToken.length < 12) throw new Error("Enter the operator token.");
  return executeManualTrade(request, operatorToken);
}
