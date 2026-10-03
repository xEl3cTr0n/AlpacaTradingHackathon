# Gemini handoff — RegimeShift AI

Audit date: September 17, 2026. Scope: immediate bug review and continuation guide.
This handoff does **not** implement fixes, enable orders, or publish a deployment.

## Start here

1. Work from `/Users/aarhakhanna/hackathon/AlpacaTradingHackathon`, preserving its
   existing tracked edits and untracked files. Read `AGENTS.md` and
   `frontend/AGENTS.md`. Do not reset, clean, or stage the whole directory.
2. Run the verification commands below. Run the offline bug witnesses. Fix B2,
   B1, B3, then B4 in small changes, with regression tests for desired behavior.
3. Resolve G1 (entry/exit horizon mismatch) before adding weekly/0DTE execution.
   Do not merely lower the contract-selection minimum DTE.
4. Implement the confirmed scanner specification below, starting with a shared
   signal lifecycle and timestamp handling. It is not implemented just because
   the UI polls quickly. Keep deterministic risk and paper-only safeguards.
5. Reconcile the root workspace with the publish clone deliberately. This audit
   does not authorize a production push or an order to verify a fix.

## Repository state: important

- Root branch `main`, HEAD `edad0d5` (old scheduled-paper-workflow commit).
  `git diff --stat` shows 35 tracked modified files, plus many untracked source,
  test, and documentation files. Root HEAD alone is **not** the current product.
- Nested `.publish-benBy8` is a separate clean checkout on `main` at
  `2ea6f6c05ce0109a7dcf3d855d8cbafe297f3495`, `feat: simplify chart-first trading workspace`.
  Root `.git` is read-only in the current agent sandbox. Do not try to bypass it.
- Most apparent root changes were already present before this review. The nested
  checkout must not be mistaken for an up-to-date copy of the local sector work.
- Source comparison confirms local-only sector/freshness work in:
  `backend/src/regimeshift/domain/sector_scanner.py`,
  `backend/src/regimeshift/services/sector_scanner.py`,
  `backend/tests/test_sector_scanner.py`, `frontend/lib/feed-freshness.ts`,
  `frontend/app/_components/sector-scanner.tsx`, and `chart-freshness.tsx`.
  Associated root changes include `main.py`, `services/market_data.py`,
  `market-chart-terminal.tsx`, `trading-workspace.tsx`, `globals.css`,
  `frontend/lib/types.ts`, and `workspace-preferences.ts`.
- Historical production URL: https://regimeshift-ai.vercel.app . Its current
  deployment, remote Git HEAD, Vercel environment, and GitHub worker status were
  **not checked in this audit**. Do not infer production parity from a local build.
- No listeners were found on local ports 3004 or 8002 at audit time. An old open
  browser tab does not prove either service is running. No server was started here.
- This review adds only this document and `scripts/reproduce_handoff_findings.py`.
  No intentional application-code edits, credentials changes, commits, or pushes.

## Confirmed bugs

Priorities are repair recommendations, not claims of observed production incidents.

### B1 — P2: live-price cache is keyed only by ticker

Location: `backend/src/regimeshift/services/live_tape.py:13`.

The module cache uses `symbol`, not provider mode or credential identity. A demo
SPY request followed by an Alpaca SPY request within 0.8 seconds returns the demo
price without consulting Alpaca. This is reproducible with two Settings objects;
the public endpoint currently uses one deployment-level Settings object, so
cross-account exposure in today's deployment is **not established**.

Evidence: offline witness B1 returns source `demo` and price 100 for the second,
Alpaca-mode request, whose mocked provider would return 200. No real prices used.

Fix: key by normalized mode, non-reversible credential identity, feed where
applicable, and symbol, following the chart-context cache pattern. Return a copy
and bound the cache. Add mode/account-isolation and expiry tests. Also consider
per-key in-flight deduplication: the existing global lock holds across upstream
I/O and can block unrelated tickers behind a slow request.

### B2 — P1: API errors return raw upstream exception text

Location: `backend/src/regimeshift/main.py:129`; similar 502 branches at lines
89, 115, 193, 228, 262, 364, 378, 395, and 411.

`detail=f"...{error}"` sends arbitrary provider/SDK exception strings to clients.
Those strings can contain private upstream details. Actual credential leakage
was **not observed**; no real exceptions or credentials were collected.

Evidence: mocked RuntimeError containing `SYNTHETIC_PRIVATE_UPSTREAM_DETAIL`
appears verbatim in the public `/api/v1/live-tape` 502 JSON response.

Fix: return a stable, generic error plus a correlation identifier if useful.
Keep diagnostic logs redacted. Review ValueError/422 branches too: separate
user-safe validation messages from upstream errors rather than hiding all useful
validation. Test every affected route with a synthetic private marker. The
sector-scanner and chart-context endpoints already have generic 502 messages.

### B3 — P2: cached sector confirmation remains current after session close

