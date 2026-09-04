# RegimeShift AI

An explainable, regime-adaptive options trading agent built for the Alpaca AI
Trading Agents Hackathon. It combines deterministic market-regime detection,
specialized evidence agents, a hard risk gate, and an operator dashboard.

> This software is an educational paper-trading prototype, not investment
> advice. Paper execution is locked by default.

## What works now

- Two-axis market regime classification: direction × volatility.
- Macro, Technical, Options Microstructure, Swing, Research, Rotation, Bull,
  Bear, and Risk outputs.
- Explicit 6-agent proposal voting followed by a separate deterministic Risk gate.
- Live Alpaca option-chain GEX, gamma concentration, and call/put wall evidence.
- Three-layer state engine: FRED GDP/CPI macro QUAD, ETF/security bottom-up
  quadrant, and options MOOD/VIBE research proxy.
- Selectable 1/5/10-second Alpaca IEX tape refresh with pause and manual refresh.
- Defined-risk strategy selection with a first-class `NO_TRADE` decision.
- XSP index-option debit spreads driven by SPY swing breakouts; DJX is excluded by validation.
- A 24-name, 15-minute large-cap scanner for liquid equity-option candidates,
  ranked by 18 EMA crosses, prior-session daily trend, SPY alignment, relative
  strength, and volume.
- Live Alpaca-only dashboard data with an explicit unavailable state; synthetic
  fallback values are never shown to production users.
- Alpaca stock-bar and news adapters for paper-account credentials.
- Responsive decision cockpit with price/regime timeline and audit trail.
- Portfolio command center with Alpaca paper P&L, positions, and recent orders.
- Interactive Strategy Lab for mode, risk budget, confidence, and expiration controls.
- Operator-token-protected manual paper ticket for one-lot, two-leg debit spreads.
- Agent Ops view showing the decision pipeline and API/MCP/CLI connection state.
- Backtesting workspace with dated train/holdout results from Alpaca historical bars.
- Portable JSON decision receipts containing the full council vote, deterministic
  risk-gate result, policy inputs, market provenance, and Alpaca tool evidence.

## Quick start

Requirements: Python 3.11+ and Node.js 20+.

