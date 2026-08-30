from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from regimeshift.config import Settings, get_settings
from regimeshift.domain.models import AnalyzeRequest, DecisionSnapshot
from regimeshift.orchestration.pipeline import DecisionPipeline
from regimeshift.services.market_data import build_market_data_provider

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
    allow_headers=["Content-Type"],
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
    }


@app.get("/api/v1/snapshot", response_model=DecisionSnapshot)
def snapshot(pipeline: PipelineDependency, symbol: str = "SPY") -> DecisionSnapshot:
    try:
        return pipeline.analyze(symbol.upper())
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502, detail=f"Market data request failed: {error}"
        ) from error


@app.post("/api/v1/analyze", response_model=DecisionSnapshot)
def analyze(request: AnalyzeRequest, pipeline: PipelineDependency) -> DecisionSnapshot:
    return snapshot(pipeline, request.symbol)
