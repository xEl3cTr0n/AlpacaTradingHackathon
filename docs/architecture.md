# Architecture

## Decision pipeline

```text
MarketDataProvider
  -> LargeCapScanner (24 names, 18 EMA cross + confirmation)
  -> RegimeEngine + SectorRotationEngine + SwingEngine
  -> Technical + Swing + Research + Rotation evidence
  -> Bull + Bear adversarial theses
  -> VotingCouncil (5 deterministic proposal-relative votes)
  -> StrategyPolicy
  -> RiskGate (approve / resize / veto)
  -> DecisionSnapshot audit record
  -> Alpaca CLI contract discovery + quote validation
  -> dry-run or gated paper-only multi-leg order
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

## Tooling and execution boundary

The official Alpaca MCP server exposes read-only account, stock, option, and
news tools to Claude and Gemini. Trading tools are intentionally excluded so an
LLM cannot bypass policy. The official Alpaca CLI is pinned separately and is
the only command path used by the autonomous execution runner.

`ENABLE_PAPER_ORDERS` defaults to false. A CLI submission additionally requires
the runner's explicit `--execute` flag and all of these conditions:

1. The 5-agent council approves the proposed direction.
2. The separate deterministic Risk gate approves it.
3. The signal is either a validated SPY swing breakout or a scanner-qualified
   18 EMA cross with trend, market, relative-strength, and volume confirmation.
4. The instrument is a one-lot, defined-risk XSP index spread or a spread on a
   stock in the scanner's fixed large-cap universe.
5. Alpaca CLI contract discovery, live bid/ask checks, and (for equity options)
   a 50-contract open-interest floor pass.
6. Quoted maximum loss is inside the account risk budget.
7. `ALPACA_LIVE_TRADE=false` is injected by code and cannot be overridden.

The public Vercel app is the observability and analysis surface. The stdio MCP
server and native CLI execute in the local/worker environment, not in a Vercel
request handler.

## Suggested parallel work

- Agent A: option-chain selection and multi-leg preview pricing.
- Agent B: persisted decision/event store and replayable backtests.
- Agent C: LLM provider adapters with JSON-schema validation.
- Agent D: dashboard interactions and historical experiment comparison.
