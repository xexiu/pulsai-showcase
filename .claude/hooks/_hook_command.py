"""Shared Bash-command classification for PreToolUse hooks: does this command RUN a thing?

THE DEFECT THIS CENTRALISES AWAY. Every hook that scans `tool_input.command` for a program name
will read a MENTION as an INVOCATION unless it is built not to. Four instances in one day,
2026-08-27, in two different guards:

  1. `grep -nE "def" apps/api/scripts/probe_stack_health.py` blocked as "running the probe sweep";
  2. a `git commit -F - <<'MSG'` heredoc whose message DESCRIBED a bug blocked its own commit,
     because splitting on newlines turns each prose line into a pseudo-command;
  3. `localhost_stack_alive_guard` blocked on a launcher string quoted in a test fixture;
  4. the same guard blocked `grep -nE "preflight" scripts/run.sh` — a READ of the launcher.

Two of those were in a guard written that morning and two in one written the day before, which is
the argument for a shared module rather than a third private copy: the next hook to scan a command
line inherits the fix instead of re-discovering the bug.

REUSE-AUDIT: considered `_hook_evidence.classify` (it buckets a command into evidence KINDS for
Stop hooks — "was a search done", "was an edit made") and `_hook_exclusions`. Neither answers
"is this segment an invocation or a reading of a file", which is the question here.
"""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import Final

#: Command words that only READ. A segment led by one of these NAMES files; it does not run them.
READER_COMMANDS: Final[frozenset[str]] = frozenset(
    {
        "grep", "egrep", "fgrep", "rg", "ag",
        "cat", "head", "tail", "less", "more", "bat",
        "sed", "awk", "cut", "sort", "uniq", "wc", "tr",
        "ls", "find", "fd", "stat", "file", "du", "tree",
        "echo", "printf", "which", "type",
        "git", "jq", "diff", "test", "true", "false",
    }
)

#: Prefixes that wrap another command without being one; skip to find the real executable.
_PREFIXES: Final[frozenset[str]] = frozenset(
    {"sudo", "time", "nohup", "command", "exec", "env", "xargs"}
)

#: Splits a command line into pipeline / list segments so each is classified on its own.
#: Kept exported for callers that already import it; `split_segments` is what this module
#: uses, because a regex cannot tell a separator from the same character inside a quote.
SEGMENT_SPLIT: Final = re.compile(r"\|\||&&|\||;|\n")

#: Unquoted separators, longest first so `||` and `&&` win over `|`.
_SEPARATORS: Final[tuple[str, ...]] = ("||", "&&", "|", ";", "\n")


def split_segments(command: str) -> list[str]:
    """Split on separators that are OUTSIDE quotes.

    THE DEFECT THIS FIXES. `SEGMENT_SPLIT` splits on a bare newline, so every line of a
    multi-line ``git commit -m "..."`` message became its own candidate command. ``git``
    is a reader, so the FIRST line was correctly dropped -- and the prose lines after it
    were not, because their first word ("I", "over", "./scripts/run.sh") is not a reader.

    MEASURED 2026-09-01: a commit whose message read "I wrote a confident message over
    run.sh and run_dev_apps.sh without reading either" was denied as a stack restart.
    This module's docstring already described that failure for HEREDOCS (case 2) and the
    fix stopped there; a quoted ``-m`` argument is the commoner shape by far.

    Quoting is deliberately shell-shaped and simple: a backslash escapes the next
    character, and a quote character inside the OTHER quote style is literal.
    """
    segments: list[str] = []
    current: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(command):
        char = command[index]
        if char == "\\" and index + 1 < len(command):
            current.append(char)
            current.append(command[index + 1])
            index += 2
            continue
        if quote is not None:
            current.append(char)
            if char == quote:
                quote = None
            index += 1
            continue
        if char in "'\"":
            quote = char
            current.append(char)
            index += 1
            continue
        matched = next((sep for sep in _SEPARATORS if command.startswith(sep, index)), None)
        if matched is not None:
            segments.append("".join(current))
            current = []
            index += len(matched)
            continue
        current.append(char)
        index += 1
    segments.append("".join(current))
    return segments

