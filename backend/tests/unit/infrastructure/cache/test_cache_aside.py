"""Behavior tests for the generic fail-open cache-aside helper + funding cache keys.

Covers read-through hit/miss, TTL+key on write, and fail-open behavior on every
Redis interaction (resolve/read/write). Redis is injected as an AsyncMock so no
network/real Redis is involved (mirrors test_market_limits_cache.py).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.cache import cache_aside as cache_aside_module
from src.infrastructure.cache.cache_aside import cache_aside_json
from src.infrastructure.cache.keys import CacheKeys

_KEY = "funding:series:binance:BTC:365"
_TTL = 900


def _redis_mock(get_value: Any = None, set_returns: bool = True) -> MagicMock:
    redis = MagicMock()
    redis.get_json = AsyncMock(return_value=get_value)
    redis.set_json = AsyncMock(return_value=set_returns)
    return redis


class TestCacheKeysFunding:
    def test_series_key_normalizes_venue_and_base(self) -> None:
        assert CacheKeys.funding_series("Binance", "btc", 365) == "funding:series:binance:BTC:365"

    def test_adverse_and_carry_path_keys_are_distinct_namespaces(self) -> None:
        venue, base, days = "hyperliquid", "ETH", 180
        keys = {
            CacheKeys.funding_series(venue, base, days),
            CacheKeys.funding_adverse_moves(venue, base, days),
            CacheKeys.funding_carry_path(venue, base, days),
        }
        assert keys == {
            "funding:series:hyperliquid:ETH:180",
            "funding:adverse:hyperliquid:ETH:180",
            "funding:carry_path:hyperliquid:ETH:180",
        }

    def test_days_partitions_the_key(self) -> None:
        assert CacheKeys.funding_series("binance", "BTC", 30) != CacheKeys.funding_series("binance", "BTC", 365)

    def test_empty_venue_or_base_rejected(self) -> None:
        with pytest.raises(ValueError, match="venue"):
            CacheKeys.funding_series("", "BTC", 365)
        with pytest.raises(ValueError, match="base"):
            CacheKeys.funding_series("binance", "  ", 365)

    def test_ttl_funding_is_fifteen_minutes(self) -> None:
        assert CacheKeys.TTL_FUNDING == 15 * 60


@pytest.mark.asyncio
async def test_returns_cached_value_and_skips_loader_on_hit() -> None:
    redis = _redis_mock(get_value={"rates": [0.1, 0.2]})
    loader = AsyncMock()

    result = await cache_aside_json(key=_KEY, ttl_seconds=_TTL, loader=loader, redis_client=redis)

    assert result == {"rates": [0.1, 0.2]}
    loader.assert_not_awaited()
    redis.set_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_calls_loader_on_miss_and_writes_with_key_and_ttl() -> None:
    redis = _redis_mock(get_value=None)
    loader = AsyncMock(return_value={"rates": [0.3]})

    result = await cache_aside_json(key=_KEY, ttl_seconds=_TTL, loader=loader, redis_client=redis)

    assert result == {"rates": [0.3]}
    loader.assert_awaited_once_with()
    redis.set_json.assert_awaited_once_with(_KEY, {"rates": [0.3]}, ex=_TTL)


@pytest.mark.asyncio
async def test_does_not_cache_empty_list_result() -> None:
    """An empty result (e.g. transient outage) is returned but NOT cached (no negative caching)."""
    redis = _redis_mock(get_value=None)
    loader = AsyncMock(return_value=[])

    result = await cache_aside_json(key=_KEY, ttl_seconds=_TTL, loader=loader, redis_client=redis)

    assert result == []
    loader.assert_awaited_once_with()
    redis.set_json.assert_not_awaited()  # empty -> skip write so the next call retries the loader


@pytest.mark.asyncio
async def test_does_not_cache_empty_dict_result() -> None:
    """Empty dict payload is likewise not cached."""
    redis = _redis_mock(get_value=None)
    loader = AsyncMock(return_value={})

    result = await cache_aside_json(key=_KEY, ttl_seconds=_TTL, loader=loader, redis_client=redis)

    assert result == {}
    redis.set_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_fails_open_on_read_error_and_still_loads_and_writes() -> None:
    redis = MagicMock()
    redis.get_json = AsyncMock(side_effect=ConnectionError("redis down"))
    redis.set_json = AsyncMock(return_value=True)
    loader = AsyncMock(return_value=["a", "b"])

    result = await cache_aside_json(key=_KEY, ttl_seconds=_TTL, loader=loader, redis_client=redis)

    assert result == ["a", "b"]
    loader.assert_awaited_once_with()
    redis.set_json.assert_awaited_once()


@pytest.mark.asyncio
async def test_returns_loader_result_when_write_fails() -> None:
    redis = MagicMock()
    redis.get_json = AsyncMock(return_value=None)
    redis.set_json = AsyncMock(side_effect=ConnectionError("redis down"))
    loader = AsyncMock(return_value={"ok": True})

    result = await cache_aside_json(key=_KEY, ttl_seconds=_TTL, loader=loader, redis_client=redis)

    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_fails_open_when_client_resolution_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom() -> Any:
        raise ConnectionError("no redis configured")

    monkeypatch.setattr(cache_aside_module, "get_redis_client", boom)
    loader = AsyncMock(return_value={"loaded": 1})

    # redis_client omitted -> falls back to get_redis_client, which raises -> loader path
    result = await cache_aside_json(key=_KEY, ttl_seconds=_TTL, loader=loader)

    assert result == {"loaded": 1}
    loader.assert_awaited_once_with()


class TestOnlyREDISFaultsAreSwallowed:
    """Fail-open covers Redis being down. It must NOT cover a bug in our own code.

    Every Redis interaction here is deliberately fail-open, and the three tests above prove it
    for the faults Redis can really have (``ConnectionError`` is an ``OSError`` subclass, so it
    is in ``REDIS_FAULTS`` alongside ``RedisError``). A blind ``except Exception`` swallowed a
    strictly larger set: a ``TypeError`` from calling ``get_json`` with the wrong signature, or
    an ``AttributeError`` from a client that never grew the method, read to the caller as a
    plain cache miss -- so the cache silently stopped working and every request paid the loader
    instead, with one WARNING line per call and nothing that said "this is our bug".

    That is the exact shape of the incident `.claude/rules/` records twice: a swallowed error
    that reads as success. These pin that a programming error now REACHES the caller.
    """

    @pytest.mark.asyncio
    async def test_a_broken_read_client_raises_instead_of_reading_as_a_miss(self) -> None:
        redis = MagicMock()
        redis.get_json = AsyncMock(side_effect=TypeError("get_json() takes 1 positional argument"))
        redis.set_json = AsyncMock(return_value=True)
        loader = AsyncMock(return_value=["a"])

        with pytest.raises(TypeError):
            await cache_aside_json(key=_KEY, ttl_seconds=_TTL, loader=loader, redis_client=redis)

    @pytest.mark.asyncio
    async def test_a_broken_write_client_raises_instead_of_being_silently_dropped(self) -> None:
        redis = MagicMock()
        redis.get_json = AsyncMock(return_value=None)
        redis.set_json = AsyncMock(side_effect=AttributeError("no set_json on this double"))
        loader = AsyncMock(return_value={"ok": True})

        with pytest.raises(AttributeError):
            await cache_aside_json(key=_KEY, ttl_seconds=_TTL, loader=loader, redis_client=redis)

    @pytest.mark.asyncio
    async def test_a_broken_client_resolver_raises_instead_of_bypassing_the_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def boom() -> Any:
            raise TypeError("get_redis_client() got an unexpected keyword argument")

        monkeypatch.setattr(cache_aside_module, "get_redis_client", boom)

        with pytest.raises(TypeError):
            await cache_aside_json(key=_KEY, ttl_seconds=_TTL, loader=AsyncMock(return_value={"loaded": 1}))


@pytest.mark.asyncio
async def test_uses_injected_client_over_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    singleton_called = False

    async def fake_singleton() -> Any:
        nonlocal singleton_called
        singleton_called = True
        return _redis_mock()

    monkeypatch.setattr(cache_aside_module, "get_redis_client", fake_singleton)
    redis = _redis_mock(get_value={"hit": 1})

    result = await cache_aside_json(key=_KEY, ttl_seconds=_TTL, loader=AsyncMock(), redis_client=redis)

    assert result == {"hit": 1}
    assert singleton_called is False  # injected client wins; singleton never resolved


# --- cache_aside_json_batch -------------------------------------------------


@pytest.mark.asyncio
async def test_batch_all_hits_skips_loader() -> None:
    from src.infrastructure.cache.cache_aside import cache_aside_json_batch

    store = {"k:a": {"v": 1}, "k:b": {"v": 2}}

    async def get_json(key: str) -> Any:
        return store.get(key)

    redis = MagicMock()
    redis.get_json = AsyncMock(side_effect=get_json)
    redis.set_json = AsyncMock(return_value=True)
    loader = AsyncMock()

    out = await cache_aside_json_batch(
        ["a", "b"],
        key_for=lambda x: f"k:{x}",
        ttl_seconds=_TTL,
        load_misses=loader,
        redis_client=redis,
    )

    assert out == [{"v": 1}, {"v": 2}]
    loader.assert_not_awaited()
    redis.set_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_batch_misses_one_loader_call_preserves_order_and_writes() -> None:
    from src.infrastructure.cache.cache_aside import cache_aside_json_batch

    store: dict[str, Any] = {"k:hit": {"v": 0}}

    async def get_json(key: str) -> Any:
        return store.get(key)

    async def set_json(key: str, value: Any, ex: int | None = None) -> bool:
        store[key] = value
        return True

    redis = MagicMock()
    redis.get_json = AsyncMock(side_effect=get_json)
    redis.set_json = AsyncMock(side_effect=set_json)

    async def load_misses(misses: list[str]) -> list[dict[str, int]]:
        return [{"v": 10 + i} for i, _ in enumerate(misses)]

    out = await cache_aside_json_batch(
        ["miss0", "hit", "miss1"],
        key_for=lambda x: f"k:{x}",
        ttl_seconds=_TTL,
        load_misses=load_misses,
        redis_client=redis,
    )

    assert out == [{"v": 10}, {"v": 0}, {"v": 11}]
    assert store["k:miss0"] == {"v": 10}
    assert store["k:miss1"] == {"v": 11}


@pytest.mark.asyncio
async def test_batch_chunks_miss_loader_calls() -> None:
    from src.infrastructure.cache.cache_aside import cache_aside_json_batch

    redis = _redis_mock(get_value=None)
    seen: list[list[str]] = []

    async def load_misses(misses: list[str]) -> list[dict[str, str]]:
        chunk = list(misses)
        seen.append(chunk)
        return [{"id": m} for m in chunk]

    out = await cache_aside_json_batch(
        ["a", "b", "c", "d", "e"],
        key_for=lambda x: f"k:{x}",
        ttl_seconds=_TTL,
        load_misses=load_misses,
        redis_client=redis,
        chunk_size=2,
    )

    assert [row["id"] for row in out] == ["a", "b", "c", "d", "e"]
    assert seen == [["a", "b"], ["c", "d"], ["e"]]
    assert redis.set_json.await_count == 5


@pytest.mark.asyncio
async def test_batch_empty_loader_payload_not_written() -> None:
    from src.infrastructure.cache.cache_aside import cache_aside_json_batch

    redis = _redis_mock(get_value=None)

    async def load_misses(misses: list[str]) -> list[dict[str, Any]]:
        return [{} for _ in misses]

    out = await cache_aside_json_batch(
        ["x"],
        key_for=lambda x: f"k:{x}",
        ttl_seconds=_TTL,
        load_misses=load_misses,
        redis_client=redis,
    )

    assert out == [{}]
    redis.set_json.assert_not_awaited()


@pytest.mark.asyncio
async def test_batch_rejects_non_positive_chunk_size() -> None:
    from src.infrastructure.cache.cache_aside import cache_aside_json_batch

    with pytest.raises(ValueError, match="chunk_size"):
        await cache_aside_json_batch(
            ["a"],
            key_for=lambda x: x,
            ttl_seconds=_TTL,
            load_misses=AsyncMock(return_value=[{"ok": True}]),
            redis_client=_redis_mock(),
            chunk_size=0,
        )


@pytest.mark.asyncio
async def test_batch_normalize_hit_rejects_force_miss() -> None:
    from src.infrastructure.cache.cache_aside import cache_aside_json_batch

    redis = _redis_mock(get_value={"label": "GARBAGE"})
    loader = AsyncMock(return_value=[{"label": "ok", "confidence": 0.5}])

    out = await cache_aside_json_batch(
        ["h"],
        key_for=lambda x: f"k:{x}",
        ttl_seconds=_TTL,
        load_misses=loader,
        redis_client=redis,
        normalize_hit=lambda raw: None,
    )

    assert out == [{"label": "ok", "confidence": 0.5}]
    loader.assert_awaited_once()


@pytest.mark.asyncio
async def test_batch_probes_keys_concurrently_not_one_after_another() -> None:
    """A function named `_batch` must not pay N sequential round trips.

    FOUND by an AST sweep for `await` assigned inside a `for` loop (25 sites across
    apps/api/src). Almost all were correctly sequential -- ordered savepoints, a deliberately
    staggered dispatch, retry loops that stop at the first success, walk-forward folds, order
    execution that must not race. This one was not: the read probe awaited once per item, so
    resolving N headlines cost N stacked Redis round trips before any loader ran.

    Same defect class as the OHLCV heartbeat read fixed the same night, and the giveaway is the
    same: a name promising a batch over a body that iterates.

    WHY CONCURRENCY RATHER THAN MGET. `RedisJsonCache` is a deliberately minimal Protocol --
    "the minimal structural surface this helper needs ... tests can inject any double with the
    same two methods". Adding `mget_json` would force every implementer to grow a method for one
    caller's benefit, which is the ISP violation that Protocol exists to avoid. Gathering the
    existing reads collapses the LATENCY (N x RTT becomes ~1 x RTT) while the interface, every
    double, and all nine sibling tests above stay exactly as they are.

    The assertion is on ELAPSED TIME rather than call ordering because the property that matters
    is "the caller does not wait N times", which any future rewrite must also satisfy.

    MEASURED AGAINST A CONTROL, not a constant (2026-09-09). The bar used to be an absolute
    `elapsed < 100 ms`, and it failed inside a full `verify.sh` while a model retrain held ~75% of
    a core -- then passed alone on the same tree seconds later. An absolute wall-clock bound cannot
    separate "the helper awaited N times" from "the event loop was not scheduled promptly", and a
    gate that fails a clean tree at random gets re-run, then ignored, then deleted.

    So the same ten delayed probes are timed twice in the same run: once genuinely sequential,
    once through the helper. Starvation inflates BOTH and cancels out of the comparison, while a
    helper that awaits one-at-a-time lands on the sequential number. Third instance of this shape
    in one session -- the chart-assembly loop test and the feature-calculator perf gate had it
    too, and it is the only form of timing assertion here that has survived a busy machine.
    """
    import asyncio
    import time

    from src.infrastructure.cache.cache_aside import cache_aside_json_batch

    read_delay_seconds = 0.02
    item_count = 10

    async def slow_get_json(key: str) -> Any:
        await asyncio.sleep(read_delay_seconds)
        return {"key": key}

    # The CONTROL: what awaiting one at a time costs on this machine, right now.
    #
    # CALIBRATED ON TWO PROBES AND SCALED, not run ten times. A full sequential control is the
    # obvious version and it would add ~200 ms to a unit test to learn something two samples
    # already show -- "don't make slow tests" is a rule here too. Two rather than one because a
    # single unlucky wakeup would set the whole bar.
    calibration_probes = 2
    calibration_started = time.perf_counter()
    for index in range(calibration_probes):
        await slow_get_json(f"control:{index}")
    sequential_elapsed = (time.perf_counter() - calibration_started) * (item_count / calibration_probes)

    redis = MagicMock()
    redis.get_json = AsyncMock(side_effect=slow_get_json)
    redis.set_json = AsyncMock(return_value=True)

    started = time.perf_counter()
    out = await cache_aside_json_batch(
        [str(i) for i in range(item_count)],
        key_for=lambda x: f"k:{x}",
        ttl_seconds=_TTL,
        load_misses=AsyncMock(),
        redis_client=redis,
    )
    elapsed = time.perf_counter() - started

    assert len(out) == item_count
    assert redis.get_json.await_count == item_count, "every key must still be probed"
    # Half the MEASURED sequential cost -- the same wide line as before, drawn against this
    # machine's own number instead of one inherited from the machine that wrote the test.
    assert elapsed < sequential_elapsed / 2, (
        f"{item_count} cache probes took {elapsed * 1000:.0f} ms against a measured sequential "
        f"cost of {sequential_elapsed * 1000:.0f} ms on this machine -- they ran one after another"
    )


@pytest.mark.asyncio
async def test_batch_ttl_for_overrides_default_ttl() -> None:
    from src.infrastructure.cache.cache_aside import cache_aside_json_batch

    redis = _redis_mock(get_value=None)

    async def load_misses(misses: list[str]) -> list[dict[str, str]]:
        return [{"id": m} for m in misses]

    await cache_aside_json_batch(
        ["a"],
        key_for=lambda x: f"k:{x}",
        ttl_seconds=_TTL,
        load_misses=load_misses,
        redis_client=redis,
        ttl_for=lambda _value: 42,
    )

    redis.set_json.assert_awaited_once_with("k:a", {"id": "a"}, ex=42)
