"""Repo code runs from tracked files or not at all (OUTSIDE-REPO-PY, owner 2026-10-20; the whole class 2026-10-30). PreToolUse.

IMPORTERS/CALLERS: registered in .claude/settings.json (PreToolUse) through _hook_mode_gate.py; its test.
AFFECTED API: none. DATA SCHEMAS: the PreToolUse payload (tool_name, tool_input, cwd).

REUSE-AUDIT: considered gortex_first_guard (refuses Bash writes INTO tracked source, so /tmp and the scratchpad are
outside its question), reinvent_wheel_guard / one_definition_guard / clone_body_guard (judge new code in the repo --
they never see a file written elsewhere, which is the gap) and single_venv_guard (whose command parsing this reuses
through _hook_command). None asks WHERE code that reaches the repo lives.

THE CASE: this session wrote parity-check scripts into /tmp and the session scratchpad. Not one of them met a test
run, a linter, a type check, a reuse guard or a review; the owner caught it -- "now your making script inside tmp
folder?? and previous sessions on .scratchpad???? ... to bypass hooks?". A tracked-in-git rule cannot see them (they
are written, not committed), and a list of forbidden directories is walked around by picking a new one, so the rule
is the inverse: a .py / .pyi is written under the repo root, wherever else it might go.

AND NOT IN A GIT-IGNORED PATH INSIDE IT (2026-10-21, owner: "im seeing ... .scratch scripts ... arent those scripts
needed for future use case? if so, why not adding them into the repo"). The first version judged only "under the repo
root", so `.scratch/agent/` -- git-ignored, inside the root -- stayed open: measured that day, 243 .py and 151 .sh
there, 7 .py written the day before by the session that wrote this guard, and 15 tracked files citing a script there
as the source of a measurement (money_tier.py among them) that no clone of the repo can re-run. An ignored path is
outside every gate exactly like /tmp, so `git check-ignore` decides; a data file (.json / .parquet / .log) there is fine.

AND NOT INLINE, AND NOT BY ANY OTHER SPELLING (2026-10-30). A .py FILE was the only shape judged, so `python - <<EOF` walked
past it: the 'every script' money tables of 13.31 and 13.41 were an inline heredoc importing live_dollars with a
hand-written % formula, shown beside the wallet grade as if one measure -- numbers the owner could not reconcile with his
wallet ("what are you using to measure? different code?"), against a rule the memory already held ("even a
`python -c`"). "HOOK and BLOCK and ENFORCE", then, on a first fix that named that one command: "only for your use case, not
for future cases, other cases, similar cases, robust, bullet proof". A list of spellings is what the 2026-10-20 paragraph
above rejects for directories, so the question is the CLASS -- does code that reaches the repo run from somewhere no gate
sees -- asked of every door:
  inline   any interpreter (found by token, so `nice`, `timeout`, `uv run`, `$( )` hide nothing) on text it was handed:
           `-c`, `-`, a heredoc, stdin
  shells   `bash -c`, `sh -c`, `zsh -c`, `eval`, a shell heredoc: their text is judged the same way, recursively
  files    an interpreter on a file outside the gates, WHATEVER its suffix; a shell script there, if it reaches the repo
  writes   any file outside the gates whose content reaches the repo, whatever its suffix; a notebook at all
"Reaches the repo" is read off the tree (_repo_reach: the packages under apps/api/src, never a typed list) plus the dynamic
doors -- importlib, runpy, __import__, sys.path, PYTHONPATH -- because a dynamic import can reach anything. Inline Python
over data alone (json, a log) reaches nothing and stays free, as does every `python -m`, test and tracked script.

Judged: Write / Edit / MultiEdit (file_path), gortex write_file / edit_file / batch_edit and the edit facade (an ABSOLUTE
path; gortex resolves a relative one inside an indexed repo), and Bash. A `git ...` segment is never judged: `git show
<ref>:<path> > x.py` copies tracked code for a checker, and a commit message is data. A path built from a shell variable
cannot be resolved here and is left alone. Fails OPEN on unreadable input. No release marker: the right place always exists.
"""

from __future__ import annotations

HOOK_EVENT = "PreToolUse"
HOOK_MATCHER = "Write|Edit|MultiEdit|mcp__gortex__write_file|mcp__gortex__edit_file|mcp__gortex__batch_edit|mcp__gortex__edit|Bash"

