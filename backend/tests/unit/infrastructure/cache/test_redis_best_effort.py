"""`best_effort_redis_client` degrades on every fault Redis can really have -- and only on those.

IMPORTERS/CALLERS: pytest only. AFFECTED API: none -- exercises
src/infrastructure/cache/redis_best_effort.py (best_effort_redis_client, REDIS_CACHE_WRITE_FAULTS);
get_redis_client is replaced, nothing connects. DATA SCHEMAS: none.

WHY, 2026-10-03: the acquisition caught bare `Exception`, so a bug in our own code read exactly like
"Redis is down" on every chart route that uses it. get_redis_client documents RuntimeError on a
failed connect; the transport raises RedisError / OSError; a malformed URL raises ValueError. Those
four degrade to None; anything else is ours and surfaces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.infrastructure.cache import redis_best_effort

if TYPE_CHECKING:
    from collections.abc import Callable


def _failing(exc: BaseException) -> Callable[[], object]:
    async def get_redis_client() -> object:
        raise exc

    return get_redis_client


async def test_best_effort_redis_client_returns_client_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client = object()

    async def get_redis_client() -> object:
        return client

    monkeypatch.setattr("src.infrastructure.cache.redis_client.get_redis_client", get_redis_client)

    assert await redis_best_effort.best_effort_redis_client() is client


@pytest.mark.parametrize(
    "fault",
    [RedisConnectionError("refused"), OSError("unreachable"), RuntimeError("connect failed"), ValueError("bad redis url")],
)
async def test_a_redis_fault_degrades_to_no_client(monkeypatch: pytest.MonkeyPatch, fault: BaseException) -> None:
    monkeypatch.setattr("src.infrastructure.cache.redis_client.get_redis_client", _failing(fault))

    assert await redis_best_effort.best_effort_redis_client() is None


async def test_a_bug_in_our_own_code_is_not_read_as_redis_being_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.infrastructure.cache.redis_client.get_redis_client", _failing(TypeError("our bug")))

    with pytest.raises(TypeError, match="our bug"):
        await redis_best_effort.best_effort_redis_client()


def test_a_cache_write_also_tolerates_an_unserializable_payload() -> None:
    import orjson

    assert issubclass(orjson.JSONEncodeError, redis_best_effort.REDIS_CACHE_WRITE_FAULTS)
    assert all(issubclass(f, redis_best_effort.REDIS_CACHE_WRITE_FAULTS) for f in redis_best_effort.REDIS_FAULTS)
