#!/usr/bin/env python3
"""Never `git push --no-verify` without the owner authorising THIS push.

Owner, 2026-08-12: *"NEver push with --no-verify unless I tell you so... Make a hook and block
you"*.

## What it cost

The owner had authorised `--no-verify` conditionally and earlier: *"use --no-verify if git push
blocks you because of the parallel dev changes/files and your 100% that your files/changes are
100% CLEAN"*. My files WERE clean. I verified ruff, ruff format, mypy and the tests on every file
I had touched, and pushed.

The push carried **197 commits**, not my files. Among them was half of a `3d`-timeframe feature:

    origin/master   Timeframe = ... '1d' | '1w'          <- no '3d'
    committed       confluence.ts references '3d'
    UNCOMMITTED     the file that adds '3d' to the union

Committed consumers referencing a type member that only existed in an uncommitted file. Vercel's
build failed on 8 type errors and the production deploy crashed. **The pre-push hook runs `tsc`
and would have caught it in seconds** — that is what it is for, and it is the thing I skipped.

The lesson is not "the authorisation was wrong". It is that authorisation to bypass a gate is
scoped to a MOMENT and a DIFF, and I applied it to a push whose contents I had not audited. "My
files are clean" is not "this push is safe" when the push carries 197 commits.

## The rule

`--no-verify` (and `-n`) on a `git push` is DENIED unless the command carries an explicit,
auditable authorisation marker naming what is being bypassed and why it is safe RIGHT NOW:

    # NO-VERIFY-OK: <owner's words authorising this push> | bypassing: <gate> | safe because: <why>

Same shape as this repo's `RERUN-OK:` and `REUSE-AUDIT:` markers. It does not make bypassing
impossible — nothing can, since the agent writes the command — but it makes it a deliberate,
recorded act instead of a reflex, and it forces the scope question ("what else is in this push?")
to be answered in writing before the gate is skipped.

Commit-time `--no-verify` is NOT blocked: that skips lint-staged on one commit and the pre-push
gate still runs afterwards. Only the push, which is the irreversible one, is guarded.

## NOVERIFY-FP-1 (2026-09-25) — a MENTION is not an INVOCATION

Measured false positive: `grep -rn "git push --no-verify" docs/` was DENIED. The original
`violation()` regex-scanned the raw command TEXT for `git ... push` next to `--no-verify`/`-n`,
so a grep PATTERN, a `git log --grep=...`, an `echo`, or a commit message that merely NAMES the
flag read the same as running it. `id_provenance_guard.py` already paid for this exact lesson
("mention is not invocation") for a different subject (opaque IDs); this hook re-learned it the
hard way for its own.

Fixed by classifying each `&&`/`;`/`|`/newline SEGMENT by its COMMAND WORD (quote-aware, via
`_hook_command.resolve_invocation` + `git_subcommand`) instead of substring-matching the whole
command: a segment only denies when its command word is `git` (directly, or unwrapped from one
level of `sh -c` / `bash -c`) AND its git SUBCOMMAND is `push` AND a bypass flag is one of push's
own argument TOKENS — never a token borrowed from someone else's quoted argument. Every prior
true-positive fixture (chains, env-prefixes, `-n`, the marker) still passes; see
`apps/api/tests/hooks/test_no_verify_push_guard.py`.

Fails OPEN on any internal error.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _hook_command import (  # noqa: E402
    git_subcommand,
    quoted_tokens,
    resolve_invocation,
    split_segments,
    strip_heredoc_bodies,
)

HOOK_EVENT = "PreToolUse"

#: Shells that can be handed a script via `-c`. `sh -c "git push --no-verify"` really pushes; the
#: segment's own command word is the shell, not `git`, so it must be unwrapped one level first.
_SHELL_WRAPPERS = frozenset({"sh", "bash", "zsh", "ksh", "dash"})
#: `eval` runs its joined arguments as a script -- the same unwrap as `sh -c`, one layer.
_EVAL = "eval"
#: husky skips every hook when this is set to 0 -- its own documented off switch.
_HUSKY_OFF = "HUSKY=0"
#: `git -c core.hooksPath=<dir>` points the hook directory at <dir>, so no pre-push gate runs.
_HOOKS_PATH_KEY = "core.hookspath="

#: `-n` is the short form of `--no-verify` on `git push`. Matched as a whole ARGUMENT TOKEN
#: (never a substring), so `feature-n` or a quoted mention elsewhere never qualifies.
_SKIP_FLAG_TOKEN = re.compile(r"^(?:--no-verify|-n)$")

#: The authorisation marker. Must name the bypass and the reason, not merely appear.
_MARKER = re.compile(
    r"NO-VERIFY-OK:\s*\S.*?\|\s*bypassing:\s*\S.*?\|\s*safe because:\s*\S",
    re.I | re.S,
)

_REASON = """DENIED — `git push --no-verify` without an authorisation marker.

