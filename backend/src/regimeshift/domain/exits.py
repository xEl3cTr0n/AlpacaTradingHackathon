import math
import re
from datetime import UTC, datetime
from typing import Any

from regimeshift.domain.models import Direction

OPTION_SYMBOL = re.compile(r"^([A-Z.]{1,6})(\d{6})([CP])(\d{8})$")


def option_contract_details(symbol: str) -> tuple[str, datetime, str, float]:
    match = OPTION_SYMBOL.fullmatch(symbol)
    if not match:
        raise ValueError(f"Unsupported option symbol {symbol}")
    underlying, expiry, option_type, strike = match.groups()
    return (
        underlying,
        datetime.strptime(expiry, "%y%m%d").replace(tzinfo=UTC),
        option_type,
        int(strike) / 1000,
    )


def managed_exit_plan(
    entry: dict[str, Any],
    positions: dict[str, dict[str, Any]],
    *,
    current_direction: Direction | None = None,
    stop_loss_fraction: float = 0.50,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Build an exit for an identified, complete RegimeShift debit spread.

    Unmanaged or no-longer-held entries return None. Ambiguous held exposure
    raises an inspectable rejection instead of guessing a closing direction.
    """
    if not 0 < stop_loss_fraction <= 1:
        raise ValueError("Stop-loss fraction must be above zero and no greater than one")
    if (
        entry.get("status") != "filled"
        or entry.get("order_class") != "mleg"
        or not str(entry.get("client_order_id", "")).startswith(
            ("regimeshift-signal-", "regimeshift-manual-")
        )
    ):
        return None
    legs = entry.get("legs") or []
    if len(legs) != 2:
        raise ValueError("Managed entry must contain exactly two legs")
    symbols = [str(leg.get("symbol", "")) for leg in legs]
    if not any(symbol in positions for symbol in symbols):
        return None
    if any(symbol not in positions for symbol in symbols):
        raise ValueError("Incomplete held spread; operator reconciliation required")
    details = [option_contract_details(symbol) for symbol in symbols]
    if symbols[0] == symbols[1] or details[0][:3] != details[1][:3]:
        raise ValueError("Held legs must share underlying, expiration, and option type")
    intents = [leg.get("position_intent") for leg in legs]
    if sorted(str(intent) for intent in intents) != ["buy_to_open", "sell_to_open"]:
        raise ValueError("Opening intents are unverified; cannot infer closing sides")
    if any(_number(leg.get("ratio_qty")) != 1 for leg in legs):
        raise ValueError("Managed exits require verified 1:1 opening ratios")
    long_index = intents.index("buy_to_open")
    short_index = intents.index("sell_to_open")
    signed_width = (details[short_index][3] - details[long_index][3]) * (
        1 if details[0][2] == "C" else -1
    )
    quantity = _number(entry.get("filled_qty"))
    entry_debit = _number(entry.get("filled_avg_price"))
    if quantity is None or quantity <= 0 or not quantity.is_integer():
        raise ValueError("Filled entry quantity could not be verified")
    if entry_debit is None or not 0 < entry_debit < signed_width:
        raise ValueError("Actual filled debit is invalid relative to spread width")
    for index, symbol in enumerate(symbols):
        position = positions[symbol]
        signed_qty = _number(position.get("qty"))
        available = _number(position.get("qty_available"))
        expected_qty = quantity if index == long_index else -quantity
        if signed_qty != expected_qty:
            raise ValueError("Held position direction/quantity does not match the opening spread")
        if available is None or abs(available) < quantity:
            raise ValueError("Full spread quantity is not available to close")
        expected_side = "buy" if index == long_index else "sell"
        if legs[index].get("side") != expected_side:
            raise ValueError("Opening side does not match its position intent")
    width = abs(details[0][3] - details[1][3])
    maximum_loss = entry_debit * quantity * 100
    maximum_reward = max(0.0, (width - entry_debit) * quantity * 100)
    profits = [_number(positions[symbol].get("unrealized_pl")) for symbol in symbols]
    if any(profit is None for profit in profits):
        raise ValueError("Held spread P&L could not be verified")
    unrealized_pnl = sum(profits)
    expected_direction = Direction.BULLISH if details[0][2] == "C" else Direction.BEARISH
    timestamp = now or datetime.now(UTC)
    days_to_expiry = (details[0][1].date() - timestamp.date()).days

    reasons: list[str] = []
    if maximum_reward > 0 and unrealized_pnl >= maximum_reward * 0.50:
        reasons.append("50% profit target reached")
    if unrealized_pnl <= -maximum_loss * stop_loss_fraction:
        reasons.append(f"{stop_loss_fraction:.0%} maximum-loss stop reached")
    if days_to_expiry <= 7:
        reasons.append("expiration is within 7 days")
    if current_direction in {Direction.BULLISH, Direction.BEARISH} and (
        current_direction != expected_direction
    ):
        reasons.append("detected trend reversed against the position")
    if not reasons:
        return None

    closing_legs = []
    for leg in legs:
        opening_intent = leg.get("position_intent")
        closing_legs.append(
            {
                "symbol": leg["symbol"],
                "ratio_qty": str(leg.get("ratio_qty") or "1"),
                "side": "sell" if opening_intent == "buy_to_open" else "buy",
                "position_intent": (
                    "sell_to_close" if opening_intent == "buy_to_open" else "buy_to_close"
                ),
            }
        )
    return {
        "entry_order_id": entry["id"],
        "entry_client_order_id": entry["client_order_id"],
        "underlying_symbol": details[0][0],
        "quantity": quantity,
        "unrealized_pnl": round(unrealized_pnl, 2),
        "maximum_loss": round(maximum_loss, 2),
        "stop_loss_dollars": round(maximum_loss * stop_loss_fraction, 2),
        "stop_loss_fraction": stop_loss_fraction,
        "maximum_reward": round(maximum_reward, 2),
        "days_to_expiry": days_to_expiry,
        "current_direction": current_direction,
        "reasons": reasons,
        "legs": closing_legs,
        "paper_only": True,
    }


def _number(value: Any) -> float | None:
    # Kept here to avoid a dependency cycle: entry checks import the OCC parser.
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None
