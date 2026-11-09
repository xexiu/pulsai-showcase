"""An in-memory async Redis that keeps state AND pipelines across event loops, for task tests.

IMPORTERS/CALLERS: tests/workers/test_econ_event_alerts.py,
tests/workers/test_econ_alerts_fire_at_release_time.py,
tests/workers/test_econ_event_alerts_fomc_odds_reminder.py,
tests/unit/infrastructure/derivatives/test_binance_daily_history_store.py.
AFFECTED API: none -- test support only. DATA SCHEMAS: none.

REUSE-AUDIT: considered fakeredis.aioredis.FakeRedis, the repo's in-process Redis -- its queues
bind to the first event loop that uses them, and these tests drive tasks through
run_async_from_sync and repeated asyncio.run. Measured 2026-10-03: a pipeline in one loop and a
GET in the next raises "Queue ... is bound to a different event loop". Considered the FakeRedis
classes in tests/unit/infrastructure/exchange/ (source resolver, whale store, slot store): none
has a pipeline, and each is private to its own file.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping, Sequence


class DictRedis:
    """``get`` / ``mget`` / ``set`` / ``pipeline`` over a dict, with TTLs, pipeline flushes and read round trips recorded."""

    def __init__(self, initial: Mapping[str, str] | None = None) -> None:
        self.store: dict[str, str] = dict(initial or {})
        self.ttls: dict[str, int | None] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.pipeline_executions = 0
        self.read_round_trips = 0

    async def get(self, key: str) -> str | None:
        self.read_round_trips += 1
        return self.store.get(key)

    async def mget(self, keys: Sequence[str]) -> list[str | None]:
        self.read_round_trips += 1
        return [self.store.get(key) for key in keys]

    async def hset(self, name: str, mapping: Mapping[str, str]) -> int:
        fields = self.hashes.setdefault(name, {})
        added = sum(1 for field in mapping if field not in fields)
        fields.update(mapping)
        return added

    async def hgetall(self, name: str) -> dict[str, str]:
        return dict(self.hashes.get(name, {}))

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.store[key] = value
        self.ttls[key] = ex
        return True

    @asynccontextmanager
    async def pipeline(self, transaction: bool = True) -> AsyncIterator[DictPipeline]:
        del transaction  # MULTI/EXEC atomicity is moot for a dict in one thread
        yield DictPipeline(self)


class DictPipeline:
    """Queues writes and applies them on ``execute`` -- one counted round trip, as in Redis."""

    def __init__(self, redis: DictRedis) -> None:
        self._redis = redis
        self._pending: list[tuple[str, str, int | None]] = []

    def set(self, key: str, value: str, ex: int | None = None) -> DictPipeline:
        self._pending.append((key, value, ex))
        return self

    async def execute(self) -> list[bool]:
        self._redis.pipeline_executions += 1
        for key, value, ex in self._pending:
            self._redis.store[key] = value
            self._redis.ttls[key] = ex
        return [True] * len(self._pending)
