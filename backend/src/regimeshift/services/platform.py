import math
import random
from datetime import UTC, datetime, timedelta

from regimeshift.config import Settings
from regimeshift.domain.models import (
    AccountSummary,
    ActivityEvent,
    EquityPoint,
    IntegrationStatus,
    OrderSummary,
    PaperAutomationStatus,
    PlatformSnapshot,
    PositionSummary,
)


def _integration_statuses(settings: Settings) -> list[IntegrationStatus]:
    return [
        IntegrationStatus(
            id="trading-api",
            name="Alpaca Trading API",
            status="connected" if settings.alpaca_configured else "setup_required",
            detail=(
                "Paper account, portfolio, orders, news, and market data"
                if settings.alpaca_configured
                else "Add paper credentials to the root .env"
            ),
            capability="read-only paper telemetry",
        ),
        IntegrationStatus(
            id="mcp",
            name="Alpaca MCP Server",
            status="connected" if settings.alpaca_mcp_enabled else "configured",
            detail=(
                "Agent tool access is enabled"
                if settings.alpaca_mcp_enabled
                else "Repo-scoped read-only MCP runs with Claude/Gemini outside Vercel"
            ),
            capability="agent-native account, news, and options tools",
        ),
        IntegrationStatus(
            id="cli",
            name="Alpaca CLI",
            status="connected" if settings.alpaca_cli_enabled else "external_runner",
            detail=(
                "CLI workflow is enabled"
                if settings.alpaca_cli_enabled
                else "Pinned paper-only runner performs contract discovery and gated orders"
            ),
            capability="terminal account and order inspection",
        ),
    ]


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


class DemoPlatformProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def get_snapshot(self) -> PlatformSnapshot:
        now = datetime.now(UTC)
        randomizer = random.Random("regimeshift-platform")
        equity = 100_000.0
        curve: list[EquityPoint] = []
        for index in range(31):
            daily_return = 0.0013 + math.sin(index / 3.5) * 0.0018 + randomizer.gauss(0, 0.0024)
            equity *= 1 + daily_return
            curve.append(
                EquityPoint(
                    timestamp=now - timedelta(days=30 - index),
                    equity=round(equity, 2),
                    profit_loss=round(equity - 100_000, 2),
                )
            )
        total_pnl = equity - 100_000
        positions = [
            PositionSummary(
                symbol="SPY",
                asset_class="us_equity",
                quantity=12,
                market_value=6902.64,
                average_entry=566.10,
                current_price=575.22,
                unrealized_pnl=109.44,
                unrealized_pnl_pct=0.0161,
            ),
            PositionSummary(
                symbol="QQQ",
                asset_class="us_equity",
                quantity=8,
                market_value=4058.40,
                average_entry=498.70,
                current_price=507.30,
                unrealized_pnl=68.80,
                unrealized_pnl_pct=0.0172,
            ),
            PositionSummary(
                symbol="SPY260918C00580000",
                asset_class="us_option",
                quantity=1,
                market_value=642.00,
                average_entry=5.75,
                current_price=6.42,
                unrealized_pnl=67.00,
                unrealized_pnl_pct=0.1165,
            ),
        ]
        orders = [
            OrderSummary(
                id="demo-ord-1",
                symbol="SPY260918C00580000",
                side="buy",
                quantity=1,
                order_type="limit",
                status="filled",
                submitted_at=now - timedelta(hours=3, minutes=18),
            ),
            OrderSummary(
                id="demo-ord-2",
                symbol="SPY260918C00590000",
                side="sell",
                quantity=1,
                order_type="limit",
                status="filled",
                submitted_at=now - timedelta(hours=3, minutes=18),
            ),
            OrderSummary(
                id="demo-ord-3",
                symbol="QQQ",
                side="buy",
                quantity=8,
                order_type="market",
                status="filled",
                submitted_at=now - timedelta(days=1, hours=2),
            ),
        ]
        activity = [
            ActivityEvent(
                timestamp=now - timedelta(minutes=2),
                source="Risk",
                title="Trade preview approved",
                detail="Maximum modeled loss is inside the 1% account budget.",
                status="success",
            ),
            ActivityEvent(
                timestamp=now - timedelta(minutes=3),
                source="Bear",
                title="Counter-thesis completed",
                detail="Whipsaw risk remains below the veto threshold.",
                status="complete",
            ),
            ActivityEvent(
                timestamp=now - timedelta(minutes=4),
                source="Technical",
                title="Regime classified",
                detail="Bullish direction with elevated volatility confidence.",
                status="complete",
            ),
            ActivityEvent(
                timestamp=now - timedelta(minutes=5),
                source="API",
                title="Market snapshot received",
                detail="Bars, news, and option telemetry normalized.",
                status="complete",
            ),
        ]
        return PlatformSnapshot(
            mode="demo",
            account=AccountSummary(
                equity=round(equity, 2),
                cash=77_406.32,
                buying_power=154_812.64,
                day_pnl=184.72,
                day_pnl_pct=0.0018,
                total_pnl=round(total_pnl, 2),
                total_pnl_pct=round(total_pnl / 100_000, 4),
                options_buying_power=61_925.06,
                options_level=3,
                trading_blocked=False,
            ),
            equity_curve=curve,
            positions=positions,
            orders=orders,
            integrations=_integration_statuses(self.settings),
            activity=activity,
            automation=PaperAutomationStatus(
                status="demo",
                market_open=True,
                next_open=now,
                next_close=now + timedelta(hours=6),
                scan_interval_minutes=5,
                worker="Demo replay",
            ),
            generated_at=now,
        )


