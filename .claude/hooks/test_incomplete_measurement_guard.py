"""The guard that fires when a turn calls its own number partial and ships it.

Importers/callers: pytest only; the guard is loaded by path via importlib, the same way its
siblings are. Affected API: none. Data schemas: synthetic transcript JSONL rows and hook payloads.

THE FIXTURES ARE THE REAL SENTENCES. The blocking case below is the text I actually wrote on
2026-09-09, and the releasing case is the text that closed it. A guard tuned against invented
phrasing catches invented phrasing.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib

_spec = importlib.util.spec_from_file_location(
    "incomplete_measurement_guard",
    pathlib.Path(__file__).with_name("incomplete_measurement_guard.py"),
)
assert _spec and _spec.loader
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


_REAL_ADMISSION = (
    "One caveat I have to state rather than bury: my count is a lower bound. The payload has a "
    "`children` key and an `isPositionTpsl` flag, and I only counted top-level `isTrigger`. "
    "2 Stop Market against 8,738 Limit. I'm not going to guess which."
)

_REAL_CLOSURE = (
    "Recount closed: descending into `children` changed nothing -- still 2 BTC Stop Market "
    "orders against 8,654 Limits, same two triggers at 1.51% and 1.87%."
)


class TestTheAdmissionIsWhatFires:
    def test_the_real_sentence_that_shipped_is_blocked(self) -> None:
        assert guard.ships_an_admitted_gap(_REAL_ADMISSION)

    def test_an_undercount_admission_is_blocked(self) -> None:
        assert guard.ships_an_admitted_gap("This undercounts: 40 of 44,956 rows were read.")

    def test_a_could_be_higher_admission_is_blocked(self) -> None:
        assert guard.ships_an_admitted_gap("We found 3 near mark, but the real figure could be materially higher.")

    def test_a_partial_sample_admission_is_blocked(self) -> None:
        assert guard.ships_an_admitted_gap("That was a partial sample -- 60 addresses of many.")


class TestClosingItReleases:
    def test_the_real_closure_passes(self) -> None:
        assert not guard.ships_an_admitted_gap(f"{_REAL_ADMISSION}\n\n{_REAL_CLOSURE}")

    def test_a_rerun_in_the_same_turn_passes(self) -> None:
        text = "My count was a lower bound at 2. Re-ran it including children: still 2."
        assert not guard.ships_an_admitted_gap(text)

    def test_confirming_the_figure_passes(self) -> None:
        text = "The 8,654 was a lower bound; I confirmed the count on a second pass."
        assert not guard.ships_an_admitted_gap(text)


class TestTheDeclaredEscape:
    def test_a_stated_blocker_passes(self) -> None:
        text = (
            "My count is a lower bound at 2 orders. "
            "MEASUREMENT-PARTIAL: the full enumeration needs 44,956 requests, which exceeds the "
            "venue's published minute budget by 70x."
        )
        assert not guard.ships_an_admitted_gap(text)

    def test_the_marker_alone_without_a_reason_does_not_release(self) -> None:
        """A bare marker would make the escape a magic word rather than a disclosure."""
        assert guard.ships_an_admitted_gap("Count is a lower bound of 2. MEASUREMENT-PARTIAL:")


class TestItDoesNotFireOnOrdinaryProse:
    """Two of these exist only to stop the guard passing vacuously -- a hook that matches
    nothing reports green forever, which is worse than no hook."""

    def test_a_complete_measurement_passes(self) -> None:
        assert not guard.ships_an_admitted_gap("Measured 3 bands within 5% of mark across 200 addresses.")

    def test_an_admission_with_no_figure_is_not_a_measurement(self) -> None:
        """'I did not check the docs' is not a partial count."""
        assert not guard.ships_an_admitted_gap("I did not check the upstream changelog for this.")

    def test_empty_text_passes(self) -> None:
        assert not guard.ships_an_admitted_gap("")

    def test_the_guard_actually_matches_something(self) -> None:
        """Non-vacuity: if the admission pattern ever stops matching, every test above would
        pass for the wrong reason."""
        assert guard._ADMISSION.search("this is a lower bound") is not None


class TestTheHookContract:
    def test_assistant_text_is_collected(self, tmp_path: pathlib.Path) -> None:
        transcript = tmp_path / "t.jsonl"
        transcript.write_text(
            json.dumps({"type": "assistant", "message": {"content": _REAL_ADMISSION}}) + "\n",
            encoding="utf-8",
        )
        assert guard.turn_text(str(transcript)) == _REAL_ADMISSION

    def test_a_user_message_starts_a_new_turn(self, tmp_path: pathlib.Path) -> None:
        """An admission from a PREVIOUS turn must not block this one forever."""
        transcript = tmp_path / "t.jsonl"
        rows = [
            {"type": "assistant", "message": {"content": _REAL_ADMISSION}},
            {"type": "user", "message": {"content": "next thing please"}},
            {"type": "assistant", "message": {"content": "Measured 3 bands across 200 addresses."}},
        ]
        transcript.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

        assert not guard.ships_an_admitted_gap(guard.turn_text(str(transcript)))

    def test_an_unreadable_transcript_fails_open(self) -> None:
        assert guard.turn_text("/nonexistent/path.jsonl") == ""
