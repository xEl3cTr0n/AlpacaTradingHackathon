# Scanner workbench: R-Factor, CHOP and RSI/volume

Research only. No new signal changes the worker, votes, broker endpoints, size,
backtest execution gates or exits. Use Scanner → filter/preset → Inspect → Open
paper options chain. That handoff selects the underlying; it never submits an order.

## Formula parity and clocks

- R-Factor ports the supplied DAY ThinkScript: `100 * (.50*directionalRVOL +
  .25*openChangePct + .15*momentumPct + .10*typicalPriceDistancePct)`, rounded to
  one decimal before the strict `>150` comparison. Current bar is included in
  the 14-bar volume mean. The actual user code does not cap RVOL, despite its
  comment. `<-150` is a separately labeled bearish extension. Typical price is
  `(high+low+close)/3`, not VWAP. Bad OHLC is unavailable, not a fake zero.
- Completed DAY readings exclude today's New York session. Today's daily score
  is separately provisional, conservatively even after close. Intraday bars
  must finish before evaluation. IEX is partial-market volume; do not expect
  identical results to Thinkorswim / consolidated exchange feeds.
- CHOP14 = `100*log10(sum(TR,14)/(maxHigh14-minLow14))/log10(14)`.
  Below 38.2 = trend, above 61.8 = chop, otherwise transition. Flat tape = 100;
  window-edge gap effects bounded to [0,100]. Daily and 15-minute CHOP remain
  separate. This measures path shape, not direction or future profit.
- RSI uses Wilder/RMA gains/losses seeded from 14 changes. Volume SMA20 includes
  current bar. Original raw signals require strict `volume/SMA20 >1.2` and
  `RSI>70` or `<30`. ATR14 uses Wilder smoothing, seeded by 14 true ranges.
  Optional ATR/price `<0.005` suppression is a **low-volatility** filter, not CHOP;
  off by default as supplied. Undefined all-flat RSI and bad bars produce no signal.

Sources: [ThinkScript Average](https://toslc.thinkorswim.com/center/reference/thinkScript/Functions/Tech-Analysis/Average),
[TradingView CHOP](https://www.tradingview.com/support/solutions/43000501980-choppiness-index-chop/),
[Pine reference](https://www.tradingview.com/pine-script-reference/v6/).

## Quieter RSI context (our extension, not the original formula)

One alert per RSI extreme excursion, with at least five bars between alerts.
The latch resets outside the extreme. Within five subsequent completed bars:

- Overbought + RSI drops below 70 + close below signal candle low: reversal down.
- Oversold + RSI rises above 30 + close above signal candle high: reversal up.
- An opposite-edge break while RSI stays extreme: continuation context.

No future bars are consulted. Reversal is emitted at its confirmation bar, never
backdated to an assumed top or bottom. Raw extrema can repeat; quiet alerts cannot.
An extreme/continuation cue may support review of an existing option position, but
does not automatically close one. No divergence detection or pivot clairvoyance claimed.
Portfolio's Alpaca chart exposes Off / Original / Quiet / Confirmed markers and
the optional low-volatility filter. Marker timestamps come from completed API bars,
not synthetic live candle updates. Initial smoothing depends on available history.

## Entry and exit map

After a completed bar, freeze the latest 20-bar high/low and arithmetic ATR14.
Call trigger = high + 0.1 ATR; put trigger = low − 0.1 ATR. Structural invalidation
uses the opposite extreme plus buffer, capped at a 2 ATR distance from entry.
Display 1R and 2R underlying targets. Entry valid for next three bars; time exit
eight bars including entry. Choppy tape says wait; >90-minute-old intraday tape
says stale. Re-scan after the window expires. Display precision is cents; backtest
calculates unrounded levels. These are underlying stock levels, not option premiums.

Live option quotes / spreads, open interest, IV, expiry, account debit cap and
configured 50% premium stop-loss policy still need the existing paper risk workflow.
The map does not register server-side triggers or broker stop orders.

## Evidence and reproducibility

Canonical aggregate report: `frontend/lib/scanner-research-results.json`, imported
directly by the UI. It contains no account data, trades or copied source bars.

```sh
backend/.venv/bin/python scripts/backtest_scanner_research.py --days 1825 --output frontend/lib/scanner-research-results.json
cd backend && .venv/bin/pytest
cd frontend && npm run lint && npm run build
```

Daily, chronological 70/30 split; 11-bar boundary purge; no overlapping trades per
symbol/variant; next-bar-or-later fills; conservative stop-first ambiguous candles;
adverse stop gaps; skip entry gaps >0.5R; 10bps underlying round-trip friction.
R-Factor variants compare the same breakout plan with no chop filter, exclude-chop
and trend-only. RSI variants compare next-open-to-fifth-close contrarian event returns.
This is **not an options backtest**, portfolio simulation, or proof for intraday
trading. Current large-cap universe has survivorship bias. No threshold was tuned
after examining holdout results, and no research variant can authorize execution.
See UI evidence for mixed/negative results, not just the favorable period.

Frontend pure-filter regression tests (no browser needed):

```sh
SCANNER_TEST_BUILD_DIR=$(mktemp -d /tmp/regimeshift-filters.XXXXXX)
frontend/node_modules/.bin/tsc frontend/lib/scanner-filters.ts --outDir "$SCANNER_TEST_BUILD_DIR" --module commonjs --target ES2021 --skipLibCheck
SCANNER_TEST_BUILD_DIR="$SCANNER_TEST_BUILD_DIR" node --test scripts/test-scanner-filters.mjs
```

Browser flow: scan all 24 → try each preset → zero-match reset → save/load preset
across reload → inspect both direction plans → options-chain handoff selects the
same ticker → switch chart marker modes / low-vol filter → verify small viewport.
Never click Execute merely to test the interface.
