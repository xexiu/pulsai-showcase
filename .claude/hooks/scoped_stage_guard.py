#!/usr/bin/env python3
"""Deny a staging command that takes MORE than the files you name.

Owner, verbatim and repeatedly: *"the commit and push make it on master branch directly please
(ONLY your files)"*.

## The violation, mine, 2026-08-15

Committing a rename I ran:

    git add -A apps/api/src/research/edge_lab/ apps/api/tests/unit/research/

It swept in `vt_17_remeasure_8h_cert_dollars.py` — a NEW 151-line untracked file I did not write —
plus a 2-line change to `walk_forward.py`. Nothing was lost or overwritten, and the commit still
read as mine, which is exactly the problem: the damage is SILENT. My own `git show --stat` audit
caught it one commit too late.

This repo's working tree is routinely dirty with the parallel developer's files — 353 of them at
the moment of the violation — so "just add the directory" is never a safe shorthand here.

## REUSE-AUDIT — why a new guard

`parallel_dev_audit_guard` watches for the parallel dev's COMMITS landing on master and demands
they be reviewed. That is the opposite direction: it says nothing about my staging command pulling
his UNCOMMITTED work into a commit of mine. No other guard reads Bash for git scope.

## Detection

PreToolUse(Bash). Blocks `git add` with `-A` / `--all` / `.` / a directory / a glob, and
`git commit -a`, which stages every tracked modification through another door. Naming files
passes. `git reset` / `git restore --staged` pass — they NARROW a commit and can never widen it.

Fails OPEN. Bounded blocks.
"""

from __future__ import annotations

import pathlib
from pathlib import Path

import json
import os
import re
import shlex
import sys
import tempfile
from dataclasses import dataclass
from typing import Final

HOOK_EVENT = "PreToolUse"
HOOK_MATCHER = "Bash"


#: Suffixes that make a path a FILE rather than a tree. Anything else staged by name is a
#: directory, and a directory is whatever happens to be dirty inside it at that moment.
_FILE_SUFFIXES: Final[tuple[str, ...]] = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".json",
    ".md",
    ".mdc",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".sh",
    ".sql",
    ".css",
    ".html",
    ".txt",
    ".lock",
    ".env",
    ".xml",
    ".svg",
    ".gitignore",
    ".dockerignore",
    "Dockerfile",
    "Makefile",
)

_STAGE_EVERYTHING: Final[frozenset[str]] = frozenset({"-A", "--all", ".", "-u", "--update", "*"})

#: CLAUDE.md requires this on every commit this agent writes. Without it,
#: `parallel_dev_audit_guard` — which identifies authorship by TRAILER, not by name — files the
#: commit as the parallel dev's and demands a review of my own work.
AGENT_TRAILER: Final[str] = "co-authored-by: claude"

#: Flags that mean "write a NEW commit message", i.e. the commit is being authored here and the
#: trailer belongs in it. `--amend --no-edit`, `--squash` and friends reuse an existing message,
#: so demanding a trailer from them would block a legitimate flow.
_AUTHORING_FLAGS: Final[frozenset[str]] = frozenset({"-m", "--message", "-F", "--file"})


#: `-F`/`--file` flags whose VALUE is a path to read. `-` means stdin (a heredoc), which is already
#: present in the command text and needs no file read.
_MESSAGE_FILE_FLAGS: Final[frozenset[str]] = frozenset({"-F", "--file"})


@dataclass(frozen=True)
class _MessageFiles:
    """What the `-F <path>` flags yielded: the text read, and the paths that would not open.

    The two travel TOGETHER because the caller needs both to write a true diagnostic. Returning
    only the text is what produced the misleading message this class exists to end: an unreadable
    file and a genuinely untrailered one became the same empty string.
    """

    text: str
    unreadable: tuple[str, ...]


