"""The standards-rule value object and the instruments behind it: Rule, the lab waiver, ruff and basedpyright counts.

IMPORTERS/CALLERS: src/lib/quality_gates/standards_rules.py (re-exports every name), src/lib/quality_gates/perf_rules.py (Rule),
tests/scripts/test_standards_rules.py. AFFECTED API: none (library). DATA SCHEMAS: reads apps/api/pyproject.toml's
per-file-ignores and the root pyrightconfig.json's pythonVersion / typeCheckingMode; runs the project's ruff and basedpyright.

LOCATE (owner, 2026-10-19: "if not expose, also update it"): a row used to say only "N at HEAD, now N"; every row now
also says WHERE (Rule.locate, the --list CLI of standards_rules) from the SAME diagnostics it counts -- an AST row's sites,
ruff's and basedpyright's own findings -- so the count and the list can never disagree.

REUSE-AUDIT: moved from standards_rules.py (a 421-effective-line file over the 400 cap) along the seam "what a rule IS and how
ruff counts it" versus "which rules exist"; no logic changed. Considered check_touched_debt's Metric: it ratchets a touch, this
module only counts one text or one tree. ANN-GATE (2026-10-18) put basedpyright beside ruff on the same contract; considered
scripts/basedpyright_gate.py (it fails on ANY error in on-disk files; a row counts selected rules in a TEXT at a ref) and
verify_gate_helpers.parse_basedpyright_counts (summary totals, not per rule).
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final, TypedDict, cast

from src.lib.quality_gates.concept_definitions import GENERIC_NAME_LAB


class _RuffLocation(TypedDict):
    row: int
    column: int


class RuffDiagnostic(TypedDict):
    """One finding of ``ruff check --output-format json`` (the fields a row reads)."""

    code: str
    message: str
    location: _RuffLocation


class _PyrightPosition(TypedDict):
    line: int  # 0-based
    character: int


class _PyrightRange(TypedDict):
    start: _PyrightPosition
    end: _PyrightPosition


class PyrightDiagnostic(TypedDict):
    """One entry of basedpyright's ``--outputjson`` generalDiagnostics (the fields a row reads)."""

    severity: str
    rule: str
    message: str
    range: _PyrightRange


API_ROOT: Final = Path(__file__).resolve().parents[3]
#: The project's type-check settings, read by the IDE, verify 2i and the pre-push gate. A pyright row takes its Python
#: version and mode from here and switches on ONLY its own rules, in a config of the run's own: turning them on here would
#: paint every existing finding red in the editor and in that gate.
PYRIGHT_CONFIG: Final = API_ROOT.parents[1] / "pyrightconfig.json"


class InstrumentUnavailableError(RuntimeError):
    """A counter cannot run; a gate refuses to read that as a clean file (check_touched_debt exits 2)."""


def parsed(source: str) -> ast.Module | None:
    """`source` as a module, or None when it does not parse (a counter then reads it as nothing)."""
    try:
        return ast.parse(source)
    except SyntaxError:
        return None


