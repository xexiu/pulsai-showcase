#!/usr/bin/env python3
"""THE one place that decides whether a hook body runs at all.

Owner, 2026-09-14: *"the hooks MUIST fire ONLY when your in AUTO mode or switch from X mode to
AUTO mode. NO hooks has to fire if not in auto mode!! SoT, centralized!!"*

## Why a gate and not 111 edits

The rule already existed for the TODO hooks (`.claude/rules/todo-always-track.md` § Scope, owner
2026-09-11) and was implemented the obvious way: each hook asks `_hook_mode` itself. Measured
today, that reached **12 of 111 hooks**. The other 99 fire in every mode, which is the state the
owner is describing.

Editing 99 files would fix today and not tomorrow: the 112th hook forgets, silently, and nothing
says so. So the decision moves to ONE process that every registration routes through, and a test
(`test_hook_mode_gate.test_every_file_based_registration_routes_through_the_gate`) fails the
build if a registration bypasses it. That is the difference between a convention and a gate.

## Why the leading underscore, and why renaming this file is dangerous

`test_every_guard_is_wired._guard_files()` treats every non-`test_`, non-`_` file here as a GUARD
that must carry its own registration. This is not a guard -- it is the wrapper in front of all of
them -- so it takes the `_` prefix that already marks shared hook infrastructure (`_hook_mode`,
`_hook_state`, `_hook_registry`, `_hook_exclusions`). Adding it to
`_hook_exclusions.NOT_RUNTIME_HOOKS` instead would be WRONG: `test_guards_end_to_end` asserts
nothing in that set is bound to a hook event, and this file is bound to all 134 of them.

RENAMING THIS FILE BREAKS THE LIVE SESSION. It cost one during development, and the failure is
worse than it sounds. The CLI CACHES `settings.json`, so the file move and the registration
rewrite are never atomic: between them every hook invocation dies with `can't open file`. Because
PreToolUse fires BEFORE the command that would repair it, Bash, Write and Edit all become
unusable at once -- the repair tool needs the very file the repair would create. The way out was
an MCP tool (`mcp__gortex__edit` move_file), which the PreToolUse matchers do not cover.

If this must ever be renamed: WRITE THE NEW FILE FIRST, update settings.json, confirm a tool call
succeeds, and only then delete the old one. Never `mv`.

## Usage

    python3 .../_hook_mode_gate.py <real_hook_path> [args...]      # payload on stdin

## The decision, in order (first match wins)

1. **Subagent** (`agent_id` present) -> SILENT, in every mode including auto. Stricter than the
   mode rule and already `_hook_mode`'s documented position: a subagent's tool calls carry the
   SAME session_id as the main conversation, so letting its hooks run corrupts the owner-facing
   todo state.
2. **ALWAYS_ON_HOOKS** -> RUN, in every mode. Irreversible-loss guards only; see `_hook_mode`.
2b. **Harness side session** (`harness_side_session`: the IDE's conversation summarizer) -> SILENT, every mode.
   Its Stop hooks blocked the summary with demands and it acted on them -- killed the MEXC demo engines twice,
   committed with `git add -A`, pushed master (ENGINE-DOWN-2, 2026-10-12). Below decision 2 on purpose: the
   irreversible-loss guards still stand between it and a stage-all or a --no-verify push.
3. **Self-gating hook** (the target imports `_hook_mode`) -> RUN. It enforces the owner's rule
   with a FINER one: outside auto it stays silent but still RECORDS baselines, which is what
   stops the first auto TodoWrite after a mode switch from being judged against a stale list.
   Gating these wholesale would reintroduce the exact defect `_hook_mode` was written to kill.
4. **GATE_HOOKS, in any mode but plan** -> RUN. A gate speaks only on a violation (a commit, a
   push, code with a second home, a money claim), so it costs nothing on clean work and must not
   go dark because the session is in `default` or `acceptEdits` (HOOK-MODE-1, 2026-09-25).
5. **auto, or no mode in the payload** -> RUN.
6. otherwise -> SILENT: exit 0, no stdout, no stderr.

## Two properties that are not obvious and are tested

**No second interpreter.** The target runs IN THIS PROCESS via `runpy`, with stdin replayed from
the text already consumed. A subprocess would have doubled Python startup on every tool call in
auto mode -- where the owner spends most of his time -- to buy nothing.

**Failure is OPEN, always.** A malformed payload, an unreadable target, a crash in the gate: the
target runs, or the tool call proceeds. A gate that eats hooks on bad input silently disables the
entire guard set, and nothing would report it.

REUSE-AUDIT: considered extending `_hook_mode.py` (imported below); not extending it because that
module is a pure predicate with no process, argv or stdin concerns, and folding a runner into it
would make every one of its 14 importers depend on runpy. Considered `_hook_state.py` (session
state I/O) -- unrelated. Searched `.claude/hooks` for gate/dispatch/wrapper/runner and gortex
`search text "_hook_mode"` (count: 0, `.claude` is pruned from the index): no dispatcher exists.
"""

