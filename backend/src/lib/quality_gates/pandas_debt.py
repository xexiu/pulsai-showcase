"""Pandas debt: the counters behind the pandas write-time hook and the two pandas ratchet rows -- one home, so the door
an agent meets while writing and the ratchet a commit meets count the same thing.

IMPORTERS/CALLERS: .claude/hooks/pandas_last_resort_guard.py (MARKER, ROW_WISE, unexcused, unexcused_runtime_lines --
refuses ADDED debt as it is written), src/lib/quality_gates/standards_rules.py (the `pandas-undeclared` and `pandas-loop` rows:
check_touched_debt makes a touched file pay its share down and a new file bring none; verify step 2f-std ratchets the
tree), tests/scripts/test_pandas_debt.py. AFFECTED API: none (library + `--list` CLI). DATA SCHEMAS: none.

WHY (owner, 2026-10-13 / 10-14): "use PANDAS as LAST resource!! PERF IS A MUST" -- then, after a session wrote pandas-first
modules straight through the hook: "can you make a ratchet like you made for ruff, linters, duplicates ... so next time,
you, or other devs, can clearly be blocked/warned of performance?" Measured that day: the hook had two holes (one
marker anywhere released the whole text; a gortex batch_edit reached no write-time guard -- fixed in the hook and the
gate), and nothing counted the debt itself.

TWO COUNTS:
  runtime_debt       a code LINE whose pandas RUNS (a pd. / pandas. attribute, a `.to_pandas()` call -- never an
                     annotation or a TYPE_CHECKING import) that no verified edge excuses: its own marker (`PANDAS-OK` +
                     colon) must name a callee called on that line whose signature takes or returns pandas. Once per line;
                     the hook's measure, so the door and the ratchet count one thing (ONE-MEASURE, 2026-10-15).
  pandas_loop_sites  the shapes that make pandas slow and that no ruff code catches (researched 2026-10-14: ruff's PD
                     rules cover `.values` / `inplace` / aliases, not row iteration or growth in a loop): iterrows /
                     itertuples / apply / applymap (row-wise Python), a frame or array GROWN by its own accumulator in a
                     loop (x = concat([x, ...]) / np.append(x, ...): quadratic), and loc / iloc / at / iat keyed by the
                     enclosing loop's own variable (per-row scalar access from Python). Tightened by sampling HEAD the same
                     day: chained subscripts were mostly dicts, per-fold slices and label-set writes are vectorised, a
                     concat per iteration that accumulates nothing is linear -- none of those count.
                     Design reference: pdperf PPO001-005 / 007 (MIT, 2 stars, no release, no config or suppression --
                     measured not mature enough to gate on, so the shapes live here, tested).

REUSE-AUDIT: concept_definitions.sources_on_disk (the scope every ratchet reads: apps/api/src + scripts, artifacts
excluded) -- imported. The regexes were pandas_last_resort_guard's; they MOVE here and the hook imports them back
(one concept, one definition). Considered ruff PD / pdperf as the counter: see TWO COUNTS.

Run from apps/api: .venv/bin/python -m src.lib.quality_gates.pandas_debt --list   (per-file debt, highest first)
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Final

from src.lib.quality_gates.concept_definitions import sources_on_disk
from src.lib.quality_gates.explicit_any import ranked_counts, type_positions

MARKER: Final = "PANDAS-OK:"
ROW_WISE: Final = re.compile(r"\.(?:iterrows|itertuples|applymap)\(|\.apply\(|\.groupby\([^()]*(?:\([^()]*\)[^()]*)*\)\s*\.apply\(")
EXCUSED: Final = re.compile(rf"{MARKER}\s*\S")
#: A PAIRED triple-quoted string: its lines are text. An unpaired quote (an Edit fragment cut mid-docstring) masks
#: nothing -- a false positive is a nuisance, hiding a real call would be a hole.
_TRIPLE: Final = re.compile(r"(\"\"\"|''')(?:.|\n)*?\1")

#: Calls that grow a frame / array by copying it: inside a loop each call copies everything so far (quadratic).
_GROWERS: Final = frozenset({("pd", "concat"), ("pandas", "concat"), ("np", "append"), ("np", "vstack"), ("np", "hstack"), ("np", "concatenate"),
                             ("np", "column_stack"), ("np", "row_stack"), ("numpy", "append"), ("numpy", "concatenate")})  # fmt: skip
_ROW_ITERATION: Final = frozenset({"iterrows", "itertuples", "apply", "applymap"})
_SCALAR_ACCESS: Final = frozenset({"loc", "iloc", "at", "iat"})
_ROOT: Final = Path(__file__).resolve().parents[5]
_SHOWN: Final = 30


def _code_lines(text: str) -> Iterator[str]:
    """`text`'s lines that can hold code: not a comment, not inside a paired triple-quoted string."""
    inside: set[int] = set()
    for span in _TRIPLE.finditer(text):
        first = text.count("\n", 0, span.start())
        inside.update(range(first, first + span.group(0).count("\n") + 1))
    for number, line in enumerate(text.splitlines()):
        if number not in inside and not line.lstrip().startswith("#"):
            yield line


