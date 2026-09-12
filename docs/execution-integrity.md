# Paper entry integrity

The manual SDK ticket and automated CLI entry path share deterministic checks in
`backend/src/regimeshift/domain/execution_checks.py`. This is an execution-safety
change, not a new strategy or a relaxation of council, Risk Agent, scanner, or
backtest gates. Scanner research indicators remain read-only.

## Checks at the submission boundary

- Paper configuration only. The SDK client is constructed with `paper=True`;
  CLI subprocesses retain their isolated configuration and `ALPACA_LIVE_TRADE=false`.
- Account status must be ACTIVE; trading-blocked, account-blocked, and
  user-suspended flags must explicitly be false. Unknown values fail closed.
  CLI 0.0.14's typed `account get` output omits false safety flags, so capacity
  uses the CLI's read-only `api GET /v2/account` to preserve them. A missing
  flag is never silently interpreted as false.
- Current and previous-close equity must be finite and positive. New entries
  stop at the configured daily loss threshold (default 2%).
- Debit exposure must fit the lesser of the configured dollar cap (default
  $1,000) and actual current equity times the configured per-trade fraction
  (default 1%). Configured demo equity is not the account-capacity source.
- Verified options buying power must cover the debit; effective options trading
  level must be at least 3 for these two-leg debit spreads.
- Existing option positions and **all** pending option entries count, including
  orders from outside RegimeShift. Duplicate-underlying entries are blocked.
  Default capacity is three concurrent spreads. Counting is conservative:
  a pending addition consumes another slot. Closing orders do not add slots,
  but positions awaiting an exit still count. A full 500-order response is
  rejected because it may have been truncated.
- A verified Alpaca clock must report the market open. Clock timestamps must be
  timezone-aware, at most 60 seconds old, and no more than 5 seconds ahead.
- Every leg requires a timezone-aware quote at most 120 seconds old (5 seconds
  future skew tolerated), finite positive bid/ask, no crossed market, at least
  one displayed contract on each side, and spread at most 20% of midpoint.
- The current natural debit must be positive and less than the spread width.
  The submitted limit cannot exceed natural debit times 1.10 plus $0.05.

Manual submission authenticates the operator first, then reruns preview with
new account, clock, exposure, and quote reads. Preview exposes `quote_checks`,
`capacity_passed`, `market_open`, and rejection `reasons` as structured data.
When account capacity cannot be approved, preview's `risk_budget` is zero to
denote unavailable approved capacity, not a statement that account equity is zero.

CLI submission additionally reconstructs risk from the actual leg symbols and
limit: exactly one 1:1 two-leg opening debit spread, matching underlying,
expiration, and approved call/put strategy. It verifies the existing DTE limits
(equities 7–60 days; XSP 21–45 days), recomputes maximum loss, and rejects
inconsistent declared loss. After capacity checks, it fetches fresh snapshots
for the exact legs. A prepared `liquidity_passed: true` cannot bypass requoting.
Successful submission evidence contains the current quote checks and capacity
summary; rejected attempts return explicit reasons. CLI dry runs are simulations,
not confirmation that live submission-time account and clock checks have passed.

## Boundaries and limitations

These are point-in-time checks, **not an atomic cross-process reservation**.
The workflow serializes its worker, but simultaneous manual and worker requests
can still race between checking capacity and submitting. Broker checks and
client-order IDs help, but a shared durable reservation/ledger is still needed
for a strict cross-writer position cap. Do not claim that race is solved.

Fresh timestamp does not establish feed entitlement, executable liquidity, or
future fills. Alpaca's indicative feed contains modified quotes and delayed
trades; OPRA access depends on subscription. No new subscription is purchased,
and this patch does not change feed selection. See the official
[option snapshots reference](https://docs.alpaca.markets/us/reference/optionsnapshots)
and [options trading documentation](https://docs.alpaca.markets/us/docs/options-trading).

These entry gates do not change managed exits or make the 50% premium stop a
guaranteed loss cap. Underlying-price research backtests are not options P&L
validation. No broker order is submitted as part of verification.

## Verification

Run `cd backend && .venv/bin/pytest` and the frontend lint/build. New tests use
fake SDK/CLI clients to cover fresh successful entries, quote expiry after
preparation, crossed/non-finite/missing quotes, altered legs and declared risk,
account losses, buying power, external exposure, operator authentication, and
market closure. Read-only integration checks can validate account-field and
CLI snapshot response compatibility without calling either submission method.
