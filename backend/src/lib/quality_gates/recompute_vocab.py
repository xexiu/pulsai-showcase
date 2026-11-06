"""Recompute-in-loop vocabulary: which calls are O(n) work, how big a loop is, what a loop body changes.

IMPORTERS/CALLERS: src/lib/quality_gates/recompute_deps.py, recompute_index.py, recompute_in_loop.py,
expression_clones.py (named_params).
AFFECTED API: none (pure functions over ``ast``). DATA SCHEMAS: none.

Ported unchanged in meaning from the P1-7c perf scan (``scan8.py``, PERF-SCAN-BE section 4), whose
hand-labelled run is the calibration this vocabulary carries: 69 A1 hits, 5 false positives. A word
added here moves that precision, so re-measure (``python -m src.lib.quality_gates.recompute_in_loop
--list``) and re-label before changing one.

REUSE-AUDIT: considered .claude/hooks/architect_standards_guard.py (``_call_name`` resolves only
``name.attr``, one level; this needs the full dotted chain through calls and subscripts) and
src/lib/quality_gates/verify_gate_helpers.py (no loop or call-target vocabulary). Nothing existing
classifies a call as O(n) work or a loop by its size.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterable, Iterator
from enum import StrEnum


class LoopSize(StrEnum):
    """How many times a loop runs, read from its iterable: only DATA / GRID / UNKNOWN loops are judged."""

    DATA = "DATA"  # rows, bars, trades, entries -- grows with the data
    GRID = "GRID"  # cert / sweep cells, folds, configs -- a search space
    SMALL = "SMALL"  # coins, timeframes, sides, a literal of <= SMALL_LITERAL_LOOP items
    UNKNOWN = "UNKNOWN"
    POLL = "POLL"  # `while True:` -- a daemon tick, never a recompute


#: The loop sizes the gate judges. SMALL and POLL repeat a handful of times or forever by design.
JUDGED_LOOP_SIZES: frozenset[LoopSize] = frozenset({LoopSize.DATA, LoopSize.GRID, LoopSize.UNKNOWN})
#: Precedence when a wrapper (`zip`, `enumerate`, ...) iterates several iterables at once.
_WRAPPED_PRECEDENCE: tuple[LoopSize, ...] = (LoopSize.DATA, LoopSize.GRID, LoopSize.UNKNOWN, LoopSize.SMALL)
#: A literal tuple or `range(<const>)` this short is a handful of arms, not data.
SMALL_LITERAL_LOOP = 64


def _words(*chunks: str) -> frozenset[str]:
    """A word set written as prose-width lines, so a 50-word vocabulary stays 3 lines, not 50."""
    return frozenset(" ".join(chunks).split())


#: O(n) receiver methods (pandas / polars / numpy). The CORE subset is clearly O(n) WORK -- not a
#: copy or a reduction -- and only a core site can make a gate finding.
HEAVY_ATTRS = _words(
    "rolling ewm expanding cumsum cumprod cummax cummin sort_values sort_index groupby group_by rank pct_change",
    "resample merge join diff shift apply corr cov quantile median rolling_mean rolling_std rolling_max rolling_min",
    "ewm_mean argsort unique value_counts drop_duplicates interpolate fillna ffill bfill dropna to_numpy copy astype",
    "reset_index set_index with_columns pivot melt explode nunique std var mean sum max min any all idxmax idxmin",
)
HEAVY_CORE = _words(
    "rolling ewm expanding cumsum cumprod cummax cummin sort_values sort_index groupby group_by rank pct_change",
    "resample merge join apply corr cov quantile median rolling_mean rolling_std rolling_max rolling_min ewm_mean",
    "argsort value_counts drop_duplicates interpolate pivot melt nunique with_columns unique",
)
#: Module-level array calls that do O(n) work on their argument.
NP_HEAVY = re.compile(
    r"^(np|numpy|pd|pandas|pl|polars|talib|ta|scipy\.\w+)\.(cumsum|cumprod|convolve|sort|argsort|percentile|quantile|"
    r"median|diff|lexsort|unique|concat|concatenate|DataFrame|Series|correlate|nanpercentile|nanquantile|"
    r"lfilter|searchsorted|maximum\.accumulate|minimum\.accumulate|ATR|EMA|SMA|RSI|MACD|BBANDS|ADX|STDDEV|"
    r"from_pandas|from_numpy|to_datetime|merge_asof|merge|cut|qcut|rolling_\w+|ewm\w*|polyfit|lstsq|"
    r"corrcoef|cov|histogram|isin|where|nanmean|nanstd|mean|std|sum|max|min|vstack|hstack|column_stack|"
    r"stack|asarray|array)$"
)
#: The NP_HEAVY leaves that are a conversion or a reduction rather than core work.
NP_NOT_CORE = _words(
    "asarray array where isin mean std sum max min nanmean nanstd to_datetime DataFrame Series from_pandas",
    "from_numpy vstack hstack column_stack stack concat concatenate histogram",
)
#: First-party helpers named for an indicator compute one over the whole series they are given.
INDICATOR_NAME = re.compile(
    r"(^|_)(atr|ema|sma|wma|rma|rsi|macd|adx|bollinger|bbands|stoch|true_range|zscore|z_score|rolling|"
    r"realized_vol|realised_vol|volatility|indicator|indicators|supertrend|keltner|donchian|vwap|obv|"
    r"drawdown|equity_curve|swing|pivots?|regime|features?|calculate_all)(_|$)",
    re.IGNORECASE,
)
#: A scalar read (`x.iloc[i]`, `x[-1]`) is O(1): its receiver is not O(n) input.
SCALAR_PICK = re.compile(r"\.(iloc|loc|iat|at)\[[^:\]]*\]$|\[-?\d+\]$")
#: A `range(...)` that does not grow with the data is not a python loop over it.
DATA_SIZED_RANGE = re.compile(r"len\(|\bn\b|n_|size|count")
_RANGE_DATA_WORD = re.compile(r"\bn(_\w+)?\b|size|count|bars|rows")
_WHILE_DATA = re.compile(r"<\s*(len\(|n\b|n_)")
_CONSTANT_NAME = re.compile(r"[A-Z0-9_]+")
#: A callee whose decorator memoises it is computed once per argument tuple, never per iteration.
MEMO_DECORATOR = re.compile(r"(lru_cache|\bcache\b|cached|memoize|functools\.cache)")
#: The gate tier: at least one dependency of the O(n) site must be annotated as an array.
ARRAY_ANNOTATION = re.compile(r"(DataFrame|Series|ndarray|NDArray|ArrayLike|LazyFrame|pl\.|pd\.|np\.)")

#: Methods that change their receiver: a name a loop body mutates is not loop-invariant.
MUTATORS = _words("append extend insert update add setdefault fill put itemset appendleft __setitem__")
_INPLACE = (MUTATORS - {"__setitem__"}) | _words(
    "pop remove clear sort shuffle permutation discard popitem drop rename reset_index set_index fillna replace",
    "sort_values clip copyto",
)
#: pandas methods that mutate only with `inplace=`; otherwise they return a copy.
_INPLACE_IF_FLAGGED = _words("drop rename reset_index set_index fillna replace sort_values clip")
_MUTATES_FIRST_ARG: frozenset[str] = frozenset({"shuffle", "copyto"})

_DATA_NAMES = re.compile(
    r"(trade|row|bar|signal|candle|record|frame|series|position|order|event|entr|timestamp|date|close|price|"
    r"value|pred|label|outcome|tick|fill|step|sample|obs|idx|index|day|hour|minute|return|ret|equity|alert|"
    r"user|message|item|line|chunk|batch|kline|ohlcv|df|arr|data|point|pair|result|job|task|txn|funding)",
    re.IGNORECASE,
)
_GRID_NAMES = re.compile(
    r"(cell|combo|grid|config|cfg|param|exit|lane|lever|sizing|hold|conf|threshold|window|fold|split|trial|"
    r"candidate|spec|variant|arm|strateg|lookback|period|horizon|seed|level|tp|sl|stop|target|book|hyp)",
    re.IGNORECASE,
)
_SMALL_NAMES = re.compile(
    r"(coin|symbol|timeframe|tf|model|exchange|provider|key|col|feature|name|file|path|dir|venue|sleeve|"
    r"source|field|kind|type|mode|side|layer|group|metric|section|header|attr|flag|env|service|queue|route)",
    re.IGNORECASE,
)
_ROW_ITERATORS: frozenset[str] = frozenset({"iterrows", "itertuples", "iter_rows"})
_WRAPPERS: frozenset[str] = frozenset({"enumerate", "zip", "sorted", "reversed", "list", "tuple", "set"})
_MAPPING_VIEWS: frozenset[str] = frozenset({"items", "keys", "values"})
_POLL_TESTS: frozenset[str] = frozenset({"True", "1"})


def dotted_call_target(node: ast.AST) -> str:
    """``a.b.c`` for an attribute chain, ``f().g`` through calls, ``x[].y`` through subscripts, ``?`` otherwise."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    elif isinstance(node, ast.Call):
        parts.append(dotted_call_target(node.func) + "()")
    elif isinstance(node, ast.Subscript):
        parts.append(dotted_call_target(node.value) + "[]")
    else:
        parts.append("?")
    return ".".join(reversed(parts))


