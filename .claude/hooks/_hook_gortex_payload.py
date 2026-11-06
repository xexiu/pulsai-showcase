"""A gortex file edit or write, seen by the hooks as the built-in Edit / Write call it stands for.

IMPORTERS/CALLERS: _hook_mode_gate.py (every registration routes through it, so every guard gets the translation),
register_guards.py (BUILTIN_OF widens a declared Write / Edit matcher), no_new_noqa_guard.py (resolve_path).
AFFECTED API: the payload a guard receives for mcp__gortex__edit_file / mcp__gortex__write_file -- tool_name "Edit" /
"Write", tool_input {file_path (absolute), old_string, new_string, replace_all} / {file_path, content}; the original
tool name rides in `gortex_tool_name`. DATA SCHEMAS: none persisted.

REUSE-AUDIT: considered no_new_noqa_guard._resolve -- the one gortex path resolver in this directory; it moves here
and that guard imports it back. Considered _hook_mode_gate itself: it is the replay point and calls this, but keeps
no payload logic of its own (a pure function here is testable without spawning the gate).

GORTEX-HOOK-HOLE (2026-10-12). CLAUDE.md sends every source edit through gortex's edit_file / write_file, and the
write-time guards were written for Edit / Write: their matchers named only those tools, and 21 of the 23 read only
tool_input["file_path"], where gortex sends "path". Measured on the real binaries: one_definition_guard denied a
second home for epoch_ms as a Write and let the same text through as mcp__gortex__write_file. Translating the payload
once, at the gate every registration routes through, fixes every guard without teaching each one gortex.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

GORTEX_EDIT_FILE: Final = "mcp__gortex__edit_file"
GORTEX_WRITE_FILE: Final = "mcp__gortex__write_file"
GORTEX_BATCH_EDIT: Final = "mcp__gortex__batch_edit"
#: The built-in tool each gortex file tool stands for. register_guards widens matchers with the same map. A batch is
#: mostly edits, so an Edit matcher hears it; as_builtins hands each of its entries over as its own Edit / Write.
#: GORTEX-BATCH-HOLE (2026-10-14): until this entry a batch_edit reached NO write-time guard -- no matcher named the tool
#: and as_builtin returned None for it (no top-level `path`). Measured by driving the real pandas guard: an `.apply` it
#: denies as a Write passed as a batch.
#: GORTEX-CONSOLIDATED-HOLE (2026-10-28): gortex merged the three into ONE tool (operation file / write / batch / symbol);
#: 0 of 60 PreToolUse matchers named it and as_builtins returned [] for it -- every gortex source edit reached no
#: write-time guard. It does an Edit's and a Write's job, so both matcher tokens hear it (HEARD_BY).
GORTEX_EDIT: Final = "mcp__gortex__edit"
BUILTIN_OF: Final = {GORTEX_EDIT_FILE: "Edit", GORTEX_WRITE_FILE: "Write", GORTEX_BATCH_EDIT: "Edit", GORTEX_EDIT: "Edit"}
#: The built-in matcher tokens a gortex tool is heard by (register_guards widens a declared token with these).
HEARD_BY: Final = {gortex: frozenset({builtin}) for gortex, builtin in BUILTIN_OF.items()} | {GORTEX_EDIT: frozenset({"Edit", "Write"})}


def resolve_path(raw: str, project_dir: str) -> Path:
    """A payload path as an absolute path; gortex also takes `<workspace>/<repo path>` and repo-relative spellings."""
    path = Path(raw)
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0] == Path(project_dir).name:
        parts = parts[1:]
    return Path(project_dir, *parts)


def as_builtin(payload: Any, project_dir: str) -> dict[str, Any] | None:
    """`payload` rewritten as the Edit / Write call a gortex edit_file / write_file is; None for any other call."""
    if not isinstance(payload, dict):
        return None
    if payload.get("tool_name") == GORTEX_EDIT:
        calls = _consolidated(payload, project_dir)
        return calls[0] if len(calls) == 1 else None
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if tool not in BUILTIN_OF or not isinstance(tool_input, dict) or not isinstance(tool_input.get("path"), str):
        return None
    builtin_input = _builtin_input(tool_input, tool == GORTEX_WRITE_FILE, project_dir)
    return {**payload, "tool_name": BUILTIN_OF[tool], "tool_input": builtin_input, "gortex_tool_name": tool}


def as_builtins(payload: Any, project_dir: str) -> list[dict[str, Any]]:
    """Every built-in call `payload` stands for: a gortex batch_edit's entries one by one (an entry carrying `content`
    and no `old_string` is a Write), a single gortex edit / write as itself; [] for any other call."""
    if isinstance(payload, dict) and payload.get("tool_name") == GORTEX_EDIT:
        return _consolidated(payload, project_dir)
    if not (isinstance(payload, dict) and payload.get("tool_name") == GORTEX_BATCH_EDIT):
        single = as_builtin(payload, project_dir)
        return [] if single is None else [single]
    tool_input = payload.get("tool_input")
    edits = tool_input.get("edits") if isinstance(tool_input, dict) else None
    out: list[dict[str, Any]] = []
    for entry in edits if isinstance(edits, list) else []:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            continue
        write = "content" in entry and "old_string" not in entry
        builtin_input = _builtin_input(entry, write, project_dir)
        out.append({**payload, "tool_name": "Write" if write else "Edit", "tool_input": builtin_input, "gortex_tool_name": GORTEX_BATCH_EDIT})
    return out


def is_batch(payload: Any) -> bool:
    """A call the mode gate judges entry by entry: a batch_edit, or the consolidated edit's batch operation."""
    if not isinstance(payload, dict):
        return False
    tool_input = payload.get("tool_input")
    consolidated = payload.get("tool_name") == GORTEX_EDIT and isinstance(tool_input, dict) and tool_input.get("operation") == "batch"
    return payload.get("tool_name") == GORTEX_BATCH_EDIT or consolidated


