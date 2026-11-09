"""The Redis singleton must be RESET even when closing it fails.

SIGNAL-LOOP-1, root-caused 2026-08-21. This is the half that made the failure PERMANENT rather
than transient, and it is four lines of ordering:

    async def close_redis_client() -> None:
        global _redis_client, ...
        if _redis_client is not None:
            await _redis_client.close()   # <- raises on a stale-loop connection
            _redis_client = None          # <- NEVER RUNS
        _redis_client_init_lock = None    # <- NEVER RUNS
        _redis_singleton_loop_id = None   # <- NEVER RUNS

`RedisClient.close()` has the same shape (`await self._pool.disconnect()` then `self._pool = None`).

So one connection created on a since-closed event loop poisons the singleton, the cleanup that
would have cleared it raises BEFORE clearing, and every later task in that worker reuses the same
poisoned client and fails identically. Measured: 22 of 23 consecutive runs, never recovering.

Resetting in a `finally` makes the next task build a fresh client on its own loop, which is what
turns a permanent outage back into a single logged hiccup.
"""

from __future__ import annotations

from typing import Any

import pytest


class _ExplodingClient:
    """Stands in for a client whose pool holds connections from a dead loop."""

    def __init__(self, boom: Exception) -> None:
        self._boom = boom
        self.close_attempted = False
        # `dispose_stale_redis_client_best_effort` reaches for these after a failed close, so a
        # stand-in without them would fail on the stub rather than on the behaviour under test.
        self._client: object | None = object()
        self._pool: object | None = None

    async def close(self) -> None:
        self.close_attempted = True
        raise self._boom


@pytest.mark.asyncio
class TestCloseAlwaysResetsTheSingleton:
    async def test_the_singleton_is_cleared_even_when_close_raises(self, monkeypatch: Any) -> None:
        import src.infrastructure.cache.redis_client as rc

        monkeypatch.setattr(rc, "_redis_client", _ExplodingClient(RuntimeError("Event loop is closed")))

        with pytest.raises((RuntimeError,)):
            await rc.close_redis_client()

        assert rc._redis_client is None, "the poisoned client stayed installed, so every later task reuses it and fails"

    async def test_the_loop_id_is_cleared_too(self, monkeypatch: Any) -> None:
        """A stale loop id would keep the next task believing the singleton matches its loop.

        Pinned on THIS loop's id on purpose. The original used a made-up 12345, which is by
        definition a foreign loop, so it was really exercising the cross-loop path while claiming
        to be about clearing state on failure. Binding to the running loop keeps the two cases
        apart: this one is "the close genuinely failed", the cross-loop class below is "the close
        was never this loop's to make".
        """
        import asyncio

        import src.infrastructure.cache.redis_client as rc

        monkeypatch.setattr(rc, "_redis_client", _ExplodingClient(RuntimeError("Event loop is closed")))
        monkeypatch.setattr(rc, "_redis_singleton_loop_id", id(asyncio.get_running_loop()))

        with pytest.raises((RuntimeError,)):
            await rc.close_redis_client()

        assert rc._redis_singleton_loop_id is None

    async def test_the_init_lock_is_cleared_too(self, monkeypatch: Any) -> None:
        import src.infrastructure.cache.redis_client as rc

        monkeypatch.setattr(rc, "_redis_client", _ExplodingClient(OSError("redis gone")))
        monkeypatch.setattr(rc, "_redis_client_init_lock", object())

        with pytest.raises((OSError,)):
            await rc.close_redis_client()

        assert rc._redis_client_init_lock is None

    async def test_the_close_failure_is_still_raised_to_the_caller(self, monkeypatch: Any) -> None:
        """Reset always; report anyway. The CALLER decides whether it is fatal.

        `run_async_from_sync` treats it as best-effort; `shutdown_sequence` may not want to.
        Swallowing it here would take that choice away from both.
        """
        import src.infrastructure.cache.redis_client as rc

        monkeypatch.setattr(rc, "_redis_client", _ExplodingClient(RuntimeError("Event loop is closed")))

        with pytest.raises(RuntimeError, match="Event loop is closed"):
            await rc.close_redis_client()

    async def test_a_clean_close_still_clears_everything(self, monkeypatch: Any) -> None:
        import src.infrastructure.cache.redis_client as rc

        class _Clean:
            def __init__(self) -> None:
                self.closed = False

            async def close(self) -> None:
                self.closed = True

        client = _Clean()
        monkeypatch.setattr(rc, "_redis_client", client)

        await rc.close_redis_client()

        assert client.closed is True
        assert rc._redis_client is None


