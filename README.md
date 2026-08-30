# RegimeShift AI

An explainable, regime-adaptive options trading agent built for the Alpaca AI
Trading Agents Hackathon. It combines deterministic market-regime detection,
specialized evidence agents, a hard risk gate, and an operator dashboard.

> This software is an educational paper-trading prototype, not investment
> advice. Paper execution is locked by default.

## What works now

- Two-axis market regime classification: direction × volatility.
- Technical, Research, Bull, Bear, and Risk agent outputs.
- Defined-risk strategy selection with a first-class `NO_TRADE` decision.
- Demo data mode that runs without credentials or an open market.
- Alpaca stock-bar and news adapters for paper-account credentials.
- Responsive decision cockpit with price/regime timeline and audit trail.
- Portfolio command center with Alpaca paper P&L, positions, and recent orders.
- Interactive Strategy Lab for mode, risk budget, confidence, and expiration controls.
- Agent Ops view showing the decision pipeline and API/MCP/CLI connection state.

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

The backend reads historical bars and recent news. It does not submit orders.
See `docs/architecture.md` for the execution roadmap and safety boundary.

## Project layout

```text
backend/   FastAPI, regime engine, agents, risk policy, Alpaca adapters
frontend/  Next.js decision cockpit
docs/      architecture and teammate handoffs
```
