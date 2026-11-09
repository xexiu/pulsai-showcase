"""RedisClient's MGET, and the contract its test double promises.

IMPORTERS/CALLERS: pytest. AFFECTED API: pins RedisDataOps.mget (econ_event_alerts._read_dedup calls it on the shared
client). DATA SCHEMAS: none -- a stub connection.

MEASURED 2026-11-06 in the local stack's pulsai.log: run_econ_post_event_alerts raised AttributeError at 13:30 and 13:31
UTC -- the jobless-claims print made a post-event alert due, _read_dedup called ``mget`` on the shared RedisClient, and
RedisDataOps had no ``mget``. The task's tests passed because tests/helpers/dict_redis.DictRedis implements one: the double
promised a method the real client never had. The contract test below holds every method of the double to the real class.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from src.infrastructure.cache.redis_client import RedisClient
from src.infrastructure.cache.redis_client_ops import RedisDataOps
from tests.helpers.dict_redis import DictRedis


def test_every_method_the_test_double_fakes_exists_on_the_real_client() -> None:
    faked = {name for name, member in inspect.getmembers(DictRedis, inspect.iscoroutinefunction) if not name.startswith("_")}
    assert faked, "the double must fake something, or this proves nothing"
    missing = sorted(name for name in faked if not hasattr(RedisClient, name))
    assert missing == [], f"DictRedis fakes {missing}, which RedisClient does not have"


class _Conn:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.sets: list[tuple[str, str, int | None, bool]] = []

    async def mget(self, keys: list[str]) -> list[str | None]:
        self.calls.append(list(keys))
        return ["1" if key.endswith("a") else None for key in keys]

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False) -> bool | None:
        self.sets.append((key, value, ex, nx))
        return None if nx and key == "taken" else True


class _Ops(RedisDataOps):
    def __init__(self) -> None:
        self.conn = _Conn()

    @property
    def client(self) -> Any:  # the mixin's one requirement: the connection
        return self.conn


@pytest.mark.asyncio
async def test_mget_reads_every_key_in_one_round_trip_aligned_with_the_keys() -> None:
    ops = _Ops()
    assert await ops.mget(["k:a", "k:b", "k:a"]) == ["1", None, "1"]
    assert ops.conn.calls == [["k:a", "k:b", "k:a"]]


@pytest.mark.asyncio
async def test_set_passes_its_expiry_and_nx_and_reads_a_refused_nx_as_false() -> None:
    """set without the kwargs dict it built (a typing.Any paid down with the mget fix): the same call, the same answer."""
    ops = _Ops()
    assert await ops.set("k", "v") is True
    assert await ops.set("k", "v", ex=60) is True
    assert await ops.set("taken", "v", nx=True) is False
    assert ops.conn.sets == [("k", "v", None, False), ("k", "v", 60, False), ("taken", "v", None, True)]


@pytest.mark.asyncio
async def test_mget_of_no_keys_sends_nothing() -> None:
    ops = _Ops()
    assert await ops.mget([]) == []
    assert ops.conn.calls == []
