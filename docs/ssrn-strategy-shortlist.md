# SSRN strategy shortlist — September 13, 2026

Scope: reviewed SSRN abstracts/indexed abstracts, not a full replication or
verification of every paper's backtest. Some SSRN direct pages failed to open;
the indexed primary-source abstracts supplied the findings below. These are
research proposals. No new strategy is enabled for execution by this note.

## 1. Gamma-conditioned breakout versus reversal

Barbon and Buraschi's [Gamma Fragility](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3725454)
links negative gamma imbalance interacting with illiquidity to intraday
momentum, and positive imbalance to reversal. It studies a gamma proxy, not a
universal rule that a particular sign guarantees the next price move.

Proposed experiment: compare the same breakout and mean-reversion rules within
positive, negative and mixed gamma cohorts, conditioning on underlying
liquidity. Our +call/−put open-interest convention is not observed dealer
inventory and is not established as equivalent to the paper's measure. Without
point-in-time historical chains, this remains forward-paper research only.

## 2. Opening-range breakout in unusually active stocks

Zarattini, Barbon and Aziz's [A Profitable Day Trading Strategy for the U.S.
Equity Market](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4729284)
studies opening-range breakouts, including five-minute ranges, using more than
7,000 U.S. stocks over 2016–2023. Its abstract emphasizes unusually active
“stocks in play,” rather than blindly trading every stock.

Proposed experiment: an opening-range overlay and completed-bar breakout
scanner, with time-of-day relative volume, spread checks and a labeled chop
filter. Our 24-large-cap universe is a different sample. The submitted daily
R-factor is a useful companion but its full-day volume must not leak into an
opening-bar test. Validate the underlying rule first, then option fills and
defined-risk structures separately; do not transfer reported stock returns to
options or advertise them as our results.

## 3. Opening-session signal for the final half hour

Gao, Han, Li and Zhou's [Market Intraday Momentum](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2440866)
reports that the first half-hour return, measured from the prior session's
close, predicts the final half-hour return in its historical ETF sample.
The abstract reports stronger effects around high volume/volatility and major
macroeconomic news.

Proposed experiment: a separate late-session strategy, not a ten-second scalp.
Use the correct overnight-inclusive opening return, exchange calendar,
shortened-session handling and scheduled-event timestamps. Evaluate whether the
effect persists in recent unseen data after spreads, commissions and slippage.

## 4. Caution: high IV is not permanent free carry

Dew-Becker and Giglio's [The Decline of the Variance Risk Premium: Evidence from
Traded and Synthetic Options](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5525882)
reports that option alphas in its recent historical window have become
indistinguishable from zero. Treat this as a challenge to a static premium-selling
assumption, not proof every volatility strategy fails.

Proposed use: display IV-versus-realized-volatility context and test rolling
regime-specific results. Do not enable an iron condor merely because IV is high.

## Test order and evidence requirements

Start with opening-range breakout, then late-session momentum (stock bars are
already available). Collect timestamped gamma observations in parallel before
testing gamma-conditioned strategy claims. This ordering is our implementation
judgment, not a conclusion drawn directly by the papers.

Use chronological train/validation/holdout splits, frozen parameters, same-time
volume baselines, explicit missing-data abstentions, bid/ask-aware option
execution and a baseline without each extra indicator. Group correlated trend
indicators instead of treating several momentum votes as independent evidence.
Report turnover, drawdown, trade count and uncertainty as well as mean return.
Paper execution eligibility does not certify that a hypothesis passed validation.

## Chart change delivered with this research

`GET /api/v1/chart-context?symbol=...` loads GEX and completed-daily swing
context without the decision pipeline. Its per-ticker, per-credential cache
coalesces simultaneous requests, expires after 60 seconds and is memory-bounded.
It is not a journal or an execution source. The chart automatically requests it
when its symbol changes; mismatched or failed responses cannot draw old ticker
levels. GEX summaries, wall levels and the expandable strike profile disclose
the sign convention and unverified upstream Greek/OI freshness.
