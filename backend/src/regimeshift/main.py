from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from regimeshift.config import Settings, get_settings
from regimeshift.domain.models import (
    AnalysisControls,
    AnalyzeRequest,
    DecisionSnapshot,
    ManualTradePreview,
    ManualTradeRequest,
    ManualTradeResult,
    PlatformSnapshot,
    ScannerSnapshot,
)
from regimeshift.domain.scanner import LARGE_CAP_UNIVERSE, LargeCapScanner
from regimeshift.orchestration.pipeline import DecisionPipeline
from regimeshift.services.manual_trading import ManualPaperTrader
from regimeshift.services.market_data import build_market_data_provider
from regimeshift.services.platform import build_platform_provider

app = FastAPI(
    title="RegimeShift AI API",
    version="0.1.0",
    description="Explainable regime-adaptive paper-trading decisions.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Operator-Token"],
)


SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_pipeline(settings: SettingsDependency) -> DecisionPipeline:
    try:
        return DecisionPipeline(settings, build_market_data_provider(settings))
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


PipelineDependency = Annotated[DecisionPipeline, Depends(get_pipeline)]


@app.get("/health")
def health(settings: SettingsDependency) -> dict[str, str | bool]:
    return {
        "status": "ok",
        "mode": settings.market_data_mode,
        "alpaca_configured": settings.alpaca_configured,
        "paper_orders_enabled": settings.enable_paper_orders,
        "manual_paper_orders_enabled": settings.manual_trading_configured,
    }


def _analyze(
    pipeline: DecisionPipeline, symbol: str, controls: AnalysisControls | None = None
) -> DecisionSnapshot:
    try:
        return pipeline.analyze(symbol.upper(), controls)
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502, detail=f"Market data request failed: {error}"
        ) from error


@app.get("/api/v1/snapshot", response_model=DecisionSnapshot)
def snapshot(pipeline: PipelineDependency, symbol: str = "SPY") -> DecisionSnapshot:
    return _analyze(pipeline, symbol)


@app.post("/api/v1/analyze", response_model=DecisionSnapshot)
def analyze(request: AnalyzeRequest, pipeline: PipelineDependency) -> DecisionSnapshot:
    return _analyze(
        pipeline,
        request.symbol,
        AnalysisControls(**request.model_dump(exclude={"symbol"})),
    )


@app.get("/api/v1/platform", response_model=PlatformSnapshot)
def platform(settings: SettingsDependency) -> PlatformSnapshot:
    try:
        return build_platform_provider(settings).get_snapshot()
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502, detail=f"Paper account request failed: {error}"
        ) from error


@app.post("/api/v1/manual-trades/preview", response_model=ManualTradePreview)
def preview_manual_trade(
    request: ManualTradeRequest, settings: SettingsDependency
) -> ManualTradePreview:
    try:
        return ManualPaperTrader(settings).preview(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502, detail=f"Option quote request failed: {error}"
        ) from error


@app.post("/api/v1/manual-trades/execute", response_model=ManualTradeResult)
def execute_manual_trade(
    request: ManualTradeRequest,
    settings: SettingsDependency,
    operator_token: Annotated[str, Header(alias="X-Operator-Token")],
) -> ManualTradeResult:
    try:
        return ManualPaperTrader(settings).submit(request, operator_token)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Paper order failed: {error}") from error


@app.get("/api/v1/scanner", response_model=ScannerSnapshot)
def scanner(
    settings: SettingsDependency,
    limit: int = Query(default=12, ge=1, le=len(LARGE_CAP_UNIVERSE)),
) -> ScannerSnapshot:
    """Rank the liquid large-cap universe without placing an order."""
    try:
        provider = build_market_data_provider(settings)
        symbols = ["SPY", *LARGE_CAP_UNIVERSE]
        histories = provider.get_intraday_history(symbols, days=10, bar_minutes=15)
        liquidity_histories = provider.get_price_history(symbols, days=120)
        source = (
            "Alpaca IEX fully adjusted 15-minute bars"
            if settings.market_data_mode.lower() == "alpaca"
            else "deterministic 15-minute demo tape"
        )
        return LargeCapScanner().scan(
            histories,
            limit=limit,
            source=source,
            timeframe="15Min",
            liquidity_histories=liquidity_histories,
            annualization_periods=252 * 26,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502, detail=f"Scanner market-data request failed: {error}"
        ) from error
