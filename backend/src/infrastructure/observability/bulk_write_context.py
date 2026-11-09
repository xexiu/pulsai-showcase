"""Is the statement being measured right now part of a deliberate BULK write?

WHY THIS EXISTS RATHER THAN A FLAG FROM SQLALCHEMY. The first attempt keyed off the
`executemany` argument that `after_cursor_execute` receives, on the assumption that a chunked
upsert arrives that way. It does not:

    stmt = pg_insert(OHLCVModel).values(chunk)   # ONE statement, N x M bind parameters
    await self._session.execute(stmt)            # executemany is False

`.values(list_of_dicts)` renders a single multi-row VALUES clause -- which is exactly why
`_execute_chunked_upsert` has to chunk at all, against asyncpg's 32,767 bind-parameter cap. So
the flag is False for the very writes it was meant to catch, and the label would never have
fired. Verified by reading the repository rather than assuming, after shipping the version that
assumed.

Parsing the SQL instead was rejected: counting `), (` groups means string-scanning a statement
that can carry forty thousand parameters, on the hot path, to recover a fact the caller already
knows.

So the CALLER declares it. `OHLCVRepository._execute_chunked_upsert` knows it is writing
thousands of rows in one statement; the metric listener does not and cannot. A contextvar
carries that across the SQLAlchemy event boundary, the same seam used for
`synthetic_probe_context` -- set at the point that has the knowledge, read at the point that
needs it.

WHAT IT BUYS. A chunked upsert is a single sample whose duration scales with chunk size.
Measured on prod 2026-09-06: single-row writes 53-70 ms, the bulk tail 655 ms, and only 12-25
INSERT samples in a five-minute window -- so one chunked upsert set the p95 and paged the owner
against a 200 ms band chosen for single rows.

@see src/infrastructure/observability/db_metrics.py (reads it)
@see src/infrastructure/persistence/ohlcv_repository.py (sets it)
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

__all__ = ["bulk_write", "bulk_write_rows", "is_bulk_write_in_progress"]

#: 0 means "no batch declared". The row count doubles as the flag, so there is ONE piece of state
#: rather than a bool and an int that can disagree about whether a batch is in progress.
#:
#: Defaults to 0 so a statement nobody declared is measured as what it looks like. Defaulting the
#: other way would quietly move ordinary writes out of the band meant to page on them.
_BULK_WRITE_ROWS: ContextVar[int] = ContextVar("pulsai_bulk_write_rows", default=0)


@contextmanager
def bulk_write(rows: int) -> Iterator[None]:
    """Mark statements in this block as ONE batched write of `rows` rows.

    THE ROW COUNT IS THE POINT, not decoration. A chunked upsert's duration scales with its chunk
    size, so the raw number answers no question anyone has: 216 ms is excellent for 4,000 rows and
    terrible for 3. Normalised per row it becomes comparable with an ordinary single-row write -
    which is exactly the claim batching makes, and if a batched row costs what an unbatched one
    costs, the batch bought nothing and that is worth paging about.

    Only the caller has this number. The metric listener sees a statement and a duration.

    ARCHITECTURE_PATTERNS section 5, the honesty clause: "a resilience pattern without
    observability is worse than none... if it can trip, it must emit - and something must read
    what it emits". The same applies to a metric: a BULK label carrying an uninterpretable
    duration emits without being readable, which is the decorative half of that failure.

    A context manager rather than a pair of calls: the token MUST be reset, on the error path
    too. `_execute_chunked_upsert` retries on deadlock and re-raises otherwise, so a leaked token
    would mark unrelated later statements as bulk and hide real write latency - a worse failure
    than the noise being removed.

    :param rows: rows in the batch; values below 1 are treated as no batch, because dividing a
        duration by zero rows would be worse than not normalising at all.
    """
    token = _BULK_WRITE_ROWS.set(max(int(rows), 0))
    try:
        yield
    finally:
        _BULK_WRITE_ROWS.reset(token)


def bulk_write_rows() -> int:
    """Rows in the batch currently being written, or 0 when none is declared."""
    return _BULK_WRITE_ROWS.get()


def is_bulk_write_in_progress() -> bool:
    """True while a caller has declared the current statements to be a batched write."""
    return _BULK_WRITE_ROWS.get() > 0
