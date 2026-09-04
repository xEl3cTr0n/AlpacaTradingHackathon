from datetime import UTC, date, datetime, timedelta
from typing import Protocol

from regimeshift.config import Settings
from regimeshift.domain.microstructure import assess_microstructure, unavailable_microstructure
from regimeshift.domain.models import (
    OptionChainContract,
    OptionChainSnapshot,
    OptionsMicrostructureAssessment,
)
from regimeshift.domain.options_chain import select_contracts_by_moneyness


class OptionsMicrostructureProvider(Protocol):
    def get_assessment(self, symbol: str, spot: float) -> OptionsMicrostructureAssessment: ...

    def get_chain(
        self,
        symbol: str,
        spot: float,
        option_type: str,
        moneyness: str,
        expiration: date | None = None,
        limit: int = 10,
    ) -> OptionChainSnapshot: ...


class UnavailableOptionsProvider:
    def __init__(self, reason: str = "Options microstructure requires Alpaca data mode"):
        self.reason = reason

    def get_assessment(self, symbol: str, spot: float) -> OptionsMicrostructureAssessment:
        del spot
        return unavailable_microstructure(symbol, "not configured", self.reason)

    def get_chain(
        self,
        symbol: str,
        spot: float,
        option_type: str,
        moneyness: str,
        expiration: date | None = None,
        limit: int = 10,
    ) -> OptionChainSnapshot:
        del symbol, spot, option_type, moneyness, expiration, limit
        raise ValueError(self.reason)


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
                        "gamma": greeks.gamma if greeks else None,
                        "delta": greeks.delta if greeks else None,
                        "vega": greeks.vega if greeks else None,
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

    def get_chain(
        self,
        symbol: str,
        spot: float,
        option_type: str,
        moneyness: str,
        expiration: date | None = None,
        limit: int = 10,
    ) -> OptionChainSnapshot:
        from alpaca.data.requests import OptionChainRequest
        from alpaca.trading.enums import ContractType
        from alpaca.trading.requests import GetOptionContractsRequest

        symbol = symbol.upper()
        today = datetime.now(UTC).date()
        start = today + timedelta(days=7)
        end = today + timedelta(days=60)
        contract_type = ContractType.CALL if option_type == "call" else ContractType.PUT
        contracts = []
        token = None
        while True:
            response = self.trading_client.get_option_contracts(
                GetOptionContractsRequest(
                    underlying_symbols=[symbol],
                    type=contract_type,
                    expiration_date_gte=start,
                    expiration_date_lte=end,
                    strike_price_gte=f"{spot * 0.70:.2f}",
                    strike_price_lte=f"{spot * 1.30:.2f}",
                    limit=1000,
                    page_token=token,
                )
            )
            contracts.extend(response.option_contracts or [])
            token = response.next_page_token
            if not token or len(contracts) >= 5000:
                break
        if not contracts:
            raise ValueError(f"Alpaca returned no 7–60 DTE {symbol} {option_type} contracts")

        expirations = sorted({contract.expiration_date for contract in contracts})
        selected_expiration = expiration or min(
            expirations, key=lambda value: abs((value - today).days - 30)
        )
        if selected_expiration not in expirations:
            raise ValueError("Selected expiration is unavailable in the 7–60 DTE chain")

        chosen_contracts = [
            contract for contract in contracts if contract.expiration_date == selected_expiration
        ]
        snapshots = self.option_client.get_option_chain(
            OptionChainRequest(
                underlying_symbol=symbol,
                type=contract_type,
                expiration_date=selected_expiration,
                strike_price_gte=spot * 0.70,
                strike_price_lte=spot * 1.30,
            )
        )
        rows: list[dict[str, object]] = []
        for contract in chosen_contracts:
            snapshot = snapshots.get(contract.symbol)
            quote = snapshot.latest_quote if snapshot else None
            greeks = snapshot.greeks if snapshot else None
            bid = float(quote.bid_price) if quote and quote.bid_price is not None else None
            ask = float(quote.ask_price) if quote and quote.ask_price is not None else None
            midpoint = (bid + ask) / 2 if bid is not None and ask is not None else None
            spread_percent = (
                (ask - bid) / midpoint
                if midpoint and ask is not None and bid is not None and ask >= bid
                else None
            )
            rows.append(
                {
                    "symbol": contract.symbol,
                    "option_type": option_type,
                    "expiration": contract.expiration_date,
                    "strike": float(contract.strike_price),
                    "moneyness": moneyness,
                    "bid": bid,
                    "ask": ask,
                    "midpoint": midpoint,
                    "spread_percent": spread_percent,
                    "open_interest": (
                        int(contract.open_interest)
                        if contract.open_interest is not None
                        else None
                    ),
                    "implied_volatility": (
                        float(snapshot.implied_volatility)
                        if snapshot and snapshot.implied_volatility is not None
                        else None
                    ),
                    "delta": float(greeks.delta) if greeks and greeks.delta is not None else None,
                    "gamma": float(greeks.gamma) if greeks and greeks.gamma is not None else None,
                }
            )
        selected = select_contracts_by_moneyness(
            rows,
            spot=spot,
            option_type=option_type,
            moneyness=moneyness,
            limit=limit,
        )
        return OptionChainSnapshot(
            underlying_symbol=symbol,
            underlying_price=round(spot, 4),
            option_type=option_type,
            moneyness=moneyness,
            expiration=selected_expiration,
            expirations=expirations,
            contracts=[OptionChainContract(**item) for item in selected],
            as_of=datetime.now(UTC),
            source="Alpaca Options API live quotes + contract open interest",
        )


def build_options_provider(settings: Settings) -> OptionsMicrostructureProvider:
    if settings.market_data_mode.lower() == "alpaca":
        return AlpacaOptionsProvider(settings)
    return UnavailableOptionsProvider()
