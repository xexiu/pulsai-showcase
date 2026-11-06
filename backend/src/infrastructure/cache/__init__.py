# Cache Infrastructure - Redis client and caching utilities
#
# Sprint 1.5: ML pipeline caching for < 50ms inference latency
# Target: < 2ms cache lookup via Redis + hiredis

from src.infrastructure.cache.keys import CacheKeys
from src.infrastructure.cache.ohlcv_cache import OHLCVCache
from src.infrastructure.cache.redis_client import RedisClient, get_redis_client

# Module-level cache instance (lazy initialization)
_ohlcv_cache: OHLCVCache | None = None


async def get_ohlcv_cache() -> OHLCVCache:
    """
    Get the global OHLCV cache instance.

    Creates a new instance on first call (lazy initialization).
    Reuses existing instance on subsequent calls.

    Returns:
        OHLCVCache instance connected to Redis
    """
    global _ohlcv_cache

    if _ohlcv_cache is None:
        redis_client = await get_redis_client()
        _ohlcv_cache = OHLCVCache(redis_client)

    return _ohlcv_cache


__all__ = [
    "CacheKeys",
    "OHLCVCache",
    "RedisClient",
    "get_ohlcv_cache",
    "get_redis_client",
]
