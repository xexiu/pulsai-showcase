"""Behavior: SoT for the market-limits warmer (Phase 2)."""

from __future__ import annotations

from datetime import timedelta

from src.shared.constants.exchanges import (
    MARKET_TYPE_SPOT,
    MARKET_TYPE_SWAP,
    SUPPORTED_EXCHANGES,
)
from src.shared.constants.market_limits import (
    MARKET_LIMITS_REFRESH_BUFFER,
    MARKET_LIMITS_WARMER_BEAT_INTERVAL,
    WARMABLE_MARKET_LIMITS_PAIRS,
    WarmableMarketLimitsPair,
)


class TestWarmablePairs:
    def test_is_a_non_empty_tuple_so_iteration_is_deterministic(self) -> None:
        assert isinstance(WARMABLE_MARKET_LIMITS_PAIRS, tuple)
        assert len(WARMABLE_MARKET_LIMITS_PAIRS) > 0

    def test_every_entry_is_typed_namedtuple_like_triple(self) -> None:
        for pair in WARMABLE_MARKET_LIMITS_PAIRS:
            assert isinstance(pair, WarmableMarketLimitsPair)
            assert pair.exchange_id
            assert pair.market_type in (MARKET_TYPE_SPOT, MARKET_TYPE_SWAP)
            assert pair.symbol

    def test_exchanges_referenced_are_supported(self) -> None:
        for pair in WARMABLE_MARKET_LIMITS_PAIRS:
            assert pair.exchange_id in SUPPORTED_EXCHANGES, f"warmable pair refers to unsupported exchange: {pair.exchange_id}"

    def test_pairs_are_unique(self) -> None:
        unique = {(p.exchange_id, p.market_type, p.symbol) for p in WARMABLE_MARKET_LIMITS_PAIRS}
        assert len(unique) == len(WARMABLE_MARKET_LIMITS_PAIRS)

    def test_initial_set_contains_bitget_btc_and_eth_swap(self) -> None:
        """The bench (cold p95=1.7s) was performed on these pairs and they are
        the highest-volume USDT-M perpetuals on the most heavily used exchange."""
        triples = [(p.exchange_id, p.market_type, p.symbol) for p in WARMABLE_MARKET_LIMITS_PAIRS]
        assert ("bitget", "swap", "BTC/USDT:USDT") in triples
        assert ("bitget", "swap", "ETH/USDT:USDT") in triples


class TestWarmerScheduleConstants:
    def test_refresh_buffer_is_positive_and_smaller_than_cache_ttl(self) -> None:
        from src.infrastructure.cache.keys import CacheKeys

        ttl = timedelta(seconds=CacheKeys.TTL_MARKET_LIMITS)
        assert timedelta(0) < MARKET_LIMITS_REFRESH_BUFFER
        assert ttl > MARKET_LIMITS_REFRESH_BUFFER, (
            "buffer must be strictly less than TTL — otherwise the warmer refreshes every tick even on a fresh cache."
        )

    def test_beat_interval_is_smaller_than_refresh_buffer(self) -> None:
        """Sampling theorem: beat must tick at least once inside the refresh
        window so we never miss a refresh deadline."""
        assert MARKET_LIMITS_WARMER_BEAT_INTERVAL < MARKET_LIMITS_REFRESH_BUFFER
