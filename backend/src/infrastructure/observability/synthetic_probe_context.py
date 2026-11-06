"""Is the request being served right now a synthetic probe?

OWNER, 2026-09-06, after being paged three more times while the agent measured prod:
*"every time you auth and test, the spikes happens (not when your guest)"*. He is right, and
the diagnosis is uncomfortable: the exclusion shipped that same morning was HALF a fix.

`is_synthetic_probe_user_agent` was wired into the endpoint middleware only, so probe traffic
stopped skewing the ENDPOINT percentiles and nothing else. But a probe request that
authenticates does real work: it INSERTs, it reads Redis, it occupies the loop. Those samples
land in the `db` and `redis` compact views, which have their own thresholds and page on their
own. The pages that followed named exactly those sources -- `db INSERT critical p95=0.208s`,
`redis GET critical p95=0.462s` -- never the endpoint. A guest request 401s before touching
either, which is precisely why the owner only saw this when the probe was authenticated.

The user-agent is known at ONE point (the HTTP middleware) and needed at several points far
below it (the SQLAlchemy listener, the Redis wrapper), none of which can see a request. A
`ContextVar` is the seam that carries it: set once per request, read wherever the work happens,
and inherited by tasks the request spawns -- which is correct here, because work a probe caused
is still work a probe caused.

REUSE-AUDIT: considered threading a flag through `observe_*` call sites (they are invoked by
SQLAlchemy event listeners and a Redis command wrapper, neither of which takes app arguments),
and considered `request.state` (invisible below the HTTP layer, which is the whole problem).

@see src/infrastructure/observability/endpoint_metrics.py (sets it)
@see src/infrastructure/observability/db_metrics.py, redis_metrics.py (read it)
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contextvars import Token

__all__ = [
    "is_current_request_synthetic",
    "mark_current_request_synthetic",
    "reset_current_request_synthetic",
]

#: False by default, so anything with no request context at all -- Celery tasks, the warmers,
#: the spike watcher itself -- is treated as real. Defaulting the other way would silently
#: erase every background sample, which is the failure mode this module exists to avoid.
_SYNTHETIC_REQUEST: ContextVar[bool] = ContextVar("pulsai_synthetic_request", default=False)


def mark_current_request_synthetic() -> Token[bool]:
    """Mark the current context as serving a synthetic probe.

    :returns: A token the caller MUST pass to :func:`reset_current_request_synthetic`.
        ContextVars are not automatically scoped to a request in an ASGI app -- the same task
        can serve the next request -- so an unreset token leaks the flag onto real traffic and
        would hide genuine degradation. That is a worse failure than the one being fixed.
    """
    return _SYNTHETIC_REQUEST.set(True)


def reset_current_request_synthetic(token: Token[bool]) -> None:
    """Restore whatever the flag was before the matching mark."""
    _SYNTHETIC_REQUEST.reset(token)


def is_current_request_synthetic() -> bool:
    """True while the work being measured was caused by a synthetic probe."""
    return _SYNTHETIC_REQUEST.get()
