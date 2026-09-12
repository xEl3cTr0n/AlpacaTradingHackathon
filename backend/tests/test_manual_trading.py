from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from regimeshift.config import Settings
from regimeshift.domain.models import ManualTradeRequest
from regimeshift.services.manual_trading import ManualPaperTrader


class FakeOptions:
    quote_age = 0
    long_bid = 2.9

    def get_option_snapshot(self, request):
        symbols = request.symbol_or_symbols
        return {
            symbols[0]: SimpleNamespace(
                latest_quote=SimpleNamespace(
                    ask_price=3.0,
                    bid_price=self.long_bid,
                    bid_size=10,
                    ask_size=10,
                    timestamp=datetime.now(UTC) - timedelta(seconds=self.quote_age),
                )
            ),
            symbols[1]: SimpleNamespace(
                latest_quote=SimpleNamespace(
                    ask_price=2.1,
                    bid_price=2.0,
                    bid_size=10,
                    ask_size=10,
                    timestamp=datetime.now(UTC) - timedelta(seconds=self.quote_age),
                )
            ),
        }


class FakeTrading:
    def __init__(self):
        self.account = {
            "equity": "100000",
            "last_equity": "100000",
            "status": "ACTIVE",
            "trading_blocked": False,
            "account_blocked": False,
            "trade_suspended_by_user": False,
            "options_buying_power": "50000",
            "options_trading_level": 3,
        }
        self.orders = []
        self.positions = []
        self.is_open = True
        self.submitted = []

    def get_account(self):
        return self.account

    def get_orders(self, **kwargs):
        return self.orders

    def get_all_positions(self):
        return self.positions

    def get_clock(self):
        return {"timestamp": datetime.now(UTC).isoformat(), "is_open": self.is_open}

    def submit_order(self, request):
        self.submitted.append(request)
        return SimpleNamespace(
            id="test-paper-order", status="accepted", client_order_id=request.client_order_id
        )


def request(debit=1):
    expiration = (datetime.now(UTC) + timedelta(days=30)).strftime("%y%m%d")
    return ManualTradeRequest(
        long_symbol=f"AAPL{expiration}C00200000",
        short_symbol=f"AAPL{expiration}C00205000",
        limit_debit=debit,
    )


def trader() -> ManualPaperTrader:
    instance = ManualPaperTrader.__new__(ManualPaperTrader)
    instance.settings = Settings(
        market_data_mode="demo",
        alpaca_api_key="paper-key",
        alpaca_secret_key="paper-secret",
        account_equity=100_000,
        enable_manual_paper_orders=True,
        manual_trade_token="test-operator-token",
    )
    instance.options = FakeOptions()
    instance.trading = FakeTrading()
    return instance


def test_manual_preview_accepts_liquid_defined_risk_call_spread() -> None:
    result = trader().preview(request())
    assert result.valid
    assert result.maximum_loss == 100
    assert result.stop_loss_dollars == 50
    assert result.stop_loss_fraction == 0.5
    assert result.maximum_reward == 400
    assert result.paper_only
    assert result.capacity_passed and result.market_open
    assert all(check.valid for check in result.quote_checks)


def test_manual_preview_rejects_over_budget_spread() -> None:
    expiration = (datetime.now(UTC) + timedelta(days=30)).strftime("%y%m%d")
    result = trader().preview(
        ManualTradeRequest(
            long_symbol=f"AAPL{expiration}C00200000",
            short_symbol=f"AAPL{expiration}C00220000",
            limit_debit=11,
        )
    )
    assert not result.valid
    assert any("$1,000" in reason for reason in result.reasons)


@pytest.mark.parametrize("age", [121, 10000, -10])
def test_stale_or_future_quote_blocks_manual_submission(age):
    instance = trader()
    instance.options.quote_age = age
    preview = instance.preview(request())
    assert not preview.valid
    assert not preview.liquidity_passed
    assert all(not check.valid for check in preview.quote_checks)
    with pytest.raises(ValueError, match="Quote"):
        instance.submit(request(), "test-operator-token")
    assert not instance.trading.submitted


def test_crossed_quote_no_longer_passes_negative_spread_test():
    instance = trader()
    instance.options.long_bid = 4.0
    assert not instance.preview(request()).valid
    with pytest.raises(ValueError, match="non-crossed"):
        instance.submit(request(), "test-operator-token")
    assert not instance.trading.submitted


@pytest.mark.parametrize(
    "change,reason",
    [
        ({"equity": "97000"}, "Daily loss circuit breaker"),
        ({"options_buying_power": "1"}, "buying power"),
        ({"options_trading_level": 2}, "level 3"),
        ({"trading_blocked": True}, "trading_blocked"),
    ],
)
def test_manual_submit_rechecks_account_after_an_approved_preview(change, reason):
    instance = trader()
    assert instance.preview(request()).valid
    instance.trading.account.update(change)
    with pytest.raises(ValueError, match=reason):
        instance.submit(request(), "test-operator-token")
    assert not instance.trading.submitted


def test_manual_rejects_market_closed_and_existing_external_exposure():
    instance = trader()
    instance.trading.is_open = False
    assert not instance.preview(request()).valid
    instance.trading.is_open = True
    instance.trading.orders = [{"symbol": request().long_symbol, "position_intent": "buy_to_open"}]
    preview = instance.preview(request())
    assert not preview.valid and not preview.capacity_passed
    assert any("already uses AAPL" in reason for reason in preview.reasons)


def test_valid_manual_request_reaches_only_fake_broker_after_token_check():
    instance = trader()
    with pytest.raises(PermissionError):
        instance.submit(request(), "wrong")
    assert not instance.trading.submitted
    result = instance.submit(request(), "test-operator-token")
    assert result.status == "accepted"
    submitted = instance.trading.submitted[0]
    assert submitted.qty == 1 and submitted.order_class.value == "mleg"
    assert submitted.limit_price == 1 and len(submitted.legs) == 2
