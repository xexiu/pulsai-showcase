"""Unit tests for Postgres server-tunables drift assertion (Option A SoT).

Pins the behavior of ``assert_postgres_tunables_match_sot``:
- Raise on **critical** drift (observed ``max_connections`` is below the
  client-pool envelope — the app would deadlock on connection acquisition).
- WARN on **soft** drift (observed value differs from SoT but is still
  above the envelope — operationally fine, but flag for reconciliation).
- Pass silently when observed == SoT.

This is the runtime safety net that makes the SoT constant
(``POSTGRES_MAX_CONNECTIONS``) honest. Local dev sets the value via
``docker-compose.yml`` env interpolation; prod sets it via
``ALTER SYSTEM SET`` per
``docs/06-devops/RAILWAY_RIGHTSIZING_RUNBOOK.md``. If either drifts
from the constant, this assert is what catches it at the next boot.

@see apps/api/src/shared/constants/postgres_server_tunables.py
@see apps/api/src/infrastructure/postgres_tunables_check.py
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.postgres_tunables_check import (
    PostgresServerTunablesDriftError,
    assert_postgres_tunables_match_sot,
)
from src.shared.constants.postgres_server_tunables import (
    POSTGRES_MAX_CONNECTIONS,
    POSTGRES_MAX_CONNECTIONS_MIN_FOR_CLIENT_POOL,
)

#: The check's own logger. Records are filtered to it: under xdist another test's leaked aiohttp session is
#: finalized mid-test and asyncio logs "Unclosed client session" at ERROR -- measured 2026-10-05, 7 such records
#: failed the equal-values test in the full suite while it passed alone. Those are not this check's warnings.
_CHECK_LOGGER = assert_postgres_tunables_match_sot.__module__


def _build_mock_engine(max_connections_observed: int) -> AsyncMock:
    """Build a mock AsyncEngine whose ``SHOW max_connections`` returns the given value."""
    engine = AsyncMock()
    conn = AsyncMock()
    result = MagicMock()
    result.scalar = MagicMock(return_value=str(max_connections_observed))
    conn.execute = AsyncMock(return_value=result)

    # `async with engine.connect() as c:` plumbing
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    engine.connect = MagicMock(return_value=cm)
    return engine


class TestAssertPostgresTunablesMatchSoT:
    """Behavior of the drift assertion under the 3 outcome classes."""

    @pytest.mark.asyncio
    async def test_passes_when_observed_equals_sot(self, caplog: pytest.LogCaptureFixture) -> None:
        """Equal values: silent pass (no log emit at WARNING)."""
        engine = _build_mock_engine(POSTGRES_MAX_CONNECTIONS)

        with caplog.at_level(logging.WARNING):
            await assert_postgres_tunables_match_sot(engine)

        warning_records = [r for r in caplog.records if r.name == _CHECK_LOGGER and r.levelno >= logging.WARNING]
        assert warning_records == [], f"Expected NO warnings when observed == SoT, got: {[r.message for r in warning_records]}"

    @pytest.mark.asyncio
    async def test_warns_on_soft_drift_above_envelope(self, caplog: pytest.LogCaptureFixture) -> None:
        """Observed != SoT but >= envelope: log WARNING, do not raise.

        Example: SoT=100, observed=150 (someone bumped via ALTER SYSTEM SET
        but forgot to update the constant) — the app still works but the
        constant is stale.
        """
        soft_drift_value = POSTGRES_MAX_CONNECTIONS + 50
        assert soft_drift_value > POSTGRES_MAX_CONNECTIONS_MIN_FOR_CLIENT_POOL  # sanity
        engine = _build_mock_engine(soft_drift_value)

        with caplog.at_level(logging.WARNING):
            await assert_postgres_tunables_match_sot(engine)

        # Exactly one WARNING, mentioning both values
        warnings = [r for r in caplog.records if r.name == _CHECK_LOGGER and r.levelno == logging.WARNING]
        assert len(warnings) == 1, f"Expected 1 warning, got {len(warnings)}: {[r.message for r in warnings]}"
        assert str(soft_drift_value) in warnings[0].getMessage()
        assert str(POSTGRES_MAX_CONNECTIONS) in warnings[0].getMessage()

    @pytest.mark.asyncio
    async def test_raises_on_critical_drift_below_envelope(self) -> None:
        """Observed < client-pool envelope: raise to abort FastAPI boot.

        Below the envelope, the app WILL deadlock on connection acquisition
        under realistic load — fail-fast at startup is strictly better than
        a runtime cascade in production.
        """
        critical_value = POSTGRES_MAX_CONNECTIONS_MIN_FOR_CLIENT_POOL - 1
        engine = _build_mock_engine(critical_value)

        with pytest.raises(PostgresServerTunablesDriftError) as exc_info:
            await assert_postgres_tunables_match_sot(engine)

        msg = str(exc_info.value)
        assert str(critical_value) in msg
        assert str(POSTGRES_MAX_CONNECTIONS_MIN_FOR_CLIENT_POOL) in msg
        assert "ALTER SYSTEM SET" in msg, "Error must include the prod remediation hint"

    @pytest.mark.asyncio
    async def test_envelope_is_derived_not_hardcoded(self) -> None:
        """SoT envelope is computed from resource_pools constants, not a magic number.

        This is a structural test — if someone replaces the derivation with
        a magic literal, this test catches it. Keeps the SoT promise: pool
        sizes change in one place (``resource_pools.py``), envelope follows.
        """
        from src.shared.constants.postgres_server_tunables import (
            _compute_min_connections_envelope,
        )
        from src.shared.constants.resource_pools import (
            DEFAULT_ASYNC_DB_MAX_OVERFLOW,
            DEFAULT_ASYNC_DB_POOL_SIZE,
            DEFAULT_SYNC_DB_MAX_OVERFLOW,
            DEFAULT_SYNC_DB_POOL_SIZE,
        )

        # Recompute envelope independently — if the helper drifts from the
        # pool constants, this test fails.
        recomputed = _compute_min_connections_envelope(
            async_pool=DEFAULT_ASYNC_DB_POOL_SIZE,
            async_overflow=DEFAULT_ASYNC_DB_MAX_OVERFLOW,
            sync_pool=DEFAULT_SYNC_DB_POOL_SIZE,
            sync_overflow=DEFAULT_SYNC_DB_MAX_OVERFLOW,
        )
        assert recomputed == POSTGRES_MAX_CONNECTIONS_MIN_FOR_CLIENT_POOL
