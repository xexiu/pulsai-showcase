"""Boot-time drift check for Postgres server-side tunables (Option A SoT).

Single responsibility: query the live Postgres server for the tunables
declared in ``src.shared.constants.postgres_server_tunables`` and emit
the right signal:

- Critical drift (observed below client-pool envelope) -> raise
  :class:`PostgresServerTunablesDriftError` so FastAPI fails to boot.
- Soft drift (observed != SoT but >= envelope) -> log WARNING. Operates
  fine, but flag for reconciliation: either the constant is stale or
  someone changed the server out-of-band.
- Match -> silent pass.

Why a dedicated module:
    ``database.py`` is at 454 lines (already over the §7.2 300-line
    standard). Adding this check there would worsen the smell.
    SRP-clean to host it here. ``main.py`` lifespan imports
    :func:`assert_postgres_tunables_match_sot` and wires it into
    :func:`build_startup_sequence` as the ``verify_postgres_tunables``
    step.

@see apps/api/src/shared/constants/postgres_server_tunables.py (SoT)
@see docs/06-devops/RAILWAY_RIGHTSIZING_RUNBOOK.md (operational workflow)
@see apps/api/tests/unit/infrastructure/test_postgres_tunables_check.py
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import text

from src.shared.constants.postgres_server_tunables import (
    POSTGRES_MAX_CONNECTIONS,
    POSTGRES_MAX_CONNECTIONS_MIN_FOR_CLIENT_POOL,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

# SoT for the SHOW query — extending the check to more parameters means
# adding a new query + a new comparison branch. Kept inline rather than
# in the constants file because it's a SQL idiom, not a tuning knob.
_SHOW_MAX_CONNECTIONS_SQL: str = "SHOW max_connections"

# Remediation hint embedded in the raise message so an SRE seeing the
# stack trace knows exactly what to do without grepping for runbooks.
_PROD_REMEDIATION_HINT: str = (
    f"On Railway: `ALTER SYSTEM SET max_connections = {POSTGRES_MAX_CONNECTIONS}; "
    f"SELECT pg_reload_conf();` then restart the Timescale service. "
    f"On local docker-compose: set `POSTGRES_MAX_CONNECTIONS={POSTGRES_MAX_CONNECTIONS}` "
    f"in .env (or rely on the docker-compose default) and recreate the postgres container. "
    f"See docs/06-devops/RAILWAY_RIGHTSIZING_RUNBOOK.md."
)


class PostgresServerTunablesDriftError(RuntimeError):
    """Raised when an observed Postgres tunable is below the operating envelope.

    Distinct exception type so callers (lifespan + tests) can distinguish
    "Postgres is mis-configured" from generic ``RuntimeError`` paths.
    """


async def assert_postgres_tunables_match_sot(engine: AsyncEngine) -> None:
    """Validate the live Postgres tunables against the SoT constants.

    Behavior matrix (see test file for the pinned contract):

    - observed == ``POSTGRES_MAX_CONNECTIONS`` -> silent pass
    - observed >= ``POSTGRES_MAX_CONNECTIONS_MIN_FOR_CLIENT_POOL`` but != SoT
      -> log WARNING with both values; do NOT raise
    - observed < ``POSTGRES_MAX_CONNECTIONS_MIN_FOR_CLIENT_POOL``
      -> raise :class:`PostgresServerTunablesDriftError`

    Args:
        engine: Async SQLAlchemy engine; connection is opened and closed
            inside this function so the caller doesn't need to manage
            it. Uses a fresh connection (not the pool's shared one) so
            the check works even at the earliest lifespan step.
    """
    async with engine.connect() as conn:
        result = await conn.execute(text(_SHOW_MAX_CONNECTIONS_SQL))
        raw = result.scalar()

    if raw is None:
        # `SHOW max_connections` always returns a row in Postgres, so this
        # branch only fires if the driver was patched/mocked badly. Treat
        # as critical drift so the boot loudly fails the test contract.
        msg = (
            f"Postgres `SHOW max_connections` returned no value. "
            f"This indicates a driver issue or mocked-but-broken test setup. "
            f"{_PROD_REMEDIATION_HINT}"
        )
        raise PostgresServerTunablesDriftError(msg)
    observed = int(raw)

    if observed < POSTGRES_MAX_CONNECTIONS_MIN_FOR_CLIENT_POOL:
        msg = (
            f"Postgres max_connections={observed} is BELOW the configured client-pool "
            f"envelope ({POSTGRES_MAX_CONNECTIONS_MIN_FOR_CLIENT_POOL}). The app would "
            f"deadlock on connection acquisition under realistic load. Aborting boot. "
            f"{_PROD_REMEDIATION_HINT}"
        )
        raise PostgresServerTunablesDriftError(msg)

    if observed != POSTGRES_MAX_CONNECTIONS:
        logger.warning(
            "postgres_tunables_drift: observed max_connections=%d differs from SoT=%d "
            "(envelope %d satisfied, so not fatal). Reconcile: either update the "
            "POSTGRES_MAX_CONNECTIONS constant or re-apply the SoT value to the server. %s",
            observed,
            POSTGRES_MAX_CONNECTIONS,
            POSTGRES_MAX_CONNECTIONS_MIN_FOR_CLIENT_POOL,
            _PROD_REMEDIATION_HINT,
        )
        return

    logger.debug(
        "postgres_tunables_match_sot: max_connections=%d (== SoT)",
        observed,
    )
