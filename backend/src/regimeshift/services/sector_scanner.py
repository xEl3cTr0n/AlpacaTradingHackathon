"""Account-scoped, bounded, read-only sector scan cache."""

import hashlib
from concurrent.futures import Future
from datetime import UTC, datetime
from threading import Lock
from time import monotonic

from regimeshift.config import Settings
from regimeshift.domain.sector_rotation import SECTOR_UNIVERSE
from regimeshift.domain.sector_scanner import (
    SECTOR_SAMPLES,
    SectorScanSnapshot,
    build_sector_scan,
    recompute_sector_snapshot_status,
)
from regimeshift.services.market_data import build_market_data_provider

_cache: dict[str, tuple[float, SectorScanSnapshot]] = {}
_inflight: dict[str, Future] = {}
_lock = Lock()
CACHE_SECONDS = 60


def get_sector_scan(settings: Settings) -> SectorScanSnapshot:
    key = hashlib.sha256(
        f"{settings.market_data_mode}:{settings.alpaca_api_key}:{settings.alpaca_secret_key.get_secret_value()}".encode()
    ).hexdigest()
    with _lock:
        cached = _cache.get(key)
        if cached and monotonic() - cached[0] < CACHE_SECONDS:
            return recompute_sector_snapshot_status(
                cached[1].model_copy(deep=True), datetime.now(UTC)
            )
        future = _inflight.get(key)
        owner = future is None
        if owner:
            if len(_inflight) >= 4:
                raise TimeoutError("Sector scanner busy")
            future = Future()
            _inflight[key] = future
    if not owner:
        return recompute_sector_snapshot_status(
            future.result(timeout=45).model_copy(deep=True), datetime.now(UTC)
        )
    try:
        provider = build_market_data_provider(settings)
        symbols = sorted(
            {"SPY", *SECTOR_UNIVERSE, *(s for group in SECTOR_SAMPLES.values() for s in group)}
        )
        histories = provider.get_intraday_history(symbols, days=7, bar_minutes=15)
        daily_failed = False
        try:
            daily = provider.get_price_history(list(SECTOR_UNIVERSE), days=90)
        except Exception:
            daily, daily_failed = {}, True
        result = build_sector_scan(
            histories,
            daily,
            datetime.now(UTC),
            "Alpaca IEX · single-exchange sample"
            if settings.market_data_mode.lower() == "alpaca"
            else "Deterministic demo · synthetic sector data",
        )
        if daily_failed:
            result.notes.append("Daily history request failed; swing return columns unavailable.")
        with _lock:
            if len(_cache) >= 4:
                _cache.pop(next(iter(_cache)))
            _cache[key] = (monotonic(), result)
        future.set_result(result)
        return result.model_copy(deep=True)
    except Exception as error:
        future.set_exception(error)
        raise
    finally:
        with _lock:
            _inflight.pop(key, None)