from __future__ import annotations

import io
import json
import os
import re
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

from _hook_mode import (
    ALWAYS_ON_HOOKS,
    GATE_HOOKS,
    agent_can_act,
    fired_inside_subagent,
    harness_side_session,
    hooks_may_speak,
)
from _hook_gortex_payload import as_builtin, as_builtins, is_batch

#: A hook that already asks the mode itself (decision 3 above) IMPORTS `_hook_mode`.
#:
#: MEASURED, and the first version of this was wrong in a way that made decision 3 inert. It read
#: the first 4096 bytes and looked for the bare token `_hook_mode`. Both halves were defects:
#:
#:   * 4096 was too small for EVERY self-gating hook -- 0 of 10 carry the token that early. The
#:     earliest sits at byte 4,195 and the latest at 22,818, because the docstrings in this
#:     directory record whole incidents before the imports. So every self-gating hook would have
#:     been classified ordinary and silenced outside auto: the regression decision 3 exists to
#:     prevent, shipped by the mechanism meant to prevent it. Any byte cap large enough today is
#:     one long docstring away from being wrong again, so there is no cap.
#:
#:   * a bare token matches PROSE. This module's own docstring names `_hook_mode` repeatedly; a
#:     hook that merely mentions it would have been waved through to speak in plan mode.
#:
#: Matching the import statement is both precise and cheap.
SELF_GATING_IMPORT: Final = re.compile(r"^\s*(?:from|import)\s+_hook_mode\b", re.MULTILINE)


class _ReplayedStdin(io.StringIO):
    """Stdin the gate already drained, handed back to the target unchanged.

    Exposes ``.buffer`` because a hook is free to read bytes -- `json.load(sys.stdin)` and
    `sys.stdin.buffer.read()` are both in use across this directory, and a gate that supported
    only the first would break the second with no error anyone would connect to this file.
    """

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self._buffer = io.BytesIO(text.encode("utf-8"))

    @property
    def buffer(self) -> io.BytesIO:
        """WHAT REFUTED THE PREVIOUS VERSION: mypy, at this line.

            hook_mode_gate.py:97: error: Property "buffer" defined in "TextIO" is read-only

        The first version assigned `self.buffer = io.BytesIO(...)` in __init__. `TextIOBase`
        declares `buffer` as a read-only property, so the assignment is invalid -- a property
        override is the supported way to supply it.
        """
        return self._buffer


def _read_payload() -> tuple[str, Any]:
    """The raw stdin text and its parsed form. Unparseable input parses to None, never raises."""
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return "", None
    try:
        return raw, json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw, None


def _is_self_gating(target: Path) -> bool:
    """True when the target already consults the mode itself, so the gate must not pre-empt it.

    MEASURED on the 10 self-gating `*_guard.py` files, which is what refuted the previous version
    of this function: it read `handle.read(4096)` and searched for the bare token `_hook_mode`.

        within the first 4096 bytes:  0 / 10
        earliest token offset:        4,195   todo_priority_order_guard.py
        latest token offset:         22,818   todo_completion_guard.py

    So the old rule returned False for EVERY self-gating hook, silencing all 10 outside auto --
    the exact regression decision 3 was added to prevent. Reading the whole file removes the
    cliff; matching the import instead of the token stops this module's own prose from matching.
    """
    try:
        source = target.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return SELF_GATING_IMPORT.search(source) is not None


def should_run(target: Path, payload: Any) -> bool:
    """The whole decision. Pure, so the tests can pin it without spawning anything."""
    if fired_inside_subagent(payload):
        return False
    if target.name in ALWAYS_ON_HOOKS:
        return True
    if harness_side_session(payload):
        return False
    if _is_self_gating(target):
        return True
    if target.name in GATE_HOOKS and agent_can_act(payload):
        return True
    return hooks_may_speak(payload)