```bash
cp .env.example .env

cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn regimeshift.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). API documentation is at
[http://localhost:8000/docs](http://localhost:8000/docs).

If a dev server was running while `npm run build` rewrote `.next`, stop it with
`Ctrl+C` and restart `npm run dev`; a stale Next process may otherwise hang.

## Connect Alpaca

Put your paper credentials in the root `.env`, then set:

```dotenv
MARKET_DATA_MODE=alpaca
ALPACA_API_KEY=your_paper_key
ALPACA_SECRET_KEY=your_paper_secret
```

The backend reads historical bars and recent news. Order execution is available
through the paper-only CLI runner and the separately locked manual MLeg endpoint.

### Trade criteria

A directional autonomous trade needs a completed 18 EMA crossover or validated
swing breakout, daily 18/50 trend alignment, SPY alignment, at least $100M of
average daily dollar volume, relative-strength/volume conviction, 3 of 6 council
votes, live quote/liquidity checks, and deterministic Risk approval. The GEX lane
adds three structure rules: missing or low-quality chain data fails closed;
negative gamma caps maximum loss at $200; and gamma concentration at or above
60% requires a confirmed breakout before chasing direction. `NO_TRADE` remains
a normal result.

The microstructure calculation follows the formulas explicitly published in
Professor Ninh D. Nguyen's supplied materials: signed GEX is
`± gamma × open interest × 100 × spot`, and Gamma Concentration is the share of
`gamma × open interest` within ±2% of spot. Alpaca supplies chain Greeks and
contract open interest for this lane. GEX+, GIV, CR(x), GRIP, and REPH are not
fabricated: GEX+ requires vanna, while GRIP/REPH need the missing formula or
graphic. Professor sources remain external research inputs; the large historical
files are not committed.

The supplied workbook's cached 2005–2026 series was checked independently with
`scripts/backtest_professor_gex.py`. On its chronological 30% holdout, GEX had a
−0.481 correlation with 5-session forward realized volatility, and negative-GEX
days had 1.934× the average realized volatility of positive-GEX days. See
`docs/professor-gex-validation.json`. This validates a volatility-risk overlay,
not a directional entry signal or option P&L strategy.

### Three-layer regime hierarchy

1. **Top-down Macro QUAD I–IV:** real GDP YoY acceleration versus the prior
   quarter and CPI YoY acceleration versus three months earlier, sourced from
   FRED `GDPC1` and `CPIAUCSL`. It is cached for six hours because macro data is
   monthly/quarterly, not tick data.
2. **Bottom-up Quad 1–4:** security trend plus weighted 1M/3M sector-ETF breadth.
   Quad 1 is broad risk-on, Quad 2 a narrow advance, Quad 3 broad risk-off, and
   Quad 4 rotation/repair. It updates on a full agent run.
3. **Options MOOD/VIBE:** an explicitly labeled research proxy that maps GEX,
   GMC, bottom-up state, and RSI into Volatility, Indifference, BTFD, or
   Euphoria. Its confidence is capped while contract volume/NOPE, vanna/GEX+,
   charm/CHR, and REPH are unavailable.

The dashboard refresh selector changes only the lightweight Alpaca price/quote
tape. Recomputing FRED history, sector history, news, and thousands of option
contracts every second would create noise and exhaust shared API limits.

```bash
python3 scripts/backtest_professor_gex.py /path/to/GEX_NN_Copy.xlsm
```

### Alpaca MCP server

The repository includes project-scoped MCP configuration for Claude Code in
`.mcp.json` and Gemini CLI in `.gemini/settings.json`. Both configurations run
the official `alpaca-mcp-server` through `scripts/run-alpaca-mcp.sh`. The
launcher reads only the required credentials from the ignored root `.env` and
forces paper trading. The committed configuration intentionally excludes
Alpaca's `trading`, `watchlists`, and `locates` toolsets so an MCP client cannot
bypass the deterministic Risk Agent.

Install `uv` if neither `uvx --version` nor `backend/.venv/bin/uvx --version`
works. Restart either client after changing MCP configuration, then verify that
the `alpaca` server is connected. Keep `ALPACA_MCP_ENABLED=true` in the root
`.env` so the dashboard reports the configured integration.

### Alpaca CLI autonomy runner

Install the pinned official Alpaca CLI binary into the ignored project-local
tool directory, then verify the paper account:

```bash
scripts/install-alpaca-cli.sh
scripts/run-alpaca-cli.sh account get --quiet
```

Run the full agent, council vote, Risk gate, XSP contract discovery, quote
liquidity check, and CLI order dry-run:

```bash
backend/.venv/bin/python scripts/autonomy_runner.py --symbol SPY
```

Actual submission requires both `ENABLE_PAPER_ORDERS=true` in the ignored local
`.env` and the explicit `--execute` flag. The adapter always exports
`ALPACA_LIVE_TRADE=false`; it supports only one-lot, defined-risk XSP or
scanner-universe debit spreads and cannot route to a live account.

### Large-cap options scanner

The dashboard Scanner workspace performs a read-only pass over 24 large-cap
stocks using completed 15-minute bars. A candidate is actionable only when
price crosses the intraday 18 EMA, the prior-session daily 18/50 trend and SPY
direction agree, 20-session dollar volume exceeds $100M, and composite
conviction is at least 55%. Signals at 60%+ are production candidates; the
55–60% exploration tier has a deterministic $200 maximum-loss cap and a
separate execution lock. The CLI then checks bid/ask width and at least 50 open
contracts on both equity-option legs.

Run one scan and optional CLI dry-run:

```bash
backend/.venv/bin/python scripts/scanner_runner.py
```

Run continuously every 15 minutes:

```bash
backend/.venv/bin/python scripts/scanner_runner.py --loop --interval-minutes 15
```

Use `--timeframe daily` to run the older production policy backed by the
five-year daily holdout. The default intraday policy is analysis-only until its
own evidence gate passes.

### Scheduled paper execution

Vercel serves the dashboard and reads Alpaca telemetry, but it does not keep the
CLI runner alive. The included `RegimeShift paper trading` GitHub Actions workflow
runs the scanner every 15 minutes during the broad US market-hours window.

Add `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` as GitHub Actions repository secrets.
The workflow remains preview-only until the repository variable
`ENABLE_PAPER_ORDERS` is explicitly set to `true` **and** the committed intraday
holdout gate passes. `ENABLE_EXPLORATION_ORDERS=true` is a separate lock and is
also ignored until its own holdout gate passes. Orders still require an
actionable crossover, council approval, the deterministic Risk gate, live
option liquidity, an open market, and duplicate-signal protection. All orders
are forced to the Alpaca paper environment.

Each cycle evaluates all qualified scanner candidates through the voting
council instead of stopping after the first rejection. It also inspects spreads
opened by RegimeShift and prepares an atomic two-leg exit at 50% of maximum
reward, 75% of maximum loss, seven DTE, or an opposing detected trend.

Add `--execute` only when you intentionally want eligible signals submitted to
Alpaca paper trading. The runner skips closed markets and persists a local,
ignored signal key so the same daily crossover cannot be submitted twice.

Reproduce its fixed five-year validation with:

```bash
backend/.venv/bin/python scripts/backtest_scanner.py --days 1825
```

The 30% chronological holdout produced 33 non-overlapping directional signals,
a 66.7% win rate, +11.7% compounded underlying proxy return, and -27.0% maximum
drawdown after 20 bps friction. See `docs/scanner-backtest-results.json`. This
does not model historical option fills and is not predictive.

Reproduce the intraday validation with:

```bash
backend/.venv/bin/python scripts/backtest_intraday_scanner.py --days 120
```

The current 120-day holdout did **not** pass after modeled friction, so both
intraday execution tiers remain locked while the scanner and council run in
preview mode. See `docs/intraday-scanner-backtest-results.json`. This fail-closed
result is intentional; changing thresholds requires a new chronological test.
The previously validated daily production policy can still submit paper trades
when `ENABLE_PAPER_ORDERS=true`.

### Backtest gate

Reproduce the five-year walk-forward directional proxy test with:

```bash
backend/.venv/bin/python scripts/backtest_strategy.py --days 1825
```

The selected SPY swing-breakout policy uses a 10-session breakout, a 10-session
holding proxy, a 52% weighted council threshold, and excludes the top 30% of
historical volatility regimes. On the chronological 30% holdout it produced 15
non-overlapping signals, a 66.7% directional win rate, +5.3% compounded proxy
return, and -3.08% maximum drawdown after 15 bps modeled friction. A fixed
DIA→DJX cross-asset confirmation failed, so DJX is deliberately excluded. See
`docs/backtest-results.json` for the complete result and limitations. This is a
signal-direction test—not historical option-fill P&L—and is not predictive.

### Manual paper ticket

The dashboard Manual Trade workspace accepts exact OCC symbols for the long and
short legs. Preview validates same underlying/expiry/type, 7–60 DTE, correct
debit-spread strike order, live two-sided quotes, at most 20% bid/ask width,
limit-price sanity, and a hard $200 maximum loss. Submission uses one atomic
Alpaca `mleg` limit order and always constructs `TradingClient(..., paper=True)`.

To unlock it locally or on Vercel, create a long random operator token and set:

```dotenv
ENABLE_MANUAL_PAPER_ORDERS=true
MANUAL_TRADE_TOKEN=replace_with_a_long_private_token
```

Keep that token private. A user must enter it in the ticket and type `PAPER` for
each submission. Manual execution cannot override structural, quote, or risk
gates.

### Vercel credentials

Do not upload or commit `.env`. After claiming/linking the Vercel project, add
`ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in **Project Settings → Environment
Variables**. Also set these non-secret production values:

```dotenv
ALPACA_PAPER=true
MARKET_DATA_MODE=alpaca
ENABLE_PAPER_ORDERS=false
ALPACA_MCP_ENABLED=false
ALPACA_CLI_ENABLED=false
ENABLE_MANUAL_PAPER_ORDERS=false
MANUAL_TRADE_TOKEN=use_a_long_random_secret
```

Apply them to Production and Preview, then redeploy. The MCP process runs on
developer machines, not inside the Vercel web deployment, so the hosted app
should leave `ALPACA_MCP_ENABLED=false` unless a remote MCP service is added.

## Project layout

```text
backend/   FastAPI, regime engine, agents, risk policy, Alpaca adapters
frontend/  Next.js decision cockpit
docs/      architecture and teammate handoffs
```
