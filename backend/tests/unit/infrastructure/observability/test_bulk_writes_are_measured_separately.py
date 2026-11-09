"""A chunked upsert and a single-row insert are not the same measurement.

OWNER, repeatedly, most recently at 12:34:
    "PulsAI spike health: CRITICAL - db INSERT 5m critical p95=0.211s"

MEASURED on prod 2026-09-06 via /admin/health/observability, db INSERT:

    window   n     p50       p95       p99
    5m       12    0.070 s   0.091 s   0.099 s
    15m      83    0.053 s   0.1996 s  0.655 s

A typical write is 53-70 ms against a 200 ms critical threshold -- nowhere near it. But
`OHLCVRepository.bulk_insert` upserts candles in CHUNKS, and one chunk is a single sample whose
duration scales with the chunk size. Those land in the same `INSERT` bucket, and with only 12-25
samples in a five-minute window a p95 is barely more than "the second-slowest sample". One
chunked upsert therefore drags p95 over the line and pages the owner.

Two separate mistakes were stacked:

  1. the BUCKET -- batched writes measured as if they were rows;
  2. the BAND -- 50 ms warn / 200 ms critical, chosen for one row, applied to thousands.

This file pins the fix for both. The same class was already fixed once in
`observability_metrics.py`: DB_SELECT_P95_WARN was bumped 0.1 -> 0.3 in 2026-06 because a
networked Timescale SELECT at ~242 ms is "normal-busy". There the band was wrong; here the
bucket was.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.infrastructure.observability.bulk_write_context import bulk_write
from src.infrastructure.observability.db_metrics import (
    DbCompactThresholds,
    _classify_sql_operation,
    get_db_compact_health_view,
    observe_db_query_duration_seconds,
)
from src.shared.constants.observability_metrics import (
    BULK_WRITE_LABEL,
    DB_OTHER_P95_CRITICAL_SECONDS,
    DB_OTHER_P95_WARN_SECONDS,
    DB_WRITE_P95_CRITICAL_SECONDS,
    DB_WRITE_P95_WARN_SECONDS,
    KNOWN_SQL_OPERATIONS,
    READ_SQL_OPERATION,
    WRITE_SQL_OPERATIONS,
)

BULK_UPSERT = "INSERT INTO ohlcv (symbol, timeframe) VALUES (%s, %s) ON CONFLICT DO NOTHING"


@pytest.fixture(autouse=True)
def _clean_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise the post-boot grace, or every observation is dropped for the wrong reason."""
    monkeypatch.setattr("src.infrastructure.observability.db_metrics._warmup_grace_seconds", lambda: 0.0)
    from src.infrastructure.observability import db_metrics

    db_metrics._db_window_state.observations.clear()


class TestClassification:
    def test_a_single_row_insert_is_still_insert(self) -> None:
        assert _classify_sql_operation(BULK_UPSERT) == "INSERT"

    def test_an_executemany_write_is_bulk(self) -> None:
        """THE FIX. The flag was always passed by SQLAlchemy and swallowed by `*_a`."""
        assert _classify_sql_operation(BULK_UPSERT, executemany=True) == BULK_WRITE_LABEL

    def test_the_verb_does_not_split_the_bulk_label(self) -> None:
        """Batching is what makes it a different measurement, not insert-vs-update.

        Splitting per verb would add Prometheus label cardinality without adding insight.
        """
        for verb in WRITE_SQL_OPERATIONS:
            assert _classify_sql_operation(f"{verb} INTO ohlcv", executemany=True) == BULK_WRITE_LABEL, verb

    def test_the_default_keeps_every_existing_caller_unchanged(self) -> None:
        """`executemany` defaults False, so nothing that does not pass it changes meaning."""
        assert _classify_sql_operation("SELECT 1") == "SELECT"
        assert _classify_sql_operation("") != BULK_WRITE_LABEL