import functools
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _hook_command import quoted_tokens, resolve_invocation, split_segments, strip_heredoc_bodies  # noqa: E402

PYTHON_SUFFIXES: Final = (".py", ".pyi", ".ipynb")
_FILE_TOOLS: Final = frozenset({"Write", "Edit", "MultiEdit"})
_GORTEX_TOOLS: Final = frozenset({"mcp__gortex__write_file", "mcp__gortex__edit_file"})
_BATCH_PATH_KEYS: Final = ("path", "destination")
_GIT_TIMEOUT_S: Final = 5  # one `git check-ignore`, ~10 ms measured; a hung git must not hold the tool call
#: `> x`, `>> x`, `2> x`, `&> x` -- the redirect operator and its target; `2>&1` has no file target and never matches.
_REDIRECT: Final = re.compile(r"(?:^|[^<>&\d])(?:\d|&)?>>?\|?\s*(\"[^\"]*\"|'[^']*'|[^\s;&|<>\"']+)")
#: a command word that is a Python interpreter: found anywhere in a segment, after a path, `$(`, a backtick or the quote of
#: a `bash -c "..."` whose heredoc left the closing quote behind
_INTERPRETER: Final = re.compile(r"(?:^|[/(`=\"'])(?:i?python[\d.]*|pypy[\d.]*)$")
_SHELLS: Final = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
_SOURCES: Final = frozenset({"source", "."})
_HEREDOC: Final = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)\n\s*\2\b", re.DOTALL)
_INLINE_C: Final = re.compile(r"-[A-Za-z]*c")
_VALUE_FLAGS: Final = frozenset({"-W", "-X"})  # interpreter flags that take the next token
_DEPTH: Final = 4  # shells inside shells: deeper than anyone writes by accident
_SRC: Final = "apps/api/src"

_REASON: Final = (
    "BLOCKED -- a Python file is being written OUTSIDE the repo, or where git ignores it (.scratch/ ...): {path}\n\n"
    "Code there meets no test run, no linter, no type check, no reuse / one-definition / clone guard and no review: it\n"
    "escapes every gate this repo has. Owner, 2026-10-20: 'now your making script inside tmp folder?? and previous\n"
    "sessions on .scratchpad???? ... to bypass hooks?'\n\n"
    "Write it where it belongs and let the gates judge it:\n"
    "  a check, parity probe or regression -> apps/api/tests/...\n"
    "  a lab study or measurement          -> apps/api/src/research/... (run it as a module)\n"
    "  an operator tool or gate            -> apps/api/scripts/...\n"
    "  a hook                              -> .claude/hooks/ beside its test_*.py\n"
    "Prose and data (.txt / .md / .json / .log) may live anywhere, and a `git show <ref>:<path> > x.py` copy of\n"
    "tracked code is allowed."
)
_UNGATED_REASON: Final = (
    "BLOCKED -- code that reaches this repo would run from somewhere no gate sees: {what}\n\n"
    "Inline text (a heredoc, `-`, stdin, `-c`, `bash -c`, `eval`), or a file outside the repo in any suffix, meets no test, no\n"
    "linter, no reuse guard, and leaves no measure anyone can re-run. Owner, 2026-10-30, on money tables built this way:\n"
    "'what are you using to measure? different code?' and 'HOOK and BLOCK and ENFORCE'.\n\n"
    "Repo code runs through a door:\n"
    "  a money number          -> the wallet grade, run as a module: python -m src.research.pine.article_ml_5m.<module>\n"
    "  a new measurement       -> a function in apps/api/src/research/... with a test, then python -m\n"
    "  a check or parity probe -> a test under apps/api/tests/...\n"
    "Inline Python over data alone (json, a log) is free. There is no release marker: the right place always exists."
)


def _repo_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])


@functools.cache
def _repo_import(repo: Path) -> str:
    """An import of a package under apps/api/src, read off the tree so a new package needs no edit here."""
    root = repo / _SRC
    packages = sorted(p.name for p in root.iterdir() if p.is_dir() and p.name.isidentifier() and not p.name.startswith("_")) if root.is_dir() else []
    return rf"(?:from|import)\s+(?:apps\.api\.)?(?:{'|'.join(['src', *packages])})(?:\.|\s|$)"


