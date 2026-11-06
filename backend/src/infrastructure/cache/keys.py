"""
Cache key and TTL policy helpers.

WHY this module exists:
- Cache namespaces must stay stable across readers, writers, and
  invalidation flows
- TTL rules must not drift between cache wrappers for the same domain
  object
"""

from datetime import timedelta
from typing import Final

from src.infrastructure.cache.keys_sentiment import SentimentCacheKeys
from src.shared.constants.chart_indicators_cache import CHART_INDICATORS_PAYLOAD_KEY_PREFIX
from src.shared.constants.derivatives_flow_cache import DERIVATIVES_FLOW_CACHE_KEY_PREFIX
from src.shared.constants.liquidation_heatmap_cache import LIQUIDATION_HEATMAP_CACHE_KEY_PREFIX
from src.shared.constants.taker_flow_cache import TAKER_FLOW_CACHE_KEY_PREFIX
from src.shared.utils.symbols import symbol_to_exchange_namespaced_segment, symbol_to_safe_key


class CacheKeys(SentimentCacheKeys):
    """
    Centralized cache key patterns.

    All keys follow the pattern: {prefix}:{type}:{identifier}
    This prevents key collisions and enables easy key scanning/deletion.
    """

    # Key prefixes by domain
    PREFIX_OHLCV: Final[str] = "ohlcv"
    PREFIX_OHLCV_LOCK: Final[str] = "ohlcv_lock"
    PREFIX_OHLCV_HISTORY_FLOOR: Final[str] = "ohlcv_history_floor"
    PREFIX_MODEL: Final[str] = "model"
    PREFIX_FEATURES: Final[str] = "features"
    PREFIX_SIGNAL: Final[str] = "signal"
    PREFIX_RATE_LIMIT: Final[str] = "ratelimit"
    PREFIX_SESSION: Final[str] = "session"
    PREFIX_MARKET_LIMITS: Final[str] = "market_limits"
    # Funding-carry monitor/backtest/paper read models (PulsAI Carry). Each call
    # fans out to external perp venues; caching the fetched series/paths makes
    # repeat admin loads instant and absorbs the cold fan-out cost once.
    PREFIX_FUNDING: Final[str] = "funding"
    # Paper-trading lifecycle Redis locks (SETNX with TTL safety net).
    # WHY namespaced together: both order + position sweeps belong to the same
    # worker-facing domain; sharing the prefix makes SCAN / ops cleanup trivial.
    PREFIX_PAPER_LIFECYCLE: Final[str] = "paper:lifecycle"
    # Polling-task short-circuit flag: SET when a subsystem has work, EXISTS
    # checked by the poller before fetching prices / opening DB sessions.
    # WHY a flat namespace: keep ops `SCAN` cheap; subsystems are small/fixed.
    PREFIX_TRADING_ACTIVITY: Final[str] = "trading_activity"
    PREFIX_OBSERVABILITY: Final[str] = "obs"

    # TTL values in seconds
    # Registry-backed cache policy:
    # - sub-5m data refreshes 10s early
    # - intraday >=5m refreshes 1m early
    # - hourly+ refreshes 5m early
    # - daily/weekly refreshes 1h early
    TTL_REFRESH_BUFFER_SUB_5M: Final[int] = 10
    TTL_REFRESH_BUFFER_INTRADAY: Final[int] = 60
    TTL_REFRESH_BUFFER_HOURLY_PLUS: Final[int] = 5 * 60
    TTL_REFRESH_BUFFER_DAILY_PLUS: Final[int] = 60 * 60
    TTL_OHLCV_DEFAULT: Final[int] = 55 * 60
    # 1h default for unknown/custom timeframes
    TTL_FEATURES_DEFAULT: Final[int] = 60
    # Fallback for unknown/custom timeframes
    TTL_MODEL_METADATA: Final[int] = 300  # 5 minutes
    TTL_SIGNAL: Final[int] = 30  # 30 seconds (fresh signals)
    TTL_RATE_LIMIT: Final[int] = 60  # 1 minute window
    TTL_EMAIL_RATE_LIMIT: Final[int] = (24 * 60 * 60) + (60 * 60)  # 25h buffer
    # Market limits (CCXT load_markets metadata): venue rules drift slowly; 1h TTL
    # cuts redundant load_markets() round-trips on every preflight while still
    # picking up tier/listing changes in bounded time.
    TTL_MARKET_LIMITS: Final[int] = 60 * 60
    # Funding-carry fetched data (realized funding series, adverse-move samples,
    # aligned carry paths). Funding settles every 1-8h, so a 15m TTL keeps the
    # monitor fresh while making repeat loads instant and bounding upstream load.
    TTL_FUNDING: Final[int] = 15 * 60
    # Trading-activity poller gate: a subsystem's flag MUST outlive realistic
    # gaps between user actions (so brackets don't go un-polled mid-trade) and
    # be re-asserted by the periodic poller's DB-fallback path when drift
    # occurs. 24h is the longest the flag can be stale before a daily
    # reconciliation pass would refresh it.
    TTL_TRADING_ACTIVITY_FLAG: Final[int] = 24 * 60 * 60

    # Redis distributed locks for cache mutations.
    OHLCV_CACHE_LOCK_TIMEOUT_SECONDS: Final[int] = 10
    OHLCV_CACHE_LOCK_BLOCKING_TIMEOUT_SECONDS: Final[int] = 2

    @classmethod
    def live_signal_obs_queue_wait(cls) -> str:
        """Rolling queue-wait samples for admin live-signal compact health (worker append)."""
        return f"{cls.PREFIX_OBSERVABILITY}:live_signal:queue_wait"

    @classmethod
    def live_signal_obs_persist_commit(cls) -> str:
        """Rolling persist+commit duration samples (worker append)."""
        return f"{cls.PREFIX_OBSERVABILITY}:live_signal:persist_commit"

    @classmethod
    def live_signal_obs_persist_errors(cls) -> str:
        """Persist/commit error events (worker append)."""
        return f"{cls.PREFIX_OBSERVABILITY}:live_signal:persist_errors"

    @classmethod
    def live_signal_obs_ohlcv_tier(cls) -> str:
        """OHLCV tier choice events for live-signal reads (worker append)."""
        return f"{cls.PREFIX_OBSERVABILITY}:live_signal:ohlcv_tier"

    @classmethod
    def trading_activity_flag(cls, *, system: str) -> str:
        """Polling-task short-circuit flag key for a named subsystem.

        Pollers EXISTS-check this before doing expensive HTTP + DB work; the
        flag is SET when a user creates work in that subsystem (or
        re-asserted by the poller's DB-fallback when Redis drift is
        detected).
        """
        cls._require_non_empty(system=system)
        return f"{cls.PREFIX_TRADING_ACTIVITY}:active:{system}"

    @staticmethod
    def _require_non_empty(**fields: str) -> None:
        """Raise ``ValueError`` when any keyword is empty or whitespace-only.

        Centralized because every paper-lifecycle lock builder must reject
        empty inputs identically: silently building a key like
        ``paper:lifecycle:sync::order-xyz`` would cause two different users'
        workers to share a lock and swallow each other's reconciliation.
        """
        for name, value in fields.items():
            if not value or not value.strip():
                raise ValueError(f"{name} must not be empty")

    @classmethod
    def paper_lifecycle_order_lock(cls, *, user_id: str, ccxt_order_id: str) -> str:
        """Redis lock key for the per-order paper-trading lifecycle sweep.

        Pairs 1:1 with a single ``(user_id, ccxt_order_id)`` so two Celery
        workers cannot race each other on the same order.

        Returns:
            Key shaped like ``paper:lifecycle:sync:{user_id}:{ccxt_order_id}``.
        """
        cls._require_non_empty(user_id=user_id, ccxt_order_id=ccxt_order_id)
        return f"{cls.PREFIX_PAPER_LIFECYCLE}:sync:{user_id}:{ccxt_order_id}"

    @classmethod
    def paper_lifecycle_position_lock(
        cls,
        *,
        user_id: str,
        connection_id: str,
        symbol: str,
    ) -> str:
        """Redis lock key for the per-(user, connection, symbol) position sweep.

        Disjoint from :meth:`paper_lifecycle_order_lock` so a slow per-order
        tick cannot block position reconciliation on the same symbol. Symbol
        is kept as the unified CCXT form (``BTC/USDT``) — callers that need
        Redis-safe collapsing should normalize upstream.
        """
        cls._require_non_empty(user_id=user_id, connection_id=connection_id, symbol=symbol)
        return f"{cls.PREFIX_PAPER_LIFECYCLE}:positions_sync:{user_id}:{connection_id}:{symbol}"

    @classmethod
    def market_limits(cls, exchange_id: str, symbol: str) -> str:
        """Generate market-limits cache key for a venue/symbol pair.

        Args:
            exchange_id: CCXT exchange id (e.g. "bitget"); lowercased.
            symbol: Unified CCXT symbol (e.g. "BTC/USDT", "BTC/USDT:USDT").

        Returns:
            Cache key like ``market_limits:bitget:btc_usdt:usdt``.
        """
        safe_symbol = symbol_to_safe_key(symbol)
        return f"{cls.PREFIX_MARKET_LIMITS}:{exchange_id.strip().lower()}:{safe_symbol}"

    @classmethod
    def _funding(cls, kind: str, venue: str, base: str, days: int) -> str:
        """Build a funding-carry cache key ``funding:{kind}:{venue}:{base}:{days}``.

        Shared by the three funding read-model key builders so the namespace
        layout lives in one place. ``venue`` is lowercased and ``base`` uppercased
        to match how the endpoints normalize their inputs (stable across callers).
        """
        cls._require_non_empty(venue=venue, base=base, kind=kind)
        return f"{cls.PREFIX_FUNDING}:{kind}:{venue.strip().lower()}:{base.strip().upper()}:{days}"

    @classmethod
    def funding_series(cls, venue: str, base: str, days: int) -> str:
        """Realized funding-rate series for ``(venue, base)`` over ``days`` (monitor + backtest)."""
        return cls._funding("series", venue, base, days)

    @classmethod
    def funding_adverse_moves(cls, venue: str, base: str, days: int) -> str:
        """Per-interval adverse-move samples for ``(venue, base)`` over ``days`` (backtest)."""
        return cls._funding("adverse", venue, base, days)

    @classmethod
    def funding_carry_path(cls, venue: str, base: str, days: int) -> str:
        """Aligned price + funding carry path for ``(venue, base)`` over ``days`` (paper)."""
        return cls._funding("carry_path", venue, base, days)

    @classmethod
    def ohlcv(cls, symbol: str, timeframe: str) -> str:
        """
        Generate OHLCV cache key.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h", "15m")

        Returns:
            Cache key like "ohlcv:btc_usdt:1h"
        """
        safe_symbol = symbol_to_safe_key(symbol)
        return f"{cls.PREFIX_OHLCV}:{safe_symbol}:{timeframe}"

    @classmethod
    def ohlcv_exchange_tail(cls, exchange: str, symbol: str, timeframe: str) -> str:
        """
        Phase 2 WebSocket supervisor rolling tail key (per-exchange namespace).

        Pattern: ``ohlcv:{exchange}:{SEG}:{timeframe}`` with ``SEG`` from
        ``symbol_to_exchange_namespaced_segment`` (uppercase, e.g. ``BTC_USDT``).

        SoT with writer: ``OHLCVStreamSupervisor._write_tail``.
        """
        ex = exchange.strip().lower()
        seg = symbol_to_exchange_namespaced_segment(symbol)
        return f"{cls.PREFIX_OHLCV}:{ex}:{seg}:{timeframe}"

    @classmethod
    def chart_indicators_payload(cls, exchange: str, symbol: str, timeframe: str) -> str:
        """J4 supervisor-precompute Redis key for the per-(exchange, symbol, tf) payload.

        Pattern: ``chart-indicators:{exchange}:{SEG}:{timeframe}`` where ``SEG`` is
        ``symbol_to_exchange_namespaced_segment(symbol)`` (uppercase, e.g. ``BTC_USDT``).

        Sibling to :meth:`ohlcv_exchange_tail` — same normalization rules so
        operators can derive both keys from the same ``(exchange, symbol, tf)``
        triple. SoT prefix lives in
        ``src.shared.constants.chart_indicators_cache``.
        """
        ex = exchange.strip().lower()
        seg = symbol_to_exchange_namespaced_segment(symbol)
        return f"{CHART_INDICATORS_PAYLOAD_KEY_PREFIX}{ex}:{seg}:{timeframe}"

    @classmethod
    def liquidation_heatmap_snapshot(
        cls,
        *,
        exchange: str,
        symbol: str,
        range_label: str,
        filter_hash: str,
    ) -> str:
        """Redis key for liquidation heatmap overlay snapshot (Phase 1)."""
        ex = exchange.strip()
        seg = symbol_to_exchange_namespaced_segment(symbol)
        return f"{LIQUIDATION_HEATMAP_CACHE_KEY_PREFIX}{ex}:{seg}:{range_label.strip()}:{filter_hash.strip()}"

    @classmethod
    def taker_flow_snapshot(cls, *, symbol: str, timeframe: str, limit: int) -> str:
        """Redis key for taker-flow CVD snapshot (Phase 3 D.1)."""
        seg = symbol_to_exchange_namespaced_segment(symbol)
        return f"{TAKER_FLOW_CACHE_KEY_PREFIX}{seg}:{timeframe.strip()}:{int(limit)}"

    @classmethod
    def derivatives_flow_snapshot(
        cls,
        *,
        symbol: str,
        timeframe: str,
        exchange: str,
        limit: int,
    ) -> str:
        """Redis key for derivatives-flow OI + liquidation snapshot (Phase 3 D.2)."""
        seg = symbol_to_exchange_namespaced_segment(symbol)
        exchange_seg = exchange.strip().replace(" ", "_")
        return f"{DERIVATIVES_FLOW_CACHE_KEY_PREFIX}{seg}:{exchange_seg}:{timeframe.strip()}:{int(limit)}"

    @classmethod
    def ohlcv_exchange_fresh_heartbeat(cls, exchange: str, symbol: str, timeframe: str) -> str:
        """
        Phase 2 freshness heartbeat key paired with ``ohlcv_exchange_tail``.

        Pattern: ``ohlcv:fresh:{exchange}:{SEG}:{timeframe}``.
        """
        ex = exchange.strip().lower()
        seg = symbol_to_exchange_namespaced_segment(symbol)
        return f"{cls.PREFIX_OHLCV}:fresh:{ex}:{seg}:{timeframe}"

    @classmethod
    def ohlcv_history_floor(cls, symbol: str, timeframe: str) -> str:
        """Oldest bar (epoch ms) the DATABASE holds for this shape, when its history is short.

        Lets a reader tell a cache that is BEHIND from one that holds every bar that exists —
        prod's ``1w`` key holds 473 bars because 473 is the whole record, not because it is
        stale. Semantics, measurements and the write/delete rules:
        ``src.application.services._ohlcv_service_history_floor``.

        Separate key prefix so a ``SCAN ohlcv:*`` over the data blobs never picks it up.
        """
        safe_symbol = symbol_to_safe_key(symbol)
        return f"{cls.PREFIX_OHLCV_HISTORY_FLOOR}:{safe_symbol}:{timeframe}"

    @classmethod
    def ohlcv_lock(cls, symbol: str, timeframe: str) -> str:
        """
        Generate Redis lock key for OHLCV cache mutations.

        WHY: Prevent concurrent writers from doing non-atomic
        read-modify-write updates (GET -> merge -> SET) on the same key.
        """
        safe_symbol = symbol_to_safe_key(symbol)
        return f"{cls.PREFIX_OHLCV_LOCK}:{safe_symbol}:{timeframe}"

    @classmethod
    def model(cls, symbol: str, timeframe: str, version: int) -> str:
        """
        Generate model metadata cache key.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")
            version: Model version number

        Returns:
            Cache key like "model:btc_usdt:1h:v3"
        """
        safe_symbol = symbol_to_safe_key(symbol)
        return f"{cls.PREFIX_MODEL}:{safe_symbol}:{timeframe}:v{version}"

    @classmethod
    def model_production(cls, symbol: str, timeframe: str) -> str:
        """
        Generate production model pointer cache key.

        This key stores which version is currently in production.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")

        Returns:
            Cache key like "model:btc_usdt:1h:production"
        """
        safe_symbol = symbol_to_safe_key(symbol)
        return f"{cls.PREFIX_MODEL}:{safe_symbol}:{timeframe}:production"

    @classmethod
    def features(cls, symbol: str, timeframe: str) -> str:
        """
        Generate features cache key.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")

        Returns:
            Cache key like "features:btc_usdt:1h"
        """
        safe_symbol = symbol_to_safe_key(symbol)
        return f"{cls.PREFIX_FEATURES}:{safe_symbol}:{timeframe}"

    @classmethod
    def signal(cls, symbol: str, timeframe: str) -> str:
        """
        Generate latest signal cache key.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")
            timeframe: Candle timeframe (e.g., "1h")

        Returns:
            Cache key like "signal:btc_usdt:1h:latest"
        """
        safe_symbol = symbol_to_safe_key(symbol)
        return f"{cls.PREFIX_SIGNAL}:{safe_symbol}:{timeframe}:latest"

    @classmethod
    def rate_limit(cls, user_id: str, endpoint: str) -> str:
        """
        Generate rate limit counter cache key.

        Args:
            user_id: User identifier
            endpoint: API endpoint identifier

        Returns:
            Cache key like "ratelimit:user123:signals"
        """
        return f"{cls.PREFIX_RATE_LIMIT}:{user_id}:{endpoint}"

    @classmethod
    def email_rate_limit(cls, user_id: str, date: str) -> str:
        """
        Generate email rate limit counter cache key (Sprint 2.4).

        Per-user daily email limit tracking. Key auto-expires at end of day.

        Args:
            user_id: User identifier (UUID as string)
            date: Date string in YYYY-MM-DD format (UTC)

        Returns:
            Cache key like "ratelimit:email:user123:2026-02-05"

        WHY include date in key:
        - Automatic daily reset without cron jobs
        - Old keys expire naturally via TTL
        - Easy to debug by checking specific date
        """
        return f"{cls.PREFIX_RATE_LIMIT}:email:{user_id}:{date}"

    @classmethod
    def get_email_rate_limit_ttl(cls) -> int:
        """Return the TTL used for per-day email rate-limit counters."""
        return cls.TTL_EMAIL_RATE_LIMIT

    @classmethod
    def get_ttl_for_timeframe(cls, timeframe: str) -> int:
        """
        Get the OHLCV cache TTL for a timeframe.

        Args:
            timeframe: Candle timeframe (e.g., "1h", "15m", "5m", "1m")

        Returns:
            TTL in seconds
        """
        return cls._get_registry_backed_cache_ttl(
            timeframe,
            unknown_ttl=cls.TTL_OHLCV_DEFAULT,
        )

    @classmethod
    def get_feature_ttl_for_timeframe(cls, timeframe: str) -> int:
        """Return the feature-cache TTL for a timeframe."""
        return cls._get_registry_backed_cache_ttl(
            timeframe,
            unknown_ttl=cls.TTL_FEATURES_DEFAULT,
        )

    @classmethod
    def _get_registry_backed_cache_ttl(
        cls,
        timeframe: str,
        *,
        unknown_ttl: int,
    ) -> int:
        """
        Derive cache TTL from the canonical timeframe registry.

        WHY derive instead of mapping twice:
        - `timeframes.py` already owns which backend timeframes exist
        - cache policy should follow the same supported surface, not maintain a
          second partial map that forgets entries like `30m` or `1w`
        """
        from src.shared.constants.timeframes import get_timeframe_delta

        try:
            delta = get_timeframe_delta(timeframe)
        except KeyError, ValueError:
            # ValueError: get_timeframe_delta raises for unsupported timeframes
            # (R-new-03)
            return unknown_ttl

        delta_seconds = int(delta.total_seconds())
        if delta >= timedelta(days=1):
            refresh_buffer = cls.TTL_REFRESH_BUFFER_DAILY_PLUS
        elif delta >= timedelta(hours=1):
            refresh_buffer = cls.TTL_REFRESH_BUFFER_HOURLY_PLUS
        elif delta >= timedelta(minutes=5):
            refresh_buffer = cls.TTL_REFRESH_BUFFER_INTRADAY
        else:
            refresh_buffer = cls.TTL_REFRESH_BUFFER_SUB_5M

        return max(delta_seconds - refresh_buffer, 1)
