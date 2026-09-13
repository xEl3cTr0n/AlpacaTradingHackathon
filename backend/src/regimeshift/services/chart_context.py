"""Ticker-keyed read-only overlays. No council, risk approval, or order adapter."""

import hashlib
from collections import OrderedDict
from concurrent.futures import Future
from datetime import UTC, datetime, timedelta
from threading import Lock
from time import monotonic

from regimeshift.config import Settings
from regimeshift.domain.models import ChartContextSnapshot
from regimeshift.domain.scanner_diagnostics import NEW_YORK, aware
from regimeshift.domain.swing import SwingEngine
from regimeshift.services.market_data import build_market_data_provider
from regimeshift.services.options_data import build_options_provider

_cache: OrderedDict[tuple[str, str, str], tuple[float, ChartContextSnapshot]] = OrderedDict()
_inflight: dict[tuple[str, str, str], Future[ChartContextSnapshot]] = {}
_lock = Lock()
CACHE_SECONDS = 60
MAX_CACHE_KEYS = 64


def build_chart_context(settings: Settings, symbol: str) -> ChartContextSnapshot:
    now = datetime.now(UTC)
    market = build_market_data_provider(settings)
    notes = [
        "Read-only overlays; changing ticker does not run the council or place orders.",
        "GEX is a signed calls-minus-puts positioning proxy, not observed dealer inventory.",
        "Options Greek/OI timestamps are not verified; retrieved-at is not quote freshness.",
        "Alpaca GEX sample: up to 45 DTE, strikes within ±15% of spot; "
        "hedge wall is not zero gamma.",
    ]
    swing = micro = spot = spot_as_of = swing_as_of = None
    try:
        bars = market.get_chart_history(symbol, "1Day", 60)
        completed = sorted(
            (
                bar
                for bar in bars
                if aware(bar.timestamp).astimezone(NEW_YORK).date()
                < now.astimezone(NEW_YORK).date()
            ),
            key=lambda bar: bar.timestamp,
        )
        if not completed or now - aware(completed[-1].timestamp) > timedelta(days=4):
            raise ValueError("Daily history is stale or missing")
        swing = SwingEngine().assess(completed)
        swing_as_of = completed[-1].timestamp
    except Exception:
        notes.append("Swing levels unavailable: daily history is missing, stale, or insufficient.")
    try:
        tick = market.get_live_tick(symbol)
        if tick.symbol.upper() != symbol:
            raise ValueError("Spot ticker mismatch")
        age = now - aware(tick.as_of)
        if age > timedelta(days=4) or age < -timedelta(seconds=60):
            raise ValueError("Spot timestamp is invalid or stale")
        spot, spot_as_of = tick.price, tick.as_of
        micro = build_options_provider(settings).get_assessment(symbol, spot)
        if micro.underlying_symbol.upper() != symbol or micro.status == "unavailable":
            micro = None
            notes.append(
                "GEX unavailable: matching option Greeks and open interest are insufficient."
            )
    except Exception:
        micro = None
        notes.append(
            "GEX unavailable: spot or option data request failed. No prior ticker is substituted."
        )
    status = (
        "available"
        if swing is not None and micro is not None
        else "partial"
        if swing is not None or micro is not None
        else "unavailable"
    )
    return ChartContextSnapshot(
        symbol=symbol,
        generated_at=now,
        status=status,
        underlying_price=spot,
        spot_as_of=spot_as_of,
        swing=swing,
        swing_as_of=swing_as_of,
        options_microstructure=micro,
        notes=notes,
    )


def get_chart_context(settings: Settings, symbol: str) -> ChartContextSnapshot:
    symbol = symbol.upper()
    # Credentials never enter a response or a disk cache. Scope by entitlement
    # so a demo/other-account response cannot be reused for this viewer.
    identity = hashlib.sha256(
        f"{settings.alpaca_api_key}:{settings.alpaca_secret_key.get_secret_value()}".encode()
    ).hexdigest()
    key = (settings.market_data_mode.lower(), identity, symbol)
    with _lock:
        cached = _cache.get(key)
        if cached and monotonic() - cached[0] < CACHE_SECONDS:
            _cache.move_to_end(key)
            return cached[1].model_copy(deep=True)
        future = _inflight.get(key)
        owner = future is None
        if owner:
            if len(_inflight) >= 16:
                raise TimeoutError("Chart context capacity reached")
            future = Future()
            _inflight[key] = future
    if not owner:
        return future.result(timeout=30).model_copy(deep=True)
    try:
        result = build_chart_context(settings, symbol)
        with _lock:
            _cache[key] = (monotonic(), result)
            _cache.move_to_end(key)
            while len(_cache) > MAX_CACHE_KEYS:
                _cache.popitem(last=False)
        future.set_result(result)
        return result.model_copy(deep=True)
    except Exception as error:
        future.set_exception(error)
        raise
    finally:
        with _lock:
            _inflight.pop(key, None)
