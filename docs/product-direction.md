# RegimeShift product direction — September 12, 2026

## Current objective

Build an Alpaca-only, chart-first paper research workstation for discovering
options opportunities, inspecting trade theses, placing controlled paper orders,
and comparing outcomes. Keep navigation and visual language consistent; move
secondary research detail out of the main trading workspace.

User explicitly authorized paper experimentation without requiring a passing
holdout backtest. `PAPER_EXPERIMENT_MODE=true` is the current default and the
scheduled worker setting. Set it to `false` to restore holdout-gated entries.
Historical results are never rewritten to imply validation. Order enable flags,
actionable signal qualification, council approval, deterministic risk, fresh
quotes, account capacity, paper endpoints, and market clock remain mandatory.
Watch-only signals never become orders merely because experiment mode is on.

## Delivery tracks

1. Opportunities → linked chart → options ticket, with compact navigation.
2. Existing R-factor, chop, and RSI/volume ideas remain inspectable research
   filters and chart markers. A filtered match is not an automatic trade thesis.
3. Paper entry experiments, managed exits independent of entry evidence, and
   inspectable reasons for every rejected or submitted decision.
4. Durable order/fill journal and reconciliation, then per-strategy results
   grouped by version, holding horizon, regime, fees and slippage. Treat paper
   fills as simulation, not proof of an executable live edge.
5. Use results to propose and test changes against unseen data, not silently
   let an LLM rewrite its own hard risk policy.
6. Fast intraday through longer swing horizons are a roadmap, not current
   capability. Current worker checks every five minutes, scanner bars are
   15-minute or daily, and option expiry/exit rules limit holding periods.
   Ten-second strategies need a continuously running streaming worker, quote
   entitlement verification, durable coordination and dedicated fast exits.
   Multi-month trades need a separate long-dated contract/exit policy.

## Confirmed eight-part roadmap

| Upgrade | Current footing | Remaining work |
| --- | --- | --- |
| Potential Move Scanner | Direction-neutral ATR/realized-volatility ranges; on-demand IV/option cost context | Point-in-time IV rank/percentile, events, term structure, verified same-strike straddles |
| Structured Thesis Engine | Structured scanner, council, risk and diagnostics | One versioned thesis, grouped support/oppose/abstain evidence, freshness and catalysts |
| High-value indicators | EMA 18/50, swing levels, relative strength, GEX proxies, sector rotation | Anchored VWAP, opening range, ADX, squeeze, breadth, rates/credit/event context |
| Dependable execution | Paper CLI worker, duplicate checks, independent managed exits | Persistent streaming service, heartbeat, partial fills, controlled cancel/replace, restart recovery |
| Evidence database | Inspectable cycle artifacts, read-only broker history | Shared transaction-safe journal, reservations, replay and reconciliation |
| Strategy plugins | Regime-aware defined-risk verticals | Independent strategy interfaces and validation; no untested condor/calendar execution |
| Portfolio risk | Whole-account capacity, daily loss and overlapping exposure guards | Greeks, sector/correlation/expiry concentration, weekly limits and shock scenarios |
| Data quality | Alpaca adapters and source/limitation labels | Verified SIP/OPRA entitlements, point-in-time quality auditing; no invented flow data |

The two supplied indicators are the daily R-factor and RSI + volume spike.
R-factor reproduces the submitted uncapped RVOL calculation (its comment says
“capped” but the expression does not cap). The bearish threshold is a labeled
mirror. RSI extremes are context, not guaranteed tops/bottoms; quiet excursions
and price-confirmed reversal modes reduce repeated marks. ATR/price is a low
volatility filter, distinct from the separate CHOP measure.

Build order after the chart/paper-policy release: persistent worker + database;
extend move scanner + unified thesis; streaming fills; strategy backtests;
portfolio Greeks; better data; additional structures. Fast refresh controls
must never be presented as fast strategy execution. All eight remain tracked,
not claimed complete merely because a field or panel exists.

No additional broker integration is required for this phase. Shared database provisioning
remains blocked on Vercel authentication; do not pretend local JSON is a durable
cross-worker ledger. The app's active-goal tool cannot edit objective text, so
this document records the revised scope without falsely completing that goal.
