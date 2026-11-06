#!/usr/bin/env python3
"""Tests for `_hook_state` — the shared SoT for guard state.

REUSE-AUDIT: considered `test_every_guard_is_wired.py` (imports this module, but tests hook
REGISTRATION, not state semantics) and `test_architect_no_defer_guard.py` (exercises
`wedged_on_no_progress` indirectly, through one caller's subprocess). Neither tests this module's
behaviour directly. Not extending; new file.

WHY IT MATTERS THAT THIS FILE DID NOT EXIST. Every guard's block accounting runs through here, so
a defect in `scoped_to_session` silences guards repo-wide — and silence is the exact failure mode
this family of guards exists to prevent. It had no direct tests while several guards depended on
it, which is the same shape as a guard that is registered but never fires.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _hook_state import (  # noqa: E402
    finding_fingerprint,
    load_state,
    save_state,
    scoped_to_session,
    wedged_on_no_progress,
)


class TestSessionScoping:
    """A counter that outlives its conversation silences the guard that owns it."""

    def test_a_new_session_zeroes_the_counter(self) -> None:
        fresh = scoped_to_session({"session_id": "old", "blocks": 7}, "new")

        assert fresh["blocks"] == 0
        assert fresh["session_id"] == "new"

    def test_the_same_session_keeps_the_counter(self) -> None:
        """Pressure must accumulate WITHIN a session, or a guard nags once and forgets."""
        same = scoped_to_session({"session_id": "s1", "blocks": 3}, "s1")

        assert same["blocks"] == 3

    def test_non_counter_state_survives_the_reset(self) -> None:
        """Cached evidence describes the REPOSITORY, not the conversation; re-deriving is waste."""
        fresh = scoped_to_session(
            {"session_id": "old", "blocks": 5, "last_investigate_at": 1234.5}, "new"
        )

        assert fresh["last_investigate_at"] == 1234.5

    def test_an_empty_session_id_changes_nothing(self) -> None:
        """Some payloads carry no session. Zeroing on that would reset the counter constantly."""
        state = {"session_id": "s1", "blocks": 4}

        assert scoped_to_session(state, "") == state


class TestPersistenceNeverRaises:
    """A guard must not die on a read-only filesystem — it would take the tool call with it."""

    def test_a_missing_file_reads_as_a_fresh_session(self, tmp_path: Path) -> None:
        """Not `{}` — a SCOPED state, which is the more useful contract.

        My first draft asserted `== {}` and failed. The code is right and the test was wrong:
        an absent file is a brand-new session, so callers get `blocks: 0` rather than a bare
        dict they must each defensively `.get` around. Written down because "the test failed,
        so loosen the test" is how a real defect gets waved through, and distinguishing the two
        requires reading the code rather than the failure.
        """
        state = load_state(tmp_path / "nope.json", "s1")

        assert state["blocks"] == 0
        assert state["session_id"] == "s1"

    def test_corrupt_json_reads_as_a_fresh_session(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"
        path.write_text("{not json", encoding="utf-8")

        assert load_state(path, "s1")["blocks"] == 0

    def test_a_json_list_reads_as_a_fresh_session(self, tmp_path: Path) -> None:
        """Valid JSON of the wrong SHAPE. `.get` on a list raises, and a guard must not."""
        path = tmp_path / "s.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")

        assert load_state(path, "s1")["blocks"] == 0

    def test_a_corrupt_file_never_reads_as_an_EXHAUSTED_budget(self, tmp_path: Path) -> None:
        """The dangerous direction. A partial read that yielded a high count would silence
        the guard, and a guard silenced by a corrupt file is a guard nobody knows is off."""
        path = tmp_path / "s.json"
        path.write_text('{"session_id": "s1", "blocks": 9', encoding="utf-8")

        assert load_state(path, "s1").get("blocks", 0) == 0

    def test_saving_to_an_unwritable_path_is_silent(self, tmp_path: Path) -> None:
        save_state(tmp_path / "no" / "such" / "dir" / "s.json", {"blocks": 1})

    def test_a_round_trip_preserves_the_state(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"
        save_state(path, {"session_id": "s1", "blocks": 2})

        assert json.loads(path.read_text())["blocks"] == 2


class TestFingerprint:
    """Identity for one finding, so repetition can be told from progress."""

    def test_reflowing_whitespace_is_the_same_finding(self) -> None:
        """Otherwise rewording nothing resets the counter — an escape hatch, not a fix."""
        assert finding_fingerprint("the right fix\nis per-row") == finding_fingerprint(
            "the right fix   is per-row"
        )

    def test_different_findings_differ(self) -> None:
        assert finding_fingerprint("a duplicate in foo.py") != finding_fingerprint(
            "a duplicate in bar.py"
        )

    def test_it_survives_undecodable_input(self) -> None:
        """Transcripts carry arbitrary bytes; a hash that raises is a guard that dies."""
        assert finding_fingerprint("caf\udce9 \U0001f600")


class TestWedgedOnNoProgress:
    """Loop safety WITHOUT the one-shot escape that let a real deferral ship on 2026-09-06."""

    def test_the_first_block_is_never_a_wedge(self, tmp_path: Path) -> None:
        assert wedged_on_no_progress(tmp_path / "s.json", "s1", "abc", max_stuck=3) is False

    def test_an_unchanged_finding_eventually_wedges(self, tmp_path: Path) -> None:
        path = tmp_path / "s.json"

        verdicts = [wedged_on_no_progress(path, "s1", "abc", max_stuck=3) for _ in range(5)]

        assert verdicts[:3] == [False, False, False]
        assert verdicts[3] is True

    def test_a_changed_finding_resets_the_counter(self, tmp_path: Path) -> None:
        """THE POINT: an agent that is working is never released, however long it takes."""
        path = tmp_path / "s.json"
        for i in range(20):
            assert wedged_on_no_progress(path, "s1", f"finding-{i}", max_stuck=3) is False

    def test_alternating_findings_never_wedge(self, tmp_path: Path) -> None:
        """Two findings traded back and forth is still movement, not a wedge."""
        path = tmp_path / "s.json"
        for i in range(10):
            assert wedged_on_no_progress(path, "s1", f"f{i % 2}", max_stuck=3) is False

    def test_a_new_session_starts_the_count_over(self, tmp_path: Path) -> None:
        """A wedge is a property of one conversation, not of the repository."""
        path = tmp_path / "s.json"
        for _ in range(5):
            wedged_on_no_progress(path, "s1", "abc", max_stuck=3)

        assert wedged_on_no_progress(path, "s2", "abc", max_stuck=3) is False

    def test_the_counter_is_persisted_between_calls(self, tmp_path: Path) -> None:
        """Guards run as separate PROCESSES; in-memory state would count to one forever."""
        path = tmp_path / "s.json"
        wedged_on_no_progress(path, "s1", "abc", max_stuck=3)

        assert json.loads(path.read_text())["blocks"] == 1
