"""P8-L-1 (L-9 remediation): CacheKeys SoT for paper-trading lifecycle locks.

Pre-P8 the Redis lock keys used by ``paper_trading_limit_lifecycle`` were
f-strings inlined into a worker module:

    f"paper:lifecycle:sync:{user_id}:{ccxt_order_id}"
    f"paper:lifecycle:positions_sync:{user_id}:{connection_id}:{symbol}"

That hid a real Ops hazard: if a second worker module ever needed to inspect
(e.g. clear or probe) those locks, it would have to duplicate the f-string,
and drift in the namespace prefix would create silent lock collisions OR
invisible unlock-failures. Moving both builders onto :class:`CacheKeys`
gives us one unit-testable Source of Truth for the key shape.
"""

from __future__ import annotations

import pytest


class TestPaperLifecycleOrderLockKey:
    def test_builder_returns_canonical_namespaced_key(self) -> None:
        from src.infrastructure.cache.keys import CacheKeys

        key = CacheKeys.paper_lifecycle_order_lock(user_id="u-123", ccxt_order_id="order-xyz")
        assert key == "paper:lifecycle:sync:u-123:order-xyz"

    def test_builder_stable_across_invocations(self) -> None:
        from src.infrastructure.cache.keys import CacheKeys

        assert CacheKeys.paper_lifecycle_order_lock(
            user_id="u-1",
            ccxt_order_id="o-2",
        ) == CacheKeys.paper_lifecycle_order_lock(user_id="u-1", ccxt_order_id="o-2")

    @pytest.mark.parametrize(
        ("user_id", "ccxt_order_id"),
        [("", "o"), ("u", ""), (" ", "o"), ("u", " ")],
    )
    def test_builder_rejects_empty_inputs(self, user_id: str, ccxt_order_id: str) -> None:
        from src.infrastructure.cache.keys import CacheKeys

        with pytest.raises(ValueError, match="must not be empty"):
            CacheKeys.paper_lifecycle_order_lock(user_id=user_id, ccxt_order_id=ccxt_order_id)


class TestPaperLifecyclePositionLockKey:
    def test_builder_returns_canonical_namespaced_key(self) -> None:
        from src.infrastructure.cache.keys import CacheKeys

        key = CacheKeys.paper_lifecycle_position_lock(
            user_id="u-123",
            connection_id="conn-7",
            symbol="BTC/USDT",
        )
        assert key == "paper:lifecycle:positions_sync:u-123:conn-7:BTC/USDT"

    def test_builder_disjoint_from_order_lock_namespace(self) -> None:
        """Position sweep MUST NOT collide with per-order lock namespace."""
        from src.infrastructure.cache.keys import CacheKeys

        order_key = CacheKeys.paper_lifecycle_order_lock(user_id="u", ccxt_order_id="X")
        position_key = CacheKeys.paper_lifecycle_position_lock(
            user_id="u",
            connection_id="c",
            symbol="BTC/USDT",
        )
        assert order_key != position_key
        assert ":positions_sync:" in position_key
        assert ":sync:" in order_key
        assert ":positions_sync:" not in order_key

    @pytest.mark.parametrize(
        ("user_id", "connection_id", "symbol"),
        [("", "c", "BTC/USDT"), ("u", "", "BTC/USDT"), ("u", "c", ""), ("u", "c", " ")],
    )
    def test_builder_rejects_empty_inputs(self, user_id: str, connection_id: str, symbol: str) -> None:
        from src.infrastructure.cache.keys import CacheKeys

        with pytest.raises(ValueError, match="must not be empty"):
            CacheKeys.paper_lifecycle_position_lock(
                user_id=user_id,
                connection_id=connection_id,
                symbol=symbol,
            )


class TestPaperLifecyclePrefixExposed:
    def test_prefix_constant_exposed(self) -> None:
        from src.infrastructure.cache.keys import CacheKeys

        assert CacheKeys.PREFIX_PAPER_LIFECYCLE == "paper:lifecycle"
