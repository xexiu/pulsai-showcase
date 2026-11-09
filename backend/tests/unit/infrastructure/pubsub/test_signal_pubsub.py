"""
Behavior tests for the Redis Pub/Sub signal bridge (Celery -> WebSocket).

Covers:
1. Regression: subscriber MUST use socket_timeout=None (the production timeout bug)
2. Publisher uses default timeout, serializes JSON, closes client
3. Subscriber dispatches messages to the on_signal callback
4. Invalid JSON is logged and swallowed (listener survives)
5. Callback errors are logged and swallowed (listener survives)
6. Connection loss triggers reconnect with configured pub/sub backoff
7. Cleanup (unsubscribe + close) always runs, even on error

Each test uses a deterministic exit pattern:
- listen() yields test messages then raises ConnectionError (breaks inner loop)
- asyncio.sleep is patched to raise CancelledError (breaks outer while-True)
This avoids real waits and ensures the test exits cleanly.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.pubsub.signal_pubsub import (
    SIGNAL_CHANNEL,
    publish_signal,
    subscribe_and_broadcast,
)
from src.shared.constants.runtime import REDIS_PUBSUB_RECONNECT_DELAY_SECONDS


def _make_pubsub(messages: list[dict[str, Any]] | None = None) -> AsyncMock:
    """
    Build a mock PubSub whose listen() yields *messages* then raises
    ``ConnectionError`` to deterministically exit the inner loop.
    """
    items = messages or []

    async def _listen() -> Any:
        for m in items:
            yield m
        raise ConnectionError("test: break inner loop")

    pubsub = AsyncMock()
    pubsub.listen = _listen
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    return pubsub


def _make_client(pubsub: AsyncMock) -> MagicMock:
    """MagicMock (not AsyncMock) because client.pubsub() is a sync call."""
    client = MagicMock()
    client.pubsub.return_value = pubsub
    return client


def _sleep_raises_cancelled(*_args: Any, **_kwargs: Any) -> Any:
    """Patch target for asyncio.sleep → breaks the while-True reconnect loop."""
    raise asyncio.CancelledError


# ---------------------------------------------------------------------------
# 1. REGRESSION: subscriber must use socket_timeout=None
# ---------------------------------------------------------------------------


class TestSubscriberSocketTimeout:
    """
    REGRESSION: subscribe_and_broadcast MUST create its Redis client with
    socket_timeout=None.

    WHY: Pub/Sub listen() blocks indefinitely waiting for messages. A finite
    socket_timeout (e.g. 5s default) causes TimeoutError on every idle period,
    triggering a reconnect storm that floods logs and drops messages.
    """

    @pytest.mark.asyncio
    async def test_subscriber_creates_client_with_socket_timeout_none(self) -> None:
        """subscribe_and_broadcast MUST pass socket_timeout=None to the factory."""
        pubsub = _make_pubsub()
        client = _make_client(pubsub)

        with (
            patch(
                "src.infrastructure.pubsub.signal_pubsub.create_async_redis_client",
                return_value=client,
            ) as factory,
            patch(
                "src.infrastructure.pubsub.signal_pubsub.close_redis_resource",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", side_effect=_sleep_raises_cancelled),
            pytest.raises(asyncio.CancelledError),
        ):
            await subscribe_and_broadcast(on_signal=AsyncMock())

        factory.assert_called_with(socket_timeout=None)

    @pytest.mark.asyncio
    async def test_publisher_uses_default_timeout_not_none(self) -> None:
        """publish_signal must NOT override socket_timeout (uses bounded default)."""
        client = AsyncMock()
        client.publish = AsyncMock(return_value=1)

        with (
            patch(
                "src.infrastructure.pubsub.signal_pubsub.create_async_redis_client",
                return_value=client,
            ) as factory,
            patch(
                "src.infrastructure.pubsub.signal_pubsub.close_redis_resource",
                new_callable=AsyncMock,
            ),
        ):
            await publish_signal({"symbol": "BTC/USDT", "action": "BUY"})

        factory.assert_called_once_with()


# ---------------------------------------------------------------------------
# 2. Publisher behavior
# ---------------------------------------------------------------------------


class TestPublishSignal:
    """publish_signal serializes to JSON, publishes to SIGNAL_CHANNEL, closes client."""

    @pytest.mark.asyncio
    async def test_publishes_json_to_correct_channel(self) -> None:
        """Signal data is JSON-serialized and sent to SIGNAL_CHANNEL."""
        signal = {"symbol": "BTC/USDT", "action": "BUY", "confidence": 0.92}

        client = AsyncMock()
        client.publish = AsyncMock(return_value=2)

        with (
            patch(
                "src.infrastructure.pubsub.signal_pubsub.create_async_redis_client",
                return_value=client,
            ),
            patch(
                "src.infrastructure.pubsub.signal_pubsub.close_redis_resource",
                new_callable=AsyncMock,
            ),
        ):
            await publish_signal(signal)

        client.publish.assert_called_once_with(SIGNAL_CHANNEL, json.dumps(signal))

    @pytest.mark.asyncio
    async def test_client_is_always_closed_after_publish(self) -> None:
        """Redis client is closed even when publish succeeds."""
        client = AsyncMock()
        client.publish = AsyncMock(return_value=0)

        with (
            patch(
                "src.infrastructure.pubsub.signal_pubsub.create_async_redis_client",
                return_value=client,
            ),
            patch(
                "src.infrastructure.pubsub.signal_pubsub.close_redis_resource",
                new_callable=AsyncMock,
            ) as close_mock,
        ):
            await publish_signal({"symbol": "X"})

        close_mock.assert_called_once_with(client)

    @pytest.mark.asyncio
    async def test_publish_failure_is_logged_not_raised(self) -> None:
        """If Redis publish fails, error is logged and does NOT propagate."""
        client = AsyncMock()
        client.publish = AsyncMock(side_effect=ConnectionError("Redis down"))

        with (
            patch(
                "src.infrastructure.pubsub.signal_pubsub.create_async_redis_client",
                return_value=client,
            ),
            patch(
                "src.infrastructure.pubsub.signal_pubsub.close_redis_resource",
                new_callable=AsyncMock,
            ),
        ):
            await publish_signal({"symbol": "X"})


# ---------------------------------------------------------------------------
# 3. Subscriber dispatch
# ---------------------------------------------------------------------------


class TestSubscriberDispatch:
    """subscribe_and_broadcast forwards valid messages to on_signal callback."""

    @pytest.mark.asyncio
    async def test_dispatches_valid_signal_to_callback(self) -> None:
        """on_signal is called with (symbol, parsed_data) for valid message."""
        signal_data = {"symbol": "ETH/USDT", "action": "SELL", "confidence": 0.85}
        pubsub = _make_pubsub([{"type": "message", "data": json.dumps(signal_data)}])
        client = _make_client(pubsub)
        callback = AsyncMock()

        with (
            patch(
                "src.infrastructure.pubsub.signal_pubsub.create_async_redis_client",
                return_value=client,
            ),
            patch(
                "src.infrastructure.pubsub.signal_pubsub.close_redis_resource",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", side_effect=_sleep_raises_cancelled),
            pytest.raises(asyncio.CancelledError),
        ):
            await subscribe_and_broadcast(on_signal=callback)

        callback.assert_called_once_with("ETH/USDT", signal_data)

    @pytest.mark.asyncio
    async def test_skips_non_message_types(self) -> None:
        """Subscribe confirmations (type != 'message') are silently ignored."""
        messages = [
            {"type": "subscribe", "data": 1},
            {"type": "message", "data": json.dumps({"symbol": "BTC/USDT"})},
        ]
        pubsub = _make_pubsub(messages)
        client = _make_client(pubsub)
        callback = AsyncMock()

        with (
            patch(
                "src.infrastructure.pubsub.signal_pubsub.create_async_redis_client",
                return_value=client,
            ),
            patch(
                "src.infrastructure.pubsub.signal_pubsub.close_redis_resource",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", side_effect=_sleep_raises_cancelled),
            pytest.raises(asyncio.CancelledError),
        ):
            await subscribe_and_broadcast(on_signal=callback)

        callback.assert_called_once_with("BTC/USDT", {"symbol": "BTC/USDT"})

    @pytest.mark.asyncio
    async def test_missing_symbol_defaults_to_empty_string(self) -> None:
        """Signal without 'symbol' key uses '' as fallback."""
        pubsub = _make_pubsub(
            [{"type": "message", "data": json.dumps({"action": "HOLD"})}],
        )
        client = _make_client(pubsub)
        callback = AsyncMock()

        with (
            patch(
                "src.infrastructure.pubsub.signal_pubsub.create_async_redis_client",
                return_value=client,
            ),
            patch(
                "src.infrastructure.pubsub.signal_pubsub.close_redis_resource",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", side_effect=_sleep_raises_cancelled),
            pytest.raises(asyncio.CancelledError),
        ):
            await subscribe_and_broadcast(on_signal=callback)

        callback.assert_called_once_with("", {"action": "HOLD"})


# ---------------------------------------------------------------------------
# 4. Error resilience
# ---------------------------------------------------------------------------


class TestSubscriberErrorResilience:
    """The listener must survive bad messages and callback errors."""

    @pytest.mark.asyncio
    async def test_invalid_json_is_logged_not_raised(self) -> None:
        """Garbled JSON is logged as warning; next valid message still processed."""
        messages = [
            {"type": "message", "data": "NOT-VALID-JSON{{{"},
            {"type": "message", "data": json.dumps({"symbol": "BTC/USDT"})},
        ]
        pubsub = _make_pubsub(messages)
        client = _make_client(pubsub)
        callback = AsyncMock()

        with (
            patch(
                "src.infrastructure.pubsub.signal_pubsub.create_async_redis_client",
                return_value=client,
            ),
            patch(
                "src.infrastructure.pubsub.signal_pubsub.close_redis_resource",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", side_effect=_sleep_raises_cancelled),
            pytest.raises(asyncio.CancelledError),
        ):
            await subscribe_and_broadcast(on_signal=callback)

        callback.assert_called_once_with("BTC/USDT", {"symbol": "BTC/USDT"})

    @pytest.mark.asyncio
    async def test_callback_error_does_not_crash_listener(self) -> None:
        """If on_signal raises, the error is logged and next message is processed."""
        messages = [
            {"type": "message", "data": json.dumps({"symbol": "FAIL"})},
            {"type": "message", "data": json.dumps({"symbol": "OK"})},
        ]
        pubsub = _make_pubsub(messages)
        client = _make_client(pubsub)
        callback = AsyncMock(side_effect=[RuntimeError("boom"), None])

        with (
            patch(
                "src.infrastructure.pubsub.signal_pubsub.create_async_redis_client",
                return_value=client,
            ),
            patch(
                "src.infrastructure.pubsub.signal_pubsub.close_redis_resource",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", side_effect=_sleep_raises_cancelled),
            pytest.raises(asyncio.CancelledError),
        ):
            await subscribe_and_broadcast(on_signal=callback)

        assert callback.call_count == 2
        callback.assert_any_call("FAIL", {"symbol": "FAIL"})
        callback.assert_any_call("OK", {"symbol": "OK"})


# ---------------------------------------------------------------------------
# 5. Reconnect behavior
# ---------------------------------------------------------------------------


class TestSubscriberReconnect:
    """Connection loss enters the except branch with 5s sleep."""

    @pytest.mark.asyncio
    async def test_connection_error_triggers_sleep_before_retry(self) -> None:
        """When listen() raises, reconnect backoff sleep runs before retry."""
        pubsub = _make_pubsub()
        client = _make_client(pubsub)

        sleep_mock = AsyncMock(side_effect=_sleep_raises_cancelled)

        with (
            patch(
                "src.infrastructure.pubsub.signal_pubsub.create_async_redis_client",
                return_value=client,
            ),
            patch(
                "src.infrastructure.pubsub.signal_pubsub.close_redis_resource",
                new_callable=AsyncMock,
            ),
            patch("asyncio.sleep", sleep_mock),
            pytest.raises(asyncio.CancelledError),
        ):
            await subscribe_and_broadcast(on_signal=AsyncMock())

        sleep_mock.assert_called_once_with(REDIS_PUBSUB_RECONNECT_DELAY_SECONDS)


# ---------------------------------------------------------------------------
# 6. Cleanup (unsubscribe + close)
# ---------------------------------------------------------------------------


class TestSubscriberCleanup:
    """Cleanup must run in the finally block regardless of exit path."""

    @pytest.mark.asyncio
    async def test_unsubscribe_and_close_on_disconnect(self) -> None:
        """Both pubsub.unsubscribe and close_redis_resource run in finally."""
        pubsub = _make_pubsub()
        client = _make_client(pubsub)
        close_mock = AsyncMock()

        with (
            patch(
                "src.infrastructure.pubsub.signal_pubsub.create_async_redis_client",
                return_value=client,
            ),
            patch(
                "src.infrastructure.pubsub.signal_pubsub.close_redis_resource",
                close_mock,
            ),
            patch("asyncio.sleep", side_effect=_sleep_raises_cancelled),
            pytest.raises(asyncio.CancelledError),
        ):
            await subscribe_and_broadcast(on_signal=AsyncMock())

        pubsub.unsubscribe.assert_called_with(SIGNAL_CHANNEL)
        close_mock.assert_called_with(client)


# ---------------------------------------------------------------------------
# 7. Redis connections factory: socket_timeout override
# ---------------------------------------------------------------------------


class TestAsyncRedisClientTimeoutOverride:
    """create_async_redis_client must pass through socket_timeout to Redis kwargs."""

    def test_default_timeout_is_5s(self) -> None:
        """Without override, socket_timeout=5.0 (bounded for regular commands)."""
        mock_client = MagicMock()
        with patch(
            "src.infrastructure.cache.redis_connections.async_redis.from_url",
            return_value=mock_client,
        ) as from_url:
            from src.infrastructure.cache.redis_connections import create_async_redis_client

            create_async_redis_client()

        kwargs = from_url.call_args
        assert kwargs[1]["socket_timeout"] == 5.0
        assert kwargs[1]["socket_connect_timeout"] == 5.0

    def test_none_timeout_for_pubsub_listeners(self) -> None:
        """socket_timeout=None disables timeout for long-lived Pub/Sub listeners."""
        mock_client = MagicMock()
        with patch(
            "src.infrastructure.cache.redis_connections.async_redis.from_url",
            return_value=mock_client,
        ) as from_url:
            from src.infrastructure.cache.redis_connections import create_async_redis_client

            create_async_redis_client(socket_timeout=None)

        kwargs = from_url.call_args
        assert kwargs[1]["socket_timeout"] is None
        assert kwargs[1]["socket_connect_timeout"] is None

    def test_sync_client_also_supports_timeout_override(self) -> None:
        """Sync client factory propagates socket_timeout=None for sync Pub/Sub."""
        mock_client = MagicMock()
        with patch(
            "src.infrastructure.cache.redis_connections.sync_redis.from_url",
            return_value=mock_client,
        ) as from_url:
            from src.infrastructure.cache.redis_connections import create_sync_redis_client

            create_sync_redis_client(socket_timeout=None)

        kwargs = from_url.call_args
        assert kwargs[1]["socket_timeout"] is None
        assert kwargs[1]["socket_connect_timeout"] is None