Owner, 2026-08-12: "NEver push with --no-verify unless I tell you so... Make a hook and block you"

WHAT IT COST (the same day). A conditional authorisation given earlier — "use --no-verify if git
push blocks you because of the parallel dev files, and you're 100% sure YOUR files are clean" —
was applied to a push carrying 197 COMMITS. My files were clean; the push was not. It shipped half
a 3d-timeframe feature:

    origin/master   Timeframe = ... '1d' | '1w'      <- no '3d'
    committed       confluence.ts references '3d'
    UNCOMMITTED     the file adding '3d' to the union

Vercel failed on 8 type errors and the production deploy crashed. The pre-push hook runs `tsc` and
would have caught it in seconds.

Authorisation to skip a gate is scoped to a MOMENT and a DIFF. "My files are clean" is not "this
push is safe" when the push carries everything else too.

DO ONE:
  * push WITH the gate (drop --no-verify) and fix whatever it reports — that is the whole point; or
  * ask the owner for authorisation for THIS push, then record it in the command:

      # NO-VERIFY-OK: <owner's words> | bypassing: <which gate> | safe because: <why, incl. what
      #               else is in this push and why that is safe>

Before writing that marker, answer: `git log --oneline origin/master..HEAD | wc -l` — how many
commits does this push actually carry, and have you looked at them?
"""


def _segment_pushes_with_bypass(segment: str) -> bool:
    """True when this ONE segment actually invokes `git push` carrying a verify bypass.

    Unwraps a single `sh -c` / `bash -c` layer (recursing into the quoted script, itself
    re-split on `&&`/`;`/`|`/newline) so a wrapped push is still caught; anything else whose
    command word is not `git` -- `grep`, `echo`, `git log`, `git commit` -- is a mention or a
    different subcommand, never a push, and is left alone.
    """
    word, args = resolve_invocation(segment)
    if word == _EVAL:
        return any(_segment_pushes_with_bypass(inner) for inner in split_segments(" ".join(args)))
    if word in _SHELL_WRAPPERS and "-c" in args:
        script_index = args.index("-c") + 1
        if script_index >= len(args):
            return False
        return any(_segment_pushes_with_bypass(inner) for inner in split_segments(args[script_index]))
    if word != "git":
        return False
    subcommand = git_subcommand(args)
    if subcommand != "push":
        return False
    push_args = args[args.index(subcommand) + 1 :]
    if any(_SKIP_FLAG_TOKEN.match(arg) for arg in push_args):
        return True
    return _skips_hooks_another_way(segment, args[: args.index(subcommand)])


def _skips_hooks_another_way(segment: str, global_args: list[str]) -> bool:
    """A push that carries no skip FLAG but still runs with no hooks (measured 2026-09-25).

    `HUSKY=0` as an environment prefix of this very segment, or `-c core.hooksPath=...` among
    git's global options. Only the invocation's own tokens are read, so a quoted mention of either
    (`echo "HUSKY=0 git push"`) stays a mention.
    """
    tokens = quoted_tokens(segment)
    git_index = next((index for index, token in enumerate(tokens) if token.rsplit("/", 1)[-1] == "git"), len(tokens))
    if _HUSKY_OFF in tokens[:git_index]:
        return True
    for flag, value in zip(global_args, global_args[1:], strict=False):
        if flag == "-c" and value.lower().startswith(_HOOKS_PATH_KEY):
            return True
    return False


def violation(command: str) -> str | None:
    """Reason to deny, or None."""
    if not command:
        return None
    if _MARKER.search(command):
        return None
    segments = split_segments(strip_heredoc_bodies(command))
    if not any(_segment_pushes_with_bypass(segment) for segment in segments):
        return None
    return "no authorisation marker"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # fail OPEN

    tool = str(payload.get("tool_name") or "")
    if tool != "Bash":
        return 0

    command = str((payload.get("tool_input") or {}).get("command") or "")
    if violation(command) is None:
        return 0

    print(_REASON, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