def _read_message_files(args: list[str], base: pathlib.Path | None = None) -> _MessageFiles:
    """The text of any `-F <path>` message file, plus the paths that could not be opened.

    `git commit -F <path>` carries the trailer in the FILE. Checking only the command line reported
    every file-based message as untrailered, which — together with the inline-size limit on heredocs
    — left no legal way to write a long, correctly-attributed commit message.

    A path that will not open is recorded rather than swallowed. This guard reads raw command TEXT,
    so `-F $SCRATCH/msg.txt` never resolves — and deliberately so: a guard that evaluates shell to
    decide whether to allow a command has given away the thing it was guarding. Naming the file is
    the honest response; expanding it is not.
    """
    chunks: list[str] = []
    unreadable: list[str] = []
    for index, arg in enumerate(args):
        if arg not in _MESSAGE_FILE_FLAGS:
            continue
        if index + 1 >= len(args):
            continue
        path = args[index + 1].strip("\"'")
        if path == "-":  # stdin: the heredoc body is already in the command text
            continue
        # A RELATIVE path is relative to where the COMMAND runs, not to this hook's cwd. Measured
        # 2026-09-23 (HOOKRT-1): `cd <repo> && git commit -F .scratch/agent/msg.txt` was refused as
        # unreadable because the hook opened it from `.claude/hooks`.
        target = pathlib.Path(path)
        if base is not None and not target.is_absolute():
            target = base / target
        try:
            chunks.append(target.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            unreadable.append(path)  # never block on IO; report it instead of guessing
    return _MessageFiles(text="\n".join(chunks), unreadable=tuple(unreadable))

def commit_message_text(command: str) -> str:
    """Everything a `git commit` will read as its message: the command line PLUS any `-F` file.

    SHARED on purpose. Every guard that inspects a commit message needs this same view, and each
    one that reimplements it reimplements the same bug: `review_before_commit_guard` looked for
    `REVIEWED-MECHANICALLY:` in the raw command and so could never see a citation written in the
    message FILE -- the identical blindness this module had for `Co-Authored-By`, found the same
    afternoon, one guard apart. Two copies of a rule is two chances to get it wrong; this is the
    one copy.

    Returns the command text too, so a `-m` message and a heredoc keep working unchanged.
    """
    chunks = [command]
    for segment in _segments(command):
        found = _read_message_files(segment).text
        if found:
            chunks.append(found)
    return "\n".join(chunks)


def _authors_a_commit(args: list[str]) -> bool:
    """True when this `git commit` writes a fresh message rather than reusing one."""
    if any(a in ("--amend", "--no-edit", "--squash", "--fixup", "-C", "--reuse-message") for a in args):
        return False
    return any(a in _AUTHORING_FLAGS for a in args)


def strip_heredocs(command: str) -> str:
    """Drop heredoc BODIES, keeping the command line that opens them.

    THE FALSE POSITIVE THIS FIXES, on this guard's own first commit: the message was written as
    `git commit -F - <<'MSG' ... MSG` and QUOTED the offending command as its own case study. The
    guard read the message body as if it were a command and refused to let itself be committed.

    A guard that blocks the correct fix teaches people to route around it — which this file's own
    commit message argues, so shipping it while it did that would have been the joke writing
    itself. A heredoc body is DATA, never a command line.
    """
    out: list[str] = []
    lines = command.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        match = re.search(r"<<-?\s*'?\"?([A-Za-z_][A-Za-z0-9_]*)'?\"?", line)
        i += 1
        if match is None:
            continue
        terminator = match.group(1)
        while i < len(lines) and lines[i].strip() != terminator:
            i += 1
        i += 1  # skip the terminator itself
    return "\n".join(out)


def _segments(command: str) -> list[list[str]]:
    """Split a shell line into its individual commands, so `a && git add -A` is still seen.

    NEWLINES separate commands too. Without that, `git commit -F - <<'MSG' … MSG` followed by a
    real `git add .` on the next line collapsed into ONE segment whose first token was `commit`,
    and the `add` was never inspected — a hole big enough to drive the original violation through.
    """
    segments: list[list[str]] = []
    for line in strip_heredocs(command).splitlines():
        # Operator-aware lexing: plain shlex.split keeps a semicolon glued to the word before it,
        # so after "a.sh; cd <repo> && ..." the cd never began its own segment and a relative
        # message-file path was read from the wrong directory (refused 2026-09-23).
        try:
            lexer = shlex.shlex(line, posix=True, punctuation_chars=";&|")
            lexer.whitespace_split = True
            tokens = list(lexer)
        except ValueError:
            tokens = line.split()
        current: list[str] = []
        for token in tokens:
            if token in ("&&", "||", ";", "|"):
                segments.append(current)
                current = []
                continue
            current.append(token)
        segments.append(current)
    return [s for s in segments if s]


def _names_a_file(arg: str, base: pathlib.Path | None = None) -> bool:
    # RESOLVE AGAINST THE COMMAND'S CWD, NOT THE HOOK'S. MEASURED 2026-09-24: this used `Path(arg)`
    # against the hook PROCESS's cwd, although the caller had already computed `base` (the payload
    # cwd plus any `cd` segment). Off-root, `git add .husky/pre-commit` -- an extensionless FILE --
    # did not resolve, fell to the no-extension default and was refused as a DIRECTORY; and
    # `git add .husky` -- a real DIRECTORY -- fell to the fallback regex, which read the leading dot
    # as an extension and ALLOWED the sweep. One cause, both directions.
    # DERIVED, NOT ENUMERATED. This was `any(arg.endswith(s) for s in _FILE_SUFFIXES)` -- an
    # extension allowlist, so any extension nobody thought of read as a DIRECTORY and was refused.
    #
    # MEASURED 2026-08-20: `.jsonl` was not on the list, so
    #   git add apps/api/src/research/artifacts/vt_17_momentum/forward_tape.jsonl
    # was denied as "stages a DIRECTORY" for a single existing tracked FILE, while a `.md` path in
    # the same commit staged fine. Every forward TAPE is `.jsonl`, and a forward tape is the
    # evidence EDGEFOUND-1 requires (">= 40 clean forward-tape days"), so one missing extension
    # meant the artifact class the main objective depends on could never be committed at all.
    #
    # The filesystem answers this exactly, for every extension that exists now or later. A path
    # that no longer exists is a DELETION being staged -- still a file, never a directory -- so
    # only a real directory is refused. `_FILE_SUFFIXES` is kept as a fallback for paths outside
    # the working tree, where nothing is on disk to inspect.
    path = Path(arg)
    if base is not None and not path.is_absolute():
        path = base / path
    # A SYMLINK IS ONE INDEX ENTRY, NEVER A DIRECTORY TO SWEEP. `is_dir()` and `exists()` both
    # FOLLOW the link, so a link to a directory read as a DIRECTORY, and a dangling link fell
    # through to the suffix fallback and lost there if it had no extension. `git add <symlink>`
    # writes exactly one entry, mode 120000, whose blob is the target PATH -- it cannot reach the
    # target's contents, so it cannot take anyone else's dirty work. `is_symlink()` lstats, so it
    # answers for a broken link too.
    #
    # MEASURED 2026-09-22: every entry in `.claude/skills/` is a symlink into `.agents/skills/`,
    # so registering the mandatory `quick-recap` skill meant staging one link -- and the guard
    # refused it while advising "NAME THE FILES", which was impossible: the link IS the file git
    # tracks. Two of four cases failed (link-to-dir, broken link); link-to-file already passed.
    if path.is_symlink():
        return True
    if path.is_dir():
        return False
    if path.exists():
        return True
    # A BARE NAME IS NOT EVIDENCE OF A FILE. This began
    #     "/" not in arg.rstrip("/") or <suffix checks>
    # so any token without a slash — `apps`, `src`, `.claude` — read as a FILE and sailed through.
    # Those are top-level DIRECTORIES, and `git add apps` is the exact command this guard was
    # written to stop. The `path.is_dir()` check above only catches it when the hook's cwd happens
    # to be the repo root; run from `apps/api` (where most commands in this repo run) the path does
    # not resolve, control reached that clause, and the directory was staged.
    #
    # Measured 2026-08-28: `_names_a_file` returned True for 'apps', 'src' and '.claude', and
    # `stages_beyond_named_files("git add apps")` returned None.
    #
    # Off disk, only an EXTENSION is evidence of a file. Anything else is unverifiable, and the
    # safe default is DIRECTORY: being told to name the file costs one retype, while staging a
    # tree silently sweeps in the parallel developer's work — the damage this guard exists for.
    # An EXTENSION needs a name before its dot: `.husky` / `apps/.claude` are dot-NAMES (dotfiles and
    # dot-directories), never an extension, so a leading dot in the last segment proves nothing.
    return any(arg.endswith(suffix) for suffix in _FILE_SUFFIXES) or bool(
        re.search(r"[^/.]\.[A-Za-z0-9]{1,10}$", arg)
    )


_ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.DOTALL)
#: `$F`, `${F}`, and zsh's `${=F}` -- the ONLY spelling that word-splits in zsh, this repo's shell:
#: a bare `$F` there reaches git as one path containing spaces (measured 2026-09-23, exit 128).
_VARIABLE = re.compile(r"^\$\{?=?([A-Za-z_][A-Za-z0-9_]*)\}?$")


