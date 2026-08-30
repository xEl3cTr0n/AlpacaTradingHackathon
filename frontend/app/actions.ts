"use server";

import { fetchSnapshot } from "@/lib/api";
import type { DecisionSnapshot } from "@/lib/types";

export async function runAnalysis(symbol: string): Promise<DecisionSnapshot> {
  const normalized = symbol.trim().toUpperCase();
  if (!/^[A-Z.]{1,10}$/.test(normalized)) {
    throw new Error("Use a valid ticker containing letters or a period.");
  }
  return fetchSnapshot(normalized);
}

