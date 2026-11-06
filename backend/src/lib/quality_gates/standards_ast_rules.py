"""The per-file AST shapes the standards gate counts: each rule reads one module and returns the line of every finding.

IMPORTERS/CALLERS: src/lib/quality_gates/standards_rules.py (each rule is one ``Rule`` entry there, its tree total and
touch row; ``--list`` prints these lines). AFFECTED API: none -- moved out of standards_rules unchanged (2026-10-19), when
returning lines instead of counts took that module past the 400-line cap. DATA SCHEMAS: none.

Split by responsibility: standards_rules owns the registry, the ratchet and the CLI; this module owns the shapes.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from typing import Final

from src.lib.quality_gates.verify_gate_helpers import classes_in, comment_lines_matching, counted_lines, line_span, silent_return_functions

#: CODING_STANDARDS 9.1: a function longer than this many effective lines does more than one thing.
MAX_FUNCTION_LINES: Final = 100
#: ISP (CODING_STANDARDS 1): an interface with more methods than this asks implementers for what they do not use.
MAX_PROTOCOL_METHODS: Final = 7
#: A directive starts its comment segment (mypy and pyright honour nothing else); prose quoting one in backticks is not one.
_SUPPRESSION: Final = re.compile(r"(?:^|\s)#\s*(?:type|pyright)\s*:\s*ignore")
_IO_TOKENS: Final = ("fetch", "load", "query", "execute", "request", "redis", "session", "http", "read_", "open", "download")


def _functions(tree: ast.AST) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    return (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))


def _name(node: ast.expr) -> str:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr
    return target.id if isinstance(target, ast.Name) else ""


def nested_ternaries(tree: ast.Module, _source: str) -> list[int]:
    """CODING_STANDARDS 3.1: a conditional expression inside another's branch is a ternary chain."""
    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.IfExp) and (isinstance(n.body, ast.IfExp) or isinstance(n.orelse, ast.IfExp))]


def type_suppressions(_tree: ast.Module, source: str) -> list[int]:
    """CODING_STANDARDS 5 / 11: the mypy and pyright ignore comments (``_SUPPRESSION``) -- a type rule switched off."""
    return comment_lines_matching(source, _SUPPRESSION)


def numba_loop_reuse(tree: ast.Module, _source: str) -> list[int]:
    """CODING_STANDARDS 8.3: a for-target name bound twice in one @njit / @jit function -- the SSA hazard (the line of
    each rebinding loop)."""
    lines: list[int] = []
    for fn in _functions(tree):
        if not any(_name(d) in ("njit", "jit") for d in fn.decorator_list):
            continue
        seen: set[str] = set()
        for loop in sorted((n for n in ast.walk(fn) if isinstance(n, ast.For) and isinstance(n.target, ast.Name)), key=lambda n: n.lineno):
            name = loop.target.id if isinstance(loop.target, ast.Name) else ""
            if name in seen:
                lines.append(loop.lineno)
            seen.add(name)
    return lines


def long_functions(tree: ast.Module, source: str) -> list[int]:
    """CODING_STANDARDS 9.1: functions over MAX_FUNCTION_LINES effective lines (non-blank; comments count; the
    function's own docstring does not)."""
    lines = source.splitlines()
    long_ones: list[int] = []
    for fn in _functions(tree):
        skip: set[int] = set()
        if ast.get_docstring(fn, clean=False) is not None:
            skip.update(line_span(fn.body[0]))
        span = range(fn.lineno, (fn.end_lineno or fn.lineno) + 1)
        if counted_lines(lines, span, skip) > MAX_FUNCTION_LINES:
            long_ones.append(fn.lineno)
    return long_ones


def global_statements(tree: ast.Module, _source: str) -> list[int]:
    """CODING_STANDARDS 1 (DIP) / 3: module-global mutable state written from a function."""
    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Global)]


def numeric_http_status(tree: ast.Module, _source: str) -> list[int]:
    """CODING_STANDARDS 12: an HTTP status as a bare int (``status_code=404``, ``HTTPException(404)``) -- use the named
    constant (``fastapi.status``)."""
    lines: list[int] = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        lines += [n.lineno for k in n.keywords if k.arg == "status_code" and isinstance(k.value, ast.Constant) and isinstance(k.value.value, int)]
        first = n.args[0] if n.args else None
        if _name(n) == "HTTPException" and isinstance(first, ast.Constant) and isinstance(first.value, int):
            lines.append(n.lineno)
    return lines


def print_calls(tree: ast.Module, _source: str) -> list[int]:
    """CODING_STANDARDS 4 / 9: ``print`` in product code -- the logger is the channel the log watch reads. A module
    with a ``__main__`` entry point is a CLI: stdout is its interface (the quality-gate tools)."""
    if _is_cli(tree):
        return []
    return [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "print"]


def _is_cli(tree: ast.Module) -> bool:
    return any(isinstance(n, ast.If) and "__main__" in ast.unparse(n.test) for n in tree.body)


def fat_protocols(tree: ast.Module, _source: str) -> list[int]:
    """CODING_STANDARDS 1 (ISP): a Protocol / ABC with more than MAX_PROTOCOL_METHODS methods."""
    return [
        cls.lineno
        for cls in classes_in(tree)
        if any(_name(b) in ("Protocol", "ABC") for b in cls.bases)
        and sum(1 for s in cls.body if isinstance(s, ast.FunctionDef | ast.AsyncFunctionDef)) > MAX_PROTOCOL_METHODS
    ]


def mutable_value_objects(tree: ast.Module, _source: str) -> list[int]:
    """DDD_PATTERNS (value objects): a dataclass value object that is not ``frozen=True``."""
    lines: list[int] = []
    for cls in classes_in(tree):
        for deco in cls.decorator_list:
            if _name(deco) != "dataclass":
                continue
            frozen = isinstance(deco, ast.Call) and any(
                k.arg == "frozen" and isinstance(k.value, ast.Constant) and k.value.value is True for k in deco.keywords
            )
            if not frozen:
                lines.append(cls.lineno)
    return lines


def io_properties(tree: ast.Module, _source: str) -> list[int]:
    """ARCHITECTURE_PATTERNS (Proxy anti-fit): a ``@property`` that performs I/O behind an attribute read."""
    lines: list[int] = []
    for fn in _functions(tree):
        if any(_name(d) == "property" for d in fn.decorator_list):
            called = {_name(n).lower() for n in ast.walk(fn) if isinstance(n, ast.Call)}
            if any(tok in name for name in called for tok in _IO_TOKENS):
                lines.append(fn.lineno)
    return lines


def lab_silent_returns(tree: ast.Module, _source: str) -> list[int]:
    """CODING_STANDARDS 4: the silent-return rule product src already pays down, held to the lab too (each function's
    first line; a name defined twice is placed at its first definition)."""
    first_line: dict[str, int] = {}
    for fn in sorted(_functions(tree), key=lambda f: f.lineno):
        first_line.setdefault(fn.name, fn.lineno)
    return [first_line.get(name.rsplit(".", 1)[-1], 0) for name in silent_return_functions(tree)]
