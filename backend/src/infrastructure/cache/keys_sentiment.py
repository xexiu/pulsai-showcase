"""Cache keys and TTLs for the sentiment / macro / econ-calendar family.

Inherited by :class:`src.infrastructure.cache.keys.CacheKeys`, which stays the ONE name callers
import. Splitting the file must not split the namespace: ``CacheKeys.macro_snapshot()`` resolves
here through inheritance, so no caller, test or worker changes.

WHY this family and not an arbitrary cut. These keys share a lifecycle that the rest of the cache
does not: a WARMER writes them on a beat and the request path only reads, so their TTLs are sized
as "last-good headroom" (how long a stale value still beats no value when FRED or Kalshi rate-limits
a single tick) rather than as freshness windows. ``PREFIX_SENTIMENT`` and ``PREFIX_FUNDAMENTAL``
move with them because — measured before moving — nothing outside this family referenced either.

REUSE-AUDIT: considered leaving them in keys.py (the file is over the §7 cap and this family is
what last grew it); considered src/shared/constants/econ_calendar.py (event-schedule constants, no
cache policy); considered the per-domain caches that consume these keys — econ_calendar_cache.py,
macro_snapshot_cache.py, headline_sentiment_snapshot.py, on_chain_snapshot.py — putting the key
next to one consumer would give four modules their own spelling of a shared namespace, which is the
drift CacheKeys exists to prevent.
"""

from __future__ import annotations

from typing import Final


class SentimentCacheKeys:
    """Key builders and TTL policy for sentiment, macro and econ-calendar cache entries."""

    PREFIX_SENTIMENT: Final[str] = "sentiment"
    PREFIX_FUNDAMENTAL: Final[str] = "fundamental"

    # Fear & Greed (alternative.me) updates roughly daily; short TTL cuts
    # upstream load + flakiness.
    TTL_SENTIMENT_COMBINED: Final[int] = 15 * 60
    # 15 minutes
    # Headline snapshot: worker refresh; tolerate longer staleness than F&G combined
    TTL_HEADLINE_SENTIMENT_SNAPSHOT: Final[int] = 30 * 60
    # Per-headline FinBERT score cache: text is immutable so the score is too; 6h
    # comfortably covers a headline's feed lifetime (mirrors NEWS_IMPACT_CACHE_TTL_SECONDS).
    TTL_HEADLINE_FINBERT_SCORES: Final[int] = 6 * 60 * 60
    # On-chain snapshot: worker refresh every ~30m; TTL > beat gap for last-good retention
    TTL_ON_CHAIN_SNAPSHOT: Final[int] = 45 * 60
    # Macro snapshot: worker refresh every ~30m; keep last-known for API/inference.
    TTL_MACRO_SNAPSHOT: Final[int] = 90 * 60
    # Kalshi FOMC decision-odds (live prediction market, request-path fetch —
    # see kalshi_fomc_odds_provider.py). Same order of magnitude as
    # TTL_SENTIMENT_COMBINED: short enough to stay current, long enough that
    # every GET /sentiment/detailed doesn't re-hit Kalshi.
    TTL_KALSHI_FOMC_ODDS: Final[int] = 15 * 60
    # Econ release schedule: warmer refreshes every 6h; TTL=25h gives 4x last-good
    # headroom when FRED rate-limits a single tick (alert task MUST NOT call FRED).
    TTL_ECON_SCHEDULE: Final[int] = 25 * 60 * 60
    # FRED latest observation pairs (CPI/NFP/FedFunds): warmer refreshes every 1h;
    # TTL=2h gives 2x last-good headroom so a single 429 still serves cached values.
    TTL_FRED_OBSERVATIONS: Final[int] = 2 * 60 * 60
    # FRED daily macro series (VIX/DGS10/DXY): warmer refreshes hourly; TTL=2h
    # gives 2x headroom. Series themselves only change once per trading day so
    # the headroom is for upstream resilience, not freshness.
    TTL_FRED_MACRO_SERIES: Final[int] = 2 * 60 * 60

    @classmethod
    def sentiment_combined_current(cls) -> str:
        """
        Aggregated /sentiment/current response (all providers combined).

        Market-wide only today (Fear & Greed); key stays stable if optional
        ``symbol`` is ignored by all providers.
        """
        return f"{cls.PREFIX_SENTIMENT}:combined:current"

    @classmethod
    def headline_sentiment_snapshot(cls) -> str:
        """Precomputed headline / news sentiment for HeadlineSentimentProvider (worker-owned)."""
        return f"{cls.PREFIX_SENTIMENT}:headline:current"

    @classmethod
    def news_impact_verdict(cls, headline_hash: str) -> str:
        """LLM news-impact verdict for one headline, cached by content hash (worker-owned).

        Headline text is immutable, so its verdict is too — caching by hash means the
        LLM is paid once per unique headline, not once per 5-min cycle it lingers.
        """
        return f"{cls.PREFIX_SENTIMENT}:news_impact:{headline_hash}"

    @classmethod
    def headline_finbert_scores(cls, headline_hash: str) -> str:
        """FinBERT tone scores for one headline, cached by content hash (worker-owned).

        Phase-1 mirror of :meth:`news_impact_verdict`: a headline's FinBERT score is
        deterministic, so caching by hash means the ~1.3 GB FinBERT pipeline only loads
        when genuinely NEW headlines appear, not on every 5-min refresh cycle.
        """
        return f"{cls.PREFIX_SENTIMENT}:headline_finbert:{headline_hash}"

    @classmethod
    def on_chain_snapshot(cls) -> str:
        """Precomputed Glassnode-backed on-chain metrics for GET /fundamental/onchain (worker-owned)."""
        return f"{cls.PREFIX_FUNDAMENTAL}:on_chain:btc_snapshot"

    @classmethod
    def macro_snapshot(cls) -> str:
        """Precomputed macro snapshot (F&G/BTC dominance/VIX/DXY/10Y) for API + inference."""
        return f"{cls.PREFIX_SENTIMENT}:macro:current"

    @classmethod
    def kalshi_fomc_odds(cls) -> str:
        """Live Kalshi Fed decision-odds for the next scheduled FOMC meeting (request-path fetch).

        Namespaced next to :meth:`macro_snapshot` — the fields it caches ride inside the
        same ``MacroSnapshotPublic`` block, right beside ``hours_until_fomc``.
        """
        return f"{cls.PREFIX_SENTIMENT}:macro:kalshi_fomc_odds"

    @classmethod
    def econ_schedule(cls) -> str:
        """FOMC/CPI/NFP release-date schedule from FRED (warmer-owned)."""
        return "econ_calendar:schedule:current"

    @classmethod
    def fred_observations(cls) -> str:
        """Latest CPI/NFP/FedFunds observation pairs from FRED (warmer-owned)."""
        return "econ_calendar:fred_observations:current"

    @classmethod
    def fred_macro_series(cls) -> str:
        """Latest VIX/DGS10/DXY close values from FRED (warmer-owned)."""
        return "fred:macro_series:current"
