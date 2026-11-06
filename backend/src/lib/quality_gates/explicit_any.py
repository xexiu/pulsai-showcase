"""Explicit-Any ratchet: every reference to ``typing.Any`` in the code that runs, counted from the AST.

IMPORTERS/CALLERS: scripts/check_touched_debt.py (the ``explicit-any`` touch row), scripts/verify.sh
(``--tree``, step 2f-any), tests/scripts/test_explicit_any.py. AFFECTED API: none (library + CLI; ``--tree``
exits 1 when the total rises, falls unrecorded, the canary dies or the scan reads too few files). DATA
SCHEMAS: none -- reads python source from git (``--tree``) or disk (``--list``).

WHY (owner, 2026-10-05): "I'm seeing ALL over the codebase Any -> dict[str, Any] or Any plain... should we
enforce this typing? Specifying / building the schema needed". Measured that day: 6,065 explicit Any in
1,248 files of apps/api/src, 68% of them ``dict[str, Any]`` -- a payload whose shape is known to its author
and written down nowhere. ruff ANN401 is ignored repo-wide ("needed for ML libraries"), which is true of an
untyped third-party object and false of that majority, and ANN401 only ever reads argument and return
annotations: an alias (``JSON = dict[str, Any]``), a ``cast(Any, ...)``, a variable annotation or a TypeVar
bound escapes it. So this counts EVERY reference -- annotation, alias, cast, bound, quoted annotation -- and
an import alone counts nothing. A RATCHET, not a demand: ``BASELINE_ANY_REFERENCES`` may only fall, and the
touch row makes a touched file pay its own down.

A SPLIT MOVES DEBT, IT DOES NOT ADD IT. A god-file split (the 400-line cap demands them) moves definitions
into a NEW file, which must carry 0, and re-addresses imports and docstrings in the files around it, which
must pay down. Replayed on the two real splits 1149b65d0 and 3aedcbd2a: neither moved one Any, and both
would still be refused -- a god file keeping its 1 Any, and two files whose only change was a docstring line
and a removed comment. :class:`MovedAny` fixes both, narrowly: a new file is charged only for Any no departed
definition carried in (a definition whose name, leading underscores dropped, LEFT another file of the commit;
a paydown is never credit, or every forced touch-to-lower payment could be reinvested in a new file and the
total would never fall), and a touched file owes no reduction when its change only removed code,
re-addressed imports or edited docstrings -- such a change cannot have added Any (:func:`only_removed_code`).

REUSE-AUDIT: considered src/lib/quality_gates/concept_definitions.py (its tree read -- ``ratchet_over_head``,
shared with recompute_in_loop -- and ``sources_on_disk`` are reused; its subject is duplicate definitions, not types), ruff ANN401 (argument and
return annotations only, and src/research is ruff force-excluded), basedpyright ``reportExplicitAny`` (a
whole-program checker, minutes per run and src-only in step 2i -- a per-file count must run in the
pre-commit's bare python3). Stdlib only, like every gate the git hook runs.
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, cast

from src.lib.quality_gates.concept_definitions import ratchet_over_head, sources_on_disk

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping

_API = Path(__file__).resolve().parents[3]
#: Over HEAD it may only fall, and every fall is recorded here (``--tree`` names the new number).
#: 6,661, 2026-10-05 (P1-14), measured by ``--tree`` on 2b8554fcc: 1,310 of 3,476 files. The same day it read
#: 6,638 on 1c57455e3 (src 6,216 incl. the lab's 2,805, apps/api/scripts 422; the annotation-only count over
#: src minus _archive was 6,058 -- the rest are aliases, casts, bounds and quoted annotations an annotation
#: scan cannot see), then +1 in 043c51d4e (a mixin's ``custom_params: dict[str, Any]``), +11 in eea594861 and
#: +11 in 21bbc6000 (a split whose new modules carry 18, 5 moved) -- each one the touch row now refuses.
#: 6,661 -> 6,586, 2026-10-06: the P1-9g F2-F6b and P1-8 landings wrote 75 shapes down (TypedDicts, dict[str, object]
#: + narrowing, typed Protocols), measured by ``--tree`` on HEAD after c821340e1.
#: 6,586 -> 6,581 on 2026-10-06 (P0-8e), measured over the working tree on d0ed6383f: the RL scan scripts'
#: ``print_row(verdict: Any)`` and rl_edge_scan_shared's ``Callable[..., Any, ...]`` now name ``OosTieredGateVerdict``;
#: hybrid_m4_lockforward_wf._run_hub_cell returns ``dict[str, object]``.
#: 6,581 -> 6,531 on 2026-10-06 (P1-9g F7), summed by ``--list`` over the working tree with F7 staged: the hub gate,
#: exit-grid, confluence and barrier walk-forward scripts write their dicts down as TypedDicts / ``dict[str, object]``.
#: 6,531 -> 6,522 on 2026-10-06 (P1-9g F8), summed by ``--list`` with F8 staged: pilot_trend_scan_gate / trend_scan_exit_wf typed.
#: 6,522 -> 6,508 on 2026-10-06 (P1-8 ccxt adoption), summed by ``--list`` with it staged: Protocols / TypedDicts in the adopters.
#: 6,508 -> 6,437 on 2026-10-06 (P1-9g F9-F11 + final), summed by ``--list`` with it staged.
#: 6,437 -> 6,391 on 2026-10-06 (P1-8: dpic split, quarter-hour / lowvol adoption, funding pager), summed by ``--list``.
#: 6,391 -> 6,365 on 2026-10-06, measured by ``--tree`` on eefe308b9 (P1-8 8b: registry split, bar-series helpers).
#: 6,365 -> 6,332 on 2026-10-07 (P1-8: eight research files split), summed by ``--list`` with it staged.
#: 6,332 -> 6,318 on 2026-10-07 (P1-8 closing slice), summed by ``--list`` with it staged.
#: 6,318 -> 6,294 on 2026-10-07, measured by ``--tree`` on f05c89dc3 (P1-0b: the cert grid files typed, ExitHubFields).
#: 6,294 -> 6,292 on 2026-10-07, measured by ``--tree`` on 12bea46e2 (run_at_door_cost typed by a bounded parameter).
#: 6,292 -> 6,281 on 2026-10-08, measured by ``--tree`` on 096d739a2 (P3-0c: the regression trainers' shared loop typed).
#: 6,281 -> 6,276 on 2026-10-08, measured by ``--tree`` on fb2dd7ec7 (stacking / Optuna-base trainers typed: 6,277)
#: plus check_clone_baseline's reply stream typed IO[str] in the same commit (-1).
#: 6,276 -> 6,275 on 2026-10-08 (check_clone_baseline's JSON-RPC send takes dict[str, object]).
#: 6,275 -> 6,267 on 2026-10-08, measured by ``--tree`` on the P1-0 commit (feat(cert) risk-sized book: the door files' cells typed, CellStats).
#: 6,267 -> 6,257 on 2026-10-08, measured by ``--tree`` on the P1-1 commit (refactor(money): money_tier carries no Any,
#: the graders take Mapping[str, object], money_ledger's duplicate window parser deleted).
#: 6,257 -> 6,250 on 2026-10-09, measured by ``--tree`` with P1-2 + P1-3a committed (the money decision and gate typed,
#: the XS harness module's lazy __getattr__ -> object, four hypothesis books' bare dict/list annotations made precise).
#: 6,250 -> 6,238 on 2026-10-09, measured by ``--tree`` (P1-3: 8 from d6d9dc720's six XS shims, never locked, plus 4 from
#: the XS panel fix -- xs_ml_zoo's hypothesis payload and xs_zscore_target's folds and payload typed).
#: 6,238 -> 6,233 on 2026-10-09, measured by ``--tree`` after 618bfe551 (the ADR-025 ruin fix deleted the lane-sum
#: fallback) and P3-0d's envelope slice (the connection lifecycle's permissions typed dict[str, bool] twice).
#: CORRECTION 2026-10-09: ``--tree`` reads HEAD, so the 6,238 and 6,233 locks above were each measured BEFORE the
#: commit that carried them; the XS panel fix's 4 and the envelope slice's 2 were not in those counts.
#: 6,233 -> 6,228 is the WORKING-TREE total (``--list``) of the commit carrying this line: HEAD at 813b95624 counts
#: 6,231, and this slice removes 3 (the audit core's fallback-details helper typed Mapping[str, object] ->
#: dict[str, object], the error handler's HTTP detail typed object).
#: 6,228 -> 6,227 on 2026-10-09 (working-tree total): purge_version returns PurgeResult, not Any.
#: 6,227 -> 6,226 (working-tree total): the edge-book executor's unused `user` parameter typed object.
#: 6,226 -> 6,200 (working-tree total, 2026-10-09): P3-0d batches A + B deleted dead code and typed what they touched.
#: 6,200 -> 6,187 (working-tree total, 2026-10-09): P2-1 paid down each file it touched (ModelSpec, ExitProfile,
#: pd.Series | ndarray and Mapping[str, object] in place of Any across the engine, the recorder and the money ledger).
#: 6,187 -> 6,186 (working-tree total): the search context's money block typed dict[str, object].
#: 6,186 -> 6,178 (working-tree total): P2-1's disclosure slice typed the served book's records, the hypothesis
#: fold's rows and two lab money scripts' records object / their real shape.
#: 6,178 -> 6,177 (working-tree total): the select-confirm door's apply result typed dict[str, object].
#: 6,177 -> 6,173 (working-tree total): the 0%-fee disclosure slice typed the ledger's record readers, the levered
#: loader, two payload readers and the persist step's model-cert loader object / their real shape.
#: 6,133 -> 6,128 (working-tree total, 2026-10-11): P2-1n/P2-1p paid down the ship path -- confirm_window_ruin
#: deleted, the ship entry point returns CandidateUploadResult, and three best/cert readers take Mapping[str, object].
#: 6,128 -> 6,121 (2026-10-12): measured by the full verify on c82a1b035, the day's MEXC engine / exchange commits.
#: -> 6,085 10-16 (a paydown, locked in ONE-DEF-LAB).
# 6,110 -> 6,091 (10-15 paydown) -> 6,086 (10-16 GATE-RED lock) -> 6,001 (10-17 VERIFY-GREEN lock)
# -> 5,998 (10-18 lock, measured by --tree at 781ecc088: backtest_response_chart typed in PANDAS-OUT 1/2)
# -> 5,995 (10-18, S2a: the engine's timestamp helpers typed object / Sequence[object]; measured on the clean tree).
# -> 5,986 (10-18, S2d: /run's caller typed User | None, the worker's config readers Mapping[str, object], the dead
# history helper gone; measured on the clean S2d tree).
# -> 5,983 (10-18, VULTURE-DEAD-BRANCH: btc_exit_wf_remaining imports the _Json alias from its home; clean tree).
# -> 5,982 (10-18, DB-POOL-TRACE: database.py's connect_args typed dict[str, object]; clean tree).
# -> 5,955 (10-18, STOP-GAP: the walk-forward runner's options, the lab callers it touched and the sweep batch typed; clean tree).
# -> 5,946 (10-18, 8g IMPORTANCE-ALWAYS: the training files it touched; clean tree).
# -> 5,945 (10-19, locked by EXIT-WEIGHTED-TRAIL: HEAD ff362117c already read 5,945 -- a 10-18 live-engine commit's fall
# left unlocked; this item's tree reads the same; clean tree).
# -> 5,924 (10-19, 8b-ATR part 2 at the commit's own tree: ts_rule_zoo's NestedWalkForward / typed per-year rows, the
# ts_rule_zoo shim, adaptive_trend_momentum's float metrics).
# -> 5,923 (10-19, 8b-EMA part 1: uncertainty_zones' ccxt market read as typed JSON).
# -> 5,921 (10-19, GIT-CLEAN-1: article_ml's search grid and PySR settings typed, gb_pine's graded params).
# -> 5,920 (10-19, GIT-CLEAN-1 C: meta_wt_screen's models() returns ProbaClassifier).
#: 5920 -> 5882 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope with its 37 Any, and check_clone_baseline's last one
#: was typed; measured at the commit's own tree).
#: 5882 -> 5881 (10-20 HEAD-RED: carry's transfer takes a ccxt.Exchange; measured at the commit's own tree).
#: 5881 -> 5839 (10-20 8f FIFO-BLIND: the scout batches' payloads TypedDicts, the joblib seam and the backtest
#: prediction wrapper typed; measured at the commit's own tree).
#: 5839 -> 5838 (10-21 SOL-5M-V2-FEATURES: train_model_cli.run_training forwards the result as dict[str, object];
#: measured at the commit's own tree).
#: 5838 -> 5812 (10-22 ZOO-STACK: SignalArray over np.integer, the panel screen's rows a Sequence of Mapping; 24 of the
#: 26 an earlier fall left unlocked; measured at the commit's own tree).
#: 5812 -> 5809 (10-22 SOL-SHORTLIST-RECIPE: the training catalog's shortlist row a dict[str, object], its Any import gone,
#: and 1 an earlier fall left unlocked; measured at this tree).
#: 5809 -> 5808 (10-22 SOL-SHORTLIST-RECIPE step 2: measured at this tree, 1 fewer than step 1's tree).
#: 5808 -> 5758 (10-23 lock, measured at 9952f6df1).
#: 5758 -> 5757 (10-23 SWITCH-LUCK-CHECK: forward_paper_certification's gate block read as dict[str, object];
#: measured at the commit's own tree).
#: 5757 -> 5754 (10-24 lock, LIVE-SOL-BOTH's gate run, measured on the tree that commit carries).
#: 5753 -> 5749 (10-29 NEWS-ARMS calendar fix: economic_calendar's dashboard rows a dict[str, str | float], its Any
#: import gone; measured at the commit's own tree).
BASELINE_ANY_REFERENCES = 5732
#: Liveness: a scope mistake that reads (almost) nothing must not pass as a clean tree.
MIN_TREE_FILES = 1000
_TYPING_MODULES = frozenset({"typing", "typing_extensions"})
_NAME = "Any"
#: Module-level code no definition owns (an ``if __name__`` block, a bare call).
UNNAMED = ""
_SHOWN_ON_FAILURE = 10
#: Every form the counter must see, one Any each, and the forms it must NOT count. 7 references.
CANARY_SOURCE = (
    "import typing\n"
    "from typing import Any, Literal, TypeAlias, TypeVar, cast\n"
    "from typing import Any as Anything\n\n"
    "JSON = dict[str, Any]\n"
    "Row: TypeAlias = 'dict[str, Any]'\n"
    "T = TypeVar('T', bound='Any')\n\n\n"
    "def f(x: 'list[Any]', mode: Literal['Any'] = 'Any') -> typing.Any:\n"
    "    return cast(Any, x)\n\n\n"
    "def g(y: Anything) -> None:\n"
    "    print('Any')\n"
)
CANARY_COUNT = 7


def _tail(node: ast.expr) -> str:
    """``Literal`` for both ``Literal`` and ``typing.Literal``."""
    if isinstance(node, ast.Name):
        return node.id
    return node.attr if isinstance(node, ast.Attribute) else ""


def _aliases(tree: ast.AST) -> frozenset[str]:
    """``Any`` plus every ``from typing import Any as X`` -- a renamed import must not dodge the count."""
    names = {_NAME}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in _TYPING_MODULES:
            names.update(alias.asname for alias in node.names if alias.name == _NAME and alias.asname)
    return frozenset(names)


def _type_children(expr: ast.expr) -> list[ast.expr]:
    """The sub-expressions still in type position: none inside ``Literal[...]``, only the type of ``Annotated[...]``."""
    head = _tail(expr.value) if isinstance(expr, ast.Subscript) else ""
    if head == "Literal":
        return []
    if isinstance(expr, ast.Subscript) and head == "Annotated":
        return [expr.slice.elts[0] if isinstance(expr.slice, ast.Tuple) and expr.slice.elts else expr.slice]
    return [child for child in ast.iter_child_nodes(expr) if isinstance(child, ast.expr)]


def _quoted(expr: ast.expr) -> Iterator[tuple[str, int]]:
    """(text, line) of each string inside a type expression, minus ``Literal[...]`` values and ``Annotated`` metadata."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        yield expr.value, expr.lineno
    for child in _type_children(expr):
        yield from _quoted(child)


