from datetime import UTC, datetime, timedelta
from typing import Protocol

from regimeshift.config import Settings
from regimeshift.domain.microstructure import assess_microstructure, unavailable_microstructure
from regimeshift.domain.models import OptionsMicrostructureAssessment


class OptionsMicrostructureProvider(Protocol):
    def get_assessment(self, symbol: str, spot: float) -> OptionsMicrostructureAssessment: ...


class UnavailableOptionsProvider:
    def __init__(self, reason: str = "Options microstructure requires Alpaca data mode"):
        self.reason = reason

    def get_assessment(self, symbol: str, spot: float) -> OptionsMicrostructureAssessment:
        del spot
        return unavailable_microstructure(symbol, "not configured", self.reason)


class AlpacaOptionsProvider:
    """Join Alpaca contract open interest with live chain Greeks."""

    def __init__(self, settings: Settings):
        if not settings.alpaca_configured:
            raise ValueError("Alpaca credentials are not configured")
        from alpaca.data.historical.option import OptionHistoricalDataClient
        from alpaca.trading.client import TradingClient

        secret = settings.alpaca_secret_key.get_secret_value()
        self.option_client = OptionHistoricalDataClient(settings.alpaca_api_key, secret)
        self.trading_client = TradingClient(settings.alpaca_api_key, secret, paper=True)

    def get_assessment(self, symbol: str, spot: float) -> OptionsMicrostructureAssessment:
        from alpaca.data.requests import OptionChainRequest
        from alpaca.trading.requests import GetOptionContractsRequest

        symbol = symbol.upper()
        today = datetime.now(UTC).date()
        end = today + timedelta(days=45)
        try:
            contracts = []
            token = None
            while True:
                response = self.trading_client.get_option_contracts(
                    GetOptionContractsRequest(
                        underlying_symbols=[symbol],
                        expiration_date_gte=today.isoformat(),
                        expiration_date_lte=end.isoformat(),
                        strike_price_gte=f"{spot * 0.85:.2f}",
                        strike_price_lte=f"{spot * 1.15:.2f}",
                        limit=1000,
                        page_token=token,
                    )
                )
                contracts.extend(response.option_contracts or [])
                token = response.next_page_token
                if not token or len(contracts) >= 3000:
                    break

            snapshots = self.option_client.get_option_chain(
                OptionChainRequest(
                    underlying_symbol=symbol,
                    expiration_date_gte=today.isoformat(),
                    expiration_date_lte=end.isoformat(),
                    strike_price_gte=spot * 0.85,
                    strike_price_lte=spot * 1.15,
                )
            )
            rows: list[dict[str, float | str | int | None]] = []
            for contract in contracts:
                snapshot = snapshots.get(contract.symbol)
                greeks = snapshot.greeks if snapshot else None
                if not greeks:
                    continue
                rows.append(
                    {
                        "symbol": contract.symbol,
                        "option_type": getattr(contract.type, "value", contract.type),
                        "strike": float(contract.strike_price),
                        "open_interest": (
                            float(contract.open_interest)
                            if contract.open_interest is not None
                            else None
                        ),
                        "gamma": greeks.gamma,
                        "delta": greeks.delta,
                        "vega": greeks.vega,
                        # Alpaca's chain snapshot has no aggregate contract volume.
                        "volume": None,
                    }
                )
            return assess_microstructure(
                symbol,
                spot,
                rows,
                source="Alpaca option chain Greeks + contract open interest",
            )
        except Exception as error:
            return unavailable_microstructure(
                symbol,
                "Alpaca Options API",
                f"Options microstructure request failed: {error}",
            )


def build_options_provider(settings: Settings) -> OptionsMicrostructureProvider:
    if settings.market_data_mode.lower() == "alpaca":
        return AlpacaOptionsProvider(settings)
    return UnavailableOptionsProvider()