Locations: `backend/src/regimeshift/services/sector_scanner.py:25` and
`backend/src/regimeshift/domain/sector_scanner.py:183`.

The 60-second cache returns stored `stale`, `signal`, and plan states without
re-evaluating time. Freshness and session status are calculated only on rebuild.

Evidence: fixture cached at 15:59:30 ET, requested again at 16:00:10 ET, returns
`confirmed_bullish`, `stale=false`. Direct evaluation at the second time returns
`historical`, `stale=true`. This is a research-display bug, not an order bypass:
this endpoint does not submit orders. The same boundary issue can occur when a
data-age threshold is crossed within the cache TTL.

Fix: cache market calculations separately from time-sensitive eligibility, or
expire at the next relevant boundary and recompute status on reads. Test market
close, stale-age transitions, and cached plans. Client displays also need aging
when refresh is paused, the browser sleeps, or the network disconnects. Current
weekday/09:30–16:00 logic is not an exchange calendar; add holiday/early-close
fixtures when calendar integration is implemented.

### B4 — P2: chart-context daily session label can show the preceding day

Location: `frontend/app/_components/chart-context-panel.tsx:39`.

`swing_as_of` is rendered using the browser's local date without specifying the
exchange timezone. A daily candle timestamp at midnight ET appears on the prior
calendar date for this user's Pacific timezone. ChartFreshness and SectorDetail
already specify ET for daily dates, so the displays disagree.

Evidence: `2026-09-14T04:00:00Z` formats as `9/13/2026` in America/Los_Angeles and
`9/14/2026` in America/New_York. The actual formatting expression was inspected;
this was not a rendered-browser reproduction in this audit.

Fix: use one exchange-session date formatter for daily labels, distinct from
intraday timestamps. Add tests in Pacific, UTC, and ET including DST boundaries.

## Verified implementation gaps / integration blockers (not newly introduced bugs)

### G1 — Resolve before enabling short-dated strategies

- `services/alpaca_cli.py:83,340`: ordinary options selection/validation is
  7–60 DTE; XSP uses 21–45 DTE. Runner default target is 30 DTE.
- `services/manual_trading.py:80`: manual spread preview rejects outside 7–60 DTE.
- `domain/exits.py:102`: every eligible held spread at **7 DTE or less** gets an
  expiration exit regardless of P&L or trend. The offline witness shows a
  seven-DTE spread with zero P&L immediately qualifying for exit. Seven DTE is
  therefore both an allowed entry boundary and an immediate exit boundary.
- `managed_exit_plan` and `submit_exit` support identified complete two-leg debit
  spreads. Single-leg calls/puts do not gain managed exits merely by changing the
  entry ticket. Unmanaged positions are reported for operator review.
- Exits currently use a fraction of filled debit, a fixed profit target at 50%
  of maximum spread reward, expiry, and detected direction reversal. There is
  no persisted trailing high-water mark or underlying-price thesis invalidation
  input to `managed_exit_plan`. The user's newly chosen exit behavior is pending.

Design entry eligibility and horizon-specific exits together, including same-day
cutoffs, broker calendar, fresh executable quotes, attribution, fill state, and
restart-safe trailing state. Keep closing orders reducing exposure; never infer
missing leg ownership. A $500 intended stop is not a guaranteed maximum loss.

### G2 — Near-live scanner and notification lifecycle are not implemented

- Trade quotes can poll at 1/5/10 seconds. Candles poll 30 seconds for 1Min and
  60 seconds otherwise. Chart-context and sector/scanner reads poll 60 seconds.
- Sector calculations and worker intraday scans use **15-minute** bars. Workflow
  cycles use five-minute waits; CLI default is 15 minutes and minimum is five.
  Neither is a 1-minute-close confirmation engine or a ten-second exit service.
- No shared durable intrabar-heads-up → confirmed → entered → exited lifecycle
  with deduplicated pop-ups/sound was established by this review. Build that
  explicitly; don't relabel frequent polling as streaming execution.
- The sector view is 11 ETFs with five curated names each, not full weighted
  sector breadth. It has trend, VWAP proxy, CHOP, matched-return correlation,
  relative strength, sample agreement, and future underlying breakout levels.
- SectorDetail picks put levels only for bearish ETFs, otherwise call levels
  (`sector-scanner.tsx:58`). Thus mixed ETFs default to call-side display despite
  the mixed-trend disclaimer. Show both directions or let users select; don't
  treat this table as a stock-specific bidirectional opportunity engine.
- Sector confirmation is read-only and separate from current trade gates. Do
  not accidentally turn sector agreement into a mandatory gate: user explicitly
  allows stock-specific opportunities when the sector disagrees.

## Confirmed user specification — preserve these decisions

- Alpaca only, free feed first. Clearly label freshness, coverage and synthetic
  data. No Webull/Robinhood integration or paid data purchase requested now.