def _repo_reach(repo: Path) -> re.Pattern[str]:
    """Reaching the repo in text handed to an interpreter, which is code by definition: an import, or a dynamic door --
    those can reach anything. A path alone is no reach: inline Python may read a data file that sits under src."""
    return re.compile(rf"\b{_repo_import(repo)}|\bimportlib\b|\brunpy\b|\b__import__\b|\bsys\.path\b|\bPYTHONPATH\b|\bexec\s*\(", re.MULTILINE)


def _written_reach(repo: Path) -> re.Pattern[str]:
    """Reaching the repo in a written file, which may be prose: an import that starts a line, a dynamic door that is called
    -- notes and commit messages name these words all day and must stay free."""
    return re.compile(rf"^\s*{_repo_import(repo)}|\b(?:importlib\.import_module|__import__|runpy\.run_\w+|sys\.path\.(?:insert|append))\s*\(", re.MULTILINE)


def _ignored_by_git(path: Path) -> bool:
    """True when git ignores ``path`` in the checkout that holds it (asked from its nearest existing directory, so a
    linked worktree answers for itself); False on any doubt -- the guard fails open."""
    folder = path.parent
    while not folder.is_dir() and folder != folder.parent:
        folder = folder.parent
    try:
        result = subprocess.run(["git", "-C", str(folder), "check-ignore", "-q", "--", str(path)],
                                capture_output=True, timeout=_GIT_TIMEOUT_S, check=False)  # fmt: skip
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _ungated(path_text: str, *, base: Path, repo: Path) -> bool:
    """A path outside ``repo`` (a relative one against ``base``), or inside it where git ignores it -- no gate sees either."""
    if not path_text or "$" in path_text:
        return False
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = base / path
    try:
        resolved = path.resolve()
        return not resolved.is_relative_to(repo.resolve()) or _ignored_by_git(resolved)
    except OSError:
        return False


def _bash_targets(command: str) -> list[str]:
    """The files a Bash command writes through a redirect or `tee`, `git` segments excepted."""
    targets: list[str] = []
    for segment in split_segments(strip_heredoc_bodies(command)):
        word, args = resolve_invocation(segment)
        if word == "git":
            continue
        if word == "tee":
            targets.extend(arg for arg in args if not arg.startswith("-"))
        targets.extend(match.group(1).strip("'\"") for match in _REDIRECT.finditer(segment))
    return targets


def _interpreter_run(args: list[str]) -> tuple[str, str]:
    """How an interpreter's arguments run code: ("module", ""), ("inline", the -c text), ("stdin", "") or ("file", path)."""
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "-m":
            return "module", ""
        if _INLINE_C.fullmatch(arg):
            return "inline", args[index + 1] if index + 1 < len(args) else ""
        if arg == "<":
            return "file", args[index + 1] if index + 1 < len(args) else ""
        if arg == "-" or arg.startswith(("<", ">", "2>", "&>", ")")):
            return "stdin", ""
        if arg.startswith("-"):
            index += 2 if arg in _VALUE_FLAGS else 1
            continue
        return "file", arg
    return "stdin", ""


def _read(path_text: str, base: Path) -> str:
    """A file's text, "" when it cannot be read: the guard fails open."""
    path = Path(path_text).expanduser()
    try:
        return (path if path.is_absolute() else base / path).read_text(errors="replace")
    except OSError:
        return ""


def _shell_reaches(tokens: list[str], at: int, bodies: str, *, base: Path, repo: Path, depth: int) -> bool:
    """A shell's own text: its `-c` string or heredoc judged as a command, or, outside the gates, the script it runs.
    ``bodies`` travel with a `-c` string: a heredoc inside the quotes was lifted out before the string was tokenised."""
    args = tokens[at + 1 :]
    if tokens[at] == "eval":
        return _ungated_code(" ".join(args), base=base, repo=repo, depth=depth + 1, outer=bodies)
    for index, arg in enumerate(args):
        if _INLINE_C.fullmatch(arg):
            text = args[index + 1] if index + 1 < len(args) else ""
            return _ungated_code(text, base=base, repo=repo, depth=depth + 1, outer=bodies)
    script = next((arg for arg in args if not arg.startswith(("-", "<", ">"))), "")
    if script and _ungated(script, base=base, repo=repo):
        return _ungated_code(_read(script, base), base=base, repo=repo, depth=depth + 1)
    return not script and bool(bodies) and _ungated_code(bodies, base=base, repo=repo, depth=depth + 1)


