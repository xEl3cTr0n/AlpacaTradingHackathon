# Claude Handoff — RegimeShift AI Terminal

**Handoff Date**: October 2, 2026 (updated October 3, 2026, see section 6)  
**Latest Pushed Commit**: [`222600a`](https://github.com/xEl3cTr0n/AlpacaTradingHackathon/commit/222600a) on `main`; chart/news work on `claude/eloquent-planck-rf4dd4`  
**Live Vercel Preview**: https://regimeshift-ai.vercel.app  
**Product Invariants**:
- Paper trading only (`ALPACA_PAPER=true`). Never point to live trading endpoints.
- The Risk Agent is a deterministic hard gate. LLM outputs cannot bypass it.
- "No trade" is a valid and expected outcome.

---

## 1. Quick Start: How to Run Locally

You can launch the complete platform with a single command from the repository root:

```bash
# Option A: Executable bash runner (recommended)
./run.sh

# Option B: Root npm proxy script
npm run dev
```

`run.sh` automatically cleans up ports 8000 & 3000, starts the Uvicorn FastAPI backend (`http://127.0.0.1:8000`), starts the Next.js Turbopack dev server (`http://localhost:3000`), and handles graceful shutdown (`Ctrl+C`).

### URLs
- **Cockpit UI**: `http://localhost:3000` (or `http://127.0.0.1:3000`)
- **Backend API**: `http://127.0.0.1:8000`
- **Interactive OpenAPI Docs**: `http://127.0.0.1:8000/docs`

---

## 2. Verification Commands

Always run these verification commands before and after making changes:

```bash
# 1. Backend Pytest Suite (241 tests passing)
backend/.venv/bin/pytest

# 2. Frontend Lint & Build (Clean Next.js 16 build)
cd frontend && npm run lint && npm run build

# 3. Frontend Unit Tests (19 tests passing)
cd frontend && npm test
```

---

## 3. What Has Been Completed & Verified

### A. Step 1: Dynamic Support & Resistance Levels
- Pure mathematical calculation of:
  - **7-DTE Weekly Implied Move**: $S \times \text{IV} \times \sqrt{7/365}$ ($\pm 1\sigma$ and $\pm 2\sigma$ extreme stretch).
  - **1-Session Daily Move**: $S \times \text{IV} \times \sqrt{1/365}$.
  - **Volume Profile**: Point of Control (POC), Value Area High (VAH), Value Area Low (VAL).
  - **Ichimoku Equilibrium**: 26-period Kijun-sen equilibrium and Session VWAP.
- Extracted Prior Day High (PDH), Prior Day Low (PDL), and Prior Day Close (PDC).
- Implemented in `backend/src/regimeshift/domain/levels.py` and synchronized in `frontend/lib/types.ts`.

### B. Step 2: Strike-Level Liquidity & IV Matrix Heatmap
- Enriched `GexStrike` in `models.py` and `microstructure.py` with contract Open Interest (`call_oi`, `put_oi`, `total_oi`), Volume (`call_volume`, `put_volume`), and average Implied Volatility (`call_iv`, `put_iv`, `average_iv`).
- Built an interactive **Liquidity & IV Strike Heatmap Matrix** inside `frontend/app/_components/chart-context-panel.tsx`:
  - View switcher: `🔥 Liquidity & IV Matrix` vs `📊 GEX Histogram`.
  - ATM strike badge and accent styling.
  - Heat gradient intensity bars for Call liquidity (green), Put liquidity (red), Net GEX, and IV skew.
  - Interactive column sorting (`▲` / `▼`) on Strike, Net GEX, Volume, and OI.

### C. Step 3 (Phase 1 & 2): On-Chart Terminal & Full Ichimoku Cloud Suite
- **Interactive On-Chart Target HUD**:
  - Floats on the top-right of the candlestick chart canvas in `market-chart-terminal.tsx`.
  - Displays Spot price, 1D & 7D Implied Move pills (+/- $ and %), Bull/Bear target levels, and Call/Put walls.
  - Toolbar toggle button: `🎯 Targets`.
- **Full 5-Line Continuous Ichimoku Indicator Suite**:
  - Computed client-side across all timeframes (`1Min`, `5Min`, `15Min`, `1Day`) directly on candlestick bars:
    - **Tenkan-sen (9)**: `#38bdf8` (Sky Blue)
    - **Kijun-sen (26)**: `#ec4899` (Hot Pink)
    - **Senkou Span A**: `#34d399` (Emerald)
    - **Senkou Span B (52)**: `#f43f5e` (Rose)
    - **Chikou Span**: `#c084fc` (Purple)
- **Shaded Kumo Cloud Primitive**:
  - Created `frontend/lib/ichimoku-cloud-plugin.ts` implementing `ISeriesPrimitive<Time>` and `IPrimitivePaneRenderer` using HTML5 Canvas (`fancy-canvas`).
  - Renders filled translucent cloud shading between Span A and Span B (`zOrder: "bottom"`):
    - **Bullish Kumo** (Span A $\ge$ Span B): `rgba(52, 211, 153, 0.22)` (soft emerald).
    - **Bearish Kumo** (Span A $<$ Span B): `rgba(244, 63, 94, 0.22)` (soft rose).
  - Toolbar toggle button: `☁️ Ichimoku`.
- **Chart Data Depth Controls**:
  - History selectors: `100b`, `300b`, `500b`, `1000b`.
  - View actions: `Fit All` (zooms out to macro timeline) and `Recent` (focuses on last 120 candles).

### D. Hardening & Bug Fixes (B1, B2, B3, G1)
- **B1 (Cache Isolation)**: Live tape cache keyed by `(market_data_mode, credential_hash, symbol)` with per-key futures deduplication in `live_tape.py`.
- **B2 (Exception Redaction)**: Upstream exception details sanitized across public endpoints in `main.py`.
- **B3 (Sector Staleness)**: Past 16:00 ET, sector ETF signals transition to `"historical"` with `stale = True` in `sector_scanner.py`.
- **G1 (7-DTE Exit Horizon)**: Exit engine in `exits.py` prevents premature expiration exits on entry day for weekly spreads.
- **Audio & Scanner Notifications**: Synthesized Web Audio API chime with sound toggle (`Sound ON / OFF`) and candidate toast alerts in `opportunity-scanner.tsx`.

---

## 4. The 4-Step Checklist Roadmap & What Claude Should Do Next

| Step | Milestone | Status | Details |
| :--- | :--- | :--- | :--- |
| **Step 1** | **Dynamic S/R Levels** | **DONE** | IV Expected Move, Volume Profile POC/VAH/VAL, Kijun Equilibrium. |
| **Step 2** | **Liquidity & IV Matrix Heatmap** | **DONE** | Enriched strike-level options data, heatmap table, sorting, ATM badges. |
| **Step 3** | **On-Chart Terminal Suite** | **IN PROGRESS** | **Completed**: On-Chart Target HUD, 5-Line Ichimoku, Shaded Kumo Cloud.<br>**Upcoming**: Horizontal Volume Profile overlay on chart canvas, TradingView / Pine Script export bridge. |
| **Step 4** | **FinancialJuice & Catalyst Layer** | **QUEUED** | Audio news squawk widget, macroeconomic catalyst calendar (FOMC, CPI, NFP). |
| **Auxiliary** | **Databento Integration** | **PLANNED** | OPRA tick-by-tick options flow and Level 2 / Level 3 MBP-10 market depth adapter. |

### Immediate Tasks for Claude:
1. **On-Chart Volume Profile**: Add horizontal volume histogram bars along the price axis directly on the Lightweight Charts canvas (using a plugin or Canvas overlay similar to `ichimoku-cloud-plugin.ts`).
2. **TradingView / Pine Script Export**: Add an action button or modal in the chart toolbar that generates the exact Pine Script v5 code corresponding to the current RegimeShift levels (Call/Put Wall, Hedge Wall, POC, IV Corridor, Kijun, Target HUD) so users can import them directly into TradingView.
3. **Step 4 — FinancialJuice Squawk**: Embed a real-time financial audio squawk widget and economic calendar into the Research -> Context tab.
4. **Databento Adapter**: Implement `DatabentoMarketDataProvider` behind `MarketDataProvider` in `backend/src/regimeshift/services/` for raw OPRA options trade prints and Level 2 depth.

---

## 5. Key Architecture Invariants for Claude

1. **Python Path**: Always run backend commands using `backend/.venv/bin/python` or `backend/.venv/bin/pytest` (system python lacks dependencies).
2. **Workspace Preferences**: If adding fields to `WorkspacePreferences`, update `DEFAULT_WORKSPACE`, `parseWorkspace()`, and `frontend/lib/types.ts`.
3. **Domain Boundary**: Prefer adding a new adapter behind an existing protocol over changing domain models. Keep calculations pure and deterministic.

## 6. October 3 update: TOS studies, flicker-free chart, news (`claude/eloquent-planck-rf4dd4`)

Supersedes the toolbar/HUD details in section 3C.

- **Studies** (`frontend/lib/indicators.ts`, tested in `scripts/test-indicators.mjs`): thinkorswim
  VWAP with volume-weighted ±σ bands (day/week/month reset on the New York date; the cut-off
  first period of the loaded window is not drawn), MovingAvgCrossover SMA 15/30, Momentum(12)
  zero-cross, Wilder RSI(14), EMA 18/50. Defaults and lengths live in `WorkspacePreferences`.
- **Chart** (`market-chart-terminal.tsx`): structure is rebuilt only for ticker, timeframe or pane
  changes; refreshes call `setData`. Momentum/RSI use Lightweight Charts panes. Chart times are
  New York wall-clock encoded as UTC, so day/month tick marks follow ET sessions. Crossover arrows
  mark completed bars only. The on-chart target HUD and toggle buttons were replaced by a
  **Studies** menu, a crosshair legend, signal chips and a `LAST` trade line.
- **Workspace**: right column with `KeyLevelsCard` (levels sorted around spot) and `NewsFeed`.
- **News**: `GET /api/v1/news?symbols=&limit=` reads Alpaca (Benzinga) headlines, ordered by
  publication time, with a 30s shared cache. Markup is stripped and non-http links dropped.
  Context only.
- **Data**: optional `PricePoint.vwap` carries Alpaca's per-bar VWAP for chart bars.
- **Running locally**: `./run.sh --demo` or `.\run.ps1 -Demo` (Windows) serves labelled demo data
  without keys; `REGIMESHIFT_ALLOW_DEMO_DATA` only works under `next dev`.
- **Open items**: price-axis label collisions between context levels, folding Portfolio into the
  dock, RTH-only VWAP option, alerts on confirmed crosses, Alpaca news WebSocket, economic
  calendar, multi-chart layout.
