"""SHUTDOWNREDIS-1: a cache read that races Redis teardown is a clean miss, not an ERROR + traceback.

callers: pytest only.
affected API: pins ``RedisClient.is_connected()`` and ``OHLCVCache``'s behaviour on a client that
    is not (or no longer) connected.
data schemas: none.

REUSE-AUDIT: considered tests/unit/infrastructure/test_ohlcv_cache_toctou_locking.py (locking
under concurrency, not the closed-client state) and
tests/unit/infrastructure/cache/test_redis_client_close_resets.py (the singleton reset, not a
consumer holding a closed instance). Neither covers a consumer reading after close.

WHY. Measured in apps/api/logs/pulsai.log on 2026-09-23 at 09:48:46 and again at 10:09:54: every
local API reload logged

    ERROR | ohlcv_cache | Error reading OHLCV cache for ohlcv:btc_usdt:5m:
        Redis client not connected. Call connect() first.   (+ full traceback)

between "Redis client closed" and "pulsai_api_shutdown_complete" -- a 5m chart read still in
flight when lifespan closed Redis. RedisClient.client raises RuntimeError once closed, and
OHLCVCache.get turned that into logger.exception. The same would fire on EVERY read in the
degraded no-Redis startup mode. Not connected is a known, expected state, so it is checked as a
precondition (a cheap miss), while a genuine Redis error on a live client keeps its ERROR and
traceback -- the falsifier below pins that the fix hides nothing real.
"""

from __future__ import annotations

import logging
from typing import Any

import polars as pl
import pytest
from redis import exceptions as redis_exceptions

from src.infrastructure.cache.ohlcv_cache import OHLCVCache
from src.infrastructure.cache.redis_client import RedisClient

_URL = "redis://127.0.0.1:6379/0"


def _closed_client() -> RedisClient:
    """A client in exactly the post-``close()`` state: constructed, handle dropped."""
    return RedisClient(_URL)


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [1_700_000_000_000],
            "open": [1.0],
            "high": [2.0],
            "low": [0.5],
            "close": [1.5],
            "volume": [10.0],
        }
    )


def _errors(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.levelno >= logging.ERROR or r.exc_info]


def test_is_connected_tracks_whether_the_client_holds_a_handle() -> None:
    client = _closed_client()
    assert client.is_connected() is False

    client._client = object()  # type: ignore[assignment]
    assert client.is_connected() is True


@pytest.mark.asyncio
async def test_ohlcv_read_after_redis_close_logs_no_error_traceback(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    result = await OHLCVCache(_closed_client()).get("BTC/USDT", "5m")

    assert result is None, "a closed client is a cache miss, so the caller falls back to the DB"
    assert _errors(caplog) == [], [r.getMessage() for r in _errors(caplog)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "args", "neutral"),
    [
        ("set", ("BTC/USDT", "5m", "frame"), False),
        ("append", ("BTC/USDT", "5m", {"timestamp": 1_700_000_000_000, "close": 1.0}), False),
        ("update_last_candle", ("BTC/USDT", "5m", {"timestamp": 1_700_000_000_000, "close": 1.0}), False),
        ("delete", ("BTC/USDT", "5m"), False),
        ("get_last_timestamp", ("BTC/USDT", "5m"), None),
        ("get_candle_count", ("BTC/USDT", "5m"), 0),
    ],
)
async def test_every_cache_operation_treats_a_closed_client_as_unavailable(
    method: str, args: tuple[Any, ...], neutral: Any, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    call_args = tuple(_frame() if a == "frame" else a for a in args)

    result = await getattr(OHLCVCache(_closed_client()), method)(*call_args)

    assert result == neutral
    assert _errors(caplog) == [], [r.getMessage() for r in _errors(caplog)]


class _BrokenRedis:
    """A CONNECTED client whose server call fails -- a real outage, not teardown."""

    async def get(self, _key: str) -> str:
        raise ConnectionError("connection reset by peer")


class _TeardownMidCall:
    """A LIVE client whose call is cut by lifespan closing Redis WHILE it is in flight.

    The precondition (`_unavailable`) passed before the await; the close landed during it. Measured
    2026-09-28..10-01: 4 of 4 'Connection closed by server' / 'Error UNKNOWN while writing to socket'
    ERRORs in pulsai.log sat inside the API's lifespan shutdown, after 'Redis client closed'.
    """

    def __init__(self, owner: RedisClient) -> None:
        self._owner = owner

    def _cut(self) -> None:
        self._owner._client = None  # what RedisClient.close() does first, before awaiting the close
        raise redis_exceptions.ConnectionError("Connection closed by server.")

    async def get(self, _key: str) -> str:
        self._cut()
        return ""

    async def set(self, _key: str, _value: bytes, ex: int | None = None, nx: bool = False) -> bool:
        """redis-py's set, as RedisDataOps.set calls it (ex and nx)."""
        del ex, nx
        self._cut()
        return False


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "args", "neutral"), [("get", ("BTC/USDT", "12h"), None), ("set", ("BTC/USDT", "12h", "frame"), False)])
async def test_a_close_landing_mid_call_is_a_clean_miss_not_an_error(
    method: str, args: tuple[Any, ...], neutral: Any, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    client = _closed_client()
    client._client = _TeardownMidCall(client)  # type: ignore[assignment]
    call_args = tuple(_frame() if a == "frame" else a for a in args)

    result = await getattr(OHLCVCache(client), method)(*call_args)

    assert result == neutral
    assert _errors(caplog) == [], [r.getMessage() for r in _errors(caplog)]


class _RedisOutageOnLiveClient:
    """The same Redis-typed error as the teardown case, but the client is STILL connected: a real outage."""

    async def get(self, _key: str) -> str:
        raise redis_exceptions.ConnectionError("Connection closed by server.")


@pytest.mark.asyncio
async def test_a_redis_typed_failure_on_a_still_connected_client_keeps_its_error(caplog: pytest.LogCaptureFixture) -> None:
    """Falsifier for the teardown clause: the error TYPE must not buy silence, only a closed client does."""
    client = _closed_client()
    client._client = _RedisOutageOnLiveClient()  # type: ignore[assignment]

    result = await OHLCVCache(client).get("BTC/USDT", "12h")

    assert result is None
    assert any(r.levelno >= logging.ERROR and r.exc_info for r in caplog.records), "a live-client Redis outage lost its ERROR"


@pytest.mark.asyncio
async def test_a_real_redis_failure_on_a_live_client_still_logs_an_error(caplog: pytest.LogCaptureFixture) -> None:
    """Falsifier: the precondition must not swallow genuine failures."""
    client = _closed_client()
    client._client = _BrokenRedis()  # type: ignore[assignment]

    result = await OHLCVCache(client).get("BTC/USDT", "5m")

    assert result is None
    assert any(r.levelno >= logging.ERROR and r.exc_info for r in caplog.records), "a live-client failure lost its ERROR + traceback"
