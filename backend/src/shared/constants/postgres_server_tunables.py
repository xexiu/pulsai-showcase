"""SoT constants for Postgres server-side tunables that we own (Option A).

Why this exists:
    Railway's managed Postgres hides ``postgresql.conf`` behind their
    container model. We can change settings via ``ALTER SYSTEM SET ...;``
    but we can't put a config file in the repo. Local dev runs Postgres
    in Docker (full control). The asymmetry is unavoidable, but the
    DRIFT can be made loudly detectable: this module holds the canonical
    expected values, and ``src.infrastructure.postgres_tunables_check``
    queries the live server at boot and fails loud on drift below the
    operating envelope.

Workflow when changing a value:
    1. Edit the constant here -> commit.
    2. Local: ``docker-compose down && up`` (compose file reads the env var).
    3. Prod: ``ALTER SYSTEM SET <name> = <new value>; SELECT pg_reload_conf();``
       (or ``DATABASE`` restart when the parameter requires it, e.g.
       ``max_connections``). See
       ``docs/06-devops/RAILWAY_RIGHTSIZING_RUNBOOK.md``.
    4. Next boot of the API: the assert verifies prod matches; logs WARN
       on soft drift, raises on critical drift.

@see docs/04-structural/PLAN_db_performance_followups.md §H1 (max_connections
     raised 25 -> 100, shipped 2026-05-31)
@see docs/06-devops/RAILWAY_RIGHTSIZING_RUNBOOK.md
@see apps/api/src/infrastructure/postgres_tunables_check.py
"""

from __future__ import annotations

from typing import Final

from src.shared.constants.resource_pools import (
    DEFAULT_ASYNC_DB_MAX_OVERFLOW,
    DEFAULT_ASYNC_DB_POOL_SIZE,
    DEFAULT_SYNC_DB_MAX_OVERFLOW,
    DEFAULT_SYNC_DB_POOL_SIZE,
)


def _compute_min_connections_envelope(
    *,
    async_pool: int,
    async_overflow: int,
    sync_pool: int,
    sync_overflow: int,
) -> int:
    """Worst-case client-side connection envelope.

    Derived (not hardcoded) so the envelope stays in sync with
    ``resource_pools.py``. Topology assumption matches
    ``docker-compose.prod.yml`` + Railway: ONE pulsai (FastAPI) service
    using the async pool, plus FOUR celery services each using the sync
    pool. The envelope is the worst-case sum if every pool is fully
    saturated with overflow active.

        envelope = (async_pool + async_overflow)         # pulsai
                 + 4 * (sync_pool + sync_overflow)       # 4 celery services

    With the current defaults (5+10 async, 3+2 sync, 4 celery) that's
    15 + 4*5 = 35 conns. Postgres ``max_connections`` MUST be at least
    this; the assert raises below it. Comfortable target is ~3x the
    envelope (the current 100-ceiling gives ~3x headroom).
    """
    pulsai_envelope = async_pool + async_overflow
    celery_envelope_per_service = sync_pool + sync_overflow
    return pulsai_envelope + _CELERY_SERVICE_COUNT * celery_envelope_per_service


# Number of celery services in the Railway deployment topology.
# ``celery-worker``, ``celery-worker-monitoring``, ``celery-worker-steam-ohlc``,
# ``celery-beat`` — each has its own sync pool. SoT for the envelope math.
_CELERY_SERVICE_COUNT: Final[int] = 4


# The canonical server-side setting. Edit here, then reconcile per the
# workflow at the top of this file. As of 2026-05-31 the prod value was
# raised from 25 -> 100 via Finding H1 in PLAN_db_performance_followups.md.
POSTGRES_MAX_CONNECTIONS: Final[int] = 100


# Minimum acceptable observed value — below this the client pool
# definitely cannot fit and the app would deadlock on connection
# acquisition under realistic load. The assert raises below this.
POSTGRES_MAX_CONNECTIONS_MIN_FOR_CLIENT_POOL: Final[int] = _compute_min_connections_envelope(
    async_pool=DEFAULT_ASYNC_DB_POOL_SIZE,
    async_overflow=DEFAULT_ASYNC_DB_MAX_OVERFLOW,
    sync_pool=DEFAULT_SYNC_DB_POOL_SIZE,
    sync_overflow=DEFAULT_SYNC_DB_MAX_OVERFLOW,
)


# Env-var name consumed by ``docker-compose.yml`` to apply the same
# value locally as the SoT constant defines. Naming this in the
# constants module (not inline in the YAML) means a rename only needs
# editing in one place.
POSTGRES_MAX_CONNECTIONS_ENV_VAR: Final[str] = "POSTGRES_MAX_CONNECTIONS"