def unexcused(pattern: re.Pattern[str], text: str) -> int:
    """Code lines matching `pattern` that do not carry the marker and a reason themselves."""
    return sum(1 for line in _code_lines(text) if pattern.search(line) and not EXCUSED.search(line))


class _LoopSites(ast.NodeVisitor):
    """Records the slow shapes as (line, kind). `targets` holds each enclosing loop's own variables (for / async for /
    comprehension targets; a while loop binds none), innermost last."""

    def __init__(self) -> None:
        self.sites: list[tuple[int, str]] = []
        self.targets: list[frozenset[str]] = []

    def _loop(self, target: ast.AST | None, header: list[ast.AST], body: list[ast.AST]) -> None:
        for child in header:
            self.visit(child)
        names: frozenset[str] = frozenset(n.id for n in ast.walk(target) if isinstance(n, ast.Name)) if target is not None else frozenset()
        self.targets.append(names)
        for child in body:
            self.visit(child)
        self.targets.pop()

    def visit_For(self, node: ast.For | ast.AsyncFor) -> None:
        self._loop(node.target, [node.iter], [*node.body, *node.orelse])

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.visit_For(node)

    def visit_While(self, node: ast.While) -> None:
        self._loop(None, [node.test], [*node.body, *node.orelse])

    def generic_visit(self, node: ast.AST) -> None:
        if not isinstance(node, ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp):
            super().generic_visit(node)
            return
        names = frozenset(n.id for g in node.generators for n in ast.walk(g.target) if isinstance(n, ast.Name))
        self.targets.append(names)
        super().generic_visit(node)
        self.targets.pop()

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr in _ROW_ITERATION:
            self.sites.append((node.lineno, f"row-wise .{node.func.attr}()"))
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        bound: frozenset[str] = frozenset[str]().union(*self.targets) if self.targets else frozenset()
        key = list(ast.walk(node.slice))
        if (bound and isinstance(node.value, ast.Attribute) and node.value.attr in _SCALAR_ACCESS
                and not any(isinstance(k, ast.Slice) for k in key) and any(isinstance(k, ast.Name) and k.id in bound for k in key)):  # fmt: skip
            self.sites.append((node.lineno, "row access by the loop variable"))
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        call, target = node.value, node.targets[0] if len(node.targets) == 1 else None
        if self.targets and isinstance(target, ast.Name) and isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
            owner = call.func.value.id if isinstance(call.func.value, ast.Name) else ""
            fed_back = any(isinstance(n, ast.Name) and n.id == target.id for a in call.args for n in ast.walk(a))
            if (owner, call.func.attr) in _GROWERS and fed_back:
                self.sites.append((node.lineno, f"{owner}.{call.func.attr}() accumulates in a loop"))
        self.generic_visit(node)


def loop_sites(tree: ast.Module) -> list[tuple[int, str]]:
    """Where the row-wise and growth-in-loop shapes are in one module: (line, kind), in source order."""
    visitor = _LoopSites()
    visitor.visit(tree)
    return sorted(visitor.sites)


