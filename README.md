# RegimeShift AI

An explainable, regime-adaptive options trading agent built for the Alpaca AI
Trading Agents Hackathon. It combines deterministic market-regime detection,
specialized evidence agents, a hard risk gate, and an operator dashboard.

> This software is an educational paper-trading prototype, not investment
> advice. Paper execution is locked by default.

## What works now

- Two-axis market regime classification: direction × volatility.
- Technical, Swing, Research, Rotation, Bull, Bear, and Risk agent outputs.
- Explicit 5-agent proposal voting followed by a separate deterministic Risk gate.
- Defined-risk strategy selection with a first-class `NO_TRADE` decision.
- XSP index-option debit spreads driven by SPY swing breakouts; DJX is excluded by validation.
- A 24-name large-cap scanner for liquid equity-option candidates, ranked by
  confirmed 18 EMA crosses, trend, SPY alignment, relative strength, and volume.
- Demo data mode that runs without credentials or an open market.
- Alpaca stock-bar and news adapters for paper-account credentials.
- Responsive decision cockpit with price/regime timeline and audit trail.
- Portfolio command center with Alpaca paper P&L, positions, and recent orders.
- Interactive Strategy Lab for mode, risk budget, confidence, and expiration controls.
- Agent Ops view showing the decision pipeline and API/MCP/CLI connection state.
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
only through the separate paper-only CLI runner described below.

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
stocks. A candidate is actionable only when price crosses the 18 EMA, the
18/50 EMA trend and SPY direction agree, 20-session dollar volume exceeds
$100M, and composite conviction is at least 60%. Dollar volume is only the
first liquidity screen: the CLI checks live bid/ask width and at least 50 open
contracts on both equity-option legs before a paper order can pass.

Run one scan and optional CLI dry-run:

```bash
backend/.venv/bin/python scripts/scanner_runner.py
```

Run continuously every 15 minutes:

```bash
backend/.venv/bin/python scripts/scanner_runner.py --loop --interval-minutes 15
```

### Scheduled paper execution

Vercel serves the dashboard and reads Alpaca telemetry, but it does not keep the
CLI runner alive. The included `RegimeShift paper trading` GitHub Actions workflow
runs the scanner every 15 minutes during the broad US market-hours window.

Add `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` as GitHub Actions repository secrets.
The workflow remains preview-only until the repository variable
`ENABLE_PAPER_ORDERS` is explicitly set to `true`. With that variable enabled,
orders still require an actionable crossover, council approval, the deterministic
Risk gate, live option liquidity, an open market, and duplicate-signal protection.
All orders are forced to the Alpaca paper environment.

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