def bare_names(node: ast.AST) -> set[str]:
    """Every ``Name`` read or written anywhere under ``node``."""
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


def walk_shallow(node: ast.AST) -> Iterator[ast.AST]:
    """``ast.walk`` that does not descend into nested function, lambda or class bodies."""
    stack = list(ast.iter_child_nodes(node))
    while stack:
        child = stack.pop()
        yield child
        if not isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef):
            stack.extend(ast.iter_child_nodes(child))


def named_params(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> list[ast.arg]:
    """A function's parameters that have a name of their own, in order: positional-only, positional, keyword-only
    (``*args`` / ``**kwargs`` excluded)."""
    return [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]


def loop_size(iterable: ast.expr) -> LoopSize:
    """The size class of ``for _ in <iterable>``."""
    if isinstance(iterable, ast.List | ast.Tuple | ast.Set):
        return LoopSize.SMALL if len(iterable.elts) <= SMALL_LITERAL_LOOP else LoopSize.DATA
    if isinstance(iterable, ast.Dict):
        return LoopSize.SMALL
    if isinstance(iterable, ast.Call):
        sized = _call_loop_size(iterable)
        if sized is not None:
            return sized
    return _named_loop_size(ast.unparse(iterable))


def while_loop_size(test: ast.expr) -> LoopSize:
    """The size class of ``while <test>``: a loop over data, a polling loop, or unknown."""
    text = ast.unparse(test)
    if _WHILE_DATA.search(text):
        return LoopSize.DATA
    return LoopSize.POLL if text in _POLL_TESTS else LoopSize.UNKNOWN


def _call_loop_size(call: ast.Call) -> LoopSize | None:
    leaf = dotted_call_target(call.func).split(".")[-1]
    if leaf in _ROW_ITERATORS:
        return LoopSize.DATA
    if leaf == "range":
        return _range_loop_size(call)
    if leaf == "product":
        return LoopSize.GRID
    if leaf in _WRAPPERS and call.args:
        sizes = {loop_size(arg) for arg in call.args}
        return next(size for size in _WRAPPED_PRECEDENCE if size in sizes)
    if leaf in _MAPPING_VIEWS:
        return loop_size(call.func.value) if isinstance(call.func, ast.Attribute) else LoopSize.UNKNOWN
    return None


def _range_loop_size(call: ast.Call) -> LoopSize:
    if all(isinstance(arg, ast.Constant) for arg in call.args):
        bounds = [arg.value for arg in call.args if isinstance(arg, ast.Constant) and isinstance(arg.value, int)]
        return LoopSize.SMALL if bounds and max(bounds) <= SMALL_LITERAL_LOOP else LoopSize.DATA
    text = ast.unparse(call)
    return LoopSize.DATA if "len(" in text or _RANGE_DATA_WORD.search(text) else LoopSize.UNKNOWN


def _named_loop_size(text: str) -> LoopSize:
    base = text.split("(", maxsplit=1)[0].split("[", maxsplit=1)[0].rsplit(".", maxsplit=1)[-1]
    if _CONSTANT_NAME.fullmatch(base or "x"):
        return LoopSize.SMALL  # a module constant tuple
    if _SMALL_NAMES.search(base) and not _DATA_NAMES.search(base):
        return LoopSize.SMALL
    if _GRID_NAMES.search(base):
        return LoopSize.GRID
    if _DATA_NAMES.search(base):
        return LoopSize.DATA
    return LoopSize.UNKNOWN


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, ast.Attribute | ast.Subscript):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _mutated_by_call(call: ast.Call) -> set[str]:
    if not isinstance(call.func, ast.Attribute) or call.func.attr not in _INPLACE:
        return set()
    out: set[str] = set()
    root = _root_name(call.func.value)
    copies = call.func.attr in _INPLACE_IF_FLAGGED and not any(k.arg == "inplace" for k in call.keywords)
    if root and root != "self" and not copies:
        out.add(root)
    if call.func.attr in _MUTATES_FIRST_ARG and call.args:
        first = _root_name(call.args[0])
        if first:
            out.add(first)
    return out


