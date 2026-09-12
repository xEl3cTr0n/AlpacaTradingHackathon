# Managed paper exit lifecycle

Entry approval and risk-reducing exit eligibility are separate decisions.
The existing exit thresholds remain unchanged: a 50% loss of entry debit,
50% of maximum spread reward, seven days to expiration, or a fresh opposing
scanner direction. These are polling triggers, not guaranteed stop fills.

## Worker order of operations

1. Inspect held managed spreads and check loss/profit/expiration exits **before**
   requesting scanner history or loading entry backtest evidence.
2. Fetch scanner data. If data fails, return the completed exit receipts and
   an explicit `scanner_unavailable` result, with no new entry.
3. When fresh scanner diagnostics are available, check directional exits.
   Do not retry entries already considered for an exit in the same cycle.
4. Evaluate new entries against the unchanged backtest/council/risk/quote gates.

`--execute` retains its existing meaning (eligible entries and exits).
`--execute-exits` allows eligible managed exits while new entries remain
preview-only. With neither flag, broker order commands remain dry runs.
`ENABLE_PAPER_ORDERS=true` and paper-only configuration are still mandatory
for actual exit submission. No entry daily-loss or buying-power gate is applied
to a risk-reducing exit.

The GitHub paper workflow passes the exit flag independently of entry holdout
results. Missing credentials still fail the job. A failed evidence validation
step writes every entry output as false and does not suppress exit monitoring.
Malformed local scanner state similarly disables new entries without disabling
explicitly enabled exits. Backtest approval fields must be actual JSON booleans;
truthy strings and numbers are rejected.

## Verified closing structure

Managed exits only consider filled RegimeShift signal/manual two-leg entries.
The held spread must have matching underlying, expiration, and option type;
verified 1:1 opening ratios; one buy-to-open and one sell-to-open; an actual
filled debit between zero and spread width; and verified integer filled quantity.
Held signed quantities must match those opening sides exactly, and both legs
must be available to close. Missing/non-finite P&L is not assumed to be zero.

Unknown opening intent is never defaulted to buy-to-close. An incomplete spread,
wrong direction, conflicting opening history, pending order touching either leg,
or truncated order history produces a reconciliation receipt, not a guessed trade.
Options without an attributable managed entry are visible as unmanaged exposure
and are not automatically closed.

Before submitting through Alpaca CLI, the adapter rereads positions and order
history, recomputes eligibility, checks that the proposed legs/quantity match,
checks the deterministic exit client-order ID against Alpaca, and verifies a
fresh open market clock. It submits both legs as one `mleg` closing order with
explicit closing intents. See Alpaca's
[multi-leg options documentation](https://docs.alpaca.markets/us/docs/options-level-3-trading).

Worker receipts include `managed_exit_checks` (hold, exit-ready, reconciliation,
or unmanaged exposure) and `managed_exits` (submission/dry-run/rejection/uncertain
response). A failure on one exit is recorded without dropping checks for the
other spreads. Broker/account identifiers are not included in these summaries.

## Still outstanding

- Shared durable reservations and an order/position ledger remain blocked on
  database setup. Current broker reads are point-in-time, not a distributed lock.
- Net positions and recent order history cannot prove lot ownership in every
  external close/reopen scenario. Ambiguous detected histories are held for
  reconciliation; a durable ledger is still needed for complete attribution.
- A previously submitted exit ID is never blindly reused. Canceled, rejected,
  expired, or uncertain exits need reconciliation before a new attempt. An
  automatic, audited retry state machine is still required.
- A full 500-order history fails closed rather than silently ignoring pagination.
  A paginated reconciler is still needed for long-lived accounts.
- Closed market, stopped worker, unavailable broker, illiquid options, and gaps
  can prevent or delay a stop. Multi-leg market exits can slip. No exact $500
  realized-loss cap or continuous monitoring is claimed.

## Verification

Tests use fake brokers only. Coverage includes existing stop/profit/reversal
thresholds, wrong or missing legs, changed holdings after preparation, overlapping
history, pending orders, reused exit IDs, market closure, scanner outages,
corrupt local state, and malformed backtest evidence. The actual workflow shell
is exercised with a fake Python executable across combinations of entry gates
and execution switches. No paper order is placed as part of verification.
