"""How much of a document does this SHELL COMMAND actually emit?

REUSE-AUDIT: considered `.claude/hooks/_hook_command.py` and IMPORT it (`split_segments`,
`strip_heredoc_bodies`, `command_word`) -- it is already the SoT for "what does this shell
command actually run", handling separators inside quotes, heredoc bodies, env-assignment
prefixes and wrapper commands, so this file parses no shell grammar of its own. Considered
`.claude/hooks/gortex_first_guard.py`, the only other hook reasoning about shell read extents:
not extending because it draws a BINARY line (bounded slice vs unbounded reader) to cap context
burn and has no notion of WHICH lines were emitted; narrowing it to answer that would change
what it blocks. Considered putting these functions inside `.claude/hooks/_hook_evidence.py`,
their only caller: not extending because that module is the LEDGER, already at the 400-line
standard, and shell-grammar parsing is a second responsibility -- the same SRP split that
already separates `_hook_command.py` from the guards that use it. Considered extending
`covers_whole_file` in place: its input is a tool_input dict with numeric offset/limit, this
one's is a command string, so the two share a question and no mechanism. The collision check
surfaced `AIAnalysisPanels.hook-error-boundary.test.tsx` on the shared `hook` token: a React
error-boundary test for a dashboard panel, sharing no subject, input or mechanism with shell
read extents.

Importers/callers: `_hook_evidence.record()`, the one place that decides whether a `rules_read`
/ `patterns_read` stamp is earned. Affected API: none outside that module. Data schemas: it owns
one nested key in the evidence ledger, ``_spans`` -- repo-relative document path to the line
ranges read so far this session.

## Why this exists

`_hook_evidence.covers_whole_file` already answers this question for the **Read tool**, by
inspecting ``offset`` / ``limit``. It was added 2026-09-12 after the standards were "read" 120
lines deep, and its docstring states the lesson plainly: *a release condition that is a phrase is
satisfied by typing the phrase*, with a PATH in place of the phrase.

MEASURED 2026-09-14: that fix landed on the road nobody drives. A **Bash** payload carries no
``offset`` and no ``limit``, so `covers_whole_file` returns True on its first branch and any
shell command that merely NAMES a standard was credited as a complete read of it. Bash is not an
edge case here -- CLAUDE.md MANDATES it in auto mode: *"read files with cat, head, or sed -n ...
rather than using the dedicated Read tool"*. The guarded path was the one the agent is told not
to take.

The demonstration, from the session that produced this file: `wc -l` over all seven standards,
plus two `grep -n "^## "` heading listings, released `todo_rules_reread_guard` in full. `wc -l`
emits ONE INTEGER. 2,284 lines across eight documents were recorded as read, and the owner --
not the suite -- caught it: *"you only open the docs or open and read and DEEP understand them
to apply to your workin day by day?????"*

## What it judges, and what it refuses to judge

It judges the SHAPE OF THE COMMAND, never the reply. No sentence changes what `wc` prints --
the same reason `edge_hunt_endpoint_write_guard` reads an AST instead of a docstring. It does
NOT judge comprehension: no hook can, and every guard here that tried to detect reasoning
quality from prose was satisfied by rephrasing. The checkable claim is narrower: *these bytes
were emitted into the transcript.*

## Three decisions worth defending

1. **Coverage ACCUMULATES across calls.** Reading a 212-line document as `sed -n '1,60p'` then
   `sed -n '60,212p'` is correct practice, not evasion. A predicate judging each call alone
   would fail both halves and teach the agent to `cat` a 1,000-line file purely to satisfy a
   gate -- the guard degrading the work to satisfy itself.

2. **Unknown command words FAIL OPEN to the whole file.** Only commands positively known to emit
   no content (`wc`, `ls`, `stat`, `find`, `du`, `test`) or to emit matches rather than a span
   (`grep`, `awk`, `rg`) lose credit. A guard that punishes a read it failed to parse teaches
   people to route around the rule.

3. **`grep` is a LOOKUP, not a read.** It returns the lines matching a pattern -- by construction
   the ones you already knew to ask for. A heading-only grep returns the table of contents.

## The joint-satisfiability check, which is not optional

Memory `guards-can-be-jointly-unsatisfiable`: one guard forbids what another requires, and the
pair wedges the session. Demanding a WHOLE-FILE read must leave a route open. Since
GORTEX-ALLOWLIST (2026-10-20) `gortex_first_guard.printed_file` refuses every Bash print of a
file, `cat` of a standard included, and names the Read tool -- whose read with no offset / limit
`_hook_evidence.covers_whole_file` credits. `test_rules_read_evidence_matcher` pins that the Read
route stays open (the gortex guard listens on Bash only).
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _hook_command import command_word, split_segments, strip_heredoc_bodies

_REPO = Path(__file__).resolve().parents[2]

#: The standards the `rules_read` evidence kind is about, as CONCRETE FILES.
#:
#: `todo_rules_reread_guard.RULE_PATHS` names the same set, but two of its entries are
#: DIRECTORIES (`.claude/skills/tdd/`) -- fine for a substring match, useless for "how many
#: lines is it". These are the files those directories mean. Every path is verified to exist by
#: `test_rules_read_evidence_matcher`, because a guard keyed to a path that does not exist is a
#: dead guard and this repo has shipped two of those.
STANDARD_DOCS: Final[tuple[str, ...]] = (
    ".cursor/rules/coding-standards-mandatory.mdc",
    ".claude/skills/tdd/SKILL.md",
    ".claude/skills/improve-codebase-architecture/SKILL.md",
    ".claude/skills/architecture-hygiene-review/SKILL.md",
    "docs/04-structural/DDD_PATTERNS.md",
    "docs/02-technical/ARCHITECTURE.md",
    "docs/04-structural/ARCHITECTURE_PATTERNS.md",
)

#: The one document `patterns_read` is about. Split out of `rules_read` on 2026-09-08 because
#: the any-of let the file answering "which pattern, and why does its anti-fit not apply" be
#: skipped by opening a cheaper sibling.
PATTERNS_DOC: Final[str] = "docs/04-structural/ARCHITECTURE_PATTERNS.md"

#: Command words that NAME a file and emit none of its content. A closed, short list: each one
#: answers a question ABOUT the file (size, existence, mode, location), not what is in it.
METADATA_ONLY: Final[frozenset[str]] = frozenset(
    {
        "wc", "ls", "stat", "file", "du", "find", "test", "[", "realpath", "basename",
        "dirname", "touch", "mkdir", "rm", "cp", "mv", "chmod", "chown", "ln",
        "md5", "md5sum", "shasum", "sha256sum", "cksum", "readlink",
    }
)

#: Readers that emit the lines MATCHING a pattern rather than a contiguous span. Not a read of
#: the document -- a lookup of what you already knew to ask for.
SELECTIVE: Final[frozenset[str]] = frozenset({"grep", "rg", "egrep", "fgrep", "ag", "awk", "jq"})

#: Readers that emit the file end to end when given no range flags.
WHOLE_FILE: Final[frozenset[str]] = frozenset({"cat", "bat", "less", "more", "nl", "tac", "tee"})

#: POSIX defaults, so a bare `head` / `tail` is scored as the ten lines it actually prints.
DEFAULT_HEAD_TAIL_LINES: Final[int] = 10


def _tokens(segment: str) -> list[str]:
    """Shell tokens, quotes resolved. Falls back to whitespace on an unbalanced quote."""
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return segment.split()


def _names_path(tokens: list[str], path: str) -> bool:
    """Does any token in this segment refer to ``path``?

    Matched on the full relative path, on either being a suffix of the other (absolute paths and
    `apps/api`-relative invocations both occur), and finally on the basename. Basename matching
    is deliberately loose: it can only ever CREDIT a read, never withhold one, and the regex it
    sits behind in `_hook_evidence` is looser still.
    """
    wanted = path.replace("\\", "/")
    base = wanted.rsplit("/", 1)[-1]
    for raw in tokens:
        token = raw.replace("\\", "/")
        if token == wanted or token.endswith("/" + wanted) or wanted.endswith("/" + token):
            return True
        if token.rsplit("/", 1)[-1] == base:
            return True
    return False


def _numeric_flag(tokens: list[str]) -> int | None:
    """The line count from `-n N` or the bare `-N` form, or None when neither is present."""
    for index, token in enumerate(tokens):
        if token == "-n" and index + 1 < len(tokens):
            candidate = tokens[index + 1].lstrip("+")
            if candidate.isdigit():
                return int(candidate)
            return None
        if len(token) > 1 and token[0] == "-" and token[1:].isdigit():
            return int(token[1:])
    return None


def _sed_span(tokens: list[str], total: int) -> tuple[int, int] | None:
    """The range a `sed -n 'A,Bp'` prints. `$` means the last line; a bare `Ap` is one line."""
    for token in tokens:
        if not token.endswith("p") or token.startswith("-"):
            continue
        body = token[:-1]
        if "," in body:
            start_text, _, end_text = body.partition(",")
            if not start_text.isdigit():
                continue
            start = int(start_text)
            if end_text == "$":
                return start, total
            if end_text.isdigit():
                return start, int(end_text)
            continue
        if body.isdigit():
            return int(body), int(body)
    return None


def _segment_span(segment: str, path: str, total: int) -> tuple[int, int] | None:
    """The span one shell segment emits of ``path``, or None when it emits nothing of it."""
    tokens = _tokens(segment)
    if not tokens or not _names_path(tokens, path):
        return None

    word = (command_word(segment) or tokens[0]).rsplit("/", 1)[-1]

    if word in METADATA_ONLY or word in SELECTIVE:
        return None
    if word == "head":
        count = _numeric_flag(tokens)
        if count is None:
            return 1, DEFAULT_HEAD_TAIL_LINES
        return 1, count
    if word == "tail":
        count = _numeric_flag(tokens)
        lines = DEFAULT_HEAD_TAIL_LINES if count is None else count
        return max(1, total - lines + 1), total
    if word == "sed":
        span = _sed_span(tokens, total)
        if span is not None:
            return span
        # `-n` with no printable range prints NOTHING at all, and scoring that as a full read is
        # the hole this module exists to close. Without `-n`, sed streams the whole file.
        if "-n" in tokens:
            return None
        return 1, total
    if word in WHOLE_FILE:
        return 1, total
    # FAIL OPEN. An unrecognised reader is credited in full -- decision 2 in the module
    # docstring. The two blocklists above are closed sets; this branch is the open world.
    return 1, total


def spans_for(command: str, path: str, *, total: int) -> list[tuple[int, int]]:
    """Every span of ``path`` that ``command`` emits, one entry per shell segment.

    Segments are judged INDIVIDUALLY, so `wc -l X && cat X` credits the `cat` and is not
    poisoned by the `wc` beside it.
    """
    out: list[tuple[int, int]] = []
    for segment in split_segments(strip_heredoc_bodies(command)):
        span = _segment_span(segment, path, total)
        if span is None:
            continue
        out.append((max(1, span[0]), min(total, span[1])))
    return out


def span_for(command: str, path: str, *, total: int) -> tuple[int, int] | None:
    """The WIDEST single span ``command`` emits of ``path``, or None.

    Reporting the widest rather than the union keeps this honest for callers that want one
    answer: two disjoint peeks stay two peeks. `spans_for` is what the ledger accumulates.
    """
    spans = spans_for(command, path, total=total)
    if not spans:
        return None
    return max(spans, key=lambda span: span[1] - span[0])


def merge(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Sorted, non-overlapping ranges. Adjacent ranges join: 1-60 then 61-400 has no gap."""
    ordered = sorted((start, end) for start, end in ranges if end >= start)
    merged: list[tuple[int, int]] = []
    for start, end in ordered:
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            continue
        merged.append((start, end))
    return merged