def pandas_loop_sites(tree: ast.Module, _source: str) -> int:
    """How many (the ratchet row's per-file count)."""
    return len(loop_sites(tree))


#: EDGE-MARKER (owner, 2026-10-14: "pandas? again? ... why hook didnt fired?"). One day put 19 free-text markers through
#: the door, several on live-engine code with no pandas API in sight: a phrase is satisfied by typing the phrase. At the
#: write door a RUNTIME pandas line is now excused only by a marker NAMING A CALLEE on that same line whose own signature
#: takes or returns a pandas type -- an edge that is checked, not claimed. Type-only uses (annotations, TYPE_CHECKING
#: imports, quoted cast targets) need no marker at all. The tree ratchet (pandas_debt) still counts as before.
EDGE: Final = re.compile(rf"{MARKER}\s*([A-Za-z_][\w.]*)")
_PANDAS_TYPE: Final = re.compile(r"\b(?:pd|pandas)\.|\bDataFrame\b|\bSeries\b")
_PANDAS_NAMES: Final = frozenset({"pd", "pandas"})


def _type_only_ids(tree: ast.Module) -> set[int]:
    """ids of every node inside an annotation or an `if TYPE_CHECKING:` block -- nothing there runs."""
    roots: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and "TYPE_CHECKING" in ast.unparse(node.test):
            roots += node.body
        else:
            roots += type_positions(node)  # explicit_any's one walker of annotations and type arguments
    return {id(n) for root in roots for n in ast.walk(root)}


def _runs_pandas(node: ast.AST) -> bool:
    """A pd. / pandas. attribute or a `.to_pandas()` call. An import alone runs nothing (an unused one is ruff's F401);
    the cost of pandas is in the lines that use it, and every one of those is judged."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id in _PANDAS_NAMES
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "to_pandas"


def runtime_pandas_lines(source: str) -> set[int]:
    """1-based lines whose pandas use RUNS: a pd. / pandas. attribute or a `.to_pandas()` call outside annotations and
    TYPE_CHECKING blocks. Empty when `source` does not parse (the door then fails open)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    skip = _type_only_ids(tree)
    lines: set[int] = set()
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if _runs_pandas(node) and isinstance(node, ast.stmt | ast.expr):  # both carry a line number
            lines.add(node.lineno)
    return lines


def _module_file(module: str, here: Path) -> Path | None:
    """A module's file: `src.x.y` under apps/api, else a sibling script of `here` (the lab's bare imports)."""
    rel = Path(*module.split("."))
    for base in (_ROOT / "apps" / "api", here.parent):
        for candidate in (base / rel.with_suffix(".py"), base / rel / "__init__.py"):
            if candidate.is_file():
                return candidate
    return None


def _callee_file(prefix: str, source: str, here: Path) -> Path | None:
    """The file defining `prefix` (an import alias, a module name, or a dotted module path) as `source` imports it."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if (alias.asname or alias.name) == prefix:
                    return _module_file(f"{node.module}.{alias.name}", here) or _module_file(node.module, here)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if (alias.asname or alias.name) == prefix:
                    return _module_file(alias.name, here)
    return _module_file(prefix, here)


def _signature_text(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """One def's parameters and return annotation as source text: `(a: int) -> str`."""
    return ast.unparse(fn.args) + " -> " + (ast.unparse(fn.returns) if fn.returns else "")


def _signature(file: Path, name: str) -> str | None:
    """The annotations of every def called `name` in `file` (any depth), joined; None when none exists."""
    try:
        tree = ast.parse(file.read_text(encoding="utf-8", errors="replace"))
    except OSError, SyntaxError:
        return None
    sigs = [_signature_text(n) for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == name]
    return " | ".join(sigs) or None


