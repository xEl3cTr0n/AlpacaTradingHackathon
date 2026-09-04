import type { DecisionSnapshot } from "@/lib/types";

export const DECISION_RECEIPT_SCHEMA = "regimeshift.decision-receipt.v1";

export function buildDecisionReceipt(snapshot: DecisionSnapshot) {
  return {
    schema: DECISION_RECEIPT_SCHEMA,
    exported_at: new Date().toISOString(),
    decision: {
      id: snapshot.decision_id,
      generated_at: snapshot.generated_at,
      mode: snapshot.mode,
      market: {
        symbol: snapshot.market.symbol,
        as_of: snapshot.market.as_of,
        source: snapshot.market.source,
        current_price: snapshot.market.current_price,
      },
      controls: snapshot.controls,
      regime: snapshot.regime,
      swing: snapshot.swing,
      sector_rotation: snapshot.sector_rotation,
      options_microstructure: snapshot.options_microstructure,
      market_layers: snapshot.market_layers,
      agents: snapshot.agents,
      council: snapshot.council,
      strategy: snapshot.strategy,
      risk_gate: snapshot.risk,
      alpaca_tool_evidence: snapshot.tool_evidence,
    },
    safety: {
      environment: "paper-only",
      deterministic_risk_gate: true,
      order_submitted: false,
      disclaimer: snapshot.disclaimer,
    },
  };
}

export function decisionReceiptFilename(snapshot: DecisionSnapshot) {
  const safeSymbol = snapshot.market.symbol.toLowerCase().replace(/[^a-z0-9.-]/g, "-");
  return `regimeshift-${safeSymbol}-${snapshot.decision_id.slice(0, 12)}.json`;
}
