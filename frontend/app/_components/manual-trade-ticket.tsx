"use client";

import { KeyRound, Send, ShieldCheck } from "lucide-react";
import { useState, useTransition } from "react";
import { runManualPreview, submitManualPaperTrade } from "@/app/actions";
import type { ManualTradePreview, ManualTradeRequest } from "@/lib/types";

const emptyTrade: ManualTradeRequest = {
  long_symbol: "",
  short_symbol: "",
  limit_debit: 1,
  quantity: 1,
  rationale: "Operator-entered defined-risk setup",
};

export function ManualTradeTicket() {
  const [trade, setTrade] = useState(emptyTrade);
  const [preview, setPreview] = useState<ManualTradePreview | null>(null);
  const [token, setToken] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("Enter exact OCC option symbols. Preview never places an order.");
  const [pending, startTransition] = useTransition();

  function runPreview() {
    setMessage("Checking structure, quotes, liquidity, and risk…");
    startTransition(async () => {
      try {
        const next = await runManualPreview(trade);
        setPreview(next);
        setMessage(next.valid ? "Preview passed. Execution still needs token + PAPER." : "Risk gate rejected this preview.");
      } catch (error) {
        setPreview(null);
        setMessage(error instanceof Error ? error.message : "Preview failed.");
      }
    });
  }

  function submit() {
    setMessage("Submitting one atomic multi-leg order to Alpaca paper…");
    startTransition(async () => {
      try {
        const result = await submitManualPaperTrade(trade, token, confirmation);
        setMessage(`Paper order ${result.status}: ${result.order_id}`);
        setToken("");
        setConfirmation("");
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Paper order failed.");
      }
    });
  }

  return (
    <div className="view-stack">
      <header className="view-heading"><div><p className="eyebrow">Operator console</p><h1>Manual paper trade</h1><p>Two-leg debit spreads only. Same underlying, expiry, and option type.</p></div><span className="decision-chip approved"><ShieldCheck size={15} aria-hidden="true" /> $200 hard cap</span></header>
      <section className="panel manual-ticket">
        <div className="panel-heading"><div><p className="eyebrow">Alpaca MLeg ticket</p><h2>Exact contracts</h2></div><KeyRound size={19} aria-hidden="true" /></div>
        <div className="manual-form-grid">
          <label>Long OCC symbol<input value={trade.long_symbol} onChange={(event) => { setTrade({ ...trade, long_symbol: event.target.value.toUpperCase() }); setPreview(null); }} placeholder="AAPL261016C00200000" /></label>
          <label>Short OCC symbol<input value={trade.short_symbol} onChange={(event) => { setTrade({ ...trade, short_symbol: event.target.value.toUpperCase() }); setPreview(null); }} placeholder="AAPL261016C00205000" /></label>
          <label>Limit debit<input type="number" min="0.01" max="2" step="0.01" value={trade.limit_debit} onChange={(event) => { setTrade({ ...trade, limit_debit: Number(event.target.value) }); setPreview(null); }} /></label>
          <label>Research note<input maxLength={240} value={trade.rationale} onChange={(event) => setTrade({ ...trade, rationale: event.target.value })} /></label>
        </div>
        <button type="button" className="secondary-action" onClick={runPreview} disabled={pending}>Preview gates</button>
        {preview && <div className={`manual-preview ${preview.valid ? "passed" : "failed"}`}><div><span>Structure</span><strong>{preview.underlying_symbol} {preview.long_strike}/{preview.short_strike} {preview.option_type}</strong></div><div><span>Natural debit</span><strong>{preview.market_debit == null ? "N/A" : `$${preview.market_debit.toFixed(2)}`}</strong></div><div><span>Maximum loss</span><strong>${preview.maximum_loss.toFixed(2)}</strong></div><div><span>Maximum reward</span><strong>${preview.maximum_reward.toFixed(2)}</strong></div><ul>{preview.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></div>}
        <div className="manual-auth">
          <label>Operator token<input type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} /></label>
          <label>Type PAPER<input value={confirmation} onChange={(event) => setConfirmation(event.target.value.toUpperCase())} /></label>
          <button type="button" className="primary-action" onClick={submit} disabled={pending || !preview?.valid}><Send size={16} aria-hidden="true" /> Submit paper order</button>
        </div>
        <p className="run-status" role="status" aria-atomic="true">{message}</p>
      </section>
    </div>
  );
}