def assigned_names(body: Iterable[ast.AST]) -> set[str]:
    """Every local a loop body binds, deletes or mutates in place: what the loop may CHANGE."""
    out: set[str] = set()
    for statement in body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store | ast.Del):
                out.add(node.id)
            elif isinstance(node, ast.arg):
                out.add(node.arg)
            elif isinstance(node, ast.Subscript | ast.Attribute) and isinstance(node.ctx, ast.Store | ast.Del):
                root = _root_name(node)
                if root and root != "self":
                    out.add(root)
            elif isinstance(node, ast.Call):
                out |= _mutated_by_call(node)
    return out


def assigned_self_attrs(body: Iterable[ast.AST]) -> set[str]:
    """The ``self.<attr>`` names ``body`` assigns."""
    return {
        node.attr
        for statement in body
        for node in ast.walk(statement)
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store) and isinstance(node.value, ast.Name) and node.value.id == "self"
    }


def is_prefix_slice(expr: ast.AST, loop_vars: set[str]) -> bool:
    """``x[:i]`` / ``x.iloc[: i + 1]`` with ``i`` a loop variable: a GROWING prefix (class A4, not A1)."""
    for node in ast.walk(expr):
        if not (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice)):
            continue
        lower, upper = node.slice.lower, node.slice.upper
        from_start = lower is None or (isinstance(lower, ast.Constant) and lower.value in (0, None))
        if from_start and upper is not None and bare_names(upper) & loop_vars:
            return True
    return False
