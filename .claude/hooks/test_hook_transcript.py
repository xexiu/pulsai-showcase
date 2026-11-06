"""A Stop guard must judge the whole TURN, not only its last message."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_HOOK = Path(__file__).resolve().parent / "_hook_transcript.py"
_spec = importlib.util.spec_from_file_location("hts", _HOOK)
assert _spec and _spec.loader
hts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hts)


def _write(tmp_path: Path, records: list[dict[str, Any]]) -> str:
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    return str(path)


def _msg(role: str, text: str) -> dict[str, Any]:
    return {"type": role, "message": {"role": role, "content": [{"type": "text", "text": text}]}}


def test_a_tool_result_does_not_end_the_turn(tmp_path: Path) -> None:
    """Tool results arrive as user-role records; stopping at one truncates the turn to its tail.

    MEASURED 2026-08-15. `parallel_dev_audit_guard` was moved from `last_assistant_text` to
    `turn_text` specifically so a mid-turn statement would be seen — and it still was not.
    `AUDITED 60765cd55` was written, work continued, and the state file recorded 28 other SHAs
    and not that one, across three consecutive stops.

    The cause was here, not in the guard: this function broke on the first user-role record, and
    a tool result IS one. So "every assistant message since the last user turn" actually meant
    "the messages after the last tool call" — in a turn with forty tool calls, the final message
    alone. `turn_tool_uses` in the same module already handled it correctly, so the 2026-08-09
    upgrade that moved several Stop guards onto `turn_text` had been largely inert since it
    shipped.
    """
    path = _write(
        tmp_path,
        [
            _msg("user", "do the thing"),
            _msg("assistant", "AUDITED abc1234"),
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
            _msg("assistant", "done"),
        ],
    )

    text = hts.turn_text(path)

    assert "AUDITED abc1234" in text, "a statement made before a tool call must still be seen"
    assert "done" in text


def test_a_real_user_message_still_ends_the_turn(tmp_path: Path) -> None:
    """The guard must not swallow the PREVIOUS turn — that would make every claim permanent."""
    path = _write(
        tmp_path,
        [
            _msg("assistant", "OLD TURN"),
            _msg("user", "next instruction"),
            _msg("assistant", "NEW TURN"),
        ],
    )

    text = hts.turn_text(path)

    assert "NEW TURN" in text
    assert "OLD TURN" not in text


def test_turn_collects_every_assistant_message_since_the_last_user_turn(tmp_path: Path) -> None:
    """THE HOLE, measured 2026-08-09 over 2,274 real messages from 6 conversations.

    `last_assistant_text` returns ONE message. A working turn in this repo routinely produces
    forty, and the violations these guards exist to catch land mid-turn — the corpus holds 58
    messages matching `disowns_without_fixing` and 30 matching `cites_without_judging`, while
    the guards saw only whichever message happened to be last. So the detectors were live and
    the guards were still effectively blind.

    Scanning the turn is what makes every guard dynamic at once, with no regex involved.
    """
    path = _write(
        tmp_path,
        [
            _msg("user", "old instruction"),
            _msg("assistant", "PREVIOUS TURN — must not be included"),
            _msg("user", "do the thing"),
            _msg("assistant", "first: that's pre-existing, not mine"),
            _msg("assistant", "second: running the tests"),
            _msg("assistant", "third: all 15 pass"),
        ],
    )
    texts = hts.turn_assistant_texts(path)

    assert len(texts) == 3
    assert "pre-existing" in texts[0]
    assert "PREVIOUS TURN" not in " ".join(texts)
    # The last message alone would have missed the violation entirely.
    assert "pre-existing" not in hts.last_assistant_text(path)


def test_turn_text_joins_the_messages_for_predicates(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [_msg("user", "go"), _msg("assistant", "alpha"), _msg("assistant", "beta")],
    )
    assert "alpha" in hts.turn_text(path)
    assert "beta" in hts.turn_text(path)


def test_no_user_message_yields_every_assistant_message(tmp_path: Path) -> None:
    """A transcript that opens with assistant output must not silently yield nothing."""
    path = _write(tmp_path, [_msg("assistant", "only message")])
    assert hts.turn_assistant_texts(path) == ["only message"]


def test_unreadable_transcript_fails_silent(tmp_path: Path) -> None:
    """Same contract as the rest of this module: a guard that cannot read must not block."""
    assert hts.turn_assistant_texts(str(tmp_path / "missing.jsonl")) == []
    assert hts.turn_text(str(tmp_path / "missing.jsonl")) == ""


def test_turn_prose_reads_thinking_records_turn_text_does_not(tmp_path: Path) -> None:
    """Prose can reach the transcript ONLY as a thinking summary (measured 2026-09-17: 5 of 7).

    A PreToolUse guard asking "was X stated before this call" must see it there; `turn_text`
    stays text-only on purpose, because Stop guards judge the reply the owner actually read.
    """
    thinking = {
        "type": "assistant",
        "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": "facts for a.py"}]},
    }
    path = _write(tmp_path, [_msg("user", "go"), thinking, _msg("assistant", "editing now")])

    assert "facts for a.py" in hts.turn_prose(path)
    assert "editing now" in hts.turn_prose(path)
    assert "facts for a.py" not in hts.turn_text(path)


def test_turn_prose_stops_at_the_real_user_message(tmp_path: Path) -> None:
    """Falsifier: prose from an EARLIER turn must not vouch for this one."""
    path = _write(
        tmp_path,
        [_msg("assistant", "old turn facts"), _msg("user", "new request"), _msg("assistant", "now")],
    )
    assert "old turn facts" not in hts.turn_prose(path)
    assert hts.turn_prose(str(tmp_path / "missing.jsonl")) == ""


def _thought(text: str) -> dict[str, Any]:
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": text}]}}


def test_turn_prose_since_tool_result_is_the_thought_before_the_call(tmp_path: Path) -> None:
    """A PreToolUse guard judges the thought that led to THIS call: a thought already followed by a tool result was
    judged at its own call, so judging it again would deny every later call of the turn."""
    tool_result = {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}
    path = _write(tmp_path, [_msg("user", "go"), _thought("earlier thought"), tool_result, _thought("this thought")])

    assert hts.turn_prose(path, since_tool_result=True) == "this thought"
    assert "earlier thought" in hts.turn_prose(path), "the default still reads the whole turn"


def test_turn_prose_reads_across_backward_chunk_boundaries(tmp_path: Path) -> None:
    """The file is read from the END in chunks; a turn longer than one chunk must come back whole and in order."""
    filler = [_msg("assistant", f"line {i} " + "y" * 500) for i in range(400)]
    path = _write(tmp_path, [_msg("user", "go"), *filler])

    prose = hts.turn_prose(path)
    assert prose.startswith("line 0 ") and prose.count("line ") == 400



def _stamped(record: Mapping[str, object], iso: str) -> dict[str, object]:
    return {**record, "timestamp": iso}


_BOUNDARY = {"type": "system", "subtype": "compact_boundary", "content": "Conversation compacted"}
_READ_AT = 1_790_000_000.0  # 2026-09-21T13:33:20Z


def test_a_compaction_after_the_read_resets_the_context(tmp_path: Path) -> None:
    """HOOKRT-1: a doc read BEFORE a compaction is no longer in context; one after it still is."""
    path = _write(
        tmp_path,
        [
            _stamped(_msg("user", "go"), "2026-09-21T13:00:00Z"),
            _stamped(_msg("assistant", "read the doc"), "2026-09-21T13:33:21Z"),
            _stamped(_BOUNDARY, "2026-09-21T15:00:00Z"),
            _stamped(_msg("assistant", "after"), "2026-09-21T15:01:00Z"),
        ],
    )
    assert hts.context_reset_since(path, _READ_AT) is True


def test_a_compaction_before_the_read_does_not(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            _stamped(_BOUNDARY, "2026-09-21T12:00:00Z"),
            _stamped(_msg("assistant", "read the doc"), "2026-09-21T13:33:21Z"),
            _stamped(_msg("assistant", "still editing hours later"), "2026-09-21T18:00:00Z"),
        ],
    )
    assert hts.context_reset_since(path, _READ_AT) is False


def test_no_compaction_at_all_is_no_reset(tmp_path: Path) -> None:
    path = _write(tmp_path, [_stamped(_msg("assistant", "x"), "2026-09-21T18:00:00Z")])
    assert hts.context_reset_since(path, _READ_AT) is False


def test_the_scan_crosses_chunk_boundaries(tmp_path: Path) -> None:
    """The reader walks the file BACKWARDS in chunks; a boundary split across two must still count."""
    filler = [_stamped(_msg("assistant", "y" * 500), "2026-09-21T16:00:00Z") for _ in range(400)]
    path = _write(tmp_path, [_stamped(_BOUNDARY, "2026-09-21T15:00:00Z"), *filler])
    assert hts.context_reset_since(path, _READ_AT) is True


def test_an_unreadable_transcript_is_not_a_reset(tmp_path: Path) -> None:
    assert hts.context_reset_since(str(tmp_path / "missing.jsonl"), _READ_AT) is False