def covers_all(ranges: list[tuple[int, int]], total: int) -> bool:
    """True when the union of ``ranges`` spans line 1 through ``total`` with no gap."""
    if total <= 0:
        return True
    merged = merge(ranges)
    if not merged:
        return False
    return merged[0][0] <= 1 and merged[0][1] >= total


def _line_count(path: str) -> int | None:
    try:
        return len((_REPO / path).read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return None


def bash_whole_file_kinds(
    command: str, prior: dict[str, list[list[int]]]
) -> tuple[set[str], dict[str, list[list[int]]]]:
    """Which document kinds this command has now FULLY covered, and the updated span ledger.

    ``prior`` maps a repo-relative standard path to the ranges already read this session. The
    returned mapping is the merged successor and is what the caller persists.
    """
    spans: dict[str, list[list[int]]] = {
        key: [list(pair) for pair in value]
        for key, value in prior.items()
        if isinstance(value, list)
    }
    satisfied: set[str] = set()
    command_tokens = _tokens(strip_heredoc_bodies(command))

    for doc in STANDARD_DOCS:
        total = _line_count(doc)
        if total is None:
            # FAIL OPEN on a document this module cannot measure, exactly as `covers_whole_file`
            # does: never punish a read whose target could not be inspected.
            if _names_path(command_tokens, doc):
                satisfied.add("rules_read")
                if doc == PATTERNS_DOC:
                    satisfied.add("patterns_read")
            continue

        fresh = spans_for(command, doc, total=total)
        if not fresh:
            continue
        existing = [(int(pair[0]), int(pair[1])) for pair in spans.get(doc, []) if len(pair) == 2]
        combined = merge(existing + fresh)
        spans[doc] = [list(pair) for pair in combined]
        if covers_all(combined, total):
            satisfied.add("rules_read")
            if doc == PATTERNS_DOC:
                satisfied.add("patterns_read")

    return satisfied, spans