class TestTheDeclarationIsWhatActuallyCatchesOhlcvUpserts:
    """`executemany` alone would NOT have caught them, and the first version shipped assuming it would.

    `OHLCVRepository._execute_chunked_upsert` builds

        stmt = pg_insert(OHLCVModel).values(chunk)
        await self._session.execute(stmt)

    `.values(list_of_dicts)` renders ONE multi-row VALUES statement -- which is precisely why that
    method must chunk against asyncpg's 32,767 bind-parameter cap. SQLAlchemy therefore reports
    `executemany=False` for a write carrying thousands of rows, and a label keyed only on that
    flag is inert for the exact case it was written for.

    The caller knows; the listener cannot. So the caller declares it.
    """

    def test_a_multi_row_values_insert_is_bulk_when_declared(self) -> None:
        with bulk_write(rows=2):
            assert _classify_sql_operation(BULK_UPSERT) == BULK_WRITE_LABEL

    def test_the_same_statement_is_a_plain_insert_when_not_declared(self) -> None:
        """Undeclared writes keep the tight band — the marker must not leak into ordinary work."""
        assert _classify_sql_operation(BULK_UPSERT) == "INSERT"

    def test_the_marker_is_released_after_the_block(self) -> None:
        with bulk_write(rows=2):
            pass

        assert _classify_sql_operation(BULK_UPSERT) == "INSERT"

    def test_the_marker_is_released_when_the_block_raises(self) -> None:
        """The upsert re-raises on non-deadlock failure; a leaked token would mislabel later work.

        That is the worse failure: ordinary slow writes would be filed as bulk and stop paging.
        """
        with pytest.raises(RuntimeError, match="upsert failed"), bulk_write(rows=2):
            raise RuntimeError("upsert failed")

        assert _classify_sql_operation(BULK_UPSERT) == "INSERT"

    def test_nesting_restores_the_outer_state_not_a_global_false(self) -> None:
        with bulk_write(rows=2):
            with bulk_write(rows=3):
                assert _classify_sql_operation(BULK_UPSERT) == BULK_WRITE_LABEL
            assert _classify_sql_operation(BULK_UPSERT) == BULK_WRITE_LABEL

        assert _classify_sql_operation(BULK_UPSERT) == "INSERT"

    def test_a_select_inside_the_block_is_still_a_select(self) -> None:
        """The marker says "these writes are batched", not "relabel everything in here".

        The first draft returned BULK before looking at the verb, so a read issued inside the
        block would have inherited the looser write band. This test's NAME caught it: the name
        said SELECT and the assertion said BULK, which is a tell that the code was wrong rather
        than the expectation.
        """
        with bulk_write(rows=2):
            assert _classify_sql_operation("SELECT 1") == "SELECT"

    def test_every_batchable_verb_is_relabelled(self) -> None:
        """Driven by the SoT set, so adding a write verb to the registry extends this test.

        It used to hand-type ("INSERT", "UPDATE", "DELETE") — the THIRD literal copy of that set,
        beside `_BATCHABLE_WRITES` and `DbCompactThresholds.for_operation`, one of which carried
        a comment promising it "mirrors" another. A mirror maintained by a comment drifts; a set
        derived from `KNOWN_SQL_OPERATIONS` cannot.
        """
        assert WRITE_SQL_OPERATIONS, "the write set must not be empty, or this test proves nothing"

        with bulk_write(rows=2):
            for verb in WRITE_SQL_OPERATIONS:
                assert _classify_sql_operation(f"{verb} INTO ohlcv") == BULK_WRITE_LABEL, verb

    def test_the_write_set_excludes_the_read_verb(self) -> None:
        """SELECT must never be batchable: a read inside a bulk block is still a read."""
        assert READ_SQL_OPERATION not in WRITE_SQL_OPERATIONS
        assert set(WRITE_SQL_OPERATIONS) | {READ_SQL_OPERATION} == set(KNOWN_SQL_OPERATIONS)


class TestThresholds:
    def test_bulk_is_judged_per_row_against_the_write_band(self) -> None:
        """The band is DERIVED once the samples are per row, not chosen.

        Batching's entire claim is that a row costs LESS inside a batch than outside one. Once
        BULK samples are normalised per row they are the same unit as a single-row write, so
        holding both to one band states that claim as a check: a batched row costing what an
        unbatched row costs means the batching bought nothing, and that is worth paging about.
        """
        assert DbCompactThresholds().for_operation(BULK_WRITE_LABEL) == (
            DB_WRITE_P95_WARN_SECONDS,
            DB_WRITE_P95_CRITICAL_SECONDS,
        )

    def test_the_other_band_is_no_longer_where_bulk_lands(self) -> None:
        """Pins the REVERSAL, so nobody restores the old parking spot without reading why.

        BULK sat on the OTHER band while its samples were raw per-statement durations, because
        no threshold over an unknown batch size can mean anything: 216 ms is excellent for 4,000
        rows and terrible for 3. That was honest at the time and is obsolete now - the row count
        arrived, so the reason for parking it there is gone.
        """
        assert DbCompactThresholds().for_operation(BULK_WRITE_LABEL) != (
            DB_OTHER_P95_WARN_SECONDS,
            DB_OTHER_P95_CRITICAL_SECONDS,
        )

    def test_single_row_writes_keep_their_tight_band(self) -> None:
        """The point is to stop misfiling bulk writes, NOT to loosen real write alerting."""
        for operation in WRITE_SQL_OPERATIONS:
            assert DbCompactThresholds().for_operation(operation) == (
                DB_WRITE_P95_WARN_SECONDS,
                DB_WRITE_P95_CRITICAL_SECONDS,
            )


