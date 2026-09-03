import hashlib
import secrets
from datetime import UTC, datetime

from regimeshift.config import Settings
from regimeshift.domain.exits import option_contract_details
from regimeshift.domain.models import (
    ManualTradePreview,
    ManualTradeRequest,
    ManualTradeResult,
)

MANUAL_RISK_CAP_DOLLARS = 200.0


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
        risk_budget = min(
            MANUAL_RISK_CAP_DOLLARS,
            self.settings.account_equity * self.settings.max_risk_per_trade_pct,
        )
        if maximum_loss > risk_budget:
            reasons.append(f"Maximum loss exceeds the ${risk_budget:,.0f} manual risk cap")

        snapshots = self.options.get_option_snapshot(
            OptionSnapshotRequest(symbol_or_symbols=[long_symbol, short_symbol])
        )
        long_quote = snapshots.get(long_symbol).latest_quote if snapshots.get(long_symbol) else None
        short_quote = (
            snapshots.get(short_symbol).latest_quote if snapshots.get(short_symbol) else None
        )
        market_debit = None
        liquidity_passed = False
        if long_quote and short_quote and long_quote.ask_price and short_quote.bid_price:
            long_ask = float(long_quote.ask_price)
            long_bid = float(long_quote.bid_price)
            short_ask = float(short_quote.ask_price)
            short_bid = float(short_quote.bid_price)
            market_debit = round(max(0.01, long_ask - short_bid), 2)
            long_mid = (long_ask + long_bid) / 2
            short_mid = (short_ask + short_bid) / 2
            long_spread = long_ask - long_bid
            short_spread = short_ask - short_bid
            liquidity_passed = (
                long_mid > 0
                and short_mid > 0
                and long_spread / long_mid <= 0.20
                and short_spread / short_mid <= 0.20
                and market_debit < width
            )
            if market_debit >= width:
                reasons.append("Current natural debit is invalid relative to spread width")
            if request.limit_debit > market_debit * 1.10 + 0.05:
                reasons.append("Limit debit is more than 10% above the current natural debit")
        else:
            reasons.append("Both legs require live two-sided option quotes")
        if not liquidity_passed:
            reasons.append("Each leg must have a bid/ask spread no wider than 20% of midpoint")

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
            maximum_reward=max(0, maximum_reward),
            risk_budget=round(risk_budget, 2),
            liquidity_passed=liquidity_passed,
            reasons=reasons or ["Defined-risk structure, quote, and $200 risk gates passed"],
        )

    def submit(self, request: ManualTradeRequest, operator_token: str) -> ManualTradeResult:
        if not self.settings.manual_trading_configured:
            raise ValueError("Manual paper orders are disabled or missing MANUAL_TRADE_TOKEN")
        expected = self.settings.manual_trade_token.get_secret_value()
        if not secrets.compare_digest(operator_token, expected):
            raise PermissionError("Invalid operator token")
        preview = self.preview(request)
        if not preview.valid:
            raise ValueError("Deterministic manual-order gates rejected the trade")

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
