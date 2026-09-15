# Focused terminal layout — September 14, 2026

## Scope

An OpenTerminal-inspired information hierarchy, using the existing Alpaca adapters
and Lightweight Charts engine. No upstream code copied or new data vendor added.

- Trade / Portfolio / Research replace the duplicate primary navigation.
- One global ticker links watchlist, chart, automatic GEX context, thesis and chain.
- Command/Ctrl-K focuses ticker search; it never submits an order.
- Watchlist and scanner share a rail. The filter dialog retains daily R-Factor,
  chop and RSI-volume presets. Full diagnostics remain under Research.
- Positions, orders and the selected ticker's options chain share a bottom dock.
- The existing one-spread paper ticket opens beside the chain on wide screens.
  Narrow screens stack it. Quotes tables scroll independently with pinned strike
  and leg columns. Selecting a ticker unmounts the old ticket and clears its draft.
- Thesis evidence and council review remain available through disclosure controls.

## Persistence and execution boundaries

`regimeshift.workspace.v1` stores a whitelist of display preferences: ticker,
timeframe, RSI mode, chart overlays, quote interval, rail/dock tabs and watchlist.
Unknown fields are stripped; corrupt storage falls back to display defaults.
When browser storage is unavailable, preferences work in memory for the session.
Tokens, order drafts, confirmations and execution permissions are never persisted.
Existing scanner presets continue to use their separate browser-local storage.

No backend, strategy, paper-experiment gate or risk rules changed. Preview, operator
authorization and explicit PAPER confirmation remain required. The ticket still
submits one defined-risk spread, not ten contracts. Closing the ticket clears its
authorization fields; successful submission clears preview and refreshes account.

Quote polling (paused/1/5/10 seconds), chart/context/scanner refresh (60 seconds),
account refresh (30 seconds), option chain refresh (30 seconds), and worker checks
remain distinct. Worker heartbeat is labeled unverified. This is not a streaming
execution worker or a guarantee of fast exits. GEX remains a positioning proxy with
unverified Greek/OI timestamp freshness, not measured dealer inventory.

## Verification

- Backend: 213 tests pass (one pre-existing websockets deprecation warning).
- Frontend: ESLint and production build pass.
- Six preference parsing/whitelist tests and three chart-context tests pass.
- Browser: ticker switch SPY → AAPL → MSFT updates chart, automatic GEX and chain
  without council invocation. Two-leg selection populates the ticket; submission
  stays disabled without preview/authorization. No order was placed.
- Filter dialog opens, preset selection works, Escape dismisses. Command-K focuses
  search; ticket close returns keyboard focus to its toggle.
- Ticker, watchlist tab, options dock, daily timeframe, 10-second quotes and collapsed
  GEX profile survive reload. Changing ticker clears the selected option legs.
- Measured no document overflow at 375px and 1440px. Fixed chart grid sizing and a
  conflicting automatic/manual resize setting found during browser checks.
- Browser warning/error log was empty after the resize fix.

Remaining work belongs to the broader roadmap: durable worker heartbeat, evidence
ledger/replay and strategy validation. This layout release does not implement those.
