"""How many DB queries the current request has run -- the number that exposes an N+1 (P1-7i).

IMPORTERS/CALLERS: db_metrics (counts in its after_cursor_execute listener), endpoint_metrics (opens and
reads the count around each request). AFFECTED API: none. DATA SCHEMAS: none.

Prod has no pg_stat_statements (measured 2026-10-05: not installed; enabling it needs a database restart),
so per-request query counts are taken in-process. The count rides a ContextVar like
``synthetic_probe_context``. The value is a one-element LIST, not an int: Starlette runs the endpoint in a
child task (and sync endpoints in a thread) with a COPY of the context, so a rebound int would be lost on
the way back, while a shared mutable box is the same object on both sides.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

_REQUEST_DB_QUERIES: ContextVar[list[int] | None] = ContextVar("pulsai_request_db_queries", default=None)


def start_request_query_count() -> Token[list[int] | None]:
    """Open a zeroed count for the current request; pass the token to :func:`finish_request_query_count`."""
    return _REQUEST_DB_QUERIES.set([0])


def finish_request_query_count(token: Token[list[int] | None]) -> int:
    """Close the count opened with ``token`` and return how many queries ran under it."""
    box = _REQUEST_DB_QUERIES.get()
    _REQUEST_DB_QUERIES.reset(token)
    return box[0] if box is not None else 0


def note_db_query_for_request() -> None:
    """Count one executed statement against the open request, if any (workers and scripts have none)."""
    box = _REQUEST_DB_QUERIES.get()
    if box is not None:
        box[0] += 1