#: Matches a heredoc opener and captures its terminator: <<EOF, <<'EOF', <<-"EOF".
_HEREDOC_OPEN: Final = re.compile(r"<<-?\s*[\'\"]?([A-Za-z_][A-Za-z0-9_]*)[\'\"]?")


def strip_heredoc_bodies(command: str) -> str:
    """Drop heredoc BODIES, keeping the command lines that open them.

    Text piped into a program's stdin is DATA: it cannot invoke anything. Keeping it makes every
    commit message, docstring and JSON payload that merely names a command read as running one.
    """
    kept: list[str] = []
    terminator: str | None = None
    for line in command.splitlines():
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            continue
        kept.append(line)
        match = _HEREDOC_OPEN.search(line)
        if match:
            terminator = match.group(1)
    return "\n".join(kept)


def heredoc_bodies(command: str) -> list[str]:
    """The heredoc BODIES themselves -- what `strip_heredoc_bodies` drops -- in order.

    A body handed to an interpreter (`python3 - <<'EOF'`) is the PROGRAM that runs, so a guard judging what that
    program does needs the text the stripping removes. An unterminated body runs to EOF, as bash reads it.
    """
    bodies: list[str] = []
    current: list[str] = []
    terminator: str | None = None
    for line in command.splitlines():
        if terminator is not None:
            if line.strip() == terminator:
                bodies.append("\n".join(current))
                current, terminator = [], None
            else:
                current.append(line)
            continue
        match = _HEREDOC_OPEN.search(line)
        if match:
            terminator = match.group(1)
    if terminator is not None:
        bodies.append("\n".join(current))
    return bodies


def is_tracked_in_git(path: str, *, repo: Path | None = None) -> bool:
    """Is this file in git -- has a human reviewed it? A relative path resolves against ``repo`` when one is given.

    Moved here from edge_hunt_endpoint_write_guard (2026-10-20, GORTEX-ALLOWLIST) so gortex_first_guard judges
    "a throwaway script" the same way. It replaced a directory denylist there, and the reason is the point. Owner,
    2026-09-20: *"now you use /scratchpad to evadate hooks... tomorrow you will use /scratchpad_ to evadate thrm
    agsin and so on. the problem are not thr hooks!!!! THE PROBLEM IS YOU!!!"* A list of PLACES is walked around by
    choosing a new place; tracked-in-git is path-independent, and the only way into the exemption is to COMMIT the
    file, which is the review being asked for.

    FAILS CLOSED -- a missing git, a path outside any repo or a timeout all read as untracked -- because "git is
    unavailable" must not become the next exemption.
    """
    target = Path(path)
    if not target.is_absolute() and repo is not None:
        target = repo / target
    try:
        proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "-C", str(target.parent), "ls-files", "--error-unmatch", "--", target.name],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return False
    return proc.returncode == 0