@dataclass(frozen=True)
class Rule:
    """One standards rule's ratchet: which files it judges, how one file counts, what to do, the measured total."""

    key: str
    unit: str
    applies: Callable[[str], bool]
    #: An AST / text row: the 1-based line of each finding in one module; its count is how many.
    sites: Callable[[ast.Module, str], Sequence[int]] | None
    remedy: str
    baseline: int
    #: A rule ruff already implements is counted BY ruff (per file at a commit, once over the tree in verify).
    ruff_codes: tuple[str, ...] = ()
    preview: bool = False
    #: A lab rule counts THROUGH the lab's ruff waiver (pyproject per-file-ignores): the waiver keeps `ruff check .`
    #: green on debt the lab already carries, and this row is what makes that debt fall (RUFF-RESEARCH). Only the
    #: waiver is lifted: a lab TEST keeps the tests' conventions (an unused fixture argument is pytest wiring).
    waived: bool = False
    #: Count through EVERY per-file ignore: the row's codes are debt in every file it judges -- missing-annotation, where
    #: the tests' blanket ANN exemption and the CLIs' ANN001 hide debt like the lab waiver does (ANN-GATE, 2026-10-18).
    everywhere: bool = False
    #: Count past per-line and file-level noqa comments (lab-ruff only): 398 lab files open with a blanket opt-out, and a ratchet
    #: a single comment can switch off is not one -- verify's research bug gate made the same call. It also keeps the
    #: noqa row satisfiable: deleting a suppression must not raise this row's count.
    ignore_noqa: bool = False
    #: The sites of a row that needs the file's own path (repo-relative) -- pandas-undeclared resolves a marker's callee
    #: from it. Used in place of ``sites`` by a touch row and by the tree total.
    path_sites: Callable[[str, str], Sequence[int]] | None = None
    #: A rule basedpyright implements (unknown-type): its diagnostics, each switched to "error" for the row's run only.
    pyright_rules: tuple[str, ...] = ()

    def tree_sites(self, tree: ast.Module, source: str) -> Sequence[int]:
        """An AST row's finding lines in one parsed module (none for a ruff / basedpyright row)."""
        return () if self.sites is None else self.sites(tree, source)

    def count(self, source: str) -> int:
        tree = parsed(source) if self.sites is not None else None
        return 0 if tree is None else len(self.tree_sites(tree, source))

    def count_file(self, path: str, source: str) -> int:
        """The shape a touch row counts with: (path, source)."""
        if self.path_sites is not None:
            return len(self.path_sites(path, source))
        if self.pyright_rules:
            return pyright_findings(self.pyright_rules, path, source)
        if not self.ruff_codes:
            return self.count(source)
        return ruff_findings(
            self.ruff_codes, path, source, preview=self.preview, waived=self.waived, everywhere=self.everywhere, ignore_noqa=self.ignore_noqa
        )

    def locate(self, path: str, source: str) -> list[str]:
        """Each finding count_file counts, as ``L<line> <what>`` -- read from the same diagnostics, so the list is
        exactly as long as the count."""
        if self.path_sites is not None:
            return [f"L{line}" for line in sorted(self.path_sites(path, source))]
        if self.pyright_rules:
            return pyright_locations(self.pyright_rules, path, source)
        if self.ruff_codes:
            return ruff_locations(
                self.ruff_codes, path, source, preview=self.preview, waived=self.waived, everywhere=self.everywhere, ignore_noqa=self.ignore_noqa
            )
        tree = parsed(source) if self.sites is not None else None
        return [] if tree is None else [f"L{line}" for line in sorted(self.tree_sites(tree, source))]


def _tool(name: str) -> str:
    """The venv's ``name`` (local), else the one on PATH (CI installs both instruments from requirements.lock)."""
    local = API_ROOT / ".venv" / "bin" / name
    if local.is_file():
        return str(local)
    found = shutil.which(name)
    if found is None:
        raise InstrumentUnavailableError(f"{name} not found -- create apps/api/.venv or install {name}")
    return found


def ruff_binary() -> str:
    """The venv's ruff (local), else the one on PATH (CI installs it system-wide)."""
    return _tool("ruff")


def pyright_binary() -> str:
    """The venv's basedpyright (local), else the one on PATH."""
    return _tool("basedpyright")


#: The lab's waiver patterns in pyproject's per-file-ignores -- ONE home for the waived codes (lab_waiver_codes reads it).
#: The lab root is the gate tooling's own spelling (GENERIC_NAME_LAB, pinned to RESEARCH_ROOT_REL by a test): the hooks
#: run this under a bare python3, and importing src.shared would pull numpy through its package __init__.
LAB_WAIVER_PATTERNS: Final = (f"{GENERIC_NAME_LAB.removeprefix('apps/api/')}**/*.py", "tests/unit/research/**/*.py")
LAB_TESTS_PREFIX: Final = "apps/api/tests/unit/research/"


