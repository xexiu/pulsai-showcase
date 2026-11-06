"""Shared Redis client factories for sync and dedicated async ownership."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse, urlunparse

import redis as sync_redis
import redis.asyncio as async_redis

from src.infrastructure.config.settings import settings

_XDIST_WORKER_PREFIX = "gw"


def resolve_redis_url() -> str:
    """
    Resolve the Redis URL for the current process.

    Under pytest-xdist, each worker uses a dedicated Redis logical DB (gw0 → /1,
    gw1 → /2, …) so token blacklist and other Redis-backed auth state cannot leak
    across parallel workers. Serial test runs keep ``settings.redis_url`` unchanged.
    """
    url = settings.redis_url
    if os.environ.get("TESTING") != "true":
        return url

    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if not worker or worker == "master" or not worker.startswith(_XDIST_WORKER_PREFIX):
        return url

    try:
        db_index = int(worker[len(_XDIST_WORKER_PREFIX) :]) + 1
    except ValueError:
        return url

    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{db_index}"))


def create_sync_redis_client(
    *,
    socket_timeout: float | None = 5.0,
) -> sync_redis.Redis[str]:
    """
    Create a sync Redis client with the shared runtime connection contract.

    socket_timeout: Prevents Celery tasks (e.g. get_scheduled_task_enabled_sync) from
    blocking forever if Redis is slow or unreachable; default 5s.
    """
    return sync_redis.from_url(
        resolve_redis_url(),
        decode_responses=True,
        health_check_interval=30,
        socket_timeout=socket_timeout,
        socket_connect_timeout=socket_timeout,
    )


def get_async_redis_connection_kwargs(
    *,
    max_connections: int | None = None,
    socket_timeout: float | None = 5.0,
) -> dict[str, Any]:
    """Return the shared async Redis connection contract."""
    kwargs: dict[str, Any] = {
        "decode_responses": True,
        "health_check_interval": 30,
        "protocol": 3,
        "socket_timeout": socket_timeout,
        "socket_connect_timeout": socket_timeout,
    }
    if max_connections is not None:
        kwargs["max_connections"] = max_connections
    return kwargs


def create_async_redis_client(
    *,
    socket_timeout: float | None = 5.0,
) -> async_redis.Redis[str]:
    """
    Create a dedicated async Redis client outside the app singleton.

    Args:
        socket_timeout: Per-operation timeout. Pass ``None`` for Pub/Sub
            listeners that block indefinitely waiting for messages.
    """
    return async_redis.from_url(
        resolve_redis_url(),
        **get_async_redis_connection_kwargs(socket_timeout=socket_timeout),
    )