def _assignments(segments: list[list[str]]) -> dict[str, str]:
    """`NAME=value` segments of this same command, in order (a later one wins, as in the shell)."""
    found: dict[str, str] = {}
    for tokens in segments:
        for token in tokens:
            match = _ASSIGNMENT.match(token)
            if match is None:
                break  # an assignment prefix ends at the first word that is not one
            # shlex keeps an attached separator: `F='a b';` arrives as the token `F=a b;`.
            found[match.group(1)] = match.group(2).rstrip(";&")
    return found


def _expanded_args(args: list[str], assignments: dict[str, str]) -> list[str]:
    """Replace an unquoted `$NAME` / `${NAME}` by its words when this command assigned it.

    HOOKRT-1, measured 2026-09-23: `F="<22 literal paths>" && git add -- $F` was refused as a
    DIRECTORY although every path sat in the same command. Expansion is a pure function of the text,
    so the literal paths are judged instead. An UNASSIGNED variable is left as-is and refused below.
    """
    out: list[str] = []
    for arg in args:
        match = _VARIABLE.match(arg)
        if match and match.group(1) in assignments:
            out.extend(assignments[match.group(1)].split())
        else:
            out.append(arg)
    return out


def stages_beyond_named_files(command: str, cwd: str = "") -> str | None:
    """Reason to block, or None when the command stages only files it names.

    `cwd` is where the command starts (the hook payload's cwd); a `cd <dir>` segment moves it, so a
    relative `-F <path>` is read from where git will actually read it.
    """
    if not command or "git" not in command:
        return None

    segments = _segments(command)
    assignments = _assignments(segments)
    base = pathlib.Path(cwd) if cwd else None
    for tokens in segments:
        if tokens[0] == "cd" and len(tokens) > 1:
            moved = pathlib.Path(tokens[1])
            base = moved if moved.is_absolute() or base is None else base / moved
            continue
        if "git" not in tokens:
            continue
        idx = tokens.index("git")
        rest = tokens[idx + 1 :]
        if not rest:
            continue
        verb = rest[0]
        args = rest[1:]

        if verb == "commit":
            for arg in args:
                # `-am` and `-a` both stage every tracked modification.
                if arg == "-a" or (arg.startswith("-") and not arg.startswith("--") and "a" in arg[1:]):
                    return f"`git commit {arg}` stages every tracked modification, not your files"
            message_files = _read_message_files(args, base)
            authored_text = f"{command}\n{message_files.text}".lower()
            if _authors_a_commit(args) and AGENT_TRAILER not in authored_text:
                if message_files.unreadable:
                    return (
                        "this commit's message file could not be read, so its "
                        "`Co-Authored-By: Claude` trailer cannot be verified: "
                        f"{', '.join(message_files.unreadable)}. Pass a LITERAL path -- this "
                        "guard reads raw command text and never expands shell, so `$VAR/msg.txt` "
                        "is taken as the filename itself"
                    )
                return (
                    "this commit carries no `Co-Authored-By: Claude` trailer, so it will be filed "
                    "as the PARALLEL DEV's work"
                )
            continue

        if verb != "add":
            continue

        if not args:
            continue
        for arg in _expanded_args(args, assignments):
            if _VARIABLE.match(arg):
                return (
                    f"`git add {arg}` names a variable this command never assigns, so what it "
                    "stages is not knowable here. Assign it in the same command, or name the files"
                )
            if arg in _STAGE_EVERYTHING:
                return f"`git add {arg}` stages everything dirty, including work that is not yours"
            if arg.startswith("-"):
                continue
            if "*" in arg or "?" in arg:
                return f"`git add {arg}` is a glob — what it stages is not knowable at review time"
            if not _names_a_file(arg, base):
                return f"`git add {arg}` stages a DIRECTORY — whatever happens to be dirty in it"
    return None