def _call_type_args(call: ast.Call) -> Iterator[ast.expr]:
    """The arguments of ``cast`` / ``TypeVar`` / ``NewType`` that are TYPE expressions, not values."""
    head = _tail(call.func)
    if head == "cast" and call.args:
        yield call.args[0]
    elif head == "TypeVar":
        yield from call.args[1:]
        yield from (kw.value for kw in call.keywords if kw.arg == "bound")
    elif head == "NewType" and len(call.args) > 1:
        yield call.args[1]


def _type_params(node: ast.AST) -> Iterator[ast.expr]:
    """A PEP 695 header's type expressions -- each parameter's bound / constraints and default: the syntax form of the
    TypeVar(..., bound=...) call above, evaluated lazily, never at run time."""
    if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.TypeAlias):
        return
    for param in node.type_params:
        if isinstance(param, ast.TypeVar) and param.bound is not None:
            yield param.bound
        if isinstance(param, ast.TypeVar | ast.ParamSpec | ast.TypeVarTuple) and param.default_value is not None:
            yield param.default_value


def type_positions(node: ast.AST) -> Iterator[ast.expr]:
    """The expressions ``node`` holds whose string constants are type expressions a checker would parse."""
    yield from _type_params(node)
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        arguments = node.args
        for arg in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs, arguments.vararg, arguments.kwarg):
            if arg is not None and arg.annotation is not None:
                yield arg.annotation
        if node.returns is not None:
            yield node.returns
    elif isinstance(node, ast.AnnAssign):
        yield node.annotation
        if node.value is not None and _tail(node.annotation) == "TypeAlias":
            yield node.value
    elif isinstance(node, ast.TypeAlias):
        yield node.value
    elif isinstance(node, ast.Call):
        yield from _call_type_args(node)


