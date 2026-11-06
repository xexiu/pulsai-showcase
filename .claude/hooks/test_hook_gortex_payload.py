"""A gortex file edit / write reaches the guards as the built-in Edit / Write it stands for.

IMPORTERS/CALLERS: none (a test module). AFFECTED API: _hook_gortex_payload (as_builtin, resolve_path, BUILTIN_OF).
DATA SCHEMAS: the PreToolUse / PostToolUse payload a guard receives.

REUSE-AUDIT: considered test_no_new_noqa_guard.py (it pins that guard's own gortex facade parsing, not the shared
translation) and test_hook_mode_gate.py (it pins the gate replaying the translated payload end to end).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _hook_gortex_payload import (
    BUILTIN_OF,
    GORTEX_BATCH_EDIT,
    GORTEX_EDIT,
    GORTEX_EDIT_FILE,
    GORTEX_WRITE_FILE,
    HEARD_BY,
    as_builtin,
    as_builtins,
    is_batch,
    resolve_path,
)

ROOT = "/work/pulsai"


def _payload(tool: str, tool_input: dict[str, object]) -> dict[str, object]:
    return {"hook_event_name": "PreToolUse", "session_id": "s-1", "tool_name": tool, "tool_input": tool_input}


def test_a_gortex_edit_is_the_edit_it_stands_for() -> None:
    edit = as_builtin(_payload(GORTEX_EDIT_FILE, {"path": "pulsai/apps/api/x.py", "old_string": "a", "new_string": "b"}), ROOT)
    assert edit is not None
    assert edit["tool_name"] == "Edit"
    assert edit["tool_input"] == {"file_path": f"{ROOT}/apps/api/x.py", "old_string": "a", "new_string": "b", "replace_all": False}
    assert edit["gortex_tool_name"] == GORTEX_EDIT_FILE
    assert edit["session_id"] == "s-1"  # everything else in the payload rides along unchanged


def test_a_gortex_write_is_the_write_it_stands_for() -> None:
    write = as_builtin(_payload(GORTEX_WRITE_FILE, {"path": f"{ROOT}/docs/n.md", "content": "text"}), ROOT)
    assert write is not None
    assert (write["tool_name"], write["tool_input"]) == ("Write", {"file_path": f"{ROOT}/docs/n.md", "content": "text"})


def test_every_path_spelling_gortex_accepts_resolves_to_the_same_file() -> None:
    """gortex takes an absolute path, a workspace-prefixed one (`pulsai/...`) or a repo-relative one."""
    spellings = (f"{ROOT}/apps/api/x.py", "pulsai/apps/api/x.py", "apps/api/x.py")
    assert {str(resolve_path(s, ROOT)) for s in spellings} == {f"{ROOT}/apps/api/x.py"}


def test_any_other_call_is_left_alone() -> None:
    assert as_builtin(_payload("Edit", {"file_path": f"{ROOT}/x.py"}), ROOT) is None
    assert as_builtin(_payload("mcp__gortex__edit_symbol", {"id": "x.py::f"}), ROOT) is None
    assert as_builtin(_payload(GORTEX_EDIT_FILE, {"old_string": "a"}), ROOT) is None  # no path: nothing to name
    assert as_builtin(None, ROOT) is None
    assert as_builtin({"tool_name": GORTEX_WRITE_FILE, "tool_input": "not a dict"}, ROOT) is None


def test_the_map_names_only_tools_gortex_ships() -> None:
    """A canary: the tool names this translation exists for, each mapped to the built-in its matcher widens from (a
    batch is mostly edits, so an Edit matcher hears it; each entry still reaches the guard as its own Edit / Write)."""
    assert BUILTIN_OF == {GORTEX_EDIT_FILE: "Edit", GORTEX_WRITE_FILE: "Write", GORTEX_BATCH_EDIT: "Edit", GORTEX_EDIT: "Edit"}
    assert HEARD_BY[GORTEX_EDIT] == frozenset({"Edit", "Write"})  # it does both jobs: a Write-only guard must hear it
    assert all(HEARD_BY[g] == frozenset({b}) for g, b in BUILTIN_OF.items() if g != GORTEX_EDIT)


def test_the_consolidated_gortex_edit_is_the_edit_or_write_each_operation_stands_for() -> None:
    """GORTEX-CONSOLIDATED-HOLE (2026-10-28): gortex merged edit_file / write_file / batch_edit into ONE tool,
    mcp__gortex__edit (operation file / write / batch / symbol). This module knew only the old names, and 0 of 60
    PreToolUse matchers named the new one: every gortex source edit since reached no write-time guard. The shapes below
    are the ones this session's own calls sent."""
    file = _payload(GORTEX_EDIT, {"operation": "file", "target": {"file": "pulsai/apps/api/x.py"}, "match": "a", "replacement": "b"})
    assert [(c["tool_name"], c["tool_input"]) for c in as_builtins(file, ROOT)] == [
        ("Edit", {"file_path": f"{ROOT}/apps/api/x.py", "old_string": "a", "new_string": "b", "replace_all": False})]  # fmt: skip
    assert as_builtin(file, ROOT) == as_builtins(file, ROOT)[0]
    write = _payload(GORTEX_EDIT, {"operation": "write", "target": {"file": "apps/api/n.py"}, "content": "text"})
    assert [(c["tool_name"], c["tool_input"]) for c in as_builtins(write, ROOT)] == [("Write", {"file_path": f"{ROOT}/apps/api/n.py", "content": "text"})]
    symbol = _payload(GORTEX_EDIT, {"operation": "symbol", "target": {"symbol": "pulsai/apps/api/s.py::f"}, "match": "m", "replacement": "n"})
    assert as_builtins(symbol, ROOT)[0]["tool_input"]["file_path"] == f"{ROOT}/apps/api/s.py"
    assert all(c["gortex_tool_name"] == GORTEX_EDIT and c["session_id"] == "s-1" for c in (*as_builtins(file, ROOT), *as_builtins(write, ROOT)))