#: `name=(` opens a bash ARRAY assignment, which spans tokens until the closing paren.
_ARRAY_ASSIGNMENT: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\+?=\(")

#: The opener of a command substitution. What runs INSIDE it is not this segment's command.
_SUBSTITUTION_OPENER: Final = re.compile(r"\$\(|`")


def command_word(segment: str) -> str:
    """The executable a segment invokes, skipping env assignments and wrapper prefixes.

    An ARRAY assignment spans several tokens, and skipping only the first hands the array's
    CONTENTS to the caller as if they were the command. MEASURED 2026-09-13:

        cases=('./scripts/verify.sh' 'pnpm verify'); printf '%s\\n' "${cases[@]}"

    was denied as a run of the verify gate. `cases=('./scripts/verify.sh'` is skipped as an
    assignment and the NEXT token -- `'pnpm` -- becomes the command word. Nothing here runs
    but `printf`. A list of command STRINGS is data, exactly like the equivalent
    `for c in …` list that was already handled, and exactly like a heredoc body.

    A `$(...)` or backtick opener is stripped for the same reason: the command word of
    `RULES=$(grep … verify.sh)` is whatever runs OUTSIDE the substitution.
    """
    tokens = _SUBSTITUTION_OPENER.sub(" ", segment).strip().split()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if _ARRAY_ASSIGNMENT.match(token):
            # Consume through the closing paren; bash allows it on a later token.
            while index < len(tokens) and not tokens[index].endswith(")"):
                index += 1
            index += 1
            continue
        if "=" in token and not token.startswith(("-", "/", ".")):
            index += 1
            continue  # FOO=bar prefix
        if token in _PREFIXES:
            index += 1
            continue
        return token.rsplit("/", 1)[-1]
    return ""


def is_reader_segment(segment: str) -> bool:
    """True when this segment only reads — whatever filenames it happens to name."""
    return command_word(segment) in READER_COMMANDS


def executable_segments(command: str) -> list[str]:
    """The segments of ``command`` that could actually RUN something.

    Heredoc bodies are removed and reader segments are dropped, so a caller can match its patterns
    against the result without re-implementing either rule.
    """
    return [
        segment
        for segment in split_segments(strip_heredoc_bodies(command))
        if segment.strip() and not is_reader_segment(segment)
    ]


def invokes(command: str, pattern: re.Pattern[str]) -> bool:
    """True when ``pattern`` matches a segment that actually runs something."""
    return any(pattern.search(segment) for segment in executable_segments(command))


#: Global `git` flags that take a following value, so the real subcommand sits one token later.
#: `git -C /repo push` names its subcommand at index 2, not 0.
_GIT_GLOBAL_FLAGS_WITH_VALUE: Final[frozenset[str]] = frozenset({"-C", "-c", "--git-dir", "--work-tree"})


def quoted_tokens(segment: str) -> list[str]:
    """Shell-quote-aware tokens of one segment.

    `command_word` above tokenizes with a bare ``.split()``, so a quoted argument containing
    spaces -- ``grep -rn "git push --no-verify" docs/`` -- is torn into several tokens and a
    caller matching PATTERNS against those tokens reads the quoted TEXT as separate words instead
    of the one argument a shell would hand the program. ``shlex.split`` keeps it as one token.

    Falls back to the naive whitespace split on unbalanced quotes -- a real shell would reject the
    line anyway, and staying conservative (still tokenizing something) beats silently producing
    nothing for a caller that must still classify the segment.
    """
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return segment.split()


def resolve_invocation(segment: str) -> tuple[str, list[str]]:
    """The real command word of one segment (quote-aware) and its remaining arguments.

    Skips ``FOO=bar`` env-assignment prefixes and the same wrapper prefixes `command_word` skips
    (`sudo`, `time`, `nohup`, `command`, `exec`, `env`, `xargs`), so ``FOO=1 git push …`` and
    ``env git push …`` both resolve to ``("git", ["push", …])``. Unlike `command_word`, quoting is
    respected throughout -- see `quoted_tokens`.
    """
    tokens = quoted_tokens(segment)
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if "=" in token and not token.startswith(("-", "/", ".")) and token.split("=", 1)[0].isidentifier():
            index += 1
            continue  # FOO=bar prefix
        base = token.rsplit("/", 1)[-1]
        if base in _PREFIXES:
            index += 1
            continue
        return base, tokens[index + 1 :]
    return "", []


def git_subcommand(args: list[str]) -> str:
    """The git SUBCOMMAND named in ``args`` (a git invocation's own argv), global flags skipped.

    ``git -C /repo push --no-verify`` names its subcommand at index 2, not 0 -- ``-C`` takes a
    following value. Returns ``""`` when ``args`` names no subcommand (a bare ``git``).
    """
    skip_next = False
    for token in args:
        if skip_next:
            skip_next = False
            continue
        if token in _GIT_GLOBAL_FLAGS_WITH_VALUE:
            skip_next = True
            continue
        if token.startswith("-"):
            continue
        return token
    return ""
