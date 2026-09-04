# Architecture

## Decision pipeline

```text
MarketDataProvider
  -> Alpaca OHLCV chart history (1m / 5m / 15m / 1D)
  -> FRED real GDP + CPI -> TopDownMacroQuad (6-hour cache)
  -> LargeCapScanner (24 names, completed 15-minute 18 EMA cross + daily context)
  -> RegimeEngine + SectorRotationEngine + SwingEngine
  -> BottomUpQuad (security trend + ETF breadth)
  -> Alpaca option chain + contract OI -> GEX / GMC microstructure evidence
  -> MOOD / VIBE research proxy (coverage and missing inputs recorded)
  -> Technical + Microstructure + Swing + Research + Rotation evidence
  -> Bull + Bear adversarial theses
  -> VotingCouncil (6 deterministic proposal-relative votes)
  -> StrategyPolicy
  -> RiskGate (approve / $200 exploration resize / veto)
  -> DecisionSnapshot audit record
  -> Alpaca CLI contract discovery + quote validation
  -> dry-run or gated paper-only multi-leg order
  -> ManagedExitPolicy (profit / loss / DTE / regime reversal)
```

The system intentionally separates calculation, persuasion, and authorization.
Technical indicators and the risk gate are deterministic. Bull and Bear agents
may later be backed by different LLM providers, but they only emit structured
evidence. The orchestrator—not an LLM—enforces the final policy.

The 1/5/10-second UI control calls a lightweight Alpaca IEX stock snapshot only.
An in-process 800 ms deduplication cache limits duplicate upstream requests from
rapid viewers. Slow macro, bottom-up, news, and option-chain layers are not tied
to that control; their source timestamps and cadences are shown in the interface.
The chart terminal separately refreshes completed Alpaca bars every 30–60
seconds, while incoming tape ticks update only the current candle. TradingView
Lightweight Charts is a client-side renderer; it is not a market-data source.

## Regime state

Regimes combine a direction (`bullish`, `sideways`, `bearish`) with a volatility
bucket (`low`, `normal`, `high`). A confidence score and component metrics are
stored with every classification. The next iteration should persist the prior
state and require confirmation across observations before switching regimes.

## Tooling and execution boundary

The official Alpaca MCP server exposes read-only account, stock, option, and
news tools to Claude and Gemini. Trading tools are intentionally excluded so an
LLM cannot bypass policy. The official Alpaca CLI is pinned separately and is
the only command path used by the autonomous execution runner. A separate
operator-token-protected API path supports manual paper MLeg orders; it is
disabled by default and hard-codes the paper client.

`ENABLE_PAPER_ORDERS` defaults to false. A CLI submission additionally requires
the runner's explicit `--execute` flag and all of these conditions:

1. The 6-agent council approves the proposed direction.
2. The separate deterministic Risk gate approves it.
3. The signal is either a validated SPY swing breakout or a scanner-qualified
   18 EMA cross with trend, market, relative-strength, and volume confirmation.
4. The instrument is a one-lot, defined-risk XSP index spread or a spread on a
   stock in the scanner's fixed large-cap universe.
5. Alpaca CLI contract discovery, live bid/ask checks, and (for equity options)
   a 50-contract open-interest floor pass.
6. Quoted maximum loss is inside the account risk budget.
7. `ALPACA_LIVE_TRADE=false` is injected by code and cannot be overridden.

Live GEX uses the supplied paper's explicit convention (+calls, -puts) over a
bounded 0–45 DTE, 85–115% moneyness chain. It joins Alpaca snapshot Greeks to
contract open interest and records data quality and the dealer-position
assumption. GEX is volatility/structure evidence, not a standalone direction
signal. Missing data abstains in the council and vetoes production authorization;
negative gamma imposes a $200 cap, while high GMC requires a confirmed breakout.
The professor-supplied `modGammaProfile` scoring is ported as a pure calculation
for call/put walls, directional bias, put trapdoor, key gamma, key delta, and
hedge wall. Those levels are exposed as evidence and chart overlays only, so
they cannot grant authorization or weaken the deterministic Risk gate.

The manual ticket obtains a bounded Alpaca chain, filters to one expiry and the
ten nearest requested ITM/OTM calls or puts, then requires a structurally valid
vertical spread. Submission remains a one-lot atomic MLeg paper order protected
by preview validation, the operator token, and explicit `PAPER` confirmation.

The scheduled worker evaluates every qualified scanner candidate through the
council rather than stopping at the first veto. The backtested daily production
tier can execute when explicitly enabled. The newer intraday production and
exploration tiers remain preview-only because their dated holdout gates failed.
`ENABLE_EXPLORATION_ORDERS` is an independent lock and cannot override that
evidence gate.

Exit automation only manages complete two-leg spreads whose entry order has a
RegimeShift client ID. It submits the inverse legs together, so it never
intentionally leaves a naked short option.

The public Vercel app is the observability and analysis surface. The stdio MCP
server and native CLI execute in the local/worker environment, not in a Vercel
request handler.

## Suggested parallel work

- Agent A: option-chain selection and multi-leg preview pricing.
- Agent B: persisted decision/event store and replayable backtests.
- Agent C: LLM provider adapters with JSON-schema validation.
- Agent D: dashboard interactions and historical experiment comparison.
