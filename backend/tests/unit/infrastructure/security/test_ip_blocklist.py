"""Behavior tests for Redis-backed IP blocklist helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.security.ip_blocklist import (
    abuse_log_redis_key,
    block_ip,
    block_redis_key,
    fetch_abuse_log_entries,
    is_ip_blocked,
    is_loopback_ip,
    list_blocked_ips,
    record_rate_limit_abuse_event,
    unblock_ip,
)


@pytest.mark.asyncio
async def test_is_ip_blocked_false_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.infrastructure.config.settings import settings

    monkeypatch.setattr(settings, "ip_block_enabled", False)
    assert await is_ip_blocked("203.0.113.1") is False


@pytest.mark.asyncio
async def test_is_ip_blocked_false_on_unknown_ip() -> None:
    assert await is_ip_blocked("unknown") is False


def test_is_loopback_ip_covers_v4_v6_and_rejects_public() -> None:
    assert is_loopback_ip("127.0.0.1") is True
    assert is_loopback_ip("::1") is True
    assert is_loopback_ip("203.0.113.10") is False
    assert is_loopback_ip("unknown") is False


@pytest.mark.asyncio
async def test_is_ip_blocked_false_for_loopback_without_redis() -> None:
    """Loopback must never 403 local FE↔API (rate-limit auto-block bricks localhost:3000)."""
    with patch(
        "src.infrastructure.security.ip_blocklist.get_redis_client",
        AsyncMock(side_effect=AssertionError("redis must not be queried for loopback")),
    ):
        assert await is_ip_blocked("127.0.0.1") is False
        assert await is_ip_blocked("::1") is False


@pytest.mark.asyncio
async def test_block_ip_refuses_loopback() -> None:
    with patch(
        "src.infrastructure.security.ip_blocklist.get_redis_client",
        AsyncMock(side_effect=AssertionError("redis must not be written for loopback")),
    ):
        assert (
            await block_ip(
                "127.0.0.1",
                reason="auto:rate_limit_strikes",
                blocked_by="auto",
                duration_seconds=3600,
            )
            is False
        )


@pytest.mark.asyncio
async def test_is_ip_blocked_uses_redis_exists() -> None:
    mock_client = MagicMock()
    mock_client.exists = AsyncMock(return_value=1)
    with patch(
        "src.infrastructure.security.ip_blocklist.get_redis_client",
        AsyncMock(return_value=mock_client),
    ):
        assert await is_ip_blocked("203.0.113.10") is True
    mock_client.exists.assert_awaited_once_with(block_redis_key("203.0.113.10"))


@pytest.mark.asyncio
async def test_is_ip_blocked_fail_open_on_error() -> None:
    with patch(
        "src.infrastructure.security.ip_blocklist.get_redis_client",
        AsyncMock(side_effect=RuntimeError("redis down")),
    ):
        assert await is_ip_blocked("203.0.113.2") is False


@pytest.mark.asyncio
async def test_block_and_unblock_round_trip() -> None:
    store: dict[str, dict] = {}
    ttls: dict[str, int | None] = {}

    client = MagicMock()

    async def set_json(key: str, value: dict, ex: int | None = None) -> bool:
        store[key] = dict(value)
        ttls[key] = ex
        return True

    async def get_json(key: str) -> dict | None:
        return store.get(key)

    async def delete(*keys: str) -> int:
        n = 0
        for k in keys:
            if k in store:
                del store[k]
                ttls.pop(k, None)
                n += 1
        return n

    async def exists(*keys: str) -> int:
        return sum(1 for k in keys if k in store)

    async def ttl(key: str) -> int:
        if key not in store:
            return -2
        ex = ttls.get(key)
        if ex is None:
            return -1
        return int(ex)

    client.set_json = AsyncMock(side_effect=set_json)
    client.get_json = AsyncMock(side_effect=get_json)
    client.delete = AsyncMock(side_effect=delete)
    client.exists = AsyncMock(side_effect=exists)
    client.ttl = AsyncMock(side_effect=ttl)

    with patch(
        "src.infrastructure.security.ip_blocklist.get_redis_client",
        AsyncMock(return_value=client),
    ):
        ok = await block_ip(
            "203.0.113.5",
            reason="test",
            blocked_by="admin",
            duration_seconds=60,
        )
        assert ok is True
        assert await is_ip_blocked("203.0.113.5") is True
        assert await unblock_ip("203.0.113.5") is True
        assert await is_ip_blocked("203.0.113.5") is False


@pytest.mark.asyncio
async def test_list_blocked_ips_empty_on_error() -> None:
    with patch(
        "src.infrastructure.security.ip_blocklist.get_redis_client",
        AsyncMock(side_effect=RuntimeError("down")),
    ):
        assert await list_blocked_ips() == []


def test_block_redis_key_uses_testing_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TESTING", "true")

    key = block_redis_key("203.0.113.7")

    assert key.startswith("pulsai:test:ip:block:v1:")


@pytest.mark.asyncio
async def test_record_and_fetch_abuse_log(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TESTING", raising=False)

    z_entries: list[tuple[str, float]] = []

    client = MagicMock()

    async def zadd(_name: str, mapping: dict[str, float]) -> int:
        for member, score in mapping.items():
            z_entries.append((member, float(score)))
        return len(mapping)

    async def zcard(_name: str) -> int:
        return len(z_entries)

    async def zremrangebyrank(_name: str, _start: int, _end: int) -> int:
        return 0

    async def zrevrange(name: str, start: int, end: int, *, withscores: bool = False) -> list[str]:
        assert name == abuse_log_redis_key()
        assert withscores is False
        sorted_e = sorted(z_entries, key=lambda x: -x[1])
        slice_e = sorted_e[start : end + 1]
        return [m for m, _ in slice_e]

    client.zadd = AsyncMock(side_effect=zadd)
    client.zcard = AsyncMock(side_effect=zcard)
    client.zremrangebyrank = AsyncMock(side_effect=zremrangebyrank)
    client.zrevrange = AsyncMock(side_effect=zrevrange)

    with patch(
        "src.infrastructure.security.ip_blocklist.get_redis_client",
        AsyncMock(return_value=client),
    ):
        await record_rate_limit_abuse_event(ip="1.1.1.1", endpoint="/x")
        out = await fetch_abuse_log_entries(limit=10)
        assert len(out) >= 1
        assert out[0].get("ip") == "1.1.1.1"
        assert out[0].get("endpoint") == "/x"


@pytest.mark.asyncio
async def test_record_rate_limit_abuse_event_skips_persistence_when_testing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TESTING", "true")

    with patch(
        "src.infrastructure.security.ip_blocklist.get_redis_client",
        AsyncMock(),
    ) as get_client:
        await record_rate_limit_abuse_event(ip="1.1.1.1", endpoint="/x")

    get_client.assert_not_awaited()