- One intraday-first scanner with swing context, primarily continuation and
  momentum. Maintain a stock's developing bias rather than separate unrelated
  scanners. Do not claim these setups are inherently safe.
- Prioritize a **few strongest** long/call or short/put opportunities, not all
  possible setups. Evidence scores must not be presented as calibrated win odds.
- Live tiles + small pop-up + optional sound. Early heads-up intrabar; confirmed
  proposal after a **1-minute close plus sector/volume confirmation**. For a
  sector-disagreeing stock, allow strong stock-specific price/volume evidence
  and display the disagreement explicitly.
- Prioritize same-day and weekly contracts; setup-aware expiry selection may
  choose longer-dated swings. Compare 2–7 and 8–21 DTE alternatives in research.
- Prefer single-leg calls/puts; other structures remain possible. Delta ~0.30 is
  a hypothesis to compare, not a hard optimum or probability of profit.
- Position cap $1,000, intended stop $500 for a full-sized position. Exit on
  underlying invalidation or option-loss limit, whichever happens first; trail
  winners. Preserve tighter deterministic limits where applicable and document
  any policy change. User approval does not bypass repository risk invariants.
- Proposed trades need trigger, invalidation, targets, horizon, contract/liquidity
  evidence, supporting/opposing evidence, data times, and rejection reasons.
- Signals include user's daily R-Factor and RSI+volume spike. R-Factor code is
  **uncapped** despite its “15x capped” comment. ATR/price filters low volatility;
  it is not equivalent to CHOP. Correlated momentum indicators are not independent
  votes. OI/GEX/walls are positioning proxies, not observed dealer inventory or
  proof of bullish/bearish order flow.
- Paper fills/backtests are for learning. No real-money execution. No autonomous
  weakening of risk from a handful of profitable simulated trades.

Eight-track roadmap lives in `docs/product-direction.md`: potential-move scanner,
structured theses, indicators/context, dependable execution, evidence database,
strategy plugins, portfolio risk, and data quality. All eight are **not complete**.
Read `docs/execution-integrity.md`, `docs/managed-exit-safety.md`,
`docs/scanner-workbench.md`, and `docs/terminal-layout-handoff.md` before changing
those areas. Older documents describe earlier scopes, not the new answers above.

Professor-model work remains pending: earlier filename search located CVX tactical
models, the Bottoms-Up Regime Segmentation workbook, and `ETF_Bucketing.xlsm` under
`/Users/aarhakhanna/Desktop/Today`. Contents/formulas were not inspected in this
audit. User authorized relevant model review; use the spreadsheet skill, read
without executing macros/external connections, and preserve provenance. Don't
claim professor MOOD/VIBE formulas have been reproduced from these filenames.

## Verification performed on current root tree

- Backend: **225 passed**, one existing `websockets.legacy` deprecation warning.
- Frontend: **ESLint passed**, **production build + TypeScript passed**.
- Frontend helper suites: **16 passed** (preferences 6, freshness 2, chart context
  3, scanner filters 5).
- Offline witnesses: B1, B2, B3, and G1 all reproduced. B4 date formatting checked
  using Node in explicit Pacific and ET timezones.
- No browser/UI smoke run, live broker/account request, production inspection,
  worker execution, strategy backtest rerun, or full security audit performed.
  Green tests do not validate strategy profitability or the missing lifecycle.

Run from repository root:

```sh
(cd backend && .venv/bin/pytest -q)
(cd frontend && npm run lint && npm run build)
backend/.venv/bin/python scripts/reproduce_handoff_findings.py

task_build_dir=$(mktemp -d /tmp/regimeshift-handoff-tests.XXXXXX)
frontend/node_modules/.bin/tsc frontend/lib/workspace-preferences.ts frontend/lib/feed-freshness.ts frontend/lib/chart-context.ts frontend/lib/scanner-filters.ts --outDir "$task_build_dir" --module commonjs --target ES2021 --skipLibCheck
WORKSPACE_TEST_BUILD_DIR="$task_build_dir" CHART_TEST_BUILD_DIR="$task_build_dir" SCANNER_TEST_BUILD_DIR="$task_build_dir" node --test scripts/test-workspace-preferences.mjs scripts/test-feed-freshness.mjs scripts/test-chart-context.mjs scripts/test-scanner-filters.mjs
```

The reproduction script asserts **current broken behavior** to prove the report.
It is not a passing correctness suite. After a fix, replace that witness with a
normal regression test asserting the corrected behavior; do not preserve the bug
to keep this script green. It uses mocks and existing deterministic test fixtures.

For future UI checks, first check ports/processes and inspect `frontend/next.config.ts`.
Previous local pairing was frontend 3004 with `REGIMESHIFT_API_URL=http://127.0.0.1:8002`.
Use explicit demo settings or stub adapters for initial verification; do not start
the execution worker just to inspect a chart. Read applicable Next.js/UI/browser
skills before UI work. Keep secrets server-side and out of logs and handoff files.
