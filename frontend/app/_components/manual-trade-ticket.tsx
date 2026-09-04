"use client";

import { KeyRound, RefreshCw, Search, Send, ShieldCheck } from "lucide-react";
import { useMemo, useState, useTransition } from "react";
import useSWR from "swr";
import { runManualPreview, submitManualPaperTrade } from "@/app/actions";
import type {
  ManualTradePreview,
  ManualTradeRequest,
  OptionChainContract,
  OptionChainSnapshot,
} from "@/lib/types";

const emptyTrade: ManualTradeRequest = {
  long_symbol: "",
  short_symbol: "",
  limit_debit: 1,
  quantity: 1,
  rationale: "Operator-entered defined-risk setup",
};

const chainFetcher = async (url: string): Promise<OptionChainSnapshot> => {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Options chain returned ${response.status}`);
  }
  return response.json() as Promise<OptionChainSnapshot>;
};

const price = (value?: number | null) => value == null ? "—" : `$${value.toFixed(2)}`;
const percent = (value?: number | null) => value == null ? "—" : `${(value * 100).toFixed(1)}%`;

export function ManualTradeTicket({ defaultSymbol = "SPY" }: { defaultSymbol?: string }) {
  const [draftSymbol, setDraftSymbol] = useState(defaultSymbol);
  const [underlying, setUnderlying] = useState(defaultSymbol);
  const [optionType, setOptionType] = useState<"call" | "put">("call");
  const [moneyness, setMoneyness] = useState<"itm" | "otm">("otm");
  const [expiration, setExpiration] = useState("");
  const [trade, setTrade] = useState(emptyTrade);
  const [preview, setPreview] = useState<ManualTradePreview | null>(null);
  const [token, setToken] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("Choose a long and short leg. Preview never places an order.");
  const [pending, startTransition] = useTransition();
  const validUnderlying = /^[A-Z.]{1,10}$/.test(underlying);
  const chainKey = validUnderlying
    ? `/api/v1/options/chain?symbol=${encodeURIComponent(underlying)}&option_type=${optionType}&moneyness=${moneyness}&limit=10${expiration ? `&expiration=${expiration}` : ""}`
    : null;
  const { data: chain, error: chainError, isLoading, isValidating, mutate } = useSWR(
    chainKey,
    chainFetcher,
    {
      refreshInterval: 30_000,
      dedupingInterval: 10_000,
      refreshWhenHidden: false,
      refreshWhenOffline: false,
      errorRetryCount: 1,
    },
  );
  const selectedExpiration = expiration || chain?.expiration || "";
  const longContract = chain?.contracts.find((contract) => contract.symbol === trade.long_symbol);
  const shortContract = chain?.contracts.find((contract) => contract.symbol === trade.short_symbol);
  const naturalDebit = useMemo(() => {
    if (longContract?.ask == null || shortContract?.bid == null) return null;
    return Math.max(0.01, longContract.ask - shortContract.bid);
  }, [longContract, shortContract]);

  function resetLegs() {
    setTrade((current) => ({ ...current, long_symbol: "", short_symbol: "" }));
    setPreview(null);
  }

  function loadSymbol() {
    const normalized = draftSymbol.trim().toUpperCase();
    if (!/^[A-Z.]{1,10}$/.test(normalized)) {
      setMessage("Use a valid ticker containing letters or a period.");
      return;
    }
    setUnderlying(normalized);
    setExpiration("");
    resetLegs();
    setMessage(`Loading ${normalized} option contracts…`);
  }

  function changeType(next: "call" | "put") {
    setOptionType(next);
    resetLegs();
  }

  function changeMoneyness(next: "itm" | "otm") {
    setMoneyness(next);
    resetLegs();
  }

  function validShort(contract: OptionChainContract) {
    if (!longContract) return true;
    return optionType === "call"
      ? contract.strike > longContract.strike
      : contract.strike < longContract.strike;
  }

  function chooseLong(contract: OptionChainContract) {
    const keepShort = shortContract && (
      optionType === "call"
        ? contract.strike < shortContract.strike
        : contract.strike > shortContract.strike
    );
    setTrade((current) => ({
      ...current,
      long_symbol: contract.symbol,
      short_symbol: keepShort ? current.short_symbol : "",
    }));
    setPreview(null);
    setMessage(`Long leg selected at ${contract.strike}. Choose the defined-risk short leg.`);
  }

  function chooseShort(contract: OptionChainContract) {
    if (!validShort(contract)) {
      setMessage(
        optionType === "call"
          ? "A call-spread short strike must be above the long strike."
          : "A put-spread short strike must be below the long strike.",
      );
      return;
    }
    const nextDebit = longContract?.ask != null && contract.bid != null
      ? Math.max(0.01, longContract.ask - contract.bid)
      : trade.limit_debit;
    setTrade((current) => ({
      ...current,
      short_symbol: contract.symbol,
      limit_debit: Math.min(10, Number(nextDebit.toFixed(2))),
    }));
    setPreview(null);
    setMessage(`Short leg selected at ${contract.strike}. Preview the deterministic gates next.`);
  }

  function runPreview() {
    if (!trade.long_symbol || !trade.short_symbol) {
      setMessage("Select both a long and short contract first.");
      return;
    }
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
      <header className="view-heading"><div><p className="eyebrow">Operator console</p><h1>Options chain ticket</h1><p>Browse ten nearby calls or puts, choose two legs, then pass the paper-only risk gate.</p></div><span className="decision-chip approved"><ShieldCheck size={15} aria-hidden="true" /> $1,000 max · 50% stop</span></header>
      <section className="panel option-chain-panel" aria-labelledby="option-chain-title">
        <div className="panel-heading"><div><p className="eyebrow">Alpaca option chain</p><h2 id="option-chain-title">Contract picker</h2></div><span className="source-label">10 contracts · selection only</span></div>
        <div className="chain-controls">
          <label>Underlying<div className="chain-symbol-input"><input aria-label="Underlying ticker" value={draftSymbol} onChange={(event) => setDraftSymbol(event.target.value.toUpperCase())} onKeyDown={(event) => { if (event.key === "Enter") loadSymbol(); }} /><button type="button" aria-label="Load option chain" onClick={loadSymbol}><Search size={15} aria-hidden="true" /></button></div></label>
          <fieldset><legend>Direction</legend><div className="segmented-control"><button type="button" className={optionType === "call" ? "active positive" : ""} aria-pressed={optionType === "call"} onClick={() => changeType("call")}>Calls · bullish</button><button type="button" className={optionType === "put" ? "active negative" : ""} aria-pressed={optionType === "put"} onClick={() => changeType("put")}>Puts · bearish</button></div></fieldset>
          <fieldset><legend>Moneyness</legend><div className="segmented-control"><button type="button" className={moneyness === "otm" ? "active" : ""} aria-pressed={moneyness === "otm"} onClick={() => changeMoneyness("otm")}>OTM</button><button type="button" className={moneyness === "itm" ? "active" : ""} aria-pressed={moneyness === "itm"} onClick={() => changeMoneyness("itm")}>ITM</button></div></fieldset>
          <label>Expiration<select value={selectedExpiration} onChange={(event) => { setExpiration(event.target.value); resetLegs(); }}>{chain?.expirations.map((item) => <option key={item} value={item}>{new Date(`${item}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</option>)}</select></label>
          <button type="button" className="secondary-action icon-action chain-refresh" aria-label="Refresh options chain" onClick={() => void mutate()}><RefreshCw size={15} className={isValidating ? "spinning" : ""} aria-hidden="true" /></button>
        </div>
        <div className="chain-meta"><span>{chain ? `${chain.underlying_symbol} $${chain.underlying_price.toFixed(2)}` : underlying}</span><span>{optionType.toUpperCase()} · {moneyness.toUpperCase()}</span><span>{chain?.source ?? "Alpaca Options API"}</span><span>Showing 10 does not mean buying 10; order quantity stays one spread.</span></div>
        {chainError && <p className="chain-error" role="alert">{chainError.message}</p>}
        <div className="table-scroll chain-table-wrap">
          <table className="option-chain-table">
            <caption>Ten nearest {moneyness.toUpperCase()} {optionType} contracts for {underlying}</caption>
            <thead><tr><th>Strike</th><th>Bid</th><th>Ask</th><th>Mid</th><th>Spread</th><th>OI</th><th>IV</th><th>Delta</th><th>Leg</th></tr></thead>
            <tbody>
              {chain?.contracts.map((contract) => {
                const isLong = trade.long_symbol === contract.symbol;
                const isShort = trade.short_symbol === contract.symbol;
                return <tr key={contract.symbol} className={isLong || isShort ? "selected-contract" : ""}><td><strong>{contract.strike.toFixed(2)}</strong><small>{contract.moneyness.toUpperCase()}</small></td><td>{price(contract.bid)}</td><td>{price(contract.ask)}</td><td>{price(contract.midpoint)}</td><td>{percent(contract.spread_percent)}</td><td>{contract.open_interest?.toLocaleString() ?? "—"}</td><td>{percent(contract.implied_volatility)}</td><td>{contract.delta?.toFixed(2) ?? "—"}</td><td><div className="leg-actions"><button type="button" className={isLong ? "active long" : ""} disabled={contract.ask == null} aria-pressed={isLong} onClick={() => chooseLong(contract)}>Long</button><button type="button" className={isShort ? "active short" : ""} disabled={contract.bid == null || !validShort(contract)} aria-pressed={isShort} onClick={() => chooseShort(contract)}>Short</button></div></td></tr>;
              })}
              {isLoading && !chain && <tr><td colSpan={9} className="portfolio-empty">Loading live Alpaca option quotes…</td></tr>}
              {!isLoading && chain?.contracts.length === 0 && <tr><td colSpan={9} className="portfolio-empty">No matching contracts returned.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
      <section className="panel manual-ticket">
        <div className="panel-heading"><div><p className="eyebrow">Alpaca MLeg ticket</p><h2>Defined-risk spread</h2></div><KeyRound size={19} aria-hidden="true" /></div>
        <div className="selected-legs" aria-label="Selected option legs">
          <div><span>Buy to open</span><strong>{longContract ? `${longContract.strike} ${optionType}` : "Choose long leg"}</strong><small>{trade.long_symbol || "No contract selected"}</small></div>
          <div><span>Sell to open</span><strong>{shortContract ? `${shortContract.strike} ${optionType}` : "Choose short leg"}</strong><small>{trade.short_symbol || "No contract selected"}</small></div>
          <div><span>Natural debit</span><strong>{price(naturalDebit)}</strong><small>Long ask − short bid</small></div>
        </div>
        <div className="manual-form-grid compact-ticket-grid">
          <label>Limit debit<input type="number" min="0.01" max="10" step="0.01" value={trade.limit_debit} onChange={(event) => { setTrade({ ...trade, limit_debit: Number(event.target.value) }); setPreview(null); }} /></label>
          <label>Research note<input maxLength={240} value={trade.rationale} onChange={(event) => setTrade({ ...trade, rationale: event.target.value })} /></label>
          <button type="button" className="secondary-action" onClick={runPreview} disabled={pending || !trade.long_symbol || !trade.short_symbol}>Preview gates</button>
        </div>
        <details className="advanced-contracts"><summary>Advanced: exact OCC symbols</summary><div><label>Long symbol<input value={trade.long_symbol} onChange={(event) => { setTrade({ ...trade, long_symbol: event.target.value.toUpperCase() }); setPreview(null); }} /></label><label>Short symbol<input value={trade.short_symbol} onChange={(event) => { setTrade({ ...trade, short_symbol: event.target.value.toUpperCase() }); setPreview(null); }} /></label></div></details>
        {preview && <div className={`manual-preview ${preview.valid ? "passed" : "failed"}`}><div><span>Structure</span><strong>{preview.underlying_symbol} {preview.long_strike}/{preview.short_strike} {preview.option_type}</strong></div><div><span>Natural debit</span><strong>{price(preview.market_debit)}</strong></div><div><span>Worst-case loss</span><strong>${preview.maximum_loss.toFixed(2)}</strong></div><div><span>Managed stop</span><strong>−${preview.stop_loss_dollars.toFixed(2)}</strong></div><div><span>Maximum reward</span><strong>${preview.maximum_reward.toFixed(2)}</strong></div><ul>{preview.reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul></div>}
        <div className="manual-auth">
          <label>Operator token<input type="password" autoComplete="off" value={token} onChange={(event) => setToken(event.target.value)} /></label>
          <label>Type PAPER<input value={confirmation} onChange={(event) => setConfirmation(event.target.value.toUpperCase())} /></label>
          <button type="button" className="primary-action" onClick={submit} disabled={pending || !preview?.valid}><Send size={16} aria-hidden="true" /> Submit paper order</button>
        </div>
        <p className="run-status" role="status" aria-atomic="true">{message}</p>
        <p className="risk-disclaimer">The 50% stop is monitored by the scheduled paper worker, not guaranteed by the exchange. Gaps, spreads, and polling delay can make realized loss larger, so the Risk Agent reserves the full debit.</p>
      </section>
    </div>
  );
}
