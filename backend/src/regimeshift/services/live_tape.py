from threading import Lock
from time import monotonic

from regimeshift.config import Settings
from regimeshift.domain.models import LiveMarketTick
from regimeshift.services.market_data import build_market_data_provider

_cache: dict[str, tuple[float, LiveMarketTick]] = {}
_lock = Lock()
MINIMUM_UPSTREAM_INTERVAL_SECONDS = 0.8


def get_live_tick(settings: Settings, symbol: str) -> LiveMarketTick:
    """Deduplicate rapid viewers before requesting another Alpaca snapshot."""
    symbol = symbol.upper()
    now = monotonic()
    cached = _cache.get(symbol)
    if cached and now - cached[0] < MINIMUM_UPSTREAM_INTERVAL_SECONDS:
        return cached[1]
    with _lock:
        cached = _cache.get(symbol)
        if cached and now - cached[0] < MINIMUM_UPSTREAM_INTERVAL_SECONDS:
            return cached[1]
        tick = build_market_data_provider(settings).get_live_tick(symbol)
        _cache[symbol] = (monotonic(), tick)
        return tick
