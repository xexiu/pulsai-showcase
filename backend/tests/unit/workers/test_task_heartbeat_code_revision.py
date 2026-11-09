"""STALEWORKER-1: the heartbeat must carry the WORKER's boot-time code identity, not only liveness.

IMPORTERS / CALLERS: pytest only. Exercises src.workers.task_heartbeat's new
`code_revision` support (heartbeat_meta, read_heartbeat, HeartbeatReading, task_heartbeat).
AFFECTED API: none directly -- the admin poll wiring is exercised in
tests/api/admin/test_research_loop_poll_code_revision.py.
DATA SCHEMAS: adds one key, `code_revision`, to the existing heartbeat meta dict.

WHY THIS EXISTS. MEASURED three times in one session (2026-09-21): a training worker kept
running code from its boot commit while API-visible commits landed 5-20 minutes later. The
liveness heartbeat (task_heartbeat.py) already tells a poller WHETHER a worker is still beating;
it did not yet say WHICH commit that worker was running, which is the question that actually
explains `unknown hypothesis tv_harvest_strategies` and `unexpected keyword argument
window_start`.
"""

from __future__ import annotations

import subprocess
import time
from datetime import timedelta
from typing import Any

from src.shared.utils.datetime_utils import utc_now
from src.workers import task_heartbeat as th
from src.workers import worker_code_revision as wcr


class _RecordingTask:
    """Stand-in for a bound Celery task; records every update_state call."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def update_state(self, *, state: str, meta: dict[str, Any], task_id: str | None = None) -> None:
        self.calls.append({"state": state, "meta": meta, "task_id": task_id})


class TestHeartbeatMetaCarriesTheCodeRevision:
    def test_the_meta_dict_carries_the_given_revision(self) -> None:
        now = utc_now()

        meta = th.heartbeat_meta(started_at=now, now=now, pid=1, code_revision="abc123")

        assert meta[th.HEARTBEAT_CODE_REVISION_KEY] == "abc123"

    def test_omitting_the_revision_defaults_to_none_so_every_existing_caller_stays_valid(self) -> None:
        """The three-kwarg call every existing caller (and the sibling heartbeat tests) already
        makes must keep working unchanged -- this is an ADDITIVE field."""
        now = utc_now()

        meta = th.heartbeat_meta(started_at=now, now=now, pid=1)

        assert meta[th.HEARTBEAT_CODE_REVISION_KEY] is None


class TestReadHeartbeatExtractsTheCodeRevision:
    def test_a_beat_with_a_revision_reads_it_back(self) -> None:
        now = utc_now()
        meta = th.heartbeat_meta(started_at=now, now=now, pid=1, code_revision="deadbeef")

        reading = th.read_heartbeat(meta, now=now)

        assert reading.code_revision == "deadbeef"

    def test_a_beat_written_before_this_key_existed_reads_as_unknown_not_a_crash(self) -> None:
        """Old beats in flight at deploy time have no `code_revision` key at all."""
        now = utc_now()
        legacy_meta = {
            th.HEARTBEAT_AT_KEY: now.isoformat(),
            th.HEARTBEAT_STARTED_AT_KEY: now.isoformat(),
            th.HEARTBEAT_PID_KEY: 123,
        }

        reading = th.read_heartbeat(legacy_meta, now=now)

        assert reading.code_revision is None

    def test_a_malformed_revision_value_reads_as_unknown_rather_than_raising(self) -> None:
        now = utc_now()
        meta = {
            th.HEARTBEAT_AT_KEY: now.isoformat(),
            th.HEARTBEAT_STARTED_AT_KEY: now.isoformat(),
            th.HEARTBEAT_PID_KEY: 123,
            th.HEARTBEAT_CODE_REVISION_KEY: 12345,  # not a string
        }

        reading = th.read_heartbeat(meta, now=now)

        assert reading.code_revision is None

    def test_an_absent_heartbeat_carries_no_revision_either(self) -> None:
        reading = th.read_heartbeat(None, now=utc_now())

        assert reading.code_revision is None


class TestTaskHeartbeatPublishesTheBootRevision:
    def test_every_beat_carries_the_process_boot_revision(self, monkeypatch: Any) -> None:
        wcr.boot_code_revision.cache_clear()
        monkeypatch.setattr(
            wcr.subprocess,
            "run",
            lambda *_a, **_k: subprocess.CompletedProcess(args=[], returncode=0, stdout="livesha1\n", stderr=""),
        )
        from src.infrastructure.config.settings import settings

        monkeypatch.setattr(settings, "app_build_sha", "")
        task = _RecordingTask()

        with th.task_heartbeat(task, interval_seconds=0.05):
            time.sleep(0.15)

        assert len(task.calls) >= 2, "need more than one beat to prove it isn't a fluke of the first"
        assert all(c["meta"][th.HEARTBEAT_CODE_REVISION_KEY] == "livesha1" for c in task.calls)
        wcr.boot_code_revision.cache_clear()

    def test_the_boot_revision_is_resolved_once_per_task_entry_not_once_per_beat(self, monkeypatch: Any) -> None:
        """`boot_code_revision` is itself `lru_cache`d (see test_worker_code_revision.py), so this
        pins the CALLER side: `task_heartbeat` must capture it once at entry and reuse it across
        every periodic beat, not call it fresh inside the beat loop."""
        calls = {"n": 0}

        def _tracking_boot_code_revision() -> str | None:
            calls["n"] += 1
            return "sha-once"

        monkeypatch.setattr(th, "boot_code_revision", _tracking_boot_code_revision)
        task = _RecordingTask()

        with th.task_heartbeat(task, interval_seconds=0.05):
            time.sleep(0.25)

        assert len(task.calls) >= 3, "expected several beats over 0.25s at a 0.05s interval"
        assert calls["n"] == 1, f"boot_code_revision was resolved {calls['n']} times, expected exactly once"


class TestHeartbeatReadingDefaultsCodeRevisionToNone:
    def test_the_default_reading_carries_no_revision(self) -> None:
        assert th.HeartbeatReading().code_revision is None

    def test_a_frozen_stale_window_edge_case_still_carries_the_revision(self) -> None:
        """Canary: the revision must survive alongside the existing stale/fresh computation, not
        be lost by whichever branch of read_heartbeat runs."""
        now = utc_now()
        meta = th.heartbeat_meta(started_at=now - timedelta(seconds=5), now=now, pid=1, code_revision="fresh-sha")

        reading = th.read_heartbeat(meta, now=now + timedelta(seconds=1))

        assert reading.stale is False
        assert reading.code_revision == "fresh-sha"
