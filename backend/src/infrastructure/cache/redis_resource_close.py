"""Shared helpers for closing raw Redis async resources safely."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


async def close_redis_resource(resource: Any) -> None:
    """
    Close Redis resources using the modern async API when available.

    WHY this helper exists:
    - redis-py 5.x deprecates `close()` in favor of `aclose()`
    - Some call sites still work with older resource types that only expose `close()`
    - Centralizing the fallback avoids repeating the same compatibility shim
    """
    aclose = getattr(resource, "aclose", None)
    if callable(aclose):
        await cast("Callable[[], Awaitable[None]]", aclose)()
        return
    await cast("Callable[[], Awaitable[None]]", resource.close)()