class TestTheViewReportsIt:
    def _primary(self) -> dict[str, Any]:
        view = get_db_compact_health_view()
        return view["by_label"][view["primary_window"]]

    def test_a_bulk_sample_appears_under_its_own_label(self) -> None:
        """A label the view does not enumerate is collected and then silently dropped."""
        observe_db_query_duration_seconds(BULK_WRITE_LABEL, 0.655)

        assert self._primary()[BULK_WRITE_LABEL]["count"] == 1

    def test_a_bulk_sample_does_not_pollute_the_insert_percentile(self) -> None:
        """THE REGRESSION: a 655 ms chunked upsert among ~20 fast rows paged the owner."""
        for _ in range(19):
            observe_db_query_duration_seconds("INSERT", 0.06)
        observe_db_query_duration_seconds(BULK_WRITE_LABEL, 0.655)

        insert = self._primary()["INSERT"]

        assert insert["count"] == 19
        assert insert["p95"] < DB_WRITE_P95_CRITICAL_SECONDS
        assert insert["status"] != "critical"

    def test_a_genuinely_slow_row_write_still_pages(self) -> None:
        """The filter must remove the misfiled samples ONLY, never mask real write latency."""
        for _ in range(19):
            observe_db_query_duration_seconds("INSERT", 0.9)

        assert self._primary()["INSERT"]["status"] == "critical"


class TestPerRowNormalisation:
    """The row count is what makes the BULK number mean anything.

    Without it a BULK sample is the duration of an unknown batch, so no threshold over it can be
    right: 216 ms is excellent for 4,000 rows and terrible for 3. The band above only became
    derivable once the samples were per row.
    """

    def _bulk_p50(self) -> float:
        """Reads the view the way `TestTheViewReportsIt` already does, not a second shape.

        The first draft invented `view["operations"]` and got `KeyError` five times - a reminder
        that guessing a payload's shape is the same defect class as guessing a threshold.
        """
        view = get_db_compact_health_view()
        return float(view["by_label"][view["primary_window"]][BULK_WRITE_LABEL]["p50"])

    def test_the_duration_is_divided_by_the_declared_rows(self) -> None:
        with bulk_write(rows=100):
            observe_db_query_duration_seconds(BULK_WRITE_LABEL, 2.0)

        assert self._bulk_p50() == pytest.approx(0.02, abs=1e-6)

    def test_the_same_duration_over_more_rows_reads_cheaper(self) -> None:
        """The property that matters: a bigger batch is not punished for being bigger."""
        from src.infrastructure.observability import db_metrics

        with bulk_write(rows=10):
            observe_db_query_duration_seconds(BULK_WRITE_LABEL, 1.0)
        small = self._bulk_p50()

        db_metrics._db_window_state.observations.clear()
        with bulk_write(rows=1000):
            observe_db_query_duration_seconds(BULK_WRITE_LABEL, 1.0)

        assert self._bulk_p50() < small

    def test_an_undeclared_executemany_sample_is_left_raw(self) -> None:
        """No caller declared a count, so there is no divisor -- inventing one would be worse.

        SQLAlchemy can batch without going through `bulk_write`. Scaling that sample by a
        made-up number would be a guess presented as a measurement.
        """
        observe_db_query_duration_seconds(BULK_WRITE_LABEL, 0.5)

        assert self._bulk_p50() == pytest.approx(0.5, abs=1e-6)

    def test_a_single_row_write_is_unaffected_by_the_division(self) -> None:
        """rows=1 is the identity case, so an ordinary write keeps its real duration."""
        with bulk_write(rows=1):
            observe_db_query_duration_seconds(BULK_WRITE_LABEL, 0.25)

        assert self._bulk_p50() == pytest.approx(0.25, abs=1e-6)

    def test_zero_rows_never_divides(self) -> None:
        """A ZeroDivisionError inside a metrics listener would take down the query it measures."""
        with bulk_write(rows=0):
            observe_db_query_duration_seconds(BULK_WRITE_LABEL, 0.3)

        assert self._bulk_p50() == pytest.approx(0.3, abs=1e-6)
