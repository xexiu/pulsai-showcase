"""Constant clones: a module-level value that already lives in another module, under any name, private or public.

IMPORTERS/CALLERS: src/lib/quality_gates/expression_clones.py (``occurrences`` adds these to the one clone index, so the
verify ratchet, check_touched_debt's expression-clone row and .claude/hooks/one_definition_guard.py read them with no
door of their own); tests/scripts/test_constant_clones.py. AFFECTED API: none (library). DATA SCHEMAS: none -- the
occurrences ride expression_clones' cache rows unchanged.

SAME-VALUE (owner, 2026-10-18: "enforce hook and memory ... robust, proactive, always, bullet proof"). The thin-stop
kernel gained `_STOP_REASONS = frozenset({REASON_INITIAL_STOP, REASON_MOVED_STOP})` while cert/risk_sized_trades.py
already held the identical set, and no door saw it: concept_definitions judges PUBLIC names, enum members and
registered shapes; expression_clones judges expressions of 25+ nodes INSIDE functions (this one is ~8, at module level);
jscpd copied line blocks. A constant is a definition by nature, so its value is compared, not its name.

THE KEY. Every name in the value is resolved to where it comes from -- an import to ``module.NAME`` (relative imports
resolved), a name the module defines to ``this_module.NAME``, a builtin as itself -- so the same text over each module's
OWN names is two values (measured: ``RESULTS = SCRATCH / "results"`` x21, every SCRATCH that file's directory), and the
same value spelt in two modules is one. A value made of literals only matches under the same constant name (leading
underscores ignored): ``(0.15, 0.20)`` as TARGET_VOLS twice is a copy, the same numbers as SIZE_CLIP may be chance.

NOT CANDIDATES, measured as the noise on the tree the day this was written (src + scripts, tests out): a lone literal or
a negated one (``-1``), a bare name or attribute (an alias), fresh state built per module (``{}``, ``set()``,
``threading.Lock()``, ``APIRouter()`` -- a call with no arguments), anything read off ``__file__`` / ``__name__`` (each
file's own location or logger), a dunder target (``__all__``), and a value with fewer than two leaves. A judged
exception carries ``CLONE-OK: <why>`` on its line, the clone gates' one marker (defined here, imported by
expression_clones).

REUSE-AUDIT: expression_clones (Occurrence, the index, the cache, the ratchet, --list) is reused by feeding it, not
copied; its ``_key`` is not reused because it turns names into placeholders, which is exactly what makes two modules'
own names look equal here; concept_definitions (names) and jscpd (lines) answer other questions and stay.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from src.lib.quality_gates.expression_clones import Occurrence

#: The clone gates' judged-exception marker, on the line of the expression or constant it excuses.
CLONE_OK: Final = "CLONE-OK:"
#: Names whose value is the module's own location or identity, never shared.
_SELF_LOCATED: Final = frozenset({"__file__", "__name__"})
#: Type-parameter declarations: each module declares its own by convention (PEP 695 makes them local outright). The
#: first rule did not hold because it counted them -- measured: `_CellT = TypeVar("_CellT", bound=...)` x3 was the one
#: miss in 20 sampled product groups (the other 19 real copies: _SIGNAL_BY_SLOT, two news regexes, SortDir x4 ...).
_TYPE_PARAMETERS: Final = frozenset({"TypeVar", "ParamSpec", "TypeVarTuple"})
#: A value with fewer leaves (constants + names) than this is one literal or one alias, not a concept.
MIN_LEAVES: Final = 2
_BUILTINS: Final = frozenset(dir(builtins))
_API_PREFIX: Final = "apps/api/"


def module_of(path: str) -> str:
    """``apps/api/src/cert/walk.py`` -> ``src.cert.walk`` (a package's ``__init__`` is the package)."""
    dotted = path.removeprefix(_API_PREFIX).removesuffix(".py").replace("/", ".")
    return dotted.removesuffix(".__init__")


def _absolute(module: str, level: int, target: str | None) -> str:
    """A relative ``from`` import's absolute module: ``level`` steps up from ``module``'s package."""
    if level == 0:
        return target or ""
    parts = module.split(".")[:-level]
    return ".".join([*parts, target] if target else parts)


def name_origins(tree: ast.Module, module: str) -> dict[str, str]:
    """Each module-level name -> where it comes from: an import's source, else this module's own definition."""
    origins: dict[str, str] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            origins.update({(a.asname or a.name).split(".")[0]: a.name if a.asname else a.name.split(".")[0] for a in stmt.names})
        elif isinstance(stmt, ast.ImportFrom):
            base = _absolute(module, stmt.level, stmt.module)
            origins.update({a.asname or a.name: f"{base}.{a.name}" for a in stmt.names})
        else:
            for node in ast.walk(stmt) if isinstance(stmt, (ast.Assign, ast.AnnAssign)) else ():
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    origins.setdefault(node.id, f"{module}.{node.id}")
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                origins.setdefault(stmt.name, f"{module}.{stmt.name}")
    return origins


def assigned_name(stmt: ast.AST) -> tuple[str, ast.expr] | None:
    """A one-name assignment's (name, value) -- ``x = v`` or ``x: T = v``; None for any other node. Also read by
    control_flow_idioms, which follows a sleep's amount back through a function's assignments."""
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
        return stmt.targets[0].id, stmt.value
    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
        return stmt.target.id, stmt.value
    return None


def _is_candidate(name: str, value: ast.expr) -> bool:
    if name.startswith("__") or isinstance(value, (ast.Constant, ast.Name, ast.Attribute)):
        return False
    if isinstance(value, ast.UnaryOp) and isinstance(value.operand, ast.Constant):
        return False
    if isinstance(value, ast.Call) and not value.args and not value.keywords:
        return False  # fresh state built per module: a lock, a router, an empty set
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id in _TYPE_PARAMETERS:
        return False
    # An empty {} / [] / () has 0 leaves, so MIN_LEAVES below excludes it; the old collection branch here did not hold
    # because `not <generator object>` is always False -- it was dead code, removed rather than tuned.
    names = {n.id for n in ast.walk(value) if isinstance(n, ast.Name)}
    if names & _SELF_LOCATED:
        return False
    return sum(1 for n in ast.walk(value) if isinstance(n, (ast.Constant, ast.Name))) >= MIN_LEAVES


def _key(name: str, value: ast.expr, origins: dict[str, str]) -> str:
    """The value's identity: names resolved to their origin; a literal-only value also carries its constant's name."""
    resolved = ast.parse(ast.unparse(value), mode="eval").body
    has_names = False
    for node in ast.walk(resolved):
        if isinstance(node, ast.Name) and node.id not in _BUILTINS:
            has_names = True
            node.id = origins.get(node.id, node.id)
    text = ast.dump(resolved, annotate_fields=False)
    if not has_names:
        text = f"{name.lstrip('_')}={text}"
    return hashlib.sha1(text.encode(), usedforsecurity=False).hexdigest()[:16]


def constant_occurrences(source: str, path: str) -> list[Occurrence]:
    """Every candidate module-level constant of ``source`` (at repo ``path``) as (key, name, line, "")."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines()
    origins = name_origins(tree, module_of(path))
    found: list[Occurrence] = []
    for stmt in tree.body:
        target = assigned_name(stmt)
        if target is None or not _is_candidate(*target):
            continue
        if CLONE_OK in "\n".join(lines[stmt.lineno - 1 : (stmt.end_lineno or stmt.lineno)]):
            continue
        found.append((_key(target[0], target[1], origins), target[0], stmt.lineno, ""))
    return found


__all__ = ["CLONE_OK", "MIN_LEAVES", "assigned_name", "constant_occurrences", "module_of", "name_origins"]
