"""Shared deterministic entry checks for the SDK and CLI paper adapters."""

import math
from datetime import UTC, datetime
from typing import Any

from regimeshift.config import Settings
from regimeshift.domain.exits import OPTION_SYMBOL
from regimeshift.domain.models import OptionQuoteCheck

MAXIMUM_QUOTE_AGE_SECONDS = 120
MAXIMUM_FUTURE_SKEW_SECONDS = 5


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def utc_timestamp(value: Any) -> datetime | None:
    try:
        result = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    # Unknown timezones cannot prove freshness.
    return result.astimezone(UTC) if result.tzinfo is not None else None


def check_option_quote(
    symbol: str,
    *,
    bid: Any,
    ask: Any,
    bid_size: Any,
    ask_size: Any,
    timestamp: Any,
    now: datetime | None = None,
) -> OptionQuoteCheck:
    now = now or datetime.now(UTC)
    bid, ask = finite_number(bid), finite_number(ask)
    bid_size, ask_size = finite_number(bid_size), finite_number(ask_size)
    as_of = utc_timestamp(timestamp)
    age = (now - as_of).total_seconds() if as_of else None
    reasons = []
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid:
        reasons.append("Quote requires finite positive, non-crossed bid and ask")
    elif (ask - bid) / ((ask + bid) / 2) > 0.20:
        reasons.append("Quote spread exceeds 20% of midpoint")
    if bid_size is None or ask_size is None or min(bid_size, ask_size) < 1:
        reasons.append("Quote requires at least one contract on both sides")
    if as_of is None:
        reasons.append("Quote timestamp is missing, malformed or lacks timezone")
    elif age < -MAXIMUM_FUTURE_SKEW_SECONDS:
        reasons.append("Quote timestamp is in the future")
    elif age > MAXIMUM_QUOTE_AGE_SECONDS:
        reasons.append(f"Quote is older than {MAXIMUM_QUOTE_AGE_SECONDS} seconds")
    return OptionQuoteCheck(
        symbol=symbol,
        valid=not reasons,
        as_of=as_of,
        age_seconds=round(age, 3) if age is not None else None,
        maximum_age_seconds=MAXIMUM_QUOTE_AGE_SECONDS,
        bid=bid,
        ask=ask,
        reasons=reasons,
    )


def verify_open_clock(clock: dict[str, Any], now: datetime | None = None) -> None:
    now = now or datetime.now(UTC)
    timestamp = utc_timestamp(clock.get("timestamp"))
    if timestamp is None or not -5 <= (now - timestamp).total_seconds() <= 60:
        raise ValueError("Fresh Alpaca market clock could not be verified")
    if clock.get("is_open") is not True:
        raise ValueError("Paper market is closed; no new entries")


def option_root(symbol: Any) -> str | None:
    match = OPTION_SYMBOL.fullmatch(str(symbol))
    return match.group(1) if match else None


def verify_entry_capacity(
    settings: Settings,
    underlying: str,
    account: dict[str, Any],
    positions: list[dict[str, Any]],
    open_orders: list[dict[str, Any]],
    *,
    maximum_loss: float = 0,
) -> dict[str, Any]:
    """Account-wide risk, not just entries with our own client-order prefix.

    This is a point-in-time gate, not a cross-process reservation. The paper
    worker remains single-writer per workflow; broker checks still apply.
    """
    equity = finite_number(account.get("equity"))
    last_equity = finite_number(account.get("last_equity"))
    loss = finite_number(maximum_loss)
    buying_power = finite_number(account.get("options_buying_power"))
    level = finite_number(account.get("options_trading_level"))
    if equity is None or last_equity is None or min(equity, last_equity) <= 0:
        raise ValueError("Paper account equity could not be verified")
    if loss is None or loss < 0:
        raise ValueError("Maximum loss must be a finite non-negative amount")
    if getattr(account.get("status"), "value", account.get("status")) != "ACTIVE":
        raise ValueError("Paper account status is not verified ACTIVE")
    for flag in ("trading_blocked", "account_blocked", "trade_suspended_by_user"):
        if account.get(flag) is not False:
            raise ValueError(f"Paper account {flag} is blocked or unverified")
    daily_return = equity / last_equity - 1
    if daily_return <= -settings.max_daily_loss_pct:
        raise ValueError(f"Daily loss circuit breaker reached {daily_return:.2%}; no new entries")
    budget = min(settings.max_position_loss_dollars, equity * settings.max_risk_per_trade_pct)
    if loss > budget:
        raise ValueError(f"Maximum loss exceeds the ${budget:,.0f} current-equity risk cap")
    if buying_power is None or buying_power < loss or buying_power <= 0:
        raise ValueError("Sufficient options buying power could not be verified")
    if level is None or level < 3:
        raise ValueError("Options trading level 3 is required for debit spreads")
    if len(open_orders) >= 500:
        raise ValueError("Open-order response may be truncated; exposure cannot be verified")
    position_roots = set()
    for position in positions:
        root = option_root(position.get("symbol"))
        asset_class = getattr(position.get("asset_class"), "value", position.get("asset_class"))
        if asset_class in {"us_option", "us_index"} and not root:
            raise ValueError("An option position has an unrecognized contract symbol")
        if root:
            quantity = finite_number(position.get("qty"))
            if quantity is None:
                raise ValueError("An option position has unverified quantity")
            if quantity != 0:
                position_roots.add(root)
    pending_roots = set()
    pending_entries = 0
    for order in open_orders:
        legs = order.get("legs") or [order]
        roots = set()
        for leg in legs:
            root = option_root(leg.get("symbol"))
            intent = getattr(leg.get("position_intent"), "value", leg.get("position_intent"))
            asset_class = getattr(leg.get("asset_class"), "value", leg.get("asset_class"))
            if asset_class in {"us_option", "us_index"} and not root:
                raise ValueError("Pending option exposure has an unrecognized contract symbol")
            if root and intent not in {"buy_to_close", "sell_to_close"}:
                roots.add(root)
            if (
                order.get("order_class") == "mleg"
                and not root
                and intent not in {"buy_to_close", "sell_to_close"}
            ):
                raise ValueError("Pending spread exposure could not be verified")
        if roots:
            pending_roots.update(roots)
            pending_entries += 1
    active_roots = position_roots | pending_roots
    if underlying in active_roots:
        raise ValueError(f"An open or pending option position already uses {underlying}")
    # Conservative: additions to existing roots still consume an entry slot.
    active_spreads = max(len(active_roots), len(position_roots) + pending_entries)
    if active_spreads >= settings.max_open_spreads:
        raise ValueError(f"Maximum of {settings.max_open_spreads} concurrent spreads reached")
    return {
        "daily_return": round(daily_return, 6),
        "daily_loss_limit": settings.max_daily_loss_pct,
        "risk_budget": round(budget, 2),
        "active_spreads": active_spreads,
        "max_open_spreads": settings.max_open_spreads,
        "same_underlying_clear": True,
        "paper_only": True,
    }