@cache
def _per_file_ignores() -> Mapping[str, list[str]]:
    """pyproject's [tool.ruff.lint.per-file-ignores], read once per process."""
    table: dict[str, list[str]] = tomllib.loads((API_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["ruff"]["lint"]["per-file-ignores"]
    return table


def lab_waiver_codes() -> tuple[str, ...]:
    """Every ruff code pyproject waives for the lab -- its measured debt, read from pyproject itself."""
    table = _per_file_ignores()
    return tuple(sorted({code for pattern in LAB_WAIVER_PATTERNS for code in table.get(pattern, ())}))


def _lifted_ignores(*, waived: bool, everywhere: bool) -> list[str]:
    """The ``--config`` that lifts what a row counts through: every per-file ignore (``everywhere``), or the lab waiver's
    entries only (``waived``) -- the conventions and the tests' exemptions stay, so a lab test is never charged an unused
    fixture argument (measured 2026-10-18: 290 such findings in tests/unit/research while every entry was lifted)."""
    if not (waived or everywhere):
        return []
    kept = {} if everywhere else {pattern: codes for pattern, codes in _per_file_ignores().items() if pattern not in LAB_WAIVER_PATTERNS}
    table = ", ".join(f"{json.dumps(pattern)} = {json.dumps(codes)}" for pattern, codes in kept.items())
    return ["--config", f"lint.per-file-ignores = {{{table}}}"]


def _ruff_command(codes: tuple[str, ...], *, preview: bool, waived: bool, everywhere: bool, ignore_noqa: bool) -> list[str]:
    cmd = [ruff_binary(), "check", "--select", ",".join(codes), "--no-fix", "--no-force-exclude", "--output-format", "json"]
    cmd += ["--preview"] if preview else []
    cmd += _lifted_ignores(waived=waived, everywhere=everywhere)
    return cmd + (["--ignore-noqa"] if ignore_noqa else [])


def _ruff_diagnostics(
    codes: tuple[str, ...], path: str, source: str, *, preview: bool, waived: bool, everywhere: bool, ignore_noqa: bool
) -> list[RuffDiagnostic]:
    """ruff's own JSON findings of ``codes`` in one text (ruff_findings counts them, ruff_locations prints them)."""
    cmd = _ruff_command(codes, preview=preview, waived=waived, everywhere=everywhere, ignore_noqa=ignore_noqa)
    cmd += ["--stdin-filename", path.removeprefix("apps/api/"), "-"]
    proc = subprocess.run(cmd, cwd=API_ROOT, input=source, capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 1):
        raise InstrumentUnavailableError(f"ruff failed on {path}: {proc.stderr.strip()[:200]}")
    return cast("list[RuffDiagnostic]", json.loads(proc.stdout or "[]"))


def ruff_findings(
    codes: tuple[str, ...],
    path: str,
    source: str,
    *,
    preview: bool = False,
    waived: bool = False,
    everywhere: bool = False,
    ignore_noqa: bool = False,
) -> int:
    """``codes`` findings in one text, by the project's own ruff config (its per-file ignores and noqa included) --
    or, ``waived`` / ``everywhere``, counted through the ignores the row lifts (the ratchet's count of the hidden debt)."""
    return len(_ruff_diagnostics(codes, path, source, preview=preview, waived=waived, everywhere=everywhere, ignore_noqa=ignore_noqa))


def ruff_locations(codes: tuple[str, ...], path: str, source: str, *, preview: bool, waived: bool, everywhere: bool, ignore_noqa: bool) -> list[str]:
    """The findings ruff_findings counts, as ``L<row> <code> <message>``."""
    found = _ruff_diagnostics(codes, path, source, preview=preview, waived=waived, everywhere=everywhere, ignore_noqa=ignore_noqa)
    return [f"L{d['location']['row']} {d['code']} {d['message']}" for d in found]


def _tree_files(rule: Rule, tracked: Collection[str], repo: Path) -> list[str]:
    """The ``tracked`` files in ``rule``'s scope that are on disk, apps/api-relative, sorted.

    A HEAD path moved or deleted in the working tree cannot be measured on disk -- handed to ruff or basedpyright it
    crashed the whole ratchet (8f, 2026-10-20: a staged ``git mv`` of uncertainty_zones.py) -- so it is skipped; the
    file's findings are counted under its new path once the move is committed.
    """
    return sorted(p.removeprefix("apps/api/") for p in tracked if p.startswith("apps/api/") and rule.applies(p) and (repo / p).is_file())


def ruff_tree_total(rule: Rule, repo: Path, tracked: Collection[str]) -> int:
    """``rule``'s ruff findings over the ``tracked`` files in its scope, as they are on disk -- one ruff run.

    The files are passed EXPLICITLY, never as directories: given the overlapping roots ``src`` and ``src/research``
    (the product config excludes the lab from ``src``), ruff 0.15.6 dropped one file's findings in about half the
    runs, cache or no cache (measured 2026-10-12: 773 vs 777 D101/D103 findings, all four in one file).
    """
    files = _tree_files(rule, tracked, repo)
    if not files:
        return 0
    cmd = _ruff_command(rule.ruff_codes, preview=rule.preview, waived=rule.waived, everywhere=rule.everywhere, ignore_noqa=rule.ignore_noqa)
    proc = subprocess.run([*cmd, "--no-cache", "--exit-zero", *files], cwd=repo / "apps" / "api", capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise InstrumentUnavailableError(f"ruff failed over the tree: {proc.stderr.strip()[:200]}")
    return len(json.loads(proc.stdout or "[]"))


def _interpreter() -> str:
    """The Python whose site-packages resolve third-party imports: the venv's (the pre-commit runs the gates under the bare
    system python3, which has no numpy), else this one (CI installs the project into it)."""
    local = API_ROOT / ".venv" / "bin" / "python"
    return str(local) if local.is_file() else sys.executable


def _pyright_errors(rules: tuple[str, ...], root: Path, files: Sequence[str]) -> int:
    """``rules`` findings in ``files`` (absolute, or relative to ``root``, the import root) -- one basedpyright run."""
    return len(_pyright_diagnostics(rules, root, files))


def _pyright_diagnostics(rules: tuple[str, ...], root: Path, files: Sequence[str]) -> list[PyrightDiagnostic]:
    """basedpyright's own error diagnostics of ``rules`` in ``files`` (_pyright_errors counts them)."""
    settings = json.loads(PYRIGHT_CONFIG.read_text(encoding="utf-8"))
    config: dict[str, object] = {
        "extraPaths": [str(root)],
        "pythonVersion": settings["pythonVersion"],
        "typeCheckingMode": settings["typeCheckingMode"],
    }
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "pyrightconfig.json"
        project.write_text(json.dumps(config | dict.fromkeys(rules, "error")), encoding="utf-8")
        cmd = [pyright_binary(), "--project", str(project), "--pythonpath", _interpreter(), "--outputjson", *files]
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
    failure = f"basedpyright failed (exit {proc.returncode}): {(proc.stderr or proc.stdout).strip()[:200]}"
    if proc.returncode not in (0, 1):  # 0 clean, 1 errors found; 2-4 fatal, config, arguments
        raise InstrumentUnavailableError(failure)
    try:
        diagnostics = cast("list[PyrightDiagnostic]", json.loads(proc.stdout)["generalDiagnostics"])
    except (ValueError, KeyError, TypeError) as exc:  # JSONDecodeError is a ValueError
        raise InstrumentUnavailableError(failure) from exc
    return [d for d in diagnostics if d.get("severity") == "error" and d.get("rule") in rules]


def _shadow(root: Path, rel: str, source: str) -> Path:
    """``source`` written at ``rel`` under ``root``, every other entry on the way a symlink to API_ROOT's own: the text's
    imports -- absolute, relative, its own package's -- resolve as the file on disk would (a missing directory is made)."""
    real, shadow = API_ROOT, root
    parts = Path(rel).parts
    for depth, part in enumerate(parts):
        if real.is_dir():
            for entry in real.iterdir():
                if entry.name != part:
                    (shadow / entry.name).symlink_to(entry)
        real, shadow = real / part, shadow / part
        if depth < len(parts) - 1:
            shadow.mkdir()
    shadow.write_text(source, encoding="utf-8")
    return shadow


def pyright_findings(rules: tuple[str, ...], path: str, source: str) -> int:
    """``rules`` findings in one text, checked at its own path in a symlinked copy of apps/api (basedpyright reads no
    stdin). The rest of the tree is read as it is ON DISK, so the count is this text against the current tree."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        return _pyright_errors(rules, root, [str(_shadow(root, path.removeprefix("apps/api/"), source))])


def pyright_locations(rules: tuple[str, ...], path: str, source: str) -> list[str]:
    """The findings pyright_findings counts, as ``L<line> <rule> <message>``."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        found = _pyright_diagnostics(rules, root, [str(_shadow(root, path.removeprefix("apps/api/"), source))])
    return [f"L{d['range']['start']['line'] + 1} {d['rule']} {d['message'].splitlines()[0]}" for d in found]


def pyright_tree_total(rule: Rule, repo: Path, tracked: Collection[str]) -> int:
    """``rule``'s basedpyright findings over the ``tracked`` files in its scope, as they are on disk -- one run, single
    threaded: ``--threads 4`` measured 3,346 against the single thread's 3,348 on the same tree (2026-10-18), and a
    ratchet must read the same total every time."""
    files = _tree_files(rule, tracked, repo)
    return _pyright_errors(rule.pyright_rules, repo / "apps" / "api", files) if files else 0
