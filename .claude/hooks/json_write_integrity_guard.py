#!/usr/bin/env python3
"""A session wrote a JSON file and left it unparseable. Say so NOW, not 43 minutes later.

TWICE IN THREE DAYS, on the two largest JSON files a session touches, by two different mechanisms:

    2026-08-18  apps/web/messages/es.json           write stopped mid-document
                4721 of 5183 lines; `Expecting property name ... line 4722 column 1`
                every `/es/*` route 404 for ~43 min; the only reporter was the browser console,
                under a wall of Celery INFO lines in pulsai.log. The owner found it by reading.

    2026-08-16  research/artifacts/edge_hunt_models/registry.json    short write, old tail left
                `Extra data: line 10199 column 2`; repaired by hand, torn original kept as
                `registry.json.torn` (EXTERNAL_SCAN_LOG.md:7649)

One class: the file stopped being valid JSON the moment a session wrote it, and the session moved on.

WHY THE EXISTING GATES DID NOT HELP — they are sound, and they are all somewhere else. Measured:

    .husky/pre-commit -> lint-staged `*.json` (matches by BASENAME, so nested files DO match)
        -> `prettier --write` exits 2 on the truncated file      => it could never be COMMITTED
    apps/web/tests/unit/messages/locale-parity.test.ts imports messages/es.json
        -> the suite cannot even load it                          => `pnpm verify` would have failed

That is why HEAD was clean both times. The hole is not the commit gate; it is that NOTHING looks at
a file between the write and the next commit, and both incidents lived entirely in that window.

WHAT THIS DOES. PostToolUse on Write/Edit: if the target is a `.json` file, parse it. Report the
failure in the SAME TURN, while the correct content is still in context and the repair is one
re-write instead of an archaeology session.

SCOPE, deliberately narrow — a guard that fires on ordinary work gets disabled by the first person
it annoys. `.json` only (both incidents; `.jsonl` is one document per line and is skipped), only
when the file is actually on disk, only on Write/Edit.

Fails OPEN on everything it cannot read. NOT bounded: it fires every time the file is still torn.
A broken JSON does not become valid by being written again, so stepping aside after N sightings
would hand the corrupt file back on attempt N+1 — REPAIRING it is what clears the block, and a
path that is repaired and torn again blocks again (owner, 2026-08-28: "hook MUST fire ALWAYS not
stay silent after X blocks").
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

#: Declared so `register_guards.py` can wire it. Without these the registrar cannot see the file at
#: all — it reported "0 undeclared" while this guard sat registered NOWHERE and therefore dead,
#: which only `test_every_guard_is_wired` (which globs the directory) caught. A guard that reports
#: torn JSON is worth nothing if it never runs.
HOOK_EVENT = "PostToolUse"
HOOK_MATCHER = "Write|Edit"

#: Overridable so the tests never touch the live ledger — the lesson from `conftest.py`.
_STATE = Path(
    os.environ.get("JSON_WRITE_INTEGRITY_STATE")
    or "/tmp/claude-json-write-integrity.json"
)

#: Generous: the block is CORRECT while the file is broken. But an unbounded guard can wedge a
#: turn, which `todo_completion_guard` already taught this repo the expensive way.
_MAX_BLOCKS = 3


def _load() -> dict:
    try:
        data = json.loads(_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(data: dict) -> None:
    try:
        _STATE.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def _target(payload: dict) -> Path | None:
    """The written path, or None when this event is none of our business."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    raw = tool_input.get("file_path") or tool_input.get("path")
    if not raw:
        return None
    path = Path(str(raw))
    if path.suffix.lower() != ".json":
        return None
    return path if path.is_file() else None


def _top_level_blocks(text: str) -> dict[str, str]:
    """Each top-level key mapped to its own TEXT, split on the `  "key":` lines at indent 2.

    Text, never a re-serialization: the whole point is to catch a round trip, so performing one to
    detect it would be the joke writing itself.
    """
    blocks: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if indent == 2 and stripped.startswith('"') and '":' in stripped:
            current = stripped[1 : stripped.index('":')]
            blocks[current] = line
        elif indent == 0 and stripped.startswith(("}", "]")):
            # The DOCUMENT's closing brace, not the key's. Without this it is appended to whichever
            # key happens to be last, so removing a later key made the previous one read as moved
            # -- caught by `test_a_removed_key_is_not_drift`, which is why it exists.
            current = None
        elif current is not None:
            blocks[current] += line
    return blocks


def reformat_drift(head_text: str, new_text: str) -> list[str]:
    """Top-level keys whose MEANING is unchanged but whose LINES moved, in file order.

    A key that did not change has no business changing its formatting. Measured 2026-09-20 on
    `.claude/settings.json`: a `json.dumps(indent=2)` rewrite added one hook entry and silently
    re-expanded `"enabledMcpjsonServers": ["gortex", "railway", "vercel"]` onto five lines, in a
    file carrying another developer's uncommitted work. Memory
    `rewriting-a-file-must-not-reformat-it` already said "splice text and read one diff"; a memory
    that only speaks after the diff is read is not a control, so it is a check now.

    Deliberately silent on anything it cannot judge -- unparseable text (the torn-write arm owns
    that), non-object documents, added and removed keys. Only "unchanged value, changed text" is
    drift, and nothing else is guessed at.
    """
    try:
        head = json.loads(head_text)
        new = json.loads(new_text)
    except ValueError:
        return []
    if not isinstance(head, dict) or not isinstance(new, dict):
        return []

    head_blocks = _top_level_blocks(head_text)
    new_blocks = _top_level_blocks(new_text)
    return [
        key
        for key in new
        if key in head
        and head[key] == new[key]
        and key in head_blocks
        and key in new_blocks
        and _without_separator(head_blocks[key]) != _without_separator(new_blocks[key])
    ]


