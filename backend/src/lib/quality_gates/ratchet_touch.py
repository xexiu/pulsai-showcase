"""The touch-to-lower rule every per-file ratchet enforces at commit, and the git readers it needs.

IMPORTERS/CALLERS: src/lib/quality_gates/concept_definitions.py, scripts/check_duplicate_lines.py (duplicated
lines), scripts/check_file_size_baseline.py (effective lines over the cap), scripts/check_touched_debt.py (every single-file ratchet: noqa, blind
except, silent returns, anti-fits, tier decisions, standalone edge_hunt modules),
tests/scripts/test_ratchet_touch.py. AFFECTED API: none (library for gate
scripts; CLI: ``python -m src.lib.quality_gates.ratchet_touch``). DATA SCHEMAS: none.

THE RULE (owner, 2026-09-24): "everytime someone touches a file, its his resp to fix/refactor and lower the
ratchet until we reach 0 -- same for OTHERS ratchets". For any per-file debt metric:

* new file            -> 0
* existing, was 0     -> stays 0
* existing, was N > 0 -> strictly below N

It lives here ONCE so each ratchet contributes only its METRIC (how to count a file's debt), never its own
copy of the rule -- two gates re-implementing it slightly differently is the duplication this rule exists to
remove.

GIT, NOT THE WORKING TREE. Every reader goes through git: the index (``git show :path`` /
``checkout-index``, both honour ``GIT_INDEX_FILE``, so ``git commit -- paths`` is judged on the commit-to-be)
and refs (``git show REF:path``). Another session's dirty file can never decide someone's commit.

REUSE-AUDIT: considered scripts/check_duplicate_lines.py, where the rule was first written -- extracted from
it rather than copied, and it now imports this module. Stdlib-only like its callers.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path, PurePosixPath

_KEY_BYTES = 16

#: Archived KILL evidence (``src/research/_archive/``, ``results/_archive/``): never touched again and never imported, so
#: its debt can never be paid down and charging it would only make archiving cost what adopting the code costs.
#: ARCHIVE-EXEMPT (owner, 2026-10-19: "exempt _archive"): every debt gate leaves it -- the commit doors through
#: ``_split_mechanical``, the tree ratchets through ``concept_definitions.in_scope`` and the scanners that list files
#: themselves through ``is_archived``. Measured that day: 4 archived .py files (2,099 lines) carried 229 findings
#: over 15 touched-debt rows. ``tests/unit/architecture/test_archive_scope.py`` holds the other half of the bargain
#: (nothing outside it imports from it) and keeps the tools' own exclude lists in step with this predicate.
ARCHIVE_SEGMENT = "/_archive/"


def is_archived(path: str) -> bool:
    """Whether a repo-relative (or absolute) path lies under an ``_archive`` directory."""
    return ARCHIVE_SEGMENT in f"/{PurePosixPath(path).as_posix()}"


def touch_violations(
    touched: Iterable[str],
    *,
    now: Mapping[str, int],
    before: Mapping[str, int],
    new_files: set[str],
    unit: str,
    clear_on_touch: bool = False,
) -> list[str]:
    """One message per touched path that did not pay its debt down; ``unit`` names the metric.

    ``clear_on_touch`` is the stricter row of the same rule: a touched file must leave with ZERO,
    not merely less. It exists for `noqa` (owner, 2026-09-17: "if someone touches a file, he MUST
    fix noqa if detected"), which carried that policy before this module existed -- moving it here
    must not weaken it.
    """
    found: list[str] = []
    for path in touched:
        current = now.get(path, 0)
        if path in new_files:
            if current:
                found.append(f"{path}: NEW file carries {current} {unit} (a new file must carry 0)")
            continue
        if clear_on_touch and current:
            found.append(f"{path}: {current} {unit} -- a touched file must leave with 0")
            continue
        previous = before.get(path, 0)
        if previous == 0 and current == 0:
            continue
        if previous == 0:
            found.append(f"{path}: was 0 {unit} at HEAD, now {current}")
            continue
        if current >= previous:
            found.append(f"{path}: {previous} {unit} at HEAD, now {current} -- touching it owes a reduction")
    return found


#: Resolved once; a bare executable name would let PATH order decide which binary a gate trusts.
_GIT = shutil.which("git") or "/usr/bin/git"


def git(repo: Path, *args: str, stdin: bytes | None = None) -> bytes:
    """Run git in ``repo``; raise on failure (a gate must never guess past a git error)."""
    result = subprocess.run([_GIT, *args], cwd=repo, input=stdin, capture_output=True, check=True)
    return result.stdout


#: Path rewrites a MOVE makes inside the files it carries. A file whose only change is one of these did not
#: change its debt, only its address -- owner, 2026-10-03: "move all ... we must only have src/research".
#: Charging it as touched would refuse the move for debt it did not add.
#:
#: Applied IN ORDER: the two research TEST trees first, so their "scripts/research" never becomes
#: "src/research". Word-bounded on both sides, so ``scripts/research_mypy_crash_class.sh`` -- a different
#: file -- is left alone. The mover uses this same function; a second copy of the rule is how the gate and
#: the move would disagree about which files were only re-addressed.
MOVE_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    # The production entries leave src/research FIRST, so src/research is the lab and nothing else -- one
    # directory, one gate policy, no allowlist mirrored into ruff/mypy/pyright/coverage/docker configs.
    (re.compile(r"src([/.])research\1cert(?!\w)"), r"src\1cert"),
    (re.compile(r'"src"(\s*/\s*)"research"\1"cert"'), r'"src"\1"cert"'),
    (re.compile(r"src([/.])research\1(tv_rule_)"), r"src\1domain\1services\1features\1\2"),
    (re.compile(r"tests([/.])unit\1research\1cert(?!\w)"), r"tests\1unit\1cert"),
    (re.compile(r"tests([/.])unit\1research\1(test_tv_rule_)"), r"tests\1unit\1domain\1services\1features\1\2"),
    (re.compile(r"tests([/.])unit\1scripts\1research(?!\w)"), r"tests\1unit\1research"),
    (re.compile(r"tests([/.])scripts\1research(?!\w)"), r"tests\1unit\1research"),
    (re.compile(r"(?<![\w.])scripts([/.])research(?!\w)"), r"src\1research"),
    # Path joins: `_API / "scripts" / "research"` (237 files measured). The test-tree joins first.
    (re.compile(r'"tests"\)(\s*/\s*)"scripts"\1"research"'), r'"tests")\1"unit"\1"research"'),
    (re.compile(r'"unit"(\s*/\s*)"scripts"\1"research"'), r'"unit"\1"research"'),
    (re.compile(r'"scripts"(\s*[/,]\s*)"research"'), r'"src"\1"research"'),
)
#: Where a moved file lived before, for pairing an ADD with its DELETE: new prefix -> old prefixes.
_MOVED_PREFIXES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("apps/api/src/cert/", ("apps/api/src/research/cert/",)),
    ("apps/api/src/domain/services/features/tv_rule_", ("apps/api/src/research/tv_rule_",)),
    ("apps/api/tests/unit/cert/", ("apps/api/tests/unit/research/cert/",)),
    ("apps/api/tests/unit/domain/services/features/test_tv_rule_", ("apps/api/tests/unit/research/test_tv_rule_",)),
    ("apps/api/tests/unit/research/", ("apps/api/tests/unit/scripts/research/", "apps/api/tests/scripts/research/")),
    ("apps/api/src/research/", ("apps/api/scripts/research/",)),
)


def rewrite_moved_paths(text: str) -> str:
    """``text`` with every research-tree path rewritten to its post-move address."""
    for pattern, replacement in MOVE_REWRITES:
        text = pattern.sub(replacement, text)
    return text


#: ``Path(__file__)[.resolve()].parents[k]`` -- a file locating an ANCESTOR of itself by depth.
_OWN_ANCESTOR = re.compile(r"(Path\(__file__\)(?:\.resolve\(\))?\.parents\[)(\d+)(\])")


def _ancestor_index_map(old_path: str, new_path: str) -> dict[int, int]:
    """old ``parents[k]`` -> new ``parents[k']`` for every ancestor the move keeps (by its re-addressed path)."""
    new_ancestors = [str(p) for p in PurePosixPath(new_path).parents]
    mapping: dict[int, int] = {}
    for k, ancestor in enumerate(str(p) for p in PurePosixPath(old_path).parents):
        moved = rewrite_moved_paths(ancestor + "/").rstrip("/") or ancestor
        if moved in new_ancestors:
            mapping[k] = new_ancestors.index(moved)
    return mapping


def rewrite_for_move(text: str, old_path: str, new_path: str) -> str:
    """:func:`rewrite_moved_paths` plus the depth change of THIS file's move.

    The lab moved depth-preserving (scripts/research -> src/research), but its tests did not
    (tests/unit/scripts/research -> tests/unit/research is one level shallower) and neither did the cert
    engine (src/research/cert -> src/cert). A file that climbs to the API root with ``parents[N]`` must climb
    one step less; measured 2026-10-03: 69 tests and src/cert/model_spec.py.
    """
    text = rewrite_moved_paths(text)
    if old_path == new_path:
        return text
    mapping = _ancestor_index_map(old_path, new_path)
    return _OWN_ANCESTOR.sub(lambda m: f"{m.group(1)}{mapping.get(int(m.group(2)), int(m.group(2)))}{m.group(3)}", text)


_NO_BLOB = "0" * 40


def _moved_addresses(path: str) -> tuple[str, ...]:
    """Every address ``path`` may have had before the move (none when it is outside the moved trees)."""
    for new_prefix, old_prefixes in _MOVED_PREFIXES:
        if path.startswith(new_prefix):
            return tuple(old + path[len(new_prefix) :] for old in old_prefixes)
    return ()


def _raw_changes(repo: Path, *diff_args: str) -> list[tuple[str, str, str, str]]:
    """(old blob, new blob, old path, path) per added/copied/modified/renamed file.

    Renames are detected without git's 1,000-file limit (``-l0``) -- a tree move is exactly the case past
    it -- and a file git reports as ADDED is paired with the file DELETED at its pre-move address: a small
    file whose path rewrite changed most of its lines falls under git's 50% similarity bar and would read
    as brand new, carrying its whole debt into the gate.
    """
    args = ("diff", "--raw", "-z", "-M", "-l0", "--no-abbrev", "--diff-filter=ACMRD", *diff_args)
    fields = git(repo, *args).decode().split("\0")
    changes: list[tuple[str, str, str, str]] = []
    deleted: dict[str, str] = {}
    index = 0
    while index < len(fields) and fields[index].startswith(":"):
        _old_mode, _new_mode, old_blob, new_blob, status = fields[index][1:].split()
        if status[0] in "RC":
            changes.append((old_blob, new_blob, fields[index + 1], fields[index + 2]))
            index += 3
            continue
        if status == "D":
            deleted[fields[index + 1]] = old_blob
        else:
            changes.append((old_blob, new_blob, fields[index + 1], fields[index + 1]))
        index += 2
    paired: list[tuple[str, str, str, str]] = []
    for old_blob, new_blob, old_path, path in changes:
        origin = next((o for o in _moved_addresses(path) if o in deleted), None)
        if old_blob == _NO_BLOB and origin is not None:
            old_blob, old_path = deleted[origin], origin
        paired.append((old_blob, new_blob, old_path, path))
    return paired


def _blobs(repo: Path, ids: set[str]) -> dict[str, bytes]:
    """Object contents by id, through ONE ``git cat-file --batch`` (a tree move reads thousands)."""
    wanted = sorted(ids - {_NO_BLOB})
    if not wanted:
        return {}
    out = git(repo, "cat-file", "--batch", stdin=("\n".join(wanted) + "\n").encode())
    contents: dict[str, bytes] = {}
    cursor = 0
    for blob_id in wanted:
        header_end = out.index(b"\n", cursor)
        header = out[cursor:header_end].split()
        if header[-1] == b"missing":
            # A working-tree diff can name a blob that was never written to the object store; the caller
            # then reads that side from disk.
            cursor = header_end + 1
            continue
        size = int(header[2])
        contents[blob_id] = out[header_end + 1 : header_end + 1 + size]
        cursor = header_end + 1 + size + 1
    return contents


def is_mechanical_move(before: bytes, now: bytes, old_path: str = "", new_path: str = "") -> bool:
    """True when ``now`` is ``before`` unchanged, or with only the move's rewrite (paths + depth) applied.

    These gates judge DEBT, which a byte-identical file cannot have changed; a stale path inside such a file is a
    correctness defect its own tests catch, not a touch.
    """
    if before == now:
        return True
    moved = rewrite_for_move(before.decode("utf-8", errors="replace"), old_path, new_path)
    current = now.decode("utf-8", errors="replace")
    if moved == current:
        return True
    return _same_after_format(moved, current, new_path)


#: apps/api, where pyproject.toml pins ruff's target version -- the formatter must read the same config.
_API_DIR = Path(__file__).resolve().parents[3]


def _ruff_command() -> list[str]:
    """The ruff binary itself, not ``python -m ruff``: the husky hook runs bare ``python3``, which resolved to a
    Homebrew interpreter with no ruff module, so every format-only file failed closed (measured 2026-10-03)."""
    venv_ruff = _API_DIR / ".venv" / "bin" / "ruff"
    if venv_ruff.is_file():
        return [str(venv_ruff)]
    found = shutil.which("ruff")
    return [found] if found else [sys.executable, "-m", "ruff"]


def _ruff_format(source: str, path: str) -> str | None:
    """``source`` as ``ruff format`` writes it, or None when the formatter cannot run or rejects the input."""
    try:
        proc = subprocess.run(
            [*_ruff_command(), "format", "--stdin-filename", PurePosixPath(path).name, "-"],
            input=source,
            capture_output=True,
            text=True,
            cwd=_API_DIR,
            check=False,
        )
    except OSError:
        return None
    return proc.stdout if proc.returncode == 0 else None


def _same_after_format(before: str, now: str, path: str) -> bool:
    """A formatter pass is not a touch: ruff format keeps the AST, so equal output means no debt changed.

    Measured 2026-10-03: 20 files the move rewrote needed only Python 3.14's unparenthesised ``except A, B:``;
    counted as touched, the debt gates demanded paydowns in all 20 that the pre-push format gate made unavoidable.
    Fails CLOSED -- a formatter that cannot run leaves the file touched.
    """
    if not path.endswith(".py"):
        return False
    formatted_before = _ruff_format(before, path)
    return formatted_before is not None and formatted_before == _ruff_format(now, path)


def moved_from(repo: Path, *diff_args: str) -> dict[str, str]:
    """New path -> old path for every rename in ``git diff <diff_args>``: a moved file's BEFORE side."""
    return {path: old for _o, _n, old, path in _raw_changes(repo, *diff_args) if old != path}


def _split_mechanical(repo: Path, *diff_args: str) -> tuple[list[str], set[str]]:
    """(touched paths, paths that are no touch) for ``git diff <diff_args>``: a mechanical move, or an archived path."""
    changes = _raw_changes(repo, *diff_args)
    contents = _blobs(repo, {blob for old, new, _p, _q in changes for blob in (old, new)})
    touched: list[str] = []
    mechanical: set[str] = set()
    for old_blob, new_blob, old_path, path in changes:
        if is_archived(path):  # ARCHIVE-EXEMPT: KILL evidence owes no debt
            mechanical.add(path)
            continue
        before = contents.get(old_blob)
        now = contents.get(new_blob) if new_blob in contents else _worktree_bytes(repo, path)
        if before is not None and now is not None and is_mechanical_move(before, now, old_path, path):
            mechanical.add(path)
        else:
            touched.append(path)
    return touched, mechanical


def changed_paths(repo: Path, *diff_args: str) -> list[str]:
    """Added, copied, modified or renamed paths in ``git diff <diff_args>`` (``--cached`` = the index),
    minus mechanical moves: a file whose content only changed address is not a touch."""
    return _split_mechanical(repo, *diff_args)[0]


def touched_only(files: list[str], repo: Path) -> list[str]:
    """``files`` (absolute, or relative to the repo root) minus the ones the index shows as mechanically moved, and
    minus archived KILL evidence (``is_archived``), staged or not.

    For lint-staged, which hands every staged path to the linters: a mechanically moved file keeps exactly the
    findings it had, so re-linting it would refuse the move for debt it did not add. ONLY a positively
    identified move is dropped -- the first version kept only paths in the staged diff, so a file handed to the
    script outside a commit (the tests, a manual run) was silently skipped and its type error went unreported.
    """
    mechanical = _split_mechanical(repo, "--cached")[1]
    root = repo.resolve()
    kept: list[str] = []
    for name in files:
        path = Path(name)
        relative = name
        if path.is_absolute():
            resolved = path.resolve()
            # A path the index cannot hold is never a positively identified move -- keep it. Raising here
            # once read as an EMPTY list to lint_staged_python.sh, which then passed a real type error.
            if not resolved.is_relative_to(root):
                kept.append(name)
                continue
            relative = resolved.relative_to(root).as_posix()
        if relative not in mechanical and not is_archived(relative):
            kept.append(name)
    return kept


def _worktree_bytes(repo: Path, path: str) -> bytes | None:
    """A working-tree diff names no new blob; the file on disk is the new side."""
    target = repo / path
    return target.read_bytes() if target.is_file() else None


def deleted_paths(repo: Path, *diff_args: str) -> list[str]:
    """Paths ``git diff <diff_args>`` deletes, the OLD side of a rename included (``--no-renames``).

    `changed_paths` cannot say this: ACMR has no D, and a moved file reads as a rename of its new
    path. A row that compares a file against the REST of the tree must drop these, or a pure move
    is judged against the copy it is replacing.
    """
    names = git(repo, "diff", "--name-only", "-z", "--no-renames", "--diff-filter=D", *diff_args).decode().split("\0")
    return [name for name in names if name]


def git_cache_file(repo: Path, name: str) -> Path:
    """A gate's cache file under the git common dir: never tracked, shared by every worktree, gone with the clone."""
    common = Path(git(repo, "rev-parse", "--git-common-dir").decode().strip())
    return (common if common.is_absolute() else repo / common) / name


def text_key(text: str) -> str:
    """A gate cache's key for one text: a 16-byte blake2b digest, hex."""
    return hashlib.blake2b(text.encode("utf-8", "surrogatepass"), digest_size=_KEY_BYTES).hexdigest()


def write_json_atomic(path: Path, data: object) -> None:
    """A gate cache written whole or not at all: a reader never sees half a file, and a cache that cannot be written
    only costs the next run time (concept definitions, expression clones, touched-debt counts)."""
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=path.name, suffix=".tmp", delete=False, encoding="utf-8") as fh:
            json.dump(data, fh)
        Path(fh.name).replace(path)


def index_blob(repo: Path, path: str) -> str:
    """The STAGED content of ``path``."""
    return git(repo, "show", f":{path}").decode("utf-8", errors="replace")


def ref_blob(repo: Path, ref: str, path: str) -> str | None:
    """``path`` as it is at ``ref``, or None when it does not exist there (a new file, or no such ref)."""
    try:
        return git(repo, "show", f"{ref}:{path}").decode("utf-8", errors="replace")
    except subprocess.CalledProcessError:
        return None


#: ``--touched-in BASE HEAD`` carries the flag plus two commits.
_TOUCHED_IN_ARGC = 3


def main(argv: list[str] | None = None) -> int:
    """``--touched-only FILE...``: the staged files that are a real touch, one per line.
    ``--changed-vs-head``: every working-tree change vs HEAD that is a real touch (verify's --fast touch-gates).
    ``--touched-in BASE HEAD``: the real touches between two commits (pre-push, so a push is judged by the
    same rule as its commits -- the move's push range was 1,711 files to the raw diff, a handful touched).
    """
    args = sys.argv[1:] if argv is None else argv
    usage = "usage: python -m src.lib.quality_gates.ratchet_touch --touched-only FILE... | --changed-vs-head | --touched-in BASE HEAD"
    if not args or args[0] not in {"--touched-only", "--changed-vs-head", "--touched-in"}:
        print(usage, file=sys.stderr)
        return 2
    repo = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").decode().strip())
    if args[0] == "--touched-in":
        if len(args) != _TOUCHED_IN_ARGC:
            print(usage, file=sys.stderr)
            return 2
        names = changed_paths(repo, args[1], args[2])
    else:
        names = touched_only(args[1:], repo) if args[0] == "--touched-only" else changed_paths(repo, "HEAD")
    for name in names:
        print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
