"""The role guard must enforce the checklist phases, and stay out of the way otherwise."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parent / "architect_role_guard.py"
_spec = importlib.util.spec_from_file_location("arg", _HOOK)
assert _spec and _spec.loader
arg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arg)


@pytest.mark.parametrize(
    "path,expected",
    [
        ("apps/api/src/domain/services/foo.py", "src"),
        ("apps/web/src/hooks/useThing.ts", "src"),
        ("apps/web/src/components/Thing.tsx", "src"),
        ("apps/api/tests/unit/test_foo.py", "test"),
        ("apps/api/tests/test_bar.py", "test"),
        ("apps/web/src/hooks/__tests__/useThing.ts", "test"),
        ("apps/web/src/lib/thing.test.ts", "test"),
        ("docs/04-structural/ARCHITECT_CHECKLIST.md", None),
        (".claude/settings.json", None),
    ],
)
def test_path_classification(path: str, expected: str | None) -> None:
    assert arg.classify_path(path) == expected


def test_source_without_tests_flags_phase_3() -> None:
    """THE FAILURE: implementation shipped with nothing pinning the behaviour."""
    gaps = arg.missing_phases({"src": 2, "gates": 1})
    assert any("PHASE 3" in g for g in gaps)
    assert not any("PHASE 6" in g for g in gaps)


def test_source_without_gates_flags_phase_6() -> None:
    gaps = arg.missing_phases({"src": 2, "test": 1})
    assert any("PHASE 6" in g for g in gaps)
    assert any("CI-BLOCKING" in g for g in gaps)


def test_a_clean_turn_passes() -> None:
    assert arg.missing_phases({"src": 3, "test": 2, "gates": 4}) == []


def test_docs_only_turn_is_never_blocked() -> None:
    """Editing rules/docs is not production source -- the checklist does not apply."""
    assert arg.missing_phases({"gates": 0, "test": 0}) == []


def test_malformed_stdin_fails_open() -> None:
    proc = subprocess.run(
        [sys.executable, str(_HOOK)], input="not json", capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_non_stop_event_is_ignored() -> None:
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps({"hook_event_name": "PreToolUse"}),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
