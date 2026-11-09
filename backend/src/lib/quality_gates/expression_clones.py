"""Expression clones: one normalised expression in two or more functions anywhere in src/ (product AND lab) and scripts/.

IMPORTERS/CALLERS: scripts/verify.sh step 2f-expr (``--tree`` ratchet), scripts/check_touched_debt.py (the
``expression-clone`` row: a touched file lowers its count), tests/scripts/test_expression_clones.py. AFFECTED API:
none (library + CLI; ``--tree`` exits 1 when the count rises or falls unrecorded). DATA SCHEMAS: reads git blobs and
the working tree; writes one cache file per judged repo, ``<repo>/.cache/expression_clones.json`` (content hash -> the file's keys),
gitignored and safe to delete.

DRY-GENERIC-SRC (owner, 2026-10-12: "why not GENERAL src/ folder", "NOT only ur use case ... BULLET PROOF"). Every DRY
door here compared something a one-expression copy does not have: concept_definitions NAMES and known SHAPES, jscpd
copied BLOCKS, gortex MinHash function BODIES, reinvent_wheel_guard new FILE names. Measured on the tree the day this
was written, at MIN_NODES 25: 825 maximal clone groups over 3,805 function sites -- the annualised Sharpe
``float(r.mean() / r.std() * np.sqrt(bpy)) if len(r) > 30 else 0.0`` alone in 68 functions -- that no door saw.

THE SHAPE. A variable name becomes a placeholder (first seen = v0, then v1 ...), so renaming does not hide a copy. A
called bare name, an attribute and a constant are kept: ``.as_unit("ms")`` and ``.as_unit("s")``, ``np.sqrt`` and
``np.log`` are different concepts. An expression of fewer than MIN_NODES AST nodes is too small to be one; only a
MAXIMAL clone counts (a part of a larger clone, at the same sites, is not reported again).

PRECISION decides the threshold, measured twice on random samples of 25 groups. At 20 nodes ~15-17 were real
re-derivations and the rest idioms that sit exactly at 20 (``not isinstance(a, str) or not isinstance(b, str)``,
``isinstance(n, ast.Constant) and isinstance(n.value, int)``); at 25, ~21 were real (a vol-target scale x12, a date-
window mask x6, a momentum IC, an OBV step, an IC sign check, residual returns ...) and the idioms were gone, for
1,792 -> 825 groups. A touch-to-lower gate makes every false positive a pointless edit, so precision wins: 25. Type
annotations, print / log lines and f-strings are never candidates. A judged exception carries
``CLONE-OK: <why>`` on its line (a Pine transcription that must mirror its source 1:1).

SAME-VALUE (2026-10-18, owner: "robust, proactive, always, bullet proof"): two more candidates join the same index, so
the same doors judge them -- a module-level CONSTANT (constant_clones: its value, names resolved to their origin) and a
whole function BODY of MIN_BODY_NODES+ (parameters as placeholders, globals resolved to their origin, so a wrapper over
each module's own constant is not a copy). Measured the day they joined: 165 constant groups and 152 body groups that
no door saw (an 18-group body sample was all real: _as_int beside the shared int_or_default, the lab _cci beside
indicators.cci ...). The write-time door is one_definition_guard.new_value_clones.

REUSE-AUDIT: concept_definitions (sources_at_ref, in_scope -- the same scope and the same one-round-trip git read) and
check_touched_debt's TreeSides (the before / after trees a cross-file row is judged against) are reused, not copied;
gortex find_clones (whole function bodies) and jscpd (line blocks) answer different questions and stay.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast

from src.lib.quality_gates.concept_definitions import in_scope, sources_at_ref, sources_on_disk
from src.lib.quality_gates.constant_clones import CLONE_OK, constant_occurrences, module_of, name_origins
from src.lib.quality_gates.ratchet_touch import write_json_atomic
from src.lib.quality_gates.recompute_vocab import named_params
from src.shared.utils.json_rows import json_object

_API: Final = Path(__file__).resolve().parents[3]
_REPO: Final = _API.parents[1]
#: Smallest expression (AST nodes) that can be a concept; 20 measured as the precision / recall balance (docstring).
MIN_NODES: Final = 25
#: Smallest whole function BODY (AST nodes) compared as one unit (SAME-VALUE, 2026-10-18): a copied helper whose every
#: expression is under MIN_NODES. Measured over src + scripts the day it was added: 215 repeated bodies at 15+ nodes,
#: 256 at 10+; a 15-group sample of 10..24-node bodies was mostly real copies (_coerce_float x3, _clamp01, _check_fitted
#: x4, _load_json ...), with globals resolved to their origin so a wrapper over each module's OWN constant is not one.
MIN_BODY_NODES: Final = 15
SHARED_HOME: Final = "apps/api/src/shared/"
#: The cache is valid for exactly the sources that compute its keys -- this module and constant_clones (whose rows it
#: stores): any change to how a key is computed invalidates it, with nobody having to remember to bump a number.
_CACHE_VERSION: Final = hashlib.sha1(
    Path(__file__).read_bytes() + Path(__file__).with_name("constant_clones.py").read_bytes(), usedforsecurity=False
).hexdigest()[:12]
#: A message is not a concept: printing or logging the same line twice is not a second definition of anything.
_LOG_METHODS: Final = frozenset({"debug", "info", "warning", "error", "exception", "critical", "log"})
_NOT_CANDIDATES: Final = (ast.Constant, ast.Name, ast.JoinedStr, ast.FormattedValue, ast.Lambda)
#: A clone is one expression in at least this many functions.
CLONE_MIN_SITES: Final = 2
#: A cached occurrence row: key, function, line, parent key.
_ROW_FIELDS: Final = 4
#: The whole-tree count. It may only fall; --tree fails when it falls unrecorded, so a paid debt cannot become room.
#: 2026-10-12: 1,704 groups at MIN_NODES 20 the day the gate was written; 825 over 3,805 sites at 25 (precision).
#: 2026-10-16 (GATE-RED): 821 -> 813, measured at c9f50859d -- paid on touch by the 10-15/16 slices, never locked;
#: -> 812 at a00a68773 (check_duplicate_lines' root test given one home); -> 810 at 6ccdabafc (10-16 paydowns, locked in ONE-DEF-LAB).
#: 798 -> 1085 (2026-10-18, SAME-VALUE), NOT new debt -- existing debt newly SEEN: module-level constants (165 groups,
#: ~19 of 20 sampled product groups real) and whole function bodies of MIN_BODY_NODES+ (152, an 18-group sample all
#: real) joined the index; measured on the exact tree this commit lands (equal to HEAD: the commit adds no group).
#: -> 1083 (2026-10-18, S2d: the ATR-family levels call given one home, atr_family_levels; the dead
#: _save_backtest_to_history deleted; measured on the clean S2d tree).
#: -> 1082 (2026-10-18, S3: model_feed's 5m bar read from the timeframe registry, no longer a timedelta(minutes=5) copy;
#: measured on the clean S3 tree).
#: -> 1081 (2026-10-18, VULTURE-DEAD-BRANCH: btc_exit_walk_forward imports passes_objective / _net from their home;
#: measured on the clean tree).
#: -> 1078 (10-18, GIT-CLEAN 2: binance_vision_metrics / data_1m / sltp_multicoin / arm87_model paid on touch; clean tree).
#: -> 1069 (10-18, STOP-GAP: the six _feature_source copies, the lab's FIFO signal tuple and the recompute gates' comprehension
#: node tuple import their homes; the lab's market frame one home, data_loaders.ohlcv_market_frame; clean tree).
#: -> 1067 (10-19, locked by EXIT-WEIGHTED-TRAIL: HEAD ff362117c already read 1067 -- a fall left unlocked; this item's
#: tree reads the same; clean tree).
#: -> 1032 (10-19, 8b-ATR part 2 at the commit's own tree: the hypotheses' ATR and ema200's EMA read the homes, four
#: breakout masks one _breakout, three channel positions one _channel_position).
#: -> 1029 (10-19, 8b-EMA part 1 at the commit's own tree: the SMA-seeded EMA copies read ema_sma_seeded).
#: -> 1025 (10-19, GIT-CLEAN-1 article_ml / gb_pine at the commit's own tree: proba_scorer and perp5m_bars one home each,
#: the argv parse an argparse CLI).
#: -> 1022 (10-19, GIT-CLEAN-1 C: the confirm windows, the coin stacks and the JTO-book lookup one home each).
#: 1022 -> 1006 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 15 groups; and model_book_core's MINUTE reads the shared 1m delta, 1).
#: 1006 -> 986 (10-20 8f FIFO-BLIND at the commit's own tree: the rule-book cell, the OOS bars fetch, the WF batch
#: payload, the stress dispatch, the Titan matrix and the Kaabar regime gate one home each).
#: 986 -> 983 (10-22 SOL-5M-ZOO, measured on the tree after its three training commits: the objective lists imported from
#: one home each by the CLI and /config/public, rank_ic on the decoded signal, the unplaceable-label refusal).
#: 983 -> 982 (10-22 SOL-SHORTLIST-RECIPE: the training catalog's frozenset(UI_TRAINING_MODEL_TYPES) copy gone).
#: 982 -> 981 (10-22 SOL-SHORTLIST-RECIPE step 2: sol_v2_retrain.calls_column reads sol_v2_meta.open_times_ms).
#: 981 -> 975 (10-23 lock, measured at 9952f6df1).
#: 975 -> 973 (10-23 SWITCH-LUCK-CHECK at the commit's own tree: the third drawdown copy and the panel builder copy gone).
#: 973 -> 971 (10-24 lock, LIVE-SOL-BOTH's gate run, measured on the tree that commit carries).
#: 971 -> 967 (11-07 GATE-IDIOMS, measured by test_the_tree_ratchet_is_current on the tree the commit carries: concept_
#: definitions._base_name and constant_clones._target one home each, vrp_screen's retry and titan's schedule on theirs).
BASELINE_CLONE_GROUPS: Final = 967

Site = tuple[str, str]  # (repo path, function name)
#: One candidate expression in one function: (key, function, line, key of the nearest candidate around it or "").
Occurrence = tuple[str, str, int, str]


def _is_message_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return (isinstance(func, ast.Name) and func.id == "print") or (isinstance(func, ast.Attribute) and func.attr in _LOG_METHODS)


def _key(node: ast.AST, resolve: Mapping[str, str] | None = None) -> str:
    """The normalised shape of ``node``: variable names as placeholders, everything else as written. ``resolve`` (a
    module's global name -> its origin) keeps a global as WHERE IT COMES FROM, so two modules' own constants differ."""
    names: dict[str, str] = {}
    origins = resolve or {}

    def walk(n: ast.AST) -> str:
        if isinstance(n, ast.Name):
            return origins[n.id] if n.id in origins else names.setdefault(n.id, f"v{len(names)}")
        if isinstance(n, ast.Call):
            head = f"call:{origins.get(n.func.id, n.func.id)}" if isinstance(n.func, ast.Name) else walk(n.func)
            args = [walk(a) for a in n.args] + [f"{k.arg}={walk(k.value)}" for k in n.keywords]
            return f"{head}({','.join(args)})"
        if isinstance(n, ast.Constant):
            return repr(n.value)
        parts: list[str] = []
        for name, value in ast.iter_fields(n):
            if isinstance(value, list):
                items = cast("list[object]", value)
                parts.append(f"{name}=[{','.join(walk(v) if isinstance(v, ast.AST) else repr(v) for v in items)}]")
            elif isinstance(value, ast.AST) and not isinstance(value, ast.expr_context):
                parts.append(f"{name}={walk(value)}")
            elif value is not None and not isinstance(value, ast.AST):
                parts.append(f"{name}={value!r}")
        return f"{type(n).__name__}({';'.join(parts)})"

    return hashlib.sha1(walk(node).encode(), usedforsecurity=False).hexdigest()[:16]


def occurrences(source: str, path: str = "") -> list[Occurrence]:
    """Every candidate expression inside every function of ``source`` and, given its repo ``path``, every module-level
    constant (constant_clones -- its key resolves names against that module); [] when it does not parse."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    origins = name_origins(tree, module_of(path)) if path else {}
    found: list[Occurrence] = []
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = _body_occurrence(fn, lines, origins)
            found.extend([body] if body else [])
            found.extend(_in_function(fn, lines, body[0] if body else ""))
    return found + (constant_occurrences(source, path) if path else [])


def _body(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    return fn.body[1:] if ast.get_docstring(fn, clean=False) is not None else fn.body


def _body_occurrence(fn: ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str], origins: Mapping[str, str]) -> Occurrence | None:
    """The whole function as one candidate: its parameters (as placeholders, in order) and body, globals resolved."""
    body = _body(fn)
    size = sum(1 for n in ast.walk(ast.Module(body=body, type_ignores=[])) if not isinstance(n, ast.expr_context))
    # A judged exception anywhere in the function covers its body (a mirror is a mirror as a whole); an empty body is
    # simply below the floor.
    if size < MIN_BODY_NODES or any(CLONE_OK in line for line in lines[fn.lineno - 1 : fn.end_lineno or fn.lineno]):
        return None
    params = named_params(fn)
    shape = ast.Module(body=[ast.Expr(value=ast.Tuple(elts=[ast.Name(id=a.arg) for a in params])), *body], type_ignores=[])
    return (_key(shape, {k: v for k, v in origins.items() if k not in {a.arg for a in params}}), fn.name, fn.lineno, "")


def _in_function(fn: ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str], body_key: str = "") -> list[Occurrence]:
    sizes: dict[int, int] = {}
    for node in reversed(list(ast.walk(fn))):  # children before parents
        sizes[id(node)] = 1 + sum(sizes.get(id(child), 1) for child in ast.iter_child_nodes(node))
    found: list[Occurrence] = []

    def visit(node: ast.AST, parent: str) -> None:
        for name, child in _children(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or name in ("annotation", "returns"):
                continue  # a nested def is its own site; a type annotation is not a computation
            if _is_message_call(child) or isinstance(child, ast.JoinedStr):
                continue
            key = ""
            if isinstance(child, ast.expr) and not isinstance(child, _NOT_CANDIDATES) and sizes[id(child)] >= MIN_NODES:
                line = lines[child.lineno - 1] if 0 < child.lineno <= len(lines) else ""
                if CLONE_OK not in line:
                    key = _key(child)
                    found.append((key, fn.name, child.lineno, parent))
            visit(child, key or parent)

    for stmt in _body(fn):
        visit(ast.Module(body=[stmt], type_ignores=[]), body_key)
    return found


def _children(node: ast.AST) -> Iterable[tuple[str, ast.AST]]:
    for name, value in ast.iter_fields(node):
        if isinstance(value, ast.AST):
            yield name, value
        elif isinstance(value, list):
            yield from ((name, v) for v in cast("list[object]", value) if isinstance(v, ast.AST))


@dataclass
class CloneIndex:
    """The maximal clone groups of a tree: key -> the function sites that hold it."""

    groups: dict[str, frozenset[Site]] = field(default_factory=dict)
    lines: dict[tuple[str, Site], int] = field(default_factory=dict)
    sources: Mapping[str, str] = field(default_factory=dict[str, str])

    def sites_in(self, path: str) -> int:
        """The per-file debt: how many (group, function) memberships this file holds."""
        return sum(1 for sites in self.groups.values() for site in sites if site[0] == path)

    def report(self, path: str | None = None) -> list[str]:
        """One line per group (touching ``path`` when given): its sites, and the src/shared home when one exists."""
        out: list[str] = []
        for key, sites in sorted(self.groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            if path is not None and all(site[0] != path for site in sites):
                continue
            homes = [s for s in sites if s[0].startswith(SHARED_HOME)]
            where = ", ".join(f"{p}:{self.lines.get((key, (p, f)), 0)} {f}" for p, f in sorted(sites))
            hint = f"HOME {homes[0][0]}::{homes[0][1]} -- call it" if homes else "no home yet -- give it one in src/shared"
            out.append(f"x{len(sites)} {self._text(key, min(sites))}  {hint}  |  {where}")
        return out

    def _text(self, key: str, site: Site) -> str:
        """The expression's first source line at ``site`` -- what a reader recognises; the key when it cannot be read."""
        line = self.lines.get((key, site), 0)
        rows = self.sources.get(site[0], "").splitlines()
        return rows[line - 1].strip()[:120] if 0 < line <= len(rows) else key


def clone_index(per_file: Mapping[str, list[Occurrence]]) -> CloneIndex:
    """The maximal groups over every file's occurrences: a key in 2+ functions, unless it only ever sits inside one
    larger clone held by exactly the same functions."""
    sites: dict[str, set[Site]] = defaultdict(set)
    parents: dict[str, set[str]] = defaultdict(set)
    index = CloneIndex()
    for path, found in per_file.items():
        for key, fn, line, parent in found:
            sites[key].add((path, fn))
            parents[key].add(parent)
            index.lines.setdefault((key, (path, fn)), line)
    clones = {k: frozenset(v) for k, v in sites.items() if len(v) >= CLONE_MIN_SITES}
    for key, held in clones.items():
        only = parents[key]
        if len(only) == 1 and (parent := next(iter(only))) and clones.get(parent) == held:
            continue
        index.groups[key] = held
    return index


def cache_for(repo: Path) -> Path:
    """The judged repo's own cache -- never another checkout's: it keeps only the last tree it saw, so a throwaway test
    repo writing the main checkout's cache would leave every later run cold."""
    return repo / ".cache" / "expression_clones.json"


def _digest(source: str) -> str:
    return hashlib.sha1(source.encode(), usedforsecurity=False).hexdigest()


def _load_cache(path: Path) -> dict[str, list[Occurrence]]:
    try:
        data = json_object(json.loads(path.read_text(encoding="utf-8")))
    except OSError, ValueError:
        return {}
    if data is None or data.get("version") != _CACHE_VERSION:
        return {}
    files = json_object(data.get("files"))
    if files is None:
        return {}
    return {
        digest: [o for o in map(_occurrence, cast("list[object]", found)) if o is not None]
        for digest, found in files.items()
        if isinstance(found, list)
    }


def _occurrence(raw: object) -> Occurrence | None:
    """A cached row back as an Occurrence; None for a malformed one (dropped, never grouped under an empty key)."""
    row = cast("list[object]", raw) if isinstance(raw, list) else []
    if not (len(row) == _ROW_FIELDS and isinstance(row[0], str) and row[0] and isinstance(row[2], int)):
        return None
    return (row[0], str(row[1]), row[2], str(row[3]))


def _save_cache(path: Path, files: Mapping[str, list[Occurrence]]) -> None:
    """Atomic (ratchet_touch.write_json_atomic): a reader never sees half a cache."""
    write_json_atomic(path, {"version": _CACHE_VERSION, "files": files})


def occurrences_by_file(sources: Mapping[str, str], cache_path: Path | None) -> dict[str, list[Occurrence]]:
    """Every in-scope file's occurrences (path -> rows), re-reading only texts the cache has not seen. A constant's key
    depends on its module, so the cache key is the path AND the text."""
    cached = _load_cache(cache_path) if cache_path is not None else {}
    fresh: dict[str, list[Occurrence]] = {}
    per_file: dict[str, list[Occurrence]] = {}
    for path, text in sources.items():
        if not in_scope(path):
            continue
        digest = _digest(f"{path}\0{text}")
        found = cached.get(digest)
        if found is None:
            found = occurrences(text, path)
        fresh[digest] = found
        per_file[path] = found
    if cache_path is not None and fresh.keys() != cached.keys():
        _save_cache(cache_path, fresh)
    return per_file


def index_for(sources: Mapping[str, str], cache_path: Path | None) -> CloneIndex:
    """The clone index of ``sources`` (path -> text, in scope only)."""
    index = clone_index(occurrences_by_file(sources, cache_path))
    index.sources = sources
    return index


def ratchet_expression_clones(repo: Path, baseline: int = BASELINE_CLONE_GROUPS) -> int:
    """Count the maximal clone groups over HEAD's sources: 1 when the count moved off `baseline` either way (a rise is
    a new second home; a fall must be locked), 0 when it holds."""
    index = index_for(sources_at_ref(repo, "HEAD"), cache_for(repo))
    count = len(index.groups)
    print(f"expression clones: {count} maximal groups over {sum(len(s) for s in index.groups.values())} function sites (baseline {baseline})")
    if count > baseline:
        print("An expression gained a second home -- call the one that exists (--list <path> names it), never raise the baseline.")
        return 1
    if count < baseline:
        print(f"below baseline -- lower BASELINE_CLONE_GROUPS to {count} in src/lib/quality_gates/expression_clones.py to lock the gain")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI: --list [PATH] prints the groups over the working tree; otherwise the HEAD ratchet's exit code."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--tree", action="store_true", help="ratchet the group count over HEAD (verify.sh)")
    parser.add_argument("--list", nargs="?", const="", metavar="PATH", help="print the groups (touching PATH) over the working tree")
    parser.add_argument("--repo-root", type=Path, default=_REPO)
    args = parser.parse_args(argv)
    if args.list is not None:
        for line in index_for(sources_on_disk(args.repo_root), cache_for(args.repo_root)).report(args.list or None):
            print(line)
        return 0
    return ratchet_expression_clones(args.repo_root)


if __name__ == "__main__":
    sys.exit(main())
