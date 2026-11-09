"""One PUBLIC backtest per (symbol, timeframe, cert window role) -- enforced by the DATABASE.

IMPORTERS/CALLERS: none -- a pytest module. It drives the partial unique index
`uq_backtest_runs_public_book_window_role`, declared on `BacktestRun.__table_args__` and mirrored
by migration `20260920_public_backtest_one_pair_per_book`.
AFFECTED API: none directly. It pins the invariant that `PATCH /backtests/{id}/visibility` and the
research CLI both write through.
DATA SCHEMAS: `backtest_runs` rows only, inside the truncating `model_db_session` fixture.

WHY A DATABASE TEST AND NOT A UNIT TEST. The rule being pinned is a RACE property: two writers
reach this table -- the admin endpoint and the research publish CLI -- and an application-side
"is there already one?" check passes in both processes before either commits. Only the database
can refuse the second write, so only a database test can show that it does. The fixture runs on
real PostgreSQL (`tests/conftest.py::model_db_session` skips when it is unavailable), which is
also required because the index is a PARTIAL EXPRESSION index over jsonb -- SQLite would create
nothing and the suite would pass while measuring nothing.

REUSE-AUDIT: considered `tests/infrastructure/test_signal_repository.py` -- the sibling that pins
`uq_signals_symbol_tf_model_version_bar`, and the source of this file's shape (real session,
commit, assert IntegrityError). Not extending it because it is named for the SIGNAL repository and
every fixture in it builds `Signal` rows; a backtest-publication invariant living there would be
findable by nobody. Considered `tests/application/services/test_backtest_publish_gate.py` -- pure
rule functions over dicts, no database, and the gate it tests is the arm that runs BEFORE this
constraint. Considered adding cases to `tests/infrastructure/test_backtest_repository.py` --
closest by table, but it exercises query methods; this pins a schema constraint that holds no
matter which method writes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from src.domain.services.edge_lifecycle.capital_cert_promote import (
    CERT_WINDOW_ROLE_CONFIRM,
    CERT_WINDOW_ROLE_KEY,
    CERT_WINDOW_ROLE_SELECT,
)
from src.infrastructure.persistence.backtest_run_model import BacktestRun, BacktestStatus, StrategyType
from src.infrastructure.persistence.user_model import User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

INDEX_NAME = "uq_backtest_runs_public_book_window_role"

_SYMBOL = "BTC/USDT"
_TIMEFRAME = "6h"


def _user_id(session: Session) -> str:
    """A real user row, because `backtest_runs.user_id` is a foreign key.

    Built through the ORM rather than hand-written SQL: `users` carries 17 NOT NULL columns
    (measured 2026-09-20) whose defaults live on the mapped class, so an INSERT naming a subset
    fails on whichever column the author did not happen to remember.
    """
    user = User(id=str(uuid4()), email=f"pair-{uuid4().hex}@pulsai.test")
    session.add(user)
    session.commit()
    return str(user.id)


def _run(*, user_id: str, is_public: bool, role: str | None, timeframe: str = _TIMEFRAME) -> BacktestRun:
    config: dict[str, Any] = {"leverage": 5}
    if role is not None:
        config[CERT_WINDOW_ROLE_KEY] = role
    return BacktestRun(
        id=str(uuid4()),
        user_id=user_id,
        strategy_type=StrategyType.MODEL.value,
        config=config,
        symbol=_SYMBOL,
        timeframe=timeframe,
        start_date=datetime(2026, 1, 14, tzinfo=UTC),
        end_date=datetime(2026, 4, 1, tzinfo=UTC),
        metrics={"total_return": 0.42},
        trades=[],
        equity_curve=[],
        status=BacktestStatus.COMPLETED.value,
        progress_percent=100,
        is_public=is_public,
    )


def _insert(session: Session, run: BacktestRun) -> None:
    session.add(run)
    session.commit()


class TestTheIndexIsActuallyThere:
    """Two assertions that exist so the rest of this file cannot pass vacuously.

    A constraint test that runs against a schema WITHOUT the constraint reports green while
    measuring nothing -- the failure mode `silent-emptiness-reports-ok` is named for.
    """

    def test_the_partial_unique_index_exists_on_the_table(self, model_db_session: Session) -> None:
        names = {ix["name"] for ix in inspect(model_db_session.get_bind()).get_indexes("backtest_runs")}

        assert INDEX_NAME in names, f"index missing; the suite would measure nothing. Present: {sorted(names)}"

    def test_the_index_is_unique_and_partial(self, model_db_session: Session) -> None:
        definition = model_db_session.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = :name"),
            {"name": INDEX_NAME},
        ).scalar_one()

        assert "UNIQUE INDEX" in definition
        assert "is_public" in definition
        assert CERT_WINDOW_ROLE_KEY in definition


class TestOnePublicRowPerBookPerRole:
    def test_a_second_public_confirm_row_for_the_same_book_is_rejected(self, model_db_session: Session) -> None:
        """The whole point: a re-publish may not leave two 'the' confirm results standing."""
        user_id = _user_id(model_db_session)
        _insert(model_db_session, _run(user_id=user_id, is_public=True, role=CERT_WINDOW_ROLE_CONFIRM))

        with pytest.raises(IntegrityError):
            _insert(model_db_session, _run(user_id=user_id, is_public=True, role=CERT_WINDOW_ROLE_CONFIRM))

    def test_the_select_and_confirm_pair_both_publish(self, model_db_session: Session) -> None:
        """Exactly two rows per promoted model is the TARGET state, not a violation."""
        user_id = _user_id(model_db_session)

        _insert(model_db_session, _run(user_id=user_id, is_public=True, role=CERT_WINDOW_ROLE_SELECT))
        _insert(model_db_session, _run(user_id=user_id, is_public=True, role=CERT_WINDOW_ROLE_CONFIRM))

        assert model_db_session.query(BacktestRun).filter(BacktestRun.is_public.is_(True)).count() == 2

    def test_another_timeframe_gets_its_own_pair(self, model_db_session: Session) -> None:
        """The key is per BOOK -- 6h and 1d are different books, not a collision."""
        user_id = _user_id(model_db_session)

        _insert(model_db_session, _run(user_id=user_id, is_public=True, role=CERT_WINDOW_ROLE_CONFIRM))
        _insert(
            model_db_session,
            _run(user_id=user_id, is_public=True, role=CERT_WINDOW_ROLE_CONFIRM, timeframe="1d"),
        )

        assert model_db_session.query(BacktestRun).filter(BacktestRun.is_public.is_(True)).count() == 2


class TestItConstrainsPublicationOnly:
    def test_private_runs_of_the_same_book_and_role_are_unconstrained(self, model_db_session: Session) -> None:
        """A user re-running their own book is history, not a public claim."""
        user_id = _user_id(model_db_session)

        for _ in range(3):
            _insert(model_db_session, _run(user_id=user_id, is_public=False, role=CERT_WINDOW_ROLE_CONFIRM))

        assert model_db_session.query(BacktestRun).count() == 3

    def test_legacy_public_rows_without_a_role_are_exempt(self, model_db_session: Session) -> None:
        """Every public row that exists today predates the role (PROD: 8 rows, none roled).

        Without the `config ? 'window_role'` half of the predicate those rows would collapse onto
        one key per book and the migration would fail on live data -- applying a new rule
        retroactively to results published under the old one.
        """
        user_id = _user_id(model_db_session)

        for _ in range(3):
            _insert(model_db_session, _run(user_id=user_id, is_public=True, role=None))

        assert model_db_session.query(BacktestRun).filter(BacktestRun.is_public.is_(True)).count() == 3