def _ungated_code(command: str, *, base: Path, repo: Path, depth: int = 0, outer: str = "") -> bool:
    """Whether ``command`` runs code that reaches the repo from anywhere no gate sees (the module docstring's doors)."""
    if depth > _DEPTH:
        return False
    reach = _repo_reach(repo)
    bodies = "\n".join([outer, *(match.group(3) for match in _HEREDOC.finditer(command))]).strip()
    for segment in split_segments(strip_heredoc_bodies(command)):
        if resolve_invocation(segment)[0] == "git":
            continue
        tokens = quoted_tokens(segment)
        at = next((i for i, token in enumerate(tokens) if _INTERPRETER.search(token)), None)
        if at is not None:
            kind, text = _interpreter_run(tokens[at + 1 :])
            if kind == "file" and _ungated(text, base=base, repo=repo):
                return True
            handed = {"inline": text, "stdin": f"{bodies}\n{command}"}.get(kind)
            if handed is not None and reach.search(f"{segment}\n{handed}"):
                return True
            continue
        shell = next((i for i, token in enumerate(tokens) if token.rsplit("/", 1)[-1] in _SHELLS or token == "eval"), None)
        if shell is not None and _shell_reaches(tokens[shell:], 0, bodies, base=base, repo=repo, depth=depth):
            return True
        if tokens and tokens[0] in _SOURCES and len(tokens) > 1 and _ungated(tokens[1], base=base, repo=repo):
            if _ungated_code(_read(tokens[1], base), base=base, repo=repo, depth=depth + 1):
                return True
    return False


def _edit_facade(tool_input: dict[str, object]) -> list[tuple[str, str]]:
    """(path, new text) of each file an mcp__gortex__edit call writes: its target and its batch changes."""
    target = tool_input.get("target")
    written = [(str(target.get("file") or ""), str(tool_input.get("content") or ""))] if isinstance(target, dict) else []
    changes = tool_input.get("changes")
    for change in changes if isinstance(changes, list) else []:
        if isinstance(change, dict):
            written.append((str(change.get("path") or change.get("destination") or ""), str(change.get("new_string") or "")))
    return written


def _writes(tool: str, tool_input: dict[str, object]) -> tuple[list[tuple[str, str]], bool]:
    """(path, new text) of what this tool call writes, and whether a relative path is gortex's (inside its repo)."""
    if tool in _FILE_TOOLS:
        text = tool_input.get("content") or tool_input.get("new_string") or ""
        return [(str(tool_input.get("file_path") or ""), str(text))], False
    if tool in _GORTEX_TOOLS:
        return [(str(tool_input.get("path") or ""), str(tool_input.get("content") or tool_input.get("new_string") or ""))], True
    if tool == "mcp__gortex__edit":
        return _edit_facade(tool_input), True
    if tool == "mcp__gortex__batch_edit":
        edits = tool_input.get("edits")
        items = edits if isinstance(edits, list) else []
        return [(str(item.get(key) or ""), str(item.get("new_string") or "")) for item in items if isinstance(item, dict) for key in _BATCH_PATH_KEYS], True
    if tool == "Bash":
        command = str(tool_input.get("command") or "")
        bodies = "\n".join(match.group(3) for match in _HEREDOC.finditer(command))
        return [(target, bodies) for target in _bash_targets(command)], False
    return [], False


def violation(payload: dict[str, object], *, repo: Path) -> str | None:
    """The deny reason naming the first thing that puts repo-reaching code outside the gates, or None."""
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    base = Path(str(payload.get("cwd") or repo))
    if tool == "Bash" and _ungated_code(str(tool_input.get("command") or ""), base=base, repo=repo):
        return _UNGATED_REASON.format(what=str(tool_input.get("command") or "").split("\n", 1)[0][:160])
    writes, gortex_resolves_relative = _writes(tool, tool_input)
    reach = _written_reach(repo)
    for path, text in writes:
        if (gortex_resolves_relative and not Path(path).is_absolute()) or not _ungated(path, base=base, repo=repo):
            continue
        if path.endswith(PYTHON_SUFFIXES):
            return _REASON.format(path=path)
        if reach.search(text):
            return _UNGATED_REASON.format(what=f"a write to {path}")
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:  # noqa: BLE001  # justified: fail OPEN -- a hook that dies on input must not block work
        return 0
    if not isinstance(payload, dict):
        return 0
    reason = violation(payload, repo=_repo_root())
    if reason is None:
        return 0
    print(reason, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
