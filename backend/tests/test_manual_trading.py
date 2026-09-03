from types import SimpleNamespace

from regimeshift.config import Settings
from regimeshift.domain.models import ManualTradeRequest
from regimeshift.services.manual_trading import ManualPaperTrader


class FakeOptions:
    def get_option_snapshot(self, request):
        symbols = request.symbol_or_symbols
        return {
            symbols[0]: SimpleNamespace(
                latest_quote=SimpleNamespace(
                    ask_price=3.0, bid_price=2.9
                )
            ),
            symbols[1]: SimpleNamespace(
                latest_quote=SimpleNamespace(
                    ask_price=2.1, bid_price=2.0
                )
            ),
        }


def trader() -> ManualPaperTrader:
    instance = ManualPaperTrader.__new__(ManualPaperTrader)
    instance.settings = Settings(
        market_data_mode="demo",
        alpaca_api_key="paper-key",
        alpaca_secret_key="paper-secret",
        account_equity=100_000,
    )
    instance.options = FakeOptions()
    return instance


def test_manual_preview_accepts_liquid_defined_risk_call_spread() -> None:
    result = trader().preview(
        ManualTradeRequest(
            long_symbol="AAPL261016C00200000",
            short_symbol="AAPL261016C00205000",
            limit_debit=1,
        )
    )
    assert result.valid
    assert result.maximum_loss == 100
    assert result.maximum_reward == 400
    assert result.paper_only


def test_manual_preview_rejects_over_budget_spread() -> None:
    result = trader().preview(
        ManualTradeRequest(
            long_symbol="AAPL261016C00200000",
            short_symbol="AAPL261016C00205000",
            limit_debit=3,
        )
    )
    assert not result.valid
    assert any("$200" in reason for reason in result.reasons)
