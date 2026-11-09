"""A request that runs many DB queries is visible: its query count rides the request context (P1-7i).

IMPORTERS/CALLERS: pytest only. AFFECTED API: none. DATA SCHEMAS: none.

Prod has no pg_stat_statements (measured 2026-10-05: the extension is not installed, and enabling it
needs a database restart), so nothing on prod could say how many queries one request ran -- the number
that exposes an N+1. These tests drive the real SQLAlchemy listeners on a real (SQLite) engine and the
real middleware on a real FastAPI app; nothing is mocked between the query and the count.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI
from sqlalchemy import Engine, create_engine, text
from starlette.testclient import TestClient

from src.infrastructure.observability import endpoint_metrics
from src.infrastructure.observability.db_metrics import install_db_event_listeners
from src.infrastructure.observability.endpoint_metrics import install_endpoint_metrics_middleware
from src.infrastructure.observability.request_query_count import (
    finish_request_query_count,
    start_request_query_count,
)

if TYPE_CHECKING:
    import pytest

_RECORD = "db_queries_per_request"


def _engine() -> Engine:
    engine = create_engine("sqlite://")
    install_db_event_listeners(engine)
    return engine


def _run_queries(engine: Engine, n: int) -> None:
    with engine.connect() as conn:
        for _ in range(n):
            conn.execute(text("select 1"))


def test_queries_run_while_a_count_is_open_are_counted() -> None:
    engine = _engine()
    token = start_request_query_count()

    _run_queries(engine, 3)

    assert finish_request_query_count(token) == 3


def test_queries_with_no_count_open_are_not_counted_and_do_not_fail() -> None:
    engine = _engine()
    _run_queries(engine, 2)  # a worker or a script: no request, no counter, nothing raises

    token = start_request_query_count()
    assert finish_request_query_count(token) == 0


def _app(engine: Engine, queries: int) -> FastAPI:
    app = FastAPI()
    install_endpoint_metrics_middleware(app)

    @app.get("/items/{item_id}")
    def item(item_id: int) -> dict[str, int]:
        _run_queries(engine, queries)
        return {"id": item_id}

    return app


def test_a_request_over_the_budget_is_logged_with_its_route_and_count(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(endpoint_metrics, "DB_QUERIES_PER_REQUEST_WARN", 2)
    app = _app(_engine(), queries=5)

    with caplog.at_level(logging.WARNING, logger=endpoint_metrics.__name__):
        assert TestClient(app).get("/items/7").status_code == 200

    records = [r for r in caplog.records if r.getMessage() == _RECORD]
    assert len(records) == 1
    assert records[0].__dict__["route"] == "/items/{item_id}"
    assert records[0].__dict__["queries"] == 5


def test_a_request_within_the_budget_is_silent(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(endpoint_metrics, "DB_QUERIES_PER_REQUEST_WARN", 5)
    app = _app(_engine(), queries=5)

    with caplog.at_level(logging.WARNING, logger=endpoint_metrics.__name__):
        TestClient(app).get("/items/7")

    assert not [r for r in caplog.records if r.getMessage() == _RECORD]


def test_one_request_never_sees_another_requests_count(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """The counter is request-scoped: a ContextVar left set would bleed into the next request."""
    monkeypatch.setattr(endpoint_metrics, "DB_QUERIES_PER_REQUEST_WARN", 4)
    app = _app(_engine(), queries=3)
    client = TestClient(app)

    with caplog.at_level(logging.WARNING, logger=endpoint_metrics.__name__):
        client.get("/items/1")
        client.get("/items/2")

    assert not [r for r in caplog.records if r.getMessage() == _RECORD]  # 3 + 3 would cross 4 if shared
