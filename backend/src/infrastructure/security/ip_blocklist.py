"""
Redis-backed IP blocklist and rate-limit abuse log (sorted set).

Used by IPBlockMiddleware, auto-ban after repeated 429s, and admin IP Security API.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from src.infrastructure.cache.redis_client import get_redis_client
from src.infrastructure.config.settings import settings
from src.shared.constants.runtime import is_testing_runtime, namespaced_runtime_redis_key

logger = logging.getLogger(__name__)

# Redis TTL sentinel values (redis-py)
_REDIS_TTL_NO_EXPIRY = -1
_REDIS_TTL_KEY_MISSING = -2

IP_BLOCK_KEY_PREFIX = "ip:block:v1:"
ABUSE_LOG_ZSET_KEY = "abuse:rate_limit:v1"


def _ip_key_suffix(ip: str) -> str:
    return hashlib.sha256(ip.strip().encode("utf-8")).hexdigest()


def ip_block_key_prefix() -> str:
    """Return the runtime-scoped Redis prefix for blocked IP entries."""
    return namespaced_runtime_redis_key(IP_BLOCK_KEY_PREFIX)


def abuse_log_redis_key() -> str:
    """Return the runtime-scoped Redis key for the abuse-log sorted set."""
    return namespaced_runtime_redis_key(ABUSE_LOG_ZSET_KEY)


def block_redis_key(ip: str) -> str:
    return f"{ip_block_key_prefix()}{_ip_key_suffix(ip)}"


def is_loopback_ip(ip: str) -> bool:
    """True for 127.0.0.0/8 and ::1. Local FE+API share this address."""
    try:
        return ipaddress.ip_address(ip.strip()).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class BlockedIPEntry:
    """One blocked IP row for admin API."""

    ip: str
    reason: str
    blocked_at_iso: str
    blocked_by: str
    ttl_seconds: int | None  # None = permanent


async def is_ip_blocked(ip: str) -> bool:
    """Return True if IP is blocked (O(1) EXISTS). Fail-open if Redis unavailable."""
    if not settings.ip_block_enabled:
        return False
    if not ip or ip == "unknown" or is_loopback_ip(ip):
        return False
    try:
        client = await get_redis_client()
        n = await client.exists(block_redis_key(ip))
        return n > 0
    except Exception as exc:
        logger.warning("ip_blocklist is_blocked failed-open: %s", exc)
        return False


async def block_ip(
    ip: str,
    *,
    reason: str,
    blocked_by: str,
    duration_seconds: int | None,
) -> bool:
    """
    Block an IP. duration_seconds None = permanent (no TTL).

    Returns False if Redis fails (caller may still log).
    """
    if not ip or ip == "unknown" or is_loopback_ip(ip):
        return False
    payload: dict[str, Any] = {
        "ip": ip,
        "reason": reason,
        "blocked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "blocked_by": blocked_by,
    }
    key = block_redis_key(ip)
    try:
        client = await get_redis_client()
        ok = await client.set_json(key, payload, ex=duration_seconds)
        return bool(ok)
    except Exception as exc:
        logger.exception("ip_blocklist block_ip failed: %s", exc)
        return False


async def unblock_ip(ip: str) -> bool:
    """Remove block. Returns True if key was deleted."""
    if not ip:
        return False
    try:
        client = await get_redis_client()
        deleted = await client.delete(block_redis_key(ip))
        return deleted > 0
    except Exception as exc:
        logger.exception("ip_blocklist unblock_ip failed: %s", exc)
        return False


async def get_block_info(ip: str) -> BlockedIPEntry | None:
    """Return metadata for one IP if blocked."""
    try:
        client = await get_redis_client()
        key = block_redis_key(ip)
        data = await client.get_json(key)
        if not data or not isinstance(data, dict):
            return None
        ttl = await client.ttl(key)
        if ttl == _REDIS_TTL_KEY_MISSING:
            return None
        ttl_seconds: int | None = None if ttl == _REDIS_TTL_NO_EXPIRY else ttl
        return BlockedIPEntry(
            ip=str(data.get("ip", ip)),
            reason=str(data.get("reason", "")),
            blocked_at_iso=str(data.get("blocked_at", "")),
            blocked_by=str(data.get("blocked_by", "")),
            ttl_seconds=ttl_seconds,
        )
    except Exception as exc:
        logger.warning("ip_blocklist get_block_info failed: %s", exc)
        return None


async def list_blocked_ips() -> list[BlockedIPEntry]:
    """Scan all ip:block keys and return entries (admin list). Uses pipeline to reduce round-trips."""
    out: list[BlockedIPEntry] = []
    try:
        client = await get_redis_client()
        keys = await client.scan_keys(f"{ip_block_key_prefix()}*")
        if not keys:
            return out

        async with client.pipeline(transaction=False) as pipe:
            for key in keys:
                await pipe.get(key)
                await pipe.ttl(key)
            results = await pipe.execute()

        for i in range(0, len(results), 2):
            raw_data = results[i]
            ttl = results[i + 1]
            key = keys[i // 2]
            if raw_data is None:
                continue
            data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            if not isinstance(data, dict):
                continue
            if ttl == _REDIS_TTL_KEY_MISSING:
                continue
            ip_val = str(data.get("ip", ""))
            ttl_seconds = None if ttl == _REDIS_TTL_NO_EXPIRY else ttl
            out.append(
                BlockedIPEntry(
                    ip=ip_val or key,
                    reason=str(data.get("reason", "")),
                    blocked_at_iso=str(data.get("blocked_at", "")),
                    blocked_by=str(data.get("blocked_by", "")),
                    ttl_seconds=ttl_seconds,
                )
            )
        return out
    except Exception as exc:
        logger.warning("ip_blocklist list_blocked_ips failed: %s", exc)
        return []


async def record_rate_limit_abuse_event(*, ip: str, endpoint: str) -> None:
    """Append one rate-limit rejection to the admin abuse log (trimmed ZSET)."""
    if is_testing_runtime():
        logger.debug("Skipping rate-limit abuse log persistence during TESTING=true")
        return

    try:
        client = await get_redis_client()
        now = time.time()
        member = json.dumps(
            {"ip": ip, "endpoint": endpoint, "at": now},
            separators=(",", ":"),
        )
        redis_key = abuse_log_redis_key()
        await client.zadd(redis_key, {member: now})
        total = await client.zcard(redis_key)
        max_entries = max(1, settings.abuse_log_max_entries)
        if total > max_entries:
            await client.zremrangebyrank(redis_key, 0, total - max_entries - 1)
    except Exception as exc:
        logger.debug("record_rate_limit_abuse_event skipped: %s", exc)


async def fetch_abuse_log_entries(*, limit: int = 100) -> list[dict[str, Any]]:
    """Recent abuse log entries (newest first)."""
    try:
        client = await get_redis_client()
        raw = await client.zrevrange(abuse_log_redis_key(), 0, limit - 1, withscores=False)
        out: list[dict[str, Any]] = []
        for item in raw:
            try:
                parsed = json.loads(str(item))
                if isinstance(parsed, dict):
                    out.append(parsed)
            except json.JSONDecodeError:
                continue
        return out
    except Exception as exc:
        logger.warning("fetch_abuse_log_entries failed: %s", exc)
        return []


async def increment_rate_limit_strike(ip: str) -> int:
    """
    Increment per-IP strike counter (429 rejections). TTL = strikes window.

    Returns new count.
    """
    window_sec = max(60, settings.ip_auto_block_strikes_window_minutes * 60)
    key = namespaced_runtime_redis_key(f"ip:strikes:v1:{_ip_key_suffix(ip)}")
    try:
        client = await get_redis_client()
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window_sec)
        return count
    except Exception as exc:
        logger.debug("increment_rate_limit_strike failed: %s", exc)
        return 0


async def load_permanent_ip_blocks_from_settings() -> None:
    """At startup: ensure env-listed IPs are blocked (permanent)."""
    raw = settings.ip_block_permanent_ips.strip()
    if not raw:
        return
    for part in raw.split(","):
        ip = part.strip()
        if not ip:
            continue
        await block_ip(
            ip,
            reason="env:ip_block_permanent_ips",
            blocked_by="config",
            duration_seconds=None,
        )
