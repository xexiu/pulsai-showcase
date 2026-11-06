from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_async_redis_connection_kwargs_define_shared_contract() -> None:
    """Async Redis clients should share one connection keyword contract."""
    from src.infrastructure.cache.redis_connections import get_async_redis_connection_kwargs

    assert get_async_redis_connection_kwargs() == {
        "decode_responses": True,
        "health_check_interval": 30,
        "protocol": 3,
        "socket_timeout": 5.0,
        "socket_connect_timeout": 5.0,
    }
    assert get_async_redis_connection_kwargs(max_connections=50) == {
        "decode_responses": True,
        "health_check_interval": 30,
        "protocol": 3,
        "socket_timeout": 5.0,
        "socket_connect_timeout": 5.0,
        "max_connections": 50,
    }


def test_create_sync_redis_client_uses_shared_settings() -> None:
    """Sync Redis callers should share one constructor contract."""
    from src.infrastructure.cache.redis_connections import create_sync_redis_client

    mock_client = MagicMock()
    with (
        patch(
            "src.infrastructure.cache.redis_connections.resolve_redis_url",
            return_value="redis://127.0.0.1:6379/2",
        ),
        patch(
            "src.infrastructure.cache.redis_connections.sync_redis.from_url",
            return_value=mock_client,
            autospec=True,
        ) as from_url,
    ):
        result = create_sync_redis_client()

    assert result is mock_client
    from_url.assert_called_once_with(
        "redis://127.0.0.1:6379/2",
        decode_responses=True,
        health_check_interval=30,
        socket_timeout=5.0,
        socket_connect_timeout=5.0,
    )


def test_create_async_redis_client_uses_shared_settings() -> None:
    """Async Redis callers should share one constructor contract."""
    from src.infrastructure.cache.redis_connections import create_async_redis_client

    mock_client = MagicMock()
    with (
        patch(
            "src.infrastructure.cache.redis_connections.resolve_redis_url",
            return_value="redis://127.0.0.1:6379/2",
        ),
        patch(
            "src.infrastructure.cache.redis_connections.async_redis.from_url",
            return_value=mock_client,
            autospec=True,
        ) as from_url,
    ):
        result = create_async_redis_client()

    assert result is mock_client
    from_url.assert_called_once_with(
        "redis://127.0.0.1:6379/2",
        decode_responses=True,
        health_check_interval=30,
        protocol=3,
        socket_timeout=5.0,
        socket_connect_timeout=5.0,
    )