def test_the_consolidated_edit_reads_the_text_its_options_carry() -> None:  # PRIORITY-OK: the hole that blocks every edit
    """GORTEX-OPTIONS-HOLE (2026-11-05): gortex takes the text under `options` too -- {operation: file, options:
    {old_string, new_string}} and {operation: write, options: {content}} -- and this session's calls sent that shape.
    The translation read only the top-level spelling, so every such edit reached the guards as "" -> "" (owner_first_guard
    read each as cosmetic and never saw its PRIORITY-OK: 6 refusals in a row) and every such write as an empty file (no
    write-time guard read margin_use.py's or file_lock.py's code)."""
    edit = _payload(GORTEX_EDIT, {"operation": "file", "target": {"file": "pulsai/apps/api/x.py"},
                                  "options": {"old_string": "return cand", "new_string": "return replace(cand)"}})  # fmt: skip
    assert [c["tool_input"] for c in as_builtins(edit, ROOT)] == [
        {"file_path": f"{ROOT}/apps/api/x.py", "old_string": "return cand", "new_string": "return replace(cand)", "replace_all": False}]  # fmt: skip
    write = _payload(GORTEX_EDIT, {"operation": "write", "target": {"file": "apps/api/n.py"}, "options": {"content": "x = 1\n"}})
    assert [c["tool_input"] for c in as_builtins(write, ROOT)] == [{"file_path": f"{ROOT}/apps/api/n.py", "content": "x = 1\n"}]


def test_the_consolidated_edit_reads_old_and_new_string_at_the_top_level() -> None:  # PRIORITY-OK: the hole that blinds every guard to my edits
    """GORTEX-TOPLEVEL-HOLE (2026-11-05): gortex also takes {operation: file, target, old_string, new_string} -- the shape
    every edit of this session sent -- and the translation read only match / replacement / options, so each reached the
    guards as "" -> "": owner_first_guard read a new function (warm_start.after_env) as cosmetic and refused it, and the
    write-time guards (one-definition, reuse) judged an empty edit."""
    edit = _payload(GORTEX_EDIT, {"operation": "file", "target": {"file": "pulsai/apps/api/x.py"},
                                  "old_string": "def a(): ...", "new_string": "def a(): ...\ndef b(): ..."})  # fmt: skip
    assert [c["tool_input"] for c in as_builtins(edit, ROOT)] == [
        {"file_path": f"{ROOT}/apps/api/x.py", "old_string": "def a(): ...", "new_string": "def a(): ...\ndef b(): ...", "replace_all": False}]  # fmt: skip


