"""
Lightweight in-memory TTL cache for weather API responses.

Prevents hammering OpenWeatherMap (1 000 calls/day free tier) during demo
conditions where multiple judges may hit /api/predict/risk in rapid succession.

Usage:
    from services.cache import weather_cache

    data = weather_cache.get(key)
    if data is None:
        data = await fetch_from_api(...)
        weather_cache.set(key, data)
"""

import time
import threading
from typing import Any, Optional


class TTLCache:
    """Thread-safe dictionary cache with per-entry TTL expiry."""

    def __init__(self, default_ttl: int = 300):
        """
        Args:
            default_ttl: Seconds before a cached entry expires (default 5 min).
        """
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Return cached value or None if missing / expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store *value* under *key* with an optional custom TTL (seconds)."""
        ttl = ttl if ttl is not None else self.default_ttl
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl)

    def delete(self, key: str) -> None:
        """Manually invalidate a cache entry."""
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Wipe the entire cache (useful in tests)."""
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        """Return the current number of live (non-expired) entries."""
        now = time.monotonic()
        with self._lock:
            return sum(1 for _, exp in self._store.values() if now <= exp)


# ── Shared singletons ────────────────────────────────────────────────────────
# 5-minute TTL for current weather (fast-moving data doesn't need longer)
weather_cache = TTLCache(default_ttl=300)

# 15-minute TTL for forecasts (changes more slowly)
forecast_cache = TTLCache(default_ttl=900)

# 10-minute TTL for Tomorrow.io hyperlocal data
tomorrow_cache = TTLCache(default_ttl=600)
