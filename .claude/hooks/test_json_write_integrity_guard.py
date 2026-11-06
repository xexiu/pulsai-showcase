"""A session's own write left a JSON file unparseable — and nothing noticed for 43 minutes.

MEASURED TWICE IN THREE DAYS, both on the largest JSON files a session touches:

    2026-08-18  apps/web/messages/es.json          4721 of 5183 lines, write stopped mid-file
                json.decoder.JSONDecodeError: Expecting property name ... line 4722 column 1
                -> every `/es/*` route 404, dev log flooded, owner found it by reading pulsai.log

    2026-08-16  .../edge_hunt_models/registry.json  short write over a longer file, old tail left
                json.decoder.JSONDecodeError: Extra data: line 10199 column 2
                -> repaired by hand; the torn original is still on disk as `registry.json.torn`
                   (EXTERNAL_SCAN_LOG.md:7649)

Two different mechanisms, one class: **the file on disk stopped being valid JSON the moment a
session wrote it, and the session moved on.**

WHY THE EXISTING GATES DID NOT HELP. They are all COMMIT-time or READ-time, and both incidents
lived in the working tree:

    .husky/pre-commit -> lint-staged `*.json` -> `prettier --write`   exit 2 (measured)
    apps/web/tests/unit/messages/locale-parity.test.ts imports es.json  -> suite fails

Those are sound — es.json could never have been committed, which is why HEAD was clean. But
nothing looks at a file BETWEEN the write and the next commit, so the only reporter was the Next
dev server's browser console, under a wall of Celery INFO lines.

WHAT THIS GUARD DOES. PostToolUse on Write/Edit: if the target is a `.json` file, parse it. A
parse failure is reported IMMEDIATELY, in the same turn, while the correct content is still in
context and the fix is one re-write — not a 43-minute archaeology session.

Deliberately JSON-only. Both incidents were JSON; `.jsonl` is not one document and is skipped.
Fails OPEN on anything it cannot read. Bounded so a file that stays broken cannot wedge a turn.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


_GUARD = Path(__file__).resolve().parent / "json_write_integrity_guard.py"


def _run(payload: dict[str, Any], state: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin", "JSON_WRITE_INTEGRITY_STATE": str(state)},
    )


def _write_payload(path: Path) -> dict:
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "session_id": "s1",
        "tool_input": {"file_path": str(path)},
    }


def test_valid_json_passes(tmp_path: Path) -> None:
    """The overwhelmingly common case must cost nothing and say nothing."""
    target = tmp_path / "ok.json"
    target.write_text('{"a": 1}', encoding="utf-8")

    proc = _run(_write_payload(target), tmp_path / "state.json")

    assert proc.returncode == 0, proc.stderr
    assert proc.stderr.strip() == ""


def test_truncated_json_blocks_and_names_the_file(tmp_path: Path) -> None:
    """The es.json shape: the write stopped mid-document, so the tail is simply gone."""
    target = tmp_path / "es.json"
    target.write_text('{\n  "a": "1",\n  "b": "2",\n', encoding="utf-8")

    proc = _run(_write_payload(target), tmp_path / "state.json")

    assert proc.returncode == 2
    assert "es.json" in proc.stderr
    assert "line 4" in proc.stderr or "Expecting" in proc.stderr


def test_trailing_junk_json_blocks(tmp_path: Path) -> None:
    """The registry.json shape: a SHORT write over a LONGER file leaves the old tail behind.

    This is the one a length check or an eyeball on the last line would miss — the document
    closes correctly and there is simply more after it.
    """
    target = tmp_path / "registry.json"
    target.write_text('{"a": 1}\n{"stale": "tail"}\n', encoding="utf-8")

    proc = _run(_write_payload(target), tmp_path / "state.json")

    assert proc.returncode == 2
    assert "Extra data" in proc.stderr


def test_non_json_target_is_none_of_its_business(tmp_path: Path) -> None:
    """A guard that fires on ordinary work gets disabled by the first person it annoys."""
    target = tmp_path / "thing.py"
    target.write_text("this is not json at all", encoding="utf-8")

    proc = _run(_write_payload(target), tmp_path / "state.json")

    assert proc.returncode == 0


def test_jsonl_is_skipped(tmp_path: Path) -> None:
    """`.jsonl` is one document PER LINE — parsing the whole file is supposed to fail."""
    target = tmp_path / "events.jsonl"
    target.write_text('{"a": 1}\n{"a": 2}\n', encoding="utf-8")

    proc = _run(_write_payload(target), tmp_path / "state.json")

    assert proc.returncode == 0


def test_missing_file_path_fails_open(tmp_path: Path) -> None:
    """`test_every_guard_is_wired` feeds every guard a benign payload; it must survive it."""
    proc = _run(
        {"hook_event_name": "PostToolUse", "tool_input": {"todos": []}},
        tmp_path / "state.json",
    )

    assert proc.returncode == 0


def test_absent_file_fails_open(tmp_path: Path) -> None:
    """A path that is not on disk is a harness detail, not a torn write."""
    proc = _run(
        _write_payload(tmp_path / "never-written.json"), tmp_path / "state.json"
    )

    assert proc.returncode == 0


def test_a_file_that_stays_broken_keeps_blocking(tmp_path: Path) -> None:
    """A torn file does not become valid by being written again.

    This asserted the reverse — that the guard stopped blocking after N sightings so it "cannot
    wedge". Owner, 2026-08-28: "hook MUST fire ALWAYS not stay silent after X blocks". The block
    is correct exactly while the file is torn, so stepping aside would hand back a corrupt JSON
    on attempt N+1. Repairing the file clears it, which the next test measures.
    """
    target = tmp_path / "stuck.json"
    target.write_text("{", encoding="utf-8")
    state = tmp_path / "state.json"

    codes = [_run(_write_payload(target), state).returncode for _ in range(8)]

    assert codes[0] == 2, "the first sighting must block"
    assert all(code == 2 for code in codes), f"went quiet while the file was still torn: {codes}"


def test_repairing_the_file_clears_the_block(tmp_path: Path) -> None:
    """Measured here: a torn file blocks, and the same path passes once its JSON parses."""
    target = tmp_path / "cycle.json"
    state = tmp_path / "state.json"
    target.write_text("{", encoding="utf-8")

    assert _run(_write_payload(target), state).returncode == 2, "a torn file must block"

    target.write_text('{"ok": true}', encoding="utf-8")
    assert _run(_write_payload(target), state).returncode == 0

    target.write_text("{", encoding="utf-8")
    assert _run(_write_payload(target), state).returncode == 2, (
        "a path that was repaired and then torn again must block again"
    )


def test_the_message_names_the_recovery_route(tmp_path: Path) -> None:
    """Both incidents cost time in DIAGNOSIS, not repair. The block must skip that step."""
    target = tmp_path / "es.json"
    target.write_text('{"a": 1,', encoding="utf-8")

    stderr = _run(_write_payload(target), tmp_path / "state.json").stderr

    assert "git diff" in stderr or "git checkout" in stderr
    assert ".torn" in stderr
    assert "write_file" in stderr, (
        "the atomic, parse-gated writer is the actual prevention"
    )
