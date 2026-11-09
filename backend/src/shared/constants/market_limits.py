"""SoT for the market-limits warmer (Phase 2).

Why this module exists
----------------------
The market-limits Redis cache (``infrastructure/cache/market_limits_cache.py``)
absorbs the steady-state cost of ``ccxt.load_markets()``, but the cold path
that the bench (``scripts/bench_market_limits_cache.py``) measured at p95
≈ 1.7s still runs once per cache miss. To stay within the
``.cursorrules`` ``trade execution < 100ms`` baseline, a Celery beat warmer
must keep a small set of high-volume pairs always-warm.

This file is the Single Source of Truth for:

- which (exchange, market_type, symbol) triples to warm proactively
  (``WARMABLE_MARKET_LIMITS_PAIRS``);
- how far before TTL expiry to trigger a refresh
  (``MARKET_LIMITS_REFRESH_BUFFER``);
- how often the Celery beat scheduler should call the warmer
  (``MARKET_LIMITS_WARMER_BEAT_INTERVAL``).

Tests in ``tests/unit/shared/constants/test_market_limits.py`` enforce the
invariants (beat < buffer < TTL, supported exchanges, uniqueness) so config
drift is caught at unit-test time, not in production.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Final, NamedTuple

from src.shared.constants.exchanges import MARKET_TYPE_SWAP

if TYPE_CHECKING:
    from src.shared.constants.exchanges import MarketType

__all__ = [
    "MARKET_LIMITS_REFRESH_BUFFER",
    "MARKET_LIMITS_WARMER_BEAT_INTERVAL",
    "WARMABLE_MARKET_LIMITS_PAIRS",
    "WarmableMarketLimitsPair",
]


class WarmableMarketLimitsPair(NamedTuple):
    """Triple identifying one cache entry the warmer maintains.

    NamedTuple (not dict) so the SoT is statically typed, immutable, and cheap
    to compare/hash for the in-memory ``last_refresh`` map in the warmer
    service.
    """

    exchange_id: str
    market_type: MarketType
    symbol: str


# Initial warmable set. Justification per pair:
#
# - bitget swap BTC/USDT:USDT — highest-volume USDT-M perp on the most-used
#   exchange in PulsAI. The ``scripts/bench_market_limits_cache.py`` cold-path
#   p95 ≈ 1.7s was measured against this exact pair.
# - bitget swap ETH/USDT:USDT — second-highest USDT-M perp on the same
#   exchange. Bench load on a fresh exchange is amortized across all swap
#   symbols (``load_markets`` returns the full set), so warming ETH alongside
#   BTC adds zero additional CCXT round-trips.
#
# Keep this set small: every entry triggers (#exchanges) ``load_markets`` calls
# per refresh window, and venues throttle aggressively. Extend deliberately,
# only after confirming SLO breach for additional symbols in production.
WARMABLE_MARKET_LIMITS_PAIRS: Final[tuple[WarmableMarketLimitsPair, ...]] = (
    WarmableMarketLimitsPair(exchange_id="bitget", market_type=MARKET_TYPE_SWAP, symbol="BTC/USDT:USDT"),
    WarmableMarketLimitsPair(exchange_id="bitget", market_type=MARKET_TYPE_SWAP, symbol="ETH/USDT:USDT"),
)


# Refresh ``refresh_buffer`` ahead of the cache TTL (currently 1h via
# ``CacheKeys.TTL_MARKET_LIMITS``). 10 min gives the beat scheduler — which
# itself ticks every 5 min — at least one chance to act before the cache
# becomes stale, i.e. before any user request would hit the cold path.
MARKET_LIMITS_REFRESH_BUFFER: Final[timedelta] = timedelta(minutes=10)

# Beat tick frequency. Must be strictly less than ``MARKET_LIMITS_REFRESH_BUFFER``
# (sampling-theorem invariant enforced by unit test).
MARKET_LIMITS_WARMER_BEAT_INTERVAL: Final[timedelta] = timedelta(minutes=5)