def _state_path(session_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "nosession")
    return os.path.join(tempfile.gettempdir(), f"pulsai_scoped_stage_{safe}.json")


def _blocks_so_far(path: str) -> int:
    try:
        with open(path, encoding="utf-8") as handle:
            return int(json.load(handle).get("blocks", 0))
    except Exception:
        return 0


def _record(path: str, count: int) -> None:
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"blocks": count}, handle)
    except Exception:
        return


_REASON = (
    "BLOCKED — {problem}.\n\n"
    "Owner, verbatim: 'the commit and push make it on master branch directly please (ONLY your "
    "files)'.\n\n"
    "THE VIOLATION (2026-08-15): `git add -A apps/api/src/research/edge_lab/ ...` swept in "
    "`vt_17_remeasure_8h_cert_dollars.py` — a new 151-line file I did not write — plus a 2-line "
    "change to `walk_forward.py`. Nothing was lost, and the commit still read as mine. That is "
    "what makes it dangerous: the damage is SILENT, and `git show --stat` only found it one "
    "commit too late.\n\n"
    "This working tree is routinely dirty with the parallel developer's files (353 at the time), "
    "so 'just add the directory' is never safe here.\n\n"
    "NAME THE FILES:\n"
    "  git add path/to/one.py path/to/two.ts\n\n"
    "`git status --short` lists what changed; stage the ones you touched. If that list is long, "
    "it is long because someone else's work is in it."
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if (payload.get("tool_name") or "") != "Bash":
        return 0
    problem = stages_beyond_named_files(
        str((payload.get("tool_input") or {}).get("command", "")), cwd=str(payload.get("cwd") or "")
    )
    if problem is None:
        return 0

    path = _state_path(str(payload.get("session_id") or ""))
    seen = _blocks_so_far(path)
    _record(path, seen + 1)

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": _REASON.format(problem=problem),
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0) from None  # fail OPEN