def builtin_view(raw: str, payload: Any) -> str:
    """The text every target is replayed: a gortex edit_file / write_file as the Edit / Write it stands for
    (GORTEX-HOOK-HOLE, 2026-10-12 -- 21 of 23 write-time guards read only `file_path`, which gortex does not send);
    any other payload byte for byte."""
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or (cwd if isinstance(cwd, str) else "") or os.getcwd()
    builtin = as_builtin(payload, project_dir)
    return raw if builtin is None else json.dumps(builtin)


def _run_python_target(target: Path, args: list[str], raw: str) -> int:
    """Run a python hook in THIS process, with stdin replayed and argv shaped as it expects."""
    original_stdin, original_argv = sys.stdin, sys.argv
    sys.stdin = _ReplayedStdin(raw)
    sys.argv = [str(target), *args]
    try:
        runpy.run_path(str(target), run_name="__main__")
    except SystemExit as exit_signal:
        code = exit_signal.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        sys.stderr.write(f"{code}\n")
        return 1
    finally:
        sys.stdin, sys.argv = original_stdin, original_argv
    return 0


def _run_other_target(target: Path, args: list[str], raw: str) -> int:
    """Shell out for a non-python hook, preserving the interpreter the registration named.

    WHAT REFUTED THE PREVIOUS VERSION: it ran `[str(target), *args]`, exec'ing the script
    directly. Measured, the one shell hook in this directory is `-rwxr-xr-x`, so that works
    TODAY -- which is exactly what makes it the wrong call. The registration this replaced said
    `bash "$CLAUDE_PROJECT_DIR/.claude/hooks/reuse-check.sh"`, and `bash <path>` does not depend
    on the executable bit. A checkout, archive or rsync that drops the bit would turn a working
    guard into one that never fires, with no error anyone would trace back to here.
    """
    interpreter = ["bash"] if target.suffix == ".sh" else []
    completed = subprocess.run(
        [*interpreter, str(target), *args],
        input=raw,
        text=True,
        env={**os.environ},
        check=False,
    )
    return completed.returncode


def main() -> int:
    if len(sys.argv) < 2:
        return 0

    target = Path(sys.argv[1])
    args = sys.argv[2:]
    raw, payload = _read_payload()

    if not target.exists():
        # A stale registration must never break the owner's tool call.
        return 0

    if not should_run(target, payload):
        return 0

    if is_batch(payload):
        return _run_batch(target, args, payload)
    raw = builtin_view(raw, payload)
    if target.suffix == ".py":
        return _run_python_target(target, args, raw)
    return _run_other_target(target, args, raw)


#: An answer that stops the call: a PreToolUse deny, or a PostToolUse / Stop block.
DECISIVE: Final = re.compile(r'"(?:permissionDecision|decision)"\s*:\s*"(?:deny|block)"')


def _run_batch(target: Path, args: list[str], payload: dict[str, Any]) -> int:
    """GORTEX-BATCH-HOLE (2026-10-14): a gortex batch_edit judged entry by entry -- the target replayed once per built-in
    call the batch stands for, each answer captured, and ONE answer emitted: the first deny / block (with its exit code),
    else the first non-empty answer. Never one answer per entry, which the harness could not parse."""
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or str(payload.get("cwd") or "") or os.getcwd()
    first: tuple[int, str] | None = None
    for builtin in as_builtins(payload, project_dir):
        code, out = _run_captured(target, args, json.dumps(builtin))
        if code == 2 or DECISIVE.search(out):
            sys.stdout.write(out)
            return code
        if out and first is None:
            first = (code, out)
    if first is None:
        return 0
    sys.stdout.write(first[1])
    return first[0]


def _run_captured(target: Path, args: list[str], raw: str) -> tuple[int, str]:
    """One replay with its stdout captured: in this process for a python hook, piped for any other."""
    if target.suffix == ".py":
        original, sys.stdout = sys.stdout, io.StringIO()
        try:
            code = _run_python_target(target, args, raw)
            return code, sys.stdout.getvalue()
        finally:
            sys.stdout = original
    interpreter = ["bash"] if target.suffix == ".sh" else []
    done = subprocess.run([*interpreter, str(target), *args], input=raw, text=True, stdout=subprocess.PIPE, env={**os.environ}, check=False)
    return done.returncode, done.stdout


if __name__ == "__main__":
    sys.exit(main())