class AlpacaPlatformProvider:
    def __init__(self, settings: Settings):
        if not settings.alpaca_configured:
            raise ValueError("Alpaca credentials are not configured")
        from alpaca.trading.client import TradingClient

        self.settings = settings
        self.client = TradingClient(
            settings.alpaca_api_key,
            settings.alpaca_secret_key.get_secret_value(),
            paper=settings.alpaca_paper,
        )

    def get_snapshot(self) -> PlatformSnapshot:
        from alpaca.trading.requests import GetOrdersRequest, GetPortfolioHistoryRequest

        now = datetime.now(UTC)
        account = self.client.get_account()
        history = self.client.get_portfolio_history(
            GetPortfolioHistoryRequest(period="1M", timeframe="1D")
        )
        positions = self.client.get_all_positions()
        orders = self.client.get_orders(GetOrdersRequest(limit=20, nested=True))
        clock = self.client.get_clock()
        equity = float(account.equity or 0)
        last_equity = float(account.last_equity or equity)
        base_value = float(history.base_value or last_equity or 1)
        day_pnl = equity - last_equity
        curve = [
            EquityPoint(
                timestamp=datetime.fromtimestamp(timestamp, UTC),
                equity=float(value),
                profit_loss=float(pnl),
            )
            for timestamp, value, pnl in zip(
                history.timestamp or [],
                history.equity or [],
                history.profit_loss or [],
                strict=False,
            )
            if float(value) > 0
        ]
        return PlatformSnapshot(
            mode="alpaca",
            account=AccountSummary(
                equity=equity,
                cash=float(account.cash or 0),
                buying_power=float(account.buying_power or 0),
                day_pnl=day_pnl,
                day_pnl_pct=day_pnl / last_equity if last_equity else 0,
                total_pnl=equity - base_value,
                total_pnl_pct=(equity - base_value) / base_value if base_value else 0,
                options_buying_power=float(account.options_buying_power or 0),
                options_level=int(account.options_trading_level or 0),
                trading_blocked=bool(account.trading_blocked),
            ),
            equity_curve=curve,
            positions=[
                PositionSummary(
                    symbol=position.symbol,
                    asset_class=_enum_value(position.asset_class),
                    quantity=float(position.qty),
                    market_value=float(position.market_value or 0),
                    average_entry=float(position.avg_entry_price),
                    current_price=float(position.current_price or 0),
                    unrealized_pnl=float(position.unrealized_pl or 0),
                    unrealized_pnl_pct=float(position.unrealized_plpc or 0),
                )
                for position in positions
            ],
            orders=[
                OrderSummary(
                    id=str(order.id),
                    symbol=order.symbol or "multi-leg",
                    side=_enum_value(order.side or "multi-leg"),
                    quantity=float(order.qty or 0),
                    order_type=_enum_value(order.order_type),
                    status=_enum_value(order.status),
                    submitted_at=order.submitted_at or order.created_at or now,
                )
                for order in orders
            ],
            integrations=_integration_statuses(self.settings),
            activity=[
                ActivityEvent(
                    timestamp=now,
                    source="API",
                    title="Paper account synchronized",
                    detail=f"Loaded {len(positions)} positions and {len(orders)} recent orders.",
                    status="success",
                )
            ],
            automation=PaperAutomationStatus(
                status="monitoring" if clock.is_open else "waiting_for_market",
                market_open=bool(clock.is_open),
                next_open=clock.next_open,
                next_close=clock.next_close,
                scan_interval_minutes=5,
                worker="GitHub Actions + Alpaca CLI",
            ),
            generated_at=now,
        )


def build_platform_provider(settings: Settings) -> DemoPlatformProvider | AlpacaPlatformProvider:
    if settings.market_data_mode.lower() == "alpaca":
        return AlpacaPlatformProvider(settings)
    return DemoPlatformProvider(settings)