@pytest.mark.asyncio
class TestClosingAClientBoundToAnotherLoopIsNotAnError:
    """A singleton from a PREVIOUS loop must be disposed, not closed and reported as a failure.

    MEASURED in `apps/api/logs/pulsai.log` over 2026-08-31 07:54 -> 2026-09-01 13:35:

        170  RuntimeError: Event loop is closed
        161  "Redis cleanup after the Celery task failed; the task result is preserved."

    A full traceback per Celery task, in the owner's terminal, for a condition the code already
    knows how to handle. `get_redis_client` detects the loop mismatch on the way IN and disposes
    the stale client through `dispose_stale_redis_client_best_effort`, which logs at DEBUG. The
    way OUT had no such check: `run_async_from_sync(from_celery=True)` closes the singleton in a
    `finally` whether or not this task ever touched Redis, so a client bound to a loop that has
    since been torn down gets `pool.disconnect()` called on dead transports.

    Nothing was broken by it — the result survives, and connected_clients measured 78 with a
    healthy command mix, so this was noise rather than a leak. Noise that trains a reader to skim
    tracebacks is still worth removing, and the same helper the getter already uses removes it.
    """

    async def test_a_client_from_another_loop_is_disposed_quietly(self, monkeypatch: Any) -> None:
        import asyncio

        import src.infrastructure.cache.redis_client as rc

        client = _ExplodingClient(RuntimeError("Event loop is closed"))
        monkeypatch.setattr(rc, "_redis_client", client)
        monkeypatch.setattr(rc, "_redis_singleton_loop_id", id(asyncio.get_running_loop()) + 1)

        await rc.close_redis_client()

        assert client.close_attempted is True, "disposal still tries the clean close first"
        assert rc._redis_client is None
        assert rc._redis_singleton_loop_id is None

    async def test_a_client_on_the_current_loop_still_reports_its_failure(self, monkeypatch: Any) -> None:
        """The quiet path is for a FOREIGN loop only — a real close failure here is still real."""
        import asyncio

        import src.infrastructure.cache.redis_client as rc

        monkeypatch.setattr(rc, "_redis_client", _ExplodingClient(OSError("redis gone")))
        monkeypatch.setattr(rc, "_redis_singleton_loop_id", id(asyncio.get_running_loop()))

        with pytest.raises(OSError, match="redis gone"):
            await rc.close_redis_client()

        assert rc._redis_client is None

    async def test_an_unbound_singleton_keeps_the_old_behaviour(self, monkeypatch: Any) -> None:
        """No recorded loop id means nothing is known about provenance — do not invent a reason.

        I briefly changed this to go quiet, to kill the 11-per-hour `Event loop is closed`
        tracebacks the owner reported. That was the wrong seam: this function's contract is
        "reset always, REPORT anyway — the caller decides whether it is fatal", and swallowing
        here takes that choice from `shutdown_sequence` as well as from Celery. The noise is
        silenced in `_run_celery_coro_with_redis_cleanup`, which has already decided the close is
        best-effort. Two tests in this file caught the overreach immediately.
        """
        import src.infrastructure.cache.redis_client as rc

        monkeypatch.setattr(rc, "_redis_client", _ExplodingClient(RuntimeError("Event loop is closed")))
        monkeypatch.setattr(rc, "_redis_singleton_loop_id", None)

        with pytest.raises(RuntimeError, match="Event loop is closed"):
            await rc.close_redis_client()


@pytest.mark.asyncio
class TestTheClientDropsItsHandlesEvenOnFailure:
    """Same ordering defect one level down, in RedisClient.close()."""

    async def test_the_pool_handle_is_dropped_when_disconnect_raises(self) -> None:
        from src.infrastructure.cache.redis_client import RedisClient

        class _Pool:
            async def disconnect(self) -> None:
                raise RuntimeError("Event loop is closed")

        client = RedisClient.__new__(RedisClient)
        client._client = None
        client._pool = _Pool()

        with pytest.raises(RuntimeError):
            await client.close()

        assert client._pool is None, "a pool from a dead loop stayed attached and was reused"
