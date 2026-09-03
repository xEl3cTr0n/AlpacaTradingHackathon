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
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Build an atomic exit only for a complete RegimeShift two-leg debit spread."""
    if (
        entry.get("status") != "filled"
        or entry.get("order_class") != "mleg"
        or not str(entry.get("client_order_id", "")).startswith("regimeshift-signal-")
    ):
        return None
    legs = entry.get("legs") or []
    if len(legs) != 2:
        return None
    symbols = [str(leg.get("symbol", "")) for leg in legs]
    if any(symbol not in positions for symbol in symbols):
        return None
    details = [option_contract_details(symbol) for symbol in symbols]
    if details[0][0] != details[1][0] or details[0][1] != details[1][1]:
        return None

    quantity = float(entry.get("filled_qty") or entry.get("qty") or 0)
    if quantity <= 0:
        return None
    if any(
        abs(float(positions[symbol].get("qty_available") or 0)) < quantity
        for symbol in symbols
    ):
        return None

    entry_debit = float(entry.get("filled_avg_price") or entry.get("limit_price") or 0)
    if entry_debit <= 0:
        return None
    width = abs(details[0][3] - details[1][3])
    maximum_loss = entry_debit * quantity * 100
    maximum_reward = max(0.0, (width - entry_debit) * quantity * 100)
    unrealized_pnl = sum(float(positions[symbol].get("unrealized_pl") or 0) for symbol in symbols)
    expected_direction = Direction.BULLISH if details[0][2] == "C" else Direction.BEARISH
    timestamp = now or datetime.now(UTC)
    days_to_expiry = (details[0][1].date() - timestamp.date()).days

    reasons: list[str] = []
    if maximum_reward > 0 and unrealized_pnl >= maximum_reward * 0.50:
        reasons.append("50% profit target reached")
    if unrealized_pnl <= -maximum_loss * 0.75:
        reasons.append("75% maximum-loss stop reached")
    if days_to_expiry <= 7:
        reasons.append("expiration is within 7 days")
    if current_direction not in {None, Direction.SIDEWAYS, expected_direction}:
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
        "maximum_reward": round(maximum_reward, 2),
        "days_to_expiry": days_to_expiry,
        "reasons": reasons,
        "legs": closing_legs,
        "paper_only": True,
    }
