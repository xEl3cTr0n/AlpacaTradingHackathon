# Architecture

## Decision pipeline

```text
MarketDataProvider
  -> RegimeEngine
  -> Technical + Research evidence
  -> Bull + Bear adversarial theses
  -> StrategyPolicy
  -> RiskGate (approve / resize / veto)
  -> DecisionSnapshot audit record
```

The system intentionally separates calculation, persuasion, and authorization.
Technical indicators and the risk gate are deterministic. Bull and Bear agents
may later be backed by different LLM providers, but they only emit structured
evidence. The orchestrator—not an LLM—enforces the final policy.

## Regime state

Regimes combine a direction (`bullish`, `sideways`, `bearish`) with a volatility
bucket (`low`, `normal`, `high`). A confidence score and component metrics are
stored with every classification. The next iteration should persist the prior
state and require confirmation across observations before switching regimes.

## Execution boundary

The MVP stops at an auditable order preview. `ENABLE_PAPER_ORDERS` is reserved
for a later broker adapter and defaults to false. Before enabling submission:

1. Resolve option contracts from Alpaca's chain using liquidity and Greeks.
2. Recalculate max loss from executable bid/ask quotes.
3. Require an explicit operator confirmation and idempotency key.
4. Submit only to `paper-api.alpaca.markets`.
5. Reconcile fills and reject stale previews.

## Suggested parallel work

- Agent A: option-chain selection and multi-leg preview pricing.
- Agent B: persisted decision/event store and replayable backtests.
- Agent C: LLM provider adapters with JSON-schema validation.
- Agent D: dashboard interactions and historical experiment comparison.

