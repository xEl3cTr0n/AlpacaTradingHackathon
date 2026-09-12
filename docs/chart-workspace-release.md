# Chart workspace and paper experiment policy

## Delivered in this increment

- Trade workspace is the default. Four top-level destinations: Trade, Scanners,
  Portfolio, Research. Research contains council, market layers, backtests and
  worker/tool details. Portfolio no longer repeats the full market chart stack.
- A compact opportunity rail links selected symbols to the Alpaca-powered
  Lightweight Charts chart, the underlying-level thesis and manual option chain.
  Built-in R-factor, trend/chop and quiet-reversal presets reuse tested filters.
- RSI marker controls are disclosed on demand. Chart viewport survives bar
  refreshes. Quotes are displayed separately from real historical candles:
  polling a last trade does not manufacture OHLC/volume or repaint newer bars.
- Tape polling can be paused or set to 1/5/10 seconds. Chart bars refresh at
  30/60 seconds, scanner display at 60 seconds, account at 30 seconds. These
  controls do not change the five-minute paper worker execution cadence.
- An account read failure can show an unavailable account while chart research
  remains accessible. No invented balances or claims of a verified heartbeat.
- `PAPER_EXPERIMENT_MODE=true` allows supported actionable scanner tiers without
  a passing holdout. Report validity/pass fields remain unchanged. Watch-only,
  unsupported horizons, disabled exploration and non-paper policies stay closed.
  Council/risk/account/quote checks and order enable switches remain independent.
- Managed exits run before entry research, including scanner/evidence outages.

## Verification and limits

Backend regression tests cover experimental authorization without falsifying
backtests, watch/unknown/live-policy rejection, Risk Agent and council vetoes,
and the actual workflow shell's independent entry/exit flags. Filter tests cover
strict daily thresholds, missing data, RSI modes, CHOP and preset round trips.
Frontend lint and production build are required for release.

Read-only integration checks returned 24 candidates and 300 NVDA bars, plus RSI
events, from Alpaca. Account lookup had one transient 502 then recovered.
Server-rendered HTML contained the new workspace, controls and experimental
policy label. This is not a browser interaction test: local Chrome exits before
opening and in-app browser control fails to initialize. Visual/responsive checks
remain unverified, not reported as passed. No order was placed for UI testing.

Next: shared durable evidence database and persistent worker, then the confirmed
eight-part roadmap in `product-direction.md`. No ten-second scalping,
multi-month holding policy, self-modifying trading rules, or verified live edge
is claimed by this release.
