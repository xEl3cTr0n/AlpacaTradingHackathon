from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    app_name: str = "RegimeShift AI"
    environment: str = "development"
    market_data_mode: str = "alpaca"
    alpaca_api_key: str = ""
    alpaca_secret_key: SecretStr = SecretStr("")
    alpaca_paper: bool = True
    enable_paper_orders: bool = False
    enable_exploration_orders: bool = False
    enable_manual_paper_orders: bool = False
    manual_trade_token: SecretStr = SecretStr("")
    alpaca_mcp_enabled: bool = False
    alpaca_cli_enabled: bool = False
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-5-mini"
    enable_gpt_mcp_research: bool = False
    default_symbol: str = "SPY"
    account_equity: float = 100_000.0
    max_risk_per_trade_pct: float = 0.01
    max_position_loss_dollars: float = Field(default=1_000.0, gt=0, le=10_000)
    defensive_risk_cap_dollars: float = Field(default=500.0, gt=0, le=10_000)
    stop_loss_fraction: float = Field(default=0.50, gt=0, le=1)
    max_daily_loss_pct: float = Field(default=0.02, gt=0, le=0.05)
    max_open_spreads: int = Field(default=3, ge=1, le=10)

    model_config = SettingsConfigDict(
        env_file=(ROOT_ENV, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def alpaca_configured(self) -> bool:
        return bool(self.alpaca_api_key and self.alpaca_secret_key.get_secret_value())

    @property
    def manual_trading_configured(self) -> bool:
        return bool(
            self.enable_manual_paper_orders
            and self.manual_trade_token.get_secret_value()
            and self.alpaca_configured
            and self.alpaca_paper
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