def _without_separator(block: str) -> str:
    """A block's text minus the comma that separates it from whatever follows.

    Caught by its own test: adding or removing a NEIGHBOURING key flips the trailing comma on the
    previous key's last line (`"a": 1,` -> `"a": 1`), which made an untouched key read as moved.
    The comma belongs to the gap between keys, not to either key's formatting, so it is excluded
    before comparing -- otherwise the guard fires on every legitimate key addition, which is the
    fastest way for a guard to be switched off.
    """
    return block.rstrip().rstrip(",")


def _drift_against_head(path: Path) -> list[str]:
    """Keys this write reformatted without changing, compared against the COMMITTED version.

    HEAD, not the previous working copy: the question is what a reviewer will see in the diff.
    Silent for untracked files, outside a repo, or when git is unavailable -- an unreadable
    baseline is not evidence of drift.
    """
    try:
        head = subprocess.run(
            ["git", "show", f"HEAD:./{path.name}"],
            cwd=path.parent,
            capture_output=True,
            check=False,
            timeout=10,
        )
        if head.returncode != 0:
            return []
        return reformat_drift(head.stdout.decode("utf-8"), path.read_text(encoding="utf-8"))
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def _report_drift(path: Path, keys: list[str]) -> None:
    named = ", ".join(f"`{k}`" for k in keys)
    print(
        f"REFORMAT DRIFT — this write changed the FORMATTING of {named} in `{path}` without "
        "changing what they mean.\n\n"
        "Those lines land in your diff as noise, and in a file carrying someone else's "
        "uncommitted work they land in your COMMIT.\n\n"
        "MEASURED 2026-09-20 on `.claude/settings.json`: a `json.dumps(indent=2)` rewrite added\n"
        "one hook entry and silently re-expanded an untouched key:\n\n"
        '    -  "enabledMcpjsonServers": ["gortex", "railway", "vercel"],\n'
        '    +  "enabledMcpjsonServers": [\n'
        '    +    "gortex",\n'
        "    +    ...\n\n"
        "Memory `rewriting-a-file-must-not-reformat-it` already says this: a parse/serialize round\n"
        "trip re-expands prettier-packed arrays. It did not stop it, so this does.\n\n"
        "FIX: splice the TEXT instead of re-serializing the document --\n"
        "  1. `git show HEAD:<path>` to get the exact committed text;\n"
        "  2. insert only your lines into it (anchor on a unique string, assert it occurs once);\n"
        "  3. `json.loads()` the result to prove it still parses;\n"
        "  4. re-read the diff -- it should contain ONLY the lines you meant to add.",
        file=sys.stderr,
    )


def _parse_error(path: Path) -> str | None:
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return str(exc)
    except OSError:
        return None
    return None


def _report(path: Path, error: str) -> None:
    print(
        f"TORN WRITE — `{path}` is no longer valid JSON after this write.\n\n"
        f"    {error}\n\n"
        "This has happened twice in three days, by two different mechanisms, and both times the\n"
        "session moved on and something else discovered it much later:\n"
        "  * messages/es.json stopped mid-document -> every /es/* route 404 for ~43 minutes, and\n"
        "    the only reporter was a browser console line buried in pulsai.log;\n"
        "  * registry.json took a SHORT write over a LONGER file, so the document closed correctly\n"
        "    and the STALE TAIL was still there (`Extra data`) — a length check would have passed it.\n\n"
        "Fix it now, in this turn:\n"
        f"  1. `git diff --numstat {path}` — additions 0 with deletions > 0 means a pure truncation\n"
        f"     and nothing was lost: `git checkout -- {path}` restores it exactly.\n"
        "  2. Untracked or genuinely new content? Preserve the damaged copy as `<name>.torn` first\n"
        "     (the convention already on disk), then rewrite it whole.\n"
        "  3. Then re-verify by PARSING it, not by looking at the last line.\n\n"
        "To stop causing it: write structured files with `mcp__gortex__write_file`, which writes\n"
        "atomically (temp+rename) and refuses a write that would introduce parse errors. A partial\n"
        "write can never be observed by a reader.",
        file=sys.stderr,
    )


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0

    path = _target(payload)
    if path is None:
        return 0

    key = str(path)
    state = _load()
    error = _parse_error(path)

    if error is None:
        if state.pop(key, None) is not None:
            _save(state)
        drift = _drift_against_head(path)
        if drift:
            _report_drift(path, drift)
            return 2
        return 0

    entry = state.get(key)
    if not isinstance(entry, dict) or entry.get("error") != error:
        entry = {"error": error, "blocks": 0}
    entry["blocks"] = int(entry.get("blocks", 0)) + 1
    state[key] = entry
    _save(state)

    # NO BLOCK BOUND (owner, 2026-08-28: "hook MUST fire ALWAYS not stay silent after X
    # blocks"). A release after N attempts makes outlasting the guard an escape hatch —
    # the claim it exists to stop would ship on attempt N+1. The only exit is to fix the
    # thing it names.
    _report(path, error)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