def _in_quotes(expr: ast.expr, aliases: frozenset[str]) -> list[int]:
    """References inside the quoted parts of one type expression, quotes within quotes included."""
    lines: list[int] = []
    for text, line in _quoted(expr):
        try:
            parsed = ast.parse(text.strip(), mode="eval")
        except SyntaxError:
            continue
        inner = len(_references(parsed, aliases)) + len(_in_quotes(parsed.body, aliases))
        lines.extend([line] * inner)
    return lines


def _references(tree: ast.AST, aliases: frozenset[str]) -> list[int]:
    """Line of every Any reference under ``tree``: names, ``typing.Any`` attributes, and quoted annotations.
    One walk -- the tree ratchet reads ~3,500 files on every verify."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Name) and node.id in aliases) or (isinstance(node, ast.Attribute) and node.attr == _NAME):
            lines.append(node.lineno)
        else:
            for expr in type_positions(node):
                lines.extend(_in_quotes(expr, aliases))
    return lines


def _parse(source: str) -> ast.Module | None:
    """The module AST, or None: an unparseable file is refused by ruff and mypy long before this gate."""
    try:
        return ast.parse(source)
    except SyntaxError, ValueError:
        return None


def any_lines(source: str) -> list[int]:
    """Line of every Any reference in one python source text (an unparseable text has none).
    A text without the letters ``Any`` cannot reference it and is not parsed (~60% of the tree)."""
    tree = _parse(source) if _NAME in source else None
    return [] if tree is None else sorted(_references(tree, _aliases(tree)))


def any_references(source: str) -> int:
    """The per-file count both doors use: the touch row and the tree total."""
    return len(any_lines(source))


def _assigned_name(statement: ast.Assign | ast.AnnAssign | ast.TypeAlias) -> str:
    targets: list[ast.expr]
    if isinstance(statement, ast.Assign):
        targets = statement.targets
    else:
        targets = [statement.name if isinstance(statement, ast.TypeAlias) else statement.target]
    return next((target.id for target in targets if isinstance(target, ast.Name)), UNNAMED)


def _block(statement: ast.stmt) -> list[ast.stmt]:
    """The statements a module-level ``if`` / ``try`` / ``with`` wraps (``if TYPE_CHECKING:``, guarded imports)."""
    if isinstance(statement, ast.If):
        return [*statement.body, *statement.orelse]
    if isinstance(statement, ast.With):
        return list(statement.body)
    if isinstance(statement, ast.Try):
        handled = [child for handler in statement.handlers for child in handler.body]
        return [*statement.body, *statement.orelse, *statement.finalbody, *handled]
    return []


def _method_key(owner: str, name: str) -> str:
    """A method keyed by its own name -- a split moves methods into a mixin or out as functions -- except a
    dunder, which only means something on its class (every class has an ``__init__``)."""
    return f"{owner}.{name}" if name.startswith("__") and name.endswith("__") else name


def _owned(statement: ast.stmt, aliases: frozenset[str]) -> list[tuple[str, int]]:
    """(definition name, its Any count) for one top-level statement; what no name owns goes to UNNAMED.
    A class gives each method under its own key and keeps the rest (bases, attributes) under its name."""
    total = len(_references(statement, aliases))
    if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
        return [(statement.name, total)]
    if isinstance(statement, ast.Assign | ast.AnnAssign | ast.TypeAlias):
        return [(_assigned_name(statement), total)]
    if isinstance(statement, ast.ClassDef):
        methods = [child for child in statement.body if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)]
        inner = [(_method_key(statement.name, method.name), len(_references(method, aliases))) for method in methods]
        owner = statement.name
    else:
        inner = [pair for child in _block(statement) for pair in _owned(child, aliases)]
        owner = UNNAMED
    return [*inner, (owner, total - sum(count for _name, count in inner))]


def any_by_definition(source: str) -> Counter[str]:
    """Any references per definition -- top-level functions, assignments, classes and their methods -- keyed
    by name with leading underscores dropped; a zero-count definition is a key too.

    The keys are what a split preserves: a function moved to a new module keeps its name, a method moved to a
    mixin keeps its name, and a private helper made importable (``_clean`` -> ``clean``) is the same
    definition. Sums to :func:`any_references`.
    """
    tree = _parse(source)
    found: Counter[str] = Counter()
    if tree is None:
        return found
    aliases = _aliases(tree)
    for statement in tree.body:
        for name, count in _owned(statement, aliases):
            found[name.lstrip("_")] += count
    return found


def _code(source: str) -> Counter[str] | None:
    """Every top-level statement, minus imports and docstrings at any depth -- what a move cannot change."""
    tree = _parse(source)
    if tree is None:
        return None
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            body = getattr(node, field, None)
            if isinstance(body, list):  # a list body / orelse / finalbody is statements on every node that has one
                statements = cast("list[ast.stmt]", body)
                setattr(node, field, [s for s in statements if not isinstance(s, ast.Import | ast.ImportFrom)])
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and ast.get_docstring(node, clean=False) is not None:
            node.body = node.body[1:]
    return Counter(ast.dump(statement) for statement in tree.body)


def only_removed_code(before: str, now: str) -> bool:
    """True when every statement ``now`` holds was already in ``before``: the change removed code (a split
    moving it out), re-addressed imports or edited comments and docstrings -- and so cannot have added Any."""
    old, new = _code(before), _code(now)
    return old is not None and new is not None and not (new - old)


class MovedAny:
    """What a commit's changed files gave up: the Any carried by definitions that LEFT their file.

    Built from every changed file's ``(text before, text after or None when deleted)``. A definition whose name
    is gone from its file's after-text departed and takes its Any with it; one still there (retyped, edited)
    departed nothing, so a paydown is never credit. A new file may carry departed Any, each unit claimed once.
    """

    def __init__(self, pairs: Iterable[tuple[str, str | None]]) -> None:
        self._credit: Counter[str] = Counter()
        for before, after in pairs:
            old = any_by_definition(before)
            kept: set[str] = set() if after is None else set(any_by_definition(after))
            self._credit.update({name: count for name, count in old.items() if name not in kept and name != UNNAMED})

    def added(self, source: str) -> int:
        """The Any references a NEW file adds beyond what it carried in from a departed definition."""
        owed = 0
        for name, count in any_by_definition(source).items():
            carried = 0 if name == UNNAMED else min(count, self._credit[name])
            self._credit[name] -= carried
            owed += count - carried
        return owed

    @staticmethod
    def owes_on_touch(before: str, now: str) -> bool:
        """Whether a touched file owes its reduction: not when the change only removed code (:func:`only_removed_code`)."""
        return not only_removed_code(before, now)


def any_canary_is_alive() -> bool:
    """Does the counter still find every canary form? False means the instrument is broken, never a clean tree."""
    return any_references(CANARY_SOURCE) == CANARY_COUNT


def any_tree_verdict(per_file: dict[str, int], baseline: int) -> tuple[int, list[str]]:
    """(exit code, report): fails on a rise and on an unrecorded fall -- both mean the baseline is wrong."""
    total = sum(per_file.values())
    carriers = sum(1 for count in per_file.values() if count)
    lines = [f"explicit Any: {total} references in {carriers} of {len(per_file)} files (baseline {baseline})"]
    if total > baseline:
        lines.append("Any references ROSE -- write the shape down: a TypedDict / dataclass / pydantic model / Protocol.")
        worst = sorted(per_file.items(), key=lambda item: -item[1])[:_SHOWN_ON_FAILURE]
        lines += [f"  {count:5d}  {path}" for path, count in worst]
        return 1, lines
    if total < baseline:
        lines.append(f"below baseline -- lower BASELINE_ANY_REFERENCES to {total} in src/lib/quality_gates/explicit_any.py to lock the gain")
        return 1, lines
    return 0, lines


def ratchet_any_tree(repo: Path, baseline: int = BASELINE_ANY_REFERENCES) -> int:
    """verify's explicit-Any gate over HEAD: 1 on a dead canary, a rise or an unrecorded fall, else 0."""
    if not any_canary_is_alive():
        print(f"explicit Any: CANARY DEAD -- the counter no longer finds the {CANARY_COUNT} canary forms. This is NOT a clean tree.")
        return 1
    return ratchet_over_head(
        repo,
        "explicit Any",
        MIN_TREE_FILES,
        lambda sources: any_tree_verdict({path: any_references(text) for path, text in sources.items()}, baseline),
    )


def ranked_counts(counts: Mapping[str, int]) -> list[tuple[str, int]]:
    """Per-file counts highest first, ties by path -- the order every gate's ``--list`` prints."""
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def main(argv: list[str] | None = None) -> int:
    """`--list` prints per-file counts over the working tree; otherwise the tree ratchet runs."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--tree", action="store_true", help="ratchet the total over HEAD (verify.sh)")
    parser.add_argument("--list", action="store_true", help="per-file counts over the working tree, highest first")
    parser.add_argument("--repo-root", type=Path, default=_API.parents[1])
    args = parser.parse_args(argv)
    if args.list:
        counts = {path: any_references(text) for path, text in sources_on_disk(args.repo_root).items()}
        for path, count in ranked_counts(counts):
            if count:
                print(f"{count:5d}  {path}")
        return 0
    return ratchet_any_tree(args.repo_root)


if __name__ == "__main__":
    sys.exit(main())
