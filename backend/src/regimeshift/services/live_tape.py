import hashlib
from collections import OrderedDict
from concurrent.futures import Future
from threading import Lock
from time import monotonic

from regimeshift.config import Settings
from regimeshift.domain.models import LiveMarketTick
from regimeshift.services.market_data import build_market_data_provider

_cache: OrderedDict[tuple[str, str, str], tuple[float, LiveMarketTick]] = OrderedDict()
_inflight: dict[tuple[str, str, str], Future[LiveMarketTick]] = {}
_lock = Lock()
MINIMUM_UPSTREAM_INTERVAL_SECONDS = 0.8
MAX_CACHE_KEYS = 128


def _cache_key(settings: Settings, symbol: str) -> tuple[str, str, str]:
    identity = hashlib.sha256(
        f"{settings.alpaca_api_key}:{settings.alpaca_secret_key.get_secret_value()}".encode()
    ).hexdigest()
    return (settings.market_data_mode.lower(), identity, symbol.upper())


def get_live_tick(settings: Settings, symbol: str) -> LiveMarketTick:
    """Deduplicate rapid viewers before requesting another Alpaca snapshot."""
    key = _cache_key(settings, symbol)
    now = monotonic()
    with _lock:
        cached = _cache.get(key)
        if cached and now - cached[0] < MINIMUM_UPSTREAM_INTERVAL_SECONDS:
            _cache.move_to_end(key)
            return cached[1].model_copy(deep=True)
        future = _inflight.get(key)
        owner = future is None
        if owner:
            if len(_inflight) >= 32:
                raise TimeoutError("Live tape capacity reached")
            future = Future()
            _inflight[key] = future
    if not owner:
        return future.result(timeout=15).model_copy(deep=True)
    try:
        tick = build_market_data_provider(settings).get_live_tick(key[2])
        with _lock:
            _cache[key] = (monotonic(), tick)
            _cache.move_to_end(key)
            while len(_cache) > MAX_CACHE_KEYS:
                _cache.popitem(last=False)
        future.set_result(tick)
        return tick.model_copy(deep=True)
    except Exception as error:
        future.set_exception(error)
        raise
    finally:
        with _lock:
            _inflight.pop(key, None)
