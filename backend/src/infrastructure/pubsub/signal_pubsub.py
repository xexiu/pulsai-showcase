"""
Redis Pub/Sub Bridge for Signal Delivery (Celery -> FastAPI WebSocket)

WHY THIS EXISTS:
Celery workers and FastAPI run in separate OS processes. The WebSocket
ConnectionManager is an in-memory singleton per process. When a Celery
worker generates a signal and calls ConnectionManager.broadcast_signal(),
it broadcasts to ITS OWN manager (which has 0 connected WebSocket clients).
The FastAPI process's manager HAS the clients but never receives the signal.

SOLUTION:
- Celery worker PUBLISHES signal to Redis channel "pulsai:signals"
- FastAPI process SUBSCRIBES to that channel in a background task
- On receiving a message, FastAPI broadcasts via its ConnectionManager

This is the standard pattern for bridging async producers (Celery) with
WebSocket servers. Redis Pub/Sub adds <1ms latency.

@see docs/02-technical/DATA_PROCESSING.md
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from src.infrastructure.cache.redis_connections import create_async_redis_client
from src.infrastructure.cache.redis_resource_close import close_redis_resource
from src.shared.constants.runtime import (
    REDIS_PUBSUB_RECONNECT_DELAY_SECONDS,
    SIGNAL_PUBSUB_CHANNEL,
)

if TYPE_CHECKING:
    from redis.asyncio.client import PubSub, Redis


logger = logging.getLogger(__name__)

SIGNAL_CHANNEL = SIGNAL_PUBSUB_CHANNEL


async def publish_signal(signal_data: dict[str, Any]) -> None:
    """
    Publish a signal to Redis Pub/Sub for WebSocket delivery.

    Called from Celery worker's _notify_signal function.
    The FastAPI process subscribes and broadcasts to WS clients.

    Args:
        signal_data: Signal dict with keys: id, action, confidence,
                     symbol, timeframe, timestamp, price, etc.
    """
    try:
        client = create_async_redis_client()
        try:
            message = json.dumps(signal_data)
            receivers = await client.publish(SIGNAL_CHANNEL, message)
            logger.debug(
                "Published signal to %s (received by %d subscribers)",
                SIGNAL_CHANNEL,
                receivers,
            )
        finally:
            await close_redis_resource(client)
    except Exception:
        logger.exception("Failed to publish signal to Redis Pub/Sub")


async def subscribe_and_broadcast(
    on_signal: Callable[[str, dict[str, Any]], Awaitable[None]],
) -> None:
    """
    Subscribe to Redis signal channel and broadcast to WebSocket clients.

    Args:
        on_signal: Async callback ``(symbol, signal_data) -> None``.
            Callers must supply the callback (typically the WebSocket
            ``ConnectionManager.broadcast_signal`` wrapped in a closure).

    WHY callback parameter:
    - Infrastructure must not import from the API layer (dependency inversion).
    - The caller (``main.py`` lifespan) passes the callback, keeping this module
      layer-clean.
    """
    while True:
        client: Redis[str] | None = None
        pubsub: PubSub | None = None
        try:
            client = create_async_redis_client(socket_timeout=None)
            pubsub = client.pubsub()
            await pubsub.subscribe(SIGNAL_CHANNEL)
            logger.info("Subscribed to Redis channel: %s", SIGNAL_CHANNEL)

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                try:
                    signal_data = json.loads(message["data"])
                    symbol = signal_data.get("symbol", "")
                    await on_signal(symbol, signal_data)
                    logger.debug(
                        "Forwarded signal from Redis to WS clients for %s",
                        symbol,
                    )
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON on signal channel: %s", message["data"])
                except Exception:
                    logger.exception("Error broadcasting signal from Redis")

        except asyncio.CancelledError:
            logger.info("Redis Pub/Sub subscriber shutting down (task cancelled)")
            raise
        except Exception:
            logger.exception(
                "Redis Pub/Sub connection lost, reconnecting in %ds...",
                REDIS_PUBSUB_RECONNECT_DELAY_SECONDS,
            )
            await asyncio.sleep(REDIS_PUBSUB_RECONNECT_DELAY_SECONDS)
        finally:
            try:
                if pubsub is not None:
                    await pubsub.unsubscribe(SIGNAL_CHANNEL)
                if client is not None:
                    await close_redis_resource(client)
            except Exception:
                logger.debug("Cleanup error during Redis Pub/Sub reconnect (non-critical)")
