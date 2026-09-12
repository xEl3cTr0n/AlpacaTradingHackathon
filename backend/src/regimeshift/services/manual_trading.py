import hashlib
import secrets
from datetime import UTC, datetime

from regimeshift.config import Settings
from regimeshift.domain.execution_checks import (
    check_option_quote,
    verify_entry_capacity,
    verify_open_clock,
)
from regimeshift.domain.exits import option_contract_details
from regimeshift.domain.models import (
    ManualTradePreview,
    ManualTradeRequest,
    ManualTradeResult,
)


class ManualPaperTrader:
    """Operator-authenticated, two-leg, defined-risk paper orders only."""

    def __init__(self, settings: Settings):
        if not settings.alpaca_configured:
            raise ValueError("Alpaca paper credentials are not configured")
        if not settings.alpaca_paper:
            raise ValueError("Manual trader refuses non-paper configuration")
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.trading.client import TradingClient

        secret = settings.alpaca_secret_key.get_secret_value()
        self.settings = settings
        self.options = OptionHistoricalDataClient(settings.alpaca_api_key, secret)
        self.trading = TradingClient(settings.alpaca_api_key, secret, paper=True)

    @staticmethod
    def _record(value) -> dict:
        return value if isinstance(value, dict) else value.model_dump(mode="json")

    def verify_capacity(self, underlying: str, maximum_loss: float) -> dict:
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        return verify_entry_capacity(
            self.settings,
            underlying,
            self._record(self.trading.get_account()),
            [self._record(p) for p in self.trading.get_all_positions()],
            [
                self._record(o)
                for o in self.trading.get_orders(
                    filter=GetOrdersRequest(
                        status=QueryOrderStatus.OPEN,
                        nested=True,
                        limit=500,
                    )
                )
            ],
            maximum_loss=maximum_loss,
        )

    def preview(self, request: ManualTradeRequest) -> ManualTradePreview:
        from alpaca.data.requests import OptionSnapshotRequest

        long_symbol = request.long_symbol.upper()
        short_symbol = request.short_symbol.upper()
        long = option_contract_details(long_symbol)
        short = option_contract_details(short_symbol)
        if long[:3] != short[:3]:
            raise ValueError("Both option legs must share underlying, expiration, and type")

        underlying, expiration, option_type, long_strike = long
        short_strike = short[3]
        dte = (expiration.date() - datetime.now(UTC).date()).days
        reasons: list[str] = []
        structure_valid = (
            long_strike < short_strike if option_type == "C" else long_strike > short_strike
        )
        if not structure_valid:
            reasons.append("Leg order is not a defined-risk debit spread")
        if not 7 <= dte <= 60:
            reasons.append("Expiration must be 7–60 days away")

        width = abs(short_strike - long_strike)
        if request.limit_debit >= width:
            reasons.append("Limit debit must be below spread width")
        maximum_loss = round(request.limit_debit * 100 * request.quantity, 2)
        maximum_reward = round((width - request.limit_debit) * 100 * request.quantity, 2)
        risk_budget = 0.0
        capacity_passed = False
        try:
            capacity = self.verify_capacity(underlying, maximum_loss)
            risk_budget = capacity["risk_budget"]
            capacity_passed = True
        except ValueError as error:
            reasons.append(str(error))
        market_open = False
        try:
            verify_open_clock(self._record(self.trading.get_clock()))
            market_open = True
        except ValueError as error:
            reasons.append(str(error))

        snapshots = self.options.get_option_snapshot(
            OptionSnapshotRequest(symbol_or_symbols=[long_symbol, short_symbol])
        )
        long_quote = snapshots.get(long_symbol).latest_quote if snapshots.get(long_symbol) else None
        short_quote = (
            snapshots.get(short_symbol).latest_quote if snapshots.get(short_symbol) else None
        )
        market_debit = None
        checked_at = datetime.now(UTC)
        quote_checks = [
            check_option_quote(
                symbol,
                bid=getattr(quote, "bid_price", None),
                ask=getattr(quote, "ask_price", None),
                bid_size=getattr(quote, "bid_size", None),
                ask_size=getattr(quote, "ask_size", None),
                timestamp=getattr(quote, "timestamp", None),
                now=checked_at,
            )
            for symbol, quote in ((long_symbol, long_quote), (short_symbol, short_quote))
        ]
        liquidity_passed = all(check.valid for check in quote_checks)
        for check in quote_checks:
            reasons.extend(f"{check.symbol}: {reason}" for reason in check.reasons)
        if quote_checks[0].ask is not None and quote_checks[1].bid is not None:
            natural = round(quote_checks[0].ask - quote_checks[1].bid, 2)
            if not 0 < natural < width:
                reasons.append("Current natural debit is invalid relative to spread width")
                liquidity_passed = False
            else:
                market_debit = natural
            if market_debit is not None and request.limit_debit > market_debit * 1.10 + 0.05:
                reasons.append("Limit debit is more than 10% above the current natural debit")

        return ManualTradePreview(
            valid=not reasons,
            underlying_symbol=underlying,
            option_type="call" if option_type == "C" else "put",
            expiration=expiration,
            long_strike=long_strike,
            short_strike=short_strike,
            width=width,
            limit_debit=request.limit_debit,
            market_debit=market_debit,
            maximum_loss=maximum_loss,
            stop_loss_dollars=round(maximum_loss * self.settings.stop_loss_fraction, 2),
            stop_loss_fraction=self.settings.stop_loss_fraction,
            maximum_reward=max(0, maximum_reward),
            risk_budget=round(risk_budget, 2),
            liquidity_passed=liquidity_passed,
            quote_checks=quote_checks,
            capacity_passed=capacity_passed,
            market_open=market_open,
            reasons=reasons
            or [
                "Defined-risk structure and quote gates passed; maximum loss stays "
                f"within ${risk_budget:,.0f}"
            ],
        )

    def submit(self, request: ManualTradeRequest, operator_token: str) -> ManualTradeResult:
        if not self.settings.manual_trading_configured:
            raise ValueError("Manual paper orders are disabled or missing MANUAL_TRADE_TOKEN")
        expected = self.settings.manual_trade_token.get_secret_value()
        if not secrets.compare_digest(operator_token, expected):
            raise PermissionError("Invalid operator token")
        preview = self.preview(request)
        if not preview.valid:
            raise ValueError(
                "Deterministic manual-order gates rejected: " + "; ".join(preview.reasons)
            )

        from alpaca.trading.enums import (
            OrderClass,
            OrderSide,
            OrderType,
            PositionIntent,
            TimeInForce,
        )
        from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

        digest = hashlib.sha256(
            f"{datetime.now(UTC).date()}:{request.long_symbol}:"
            f"{request.short_symbol}:{request.limit_debit}".encode()
        ).hexdigest()[:24]
        client_order_id = f"regimeshift-manual-{digest}"
        order = self.trading.submit_order(
            LimitOrderRequest(
                qty=request.quantity,
                type=OrderType.LIMIT,
                order_class=OrderClass.MLEG,
                limit_price=request.limit_debit,
                time_in_force=TimeInForce.DAY,
                client_order_id=client_order_id,
                legs=[
                    OptionLegRequest(
                        symbol=request.long_symbol.upper(),
                        ratio_qty=1,
                        side=OrderSide.BUY,
                        position_intent=PositionIntent.BUY_TO_OPEN,
                    ),
                    OptionLegRequest(
                        symbol=request.short_symbol.upper(),
                        ratio_qty=1,
                        side=OrderSide.SELL,
                        position_intent=PositionIntent.SELL_TO_OPEN,
                    ),
                ],
            )
        )
        return ManualTradeResult(
            status=str(getattr(order.status, "value", order.status)),
            order_id=str(order.id),
            client_order_id=order.client_order_id,
        )