def _consolidated(payload: dict[str, Any], project_dir: str) -> list[dict[str, Any]]:
    """The consolidated tool's call as the Edit / Write calls it stands for: `file` / `symbol` an Edit, `write` a Write,
    `batch` one per entry that changes text; [] for an operation that changes none (docs, a move, a delete)."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    operation = tool_input.get("operation")
    if operation == "batch":
        changes = tool_input.get("changes")
        return [call for entry in (changes if isinstance(changes, list) else []) if (call := _batch_entry(payload, entry, project_dir))]
    target = tool_input.get("target") if isinstance(tool_input.get("target"), dict) else {}
    path = target.get("file") or _symbol_path(target.get("symbol"))
    if not isinstance(path, str):
        return []
    # GORTEX-OPTIONS-HOLE (2026-11-05): the text rides under `options` too -- read both spellings, or the guards see "" -> ""
    options = tool_input.get("options") if isinstance(tool_input.get("options"), dict) else {}
    if operation == "write":
        return [_call(payload, "Write", {"path": path, "content": tool_input.get("content") or options.get("content")}, project_dir)]
    if operation in ("file", "symbol"):
        # GORTEX-TOPLEVEL-HOLE (2026-11-05): and top-level old_string / new_string, the shape this session's edits sent
        old = tool_input.get("match") or tool_input.get("old_source") or tool_input.get("old_string")
        old = old or options.get("old_string") or options.get("old_source")
        new = tool_input.get("replacement") or tool_input.get("new_source") or tool_input.get("new_string") or tool_input.get("content")
        new = new or options.get("new_string") or options.get("new_source") or options.get("content")
        edit = {"path": path, "old_string": old, "new_string": new, "replace_all": options.get("replace_all")}
        return [_call(payload, "Edit", edit, project_dir)]
    return []


def _batch_entry(payload: dict[str, Any], entry: Any, project_dir: str) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    if entry.get("op") == "edit_file" and isinstance(entry.get("path"), str):
        write = "content" in entry and "old_string" not in entry
        return _call(payload, "Write" if write else "Edit", entry, project_dir)
    if entry.get("op") == "edit_symbol" and (path := _symbol_path(entry.get("id"))):
        return _call(payload, "Edit", {"path": path, "old_string": entry.get("old_source"), "new_string": entry.get("new_source")}, project_dir)
    return None  # move_file / delete_file change no text a write-time guard reads


def _symbol_path(symbol: Any) -> str | None:
    """The file of a gortex symbol id (`<workspace>/<path>::<Name>`)."""
    return symbol.split("::", 1)[0] if isinstance(symbol, str) and "::" in symbol else None


def _call(payload: dict[str, Any], builtin: str, entry: dict[str, Any], project_dir: str) -> dict[str, Any]:
    return {**payload, "tool_name": builtin, "tool_input": _builtin_input(entry, builtin == "Write", project_dir), "gortex_tool_name": GORTEX_EDIT}


def _builtin_input(tool_input: dict[str, Any], write: bool, project_dir: str) -> dict[str, Any]:
    file_path = str(resolve_path(tool_input["path"], project_dir))
    if write:
        return {"file_path": file_path, "content": str(tool_input.get("content") or "")}
    return {
        "file_path": file_path,
        "old_string": str(tool_input.get("old_string") or ""),
        "new_string": str(tool_input.get("new_string") or ""),
        "replace_all": bool(tool_input.get("replace_all")),
    }