def test_a_consolidated_batch_is_one_call_per_entry_that_changes_text() -> None:
    batch = _payload(GORTEX_EDIT, {"operation": "batch", "changes": [
        {"op": "edit_file", "path": "pulsai/apps/api/a.py", "old_string": "x", "new_string": "y", "replace_all": True},
        {"op": "edit_symbol", "id": "pulsai/apps/api/b.py::Cls.f", "old_source": "p", "new_source": "q"},
        {"op": "move_file", "source": "apps/api/c.py", "destination": "apps/api/d.py"},
        {"op": "delete_file", "path": "apps/api/e.py"},
        7,
    ]})  # fmt: skip
    calls = as_builtins(batch, ROOT)
    assert [(c["tool_name"], c["tool_input"]["file_path"]) for c in calls] == [("Edit", f"{ROOT}/apps/api/a.py"), ("Edit", f"{ROOT}/apps/api/b.py")]
    assert calls[0]["tool_input"]["replace_all"] is True and calls[1]["tool_input"]["new_string"] == "q"
    assert is_batch(batch) and is_batch(_payload(GORTEX_BATCH_EDIT, {"edits": []}))
    assert as_builtin(batch, ROOT) is None  # several calls are never squeezed into one


def test_a_consolidated_call_that_changes_no_text_is_left_alone() -> None:
    for tool_input in ({"operation": "docs"}, {"operation": "file"}, {"operation": "batch", "changes": "x"}, "not a dict"):
        assert as_builtins(_payload(GORTEX_EDIT, tool_input), ROOT) == []  # type: ignore[arg-type]
    assert not is_batch(_payload(GORTEX_EDIT, {"operation": "file"})) and not is_batch(None)


def test_a_gortex_batch_is_one_builtin_call_per_entry() -> None:
    """GORTEX-BATCH-HOLE (2026-10-14): a batch_edit reached no write-time guard -- as_builtin returned None (no top-level
    `path`) and no matcher named the tool. Measured: an `.apply` the pandas guard denies as a Write passed as a batch."""
    batch = _payload(GORTEX_BATCH_EDIT, {"edits": [
        {"path": "pulsai/apps/api/a.py", "old_string": "x", "new_string": "y"},
        {"path": "apps/api/b.py", "old_string": "p", "new_string": "q", "replace_all": True},
        {"path": f"{ROOT}/apps/api/c.py", "content": "new file"},
    ]})  # fmt: skip
    calls = as_builtins(batch, ROOT)
    assert [c["tool_name"] for c in calls] == ["Edit", "Edit", "Write"]
    assert [c["tool_input"]["file_path"] for c in calls] == [f"{ROOT}/apps/api/{n}.py" for n in "abc"]
    assert calls[1]["tool_input"]["replace_all"] is True and calls[2]["tool_input"]["content"] == "new file"
    assert all(c["gortex_tool_name"] == GORTEX_BATCH_EDIT and c["session_id"] == "s-1" for c in calls)


def test_a_single_gortex_call_is_one_entry_and_anything_else_is_none() -> None:
    single = _payload(GORTEX_EDIT_FILE, {"path": "apps/api/x.py", "old_string": "a", "new_string": "b"})
    assert as_builtins(single, ROOT) == [as_builtin(single, ROOT)]
    assert as_builtins(_payload("Edit", {"file_path": f"{ROOT}/x.py"}), ROOT) == []
    assert as_builtins(_payload(GORTEX_BATCH_EDIT, {"edits": "not a list"}), ROOT) == []
    assert as_builtins(_payload(GORTEX_BATCH_EDIT, {"edits": [{"old_string": "no path"}, 7]}), ROOT) == []