def verified_edge(line: str, source: str, here: Path) -> bool:
    """Does `line`'s marker name a callee called on that line whose own signature takes or returns a pandas type?"""
    found = EDGE.search(line)
    if found is None:
        return False
    dotted = found.group(1).rstrip(".")
    prefix, _, name = dotted.rpartition(".")
    if f"{name}(" not in line.split("#", 1)[0]:
        return False
    try:
        file = _callee_file(prefix, source, here) if prefix else here
    except SyntaxError:
        return False
    sig = _signature(file, name) if file is not None else None
    return bool(sig and _PANDAS_TYPE.search(sig))


def pandas_apis(source: str) -> frozenset[str]:
    """Names of the defs in `source` whose own signature takes or returns a pandas type -- an existing pandas API, whose
    body may build the frames its contract promises (a lab function its callers read as a DataFrame)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return frozenset()
    defs = (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef))
    return frozenset(n.name for n in defs if _PANDAS_TYPE.search(_signature_text(n)))


def _enclosing_def(tree: ast.Module) -> dict[int, str]:
    """Each line's innermost enclosing def name (the def that starts latest among those spanning the line)."""
    owner: dict[int, tuple[int, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            for line in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                if node.lineno > owner.get(line, (0, ""))[0]:
                    owner[line] = (node.lineno, node.name)
    return {line: name for line, (_, name) in owner.items()}


def unexcused_runtime_lines(source: str, here: Path, context: str | None = None, apis: frozenset[str] = frozenset()) -> Counter[str]:
    """The runtime pandas lines of `source` that no verified edge excuses, by their code (a moved line is the same line).
    `context`: the file whose imports resolve a marker's callee when `source` is only an edit's fragment. `apis`: the
    pandas APIs that existed BEFORE the edit (pandas_apis) -- a line inside one keeps its contract and is excused."""
    lines = source.splitlines()  # keyed by the code, not its comment: a moved line is the same line
    return Counter(lines[n - 1].split("#", 1)[0].strip() for n in _unexcused_line_numbers(source, here, context, apis))


def _unexcused_line_numbers(source: str, here: Path, context: str | None, apis: frozenset[str]) -> list[int]:
    """The 1-based lines unexcused_runtime_lines keys by their code."""
    lines = source.splitlines()
    imports = context if context is not None else source
    try:
        owner = _enclosing_def(ast.parse(source)) if apis else {}
    except SyntaxError:
        owner = {}
    return [n for n in runtime_pandas_lines(source)
            if n <= len(lines) and owner.get(n) not in apis and not verified_edge(lines[n - 1], imports, here)]  # fmt: skip


def runtime_debt(path: str, source: str) -> int:
    """The `pandas-undeclared` count of one file (`path` repo-relative): its RUNTIME pandas lines that no verified edge
    excuses -- the write-time hook's own measure. ONE-MEASURE (2026-10-15): the row counted with pandas_debt's line
    regex, which charged annotations and TYPE_CHECKING imports and accepted any free-text marker, while the hook judges
    runtime lines only -- 8,444 vs 3,555 lines over the tree, 111 files whose whole debt was types or free text."""
    return len(runtime_debt_lines(path, source))


def runtime_debt_lines(path: str, source: str) -> list[int]:
    """The 1-based line of each pandas line runtime_debt counts (the pandas-undeclared row's sites)."""
    return _unexcused_line_numbers(source, _ROOT / path, None, frozenset())


def tree_debt(repo: Path) -> dict[str, int]:
    """Every in-scope file's runtime pandas debt on disk (runtime_debt), the files carrying any."""
    counts = {path: runtime_debt(path, text) for path, text in sources_on_disk(repo).items()}
    return {path: n for path, n in counts.items() if n}


def main(argv: list[str] | None = None) -> int:
    """`--list` prints every file's pandas debt over the working tree (highest first); the total either way."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--list", action="store_true", help="every file's pandas debt over the working tree, highest first")
    parser.add_argument("--repo-root", type=Path, default=_ROOT)
    args = parser.parse_args(argv)
    debt = tree_debt(args.repo_root)
    for path, n in ranked_counts(debt)[: None if args.list else _SHOWN]:
        print(f"{n:5d}  {path}")
    print(f"pandas debt: {sum(debt.values())} lines in {len(debt)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
