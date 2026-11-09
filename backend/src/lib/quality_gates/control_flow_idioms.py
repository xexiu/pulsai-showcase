"""Control-flow idioms: every loop that sleeps is a poll, a retry, a pace or a schedule -- and each idiom has one home.

IMPORTERS/CALLERS: src/lib/quality_gates/concept_definitions.py (``_structures`` tags each sleeping loop, ``--idioms``
lists them, the ``--tree`` ratchet runs ``canary_holds``; the idiom rows of scripts/concept_owners.json name the homes,
so the doors already wired to it -- .claude/hooks/one_definition_guard.py, check_touched_debt's duplicate-definition
row, verify's --tree ratchet -- refuse a new copy, charge a touched file and hold the total);
tests/scripts/test_control_flow_idioms.py. AFFECTED API: new module. DATA SCHEMAS: reads control_flow_idioms_canary.txt.

WHY (GATE-IDIOMS, owner 2026-11-06: "not only for this use case, but also for other features uses cases? deep think of
everythings, edge cases"): the same poll was written four times -- three candle looks beside LighterReads.first_within
-- and no gate saw it (jscpd at 6 lines / 50 tokens: 0 clones in the three files' 534 lines). Every door compares text,
values, whole bodies, names or file names, and a control-flow skeleton re-typed around a different call matches none of
them. This one reads the SHAPE: how a loop that sleeps ends.

THE IDIOMS, first match wins:
  retry-loop     the sleep sits in an ``except``, or in ``if <failure>: ... continue`` (a status, an error, a rate limit),
                 or the loop's ``try`` returns on success
  page-loop      forward paging: a loop with an exit (an ``if ...: return / break``, or a ``while`` test) that keeps what
                 it reads (``out += rows``, ``.extend``) or feeds its read's result back into the next read (``page(c)``
                 then ``c = ...``); classified so it is never told to import the poll; no home yet (MEASURED, see PAGE)
  poll-loop      any other loop with such an exit: the same read asked again until its answer comes, or until something
                 goes (a process exits, a position closes)
  schedule-loop  any other ``while``: a fixed interval or a due time, until a stop flag
  pace-sleep     a sleep computed from a clock read minus another time, outside a loop or in a ``for`` over work
  unclassified   a ``for`` with a fixed sleep and no answer exit (a delay between items): listed, never a finding

SLEEP SPELLINGS: a call whose name ends in ``sleep`` (time.sleep, asyncio.sleep, self._sleep, clocks.sleep, an injected
``sleep``), and ``.wait(timeout)`` / ``.wait_for(pred, timeout)`` (Event, Condition), which sleep without the word;
``asyncio.wait`` / ``asyncio.wait_for`` wait on tasks, they are not sleeps. KNOWN BLIND SPOT: a retry by recursion (the
function calls itself after a sleep) writes no loop. Library retries (tenacity, backoff) write no loop either, so they are
never findings. A judged exception carries ``CLONE-OK: <why>`` (constant_clones.CLONE_OK) on the loop's or the sleep's
line.

REUSE-AUDIT: considered concept_definitions._is_reconnect_loop (one shape, the websocket reconnect -- those loops are
passed in ``skip``, so a reconnect loop is never also a retry), expression_clones / constant_clones (bodies and values:
blind to one skeleton around different calls; constant_clones.assigned_name and CLONE_OK are imported, not re-written)
and scripts/check_duplicate_lines.py (text). None reads how a loop ends.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from src.lib.quality_gates.constant_clones import CLONE_OK, assigned_name

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Iterator, Sequence

POLL, RETRY, PACE, SCHEDULE = "poll-loop", "retry-loop", "pace-sleep", "schedule-loop"
PAGE, UNCLASSIFIED = "page-loop", "unclassified-sleep"
#: The idioms a registry row can own (concept_owners.json ``structures``). An unclassified loop is listed, never refused.
#: PAGE exists because the first version did not hold -- MEASURED by `concept_definitions --idioms` over the tree (120
#: sites, 2026-11-07): it read every paging loop as a poll (marketing_newsletter_tasks' `while recipients:`, the lab
#: fetchers' `if not rows: break`), so a refusal would have told a pager to import poll_until_answer.
IDIOMS: tuple[str, ...] = (POLL, RETRY, PACE, SCHEDULE, PAGE)
#: A call named ``is_sleep`` asks a question about a sleep; it does not sleep. MEASURED the same run: the first version's
#: "a name ending in sleep" read this module's own `is_sleep(node)` as a sleeping loop.
PREDICATE_PREFIXES: tuple[str, ...] = ("is_", "has_", "should_", "can_")
#: Calls that keep what a loop read; with ``+=`` they mark a pager (MEASURED, see ``_pages``).
ACCUMULATING_CALLS: frozenset[str] = frozenset({"append", "extend", "update", "add", "concat"})
#: Calls that compute rather than read: a name fed back through one of these is a backoff or a bound, not a cursor.
BUILTIN_ARITHMETIC: frozenset[str] = frozenset({"min", "max", "abs", "round", "int", "float", "len", "sum"})
TAG_SEPARATOR, ORDINAL_SEPARATOR = "@", "#"
#: Calls that read a clock: a sleep computed from one minus another time paces (or, in a ``while``, waits for a due time).
CLOCK_CALLS: frozenset[str] = frozenset({"monotonic", "monotonic_ns", "time", "time_ns", "perf_counter", "now", "utcnow", "clock"})
#: Words that make an ``if`` a FAILURE test (a retry backs off on it) and a loop test a STOP flag (a schedule's exit).
#: "status" was one and did not hold -- MEASURED by `--idioms` (2026-11-07): poll_admin_task / poll_training_job wait for a
#: job's `status in (completed, failed)` and read as retries. A failure is a rate limit or an error, not a state field.
FAILURE_WORDS: tuple[str, ...] = ("too_many", "error", "exc", "fail", "retry", "rate_limit", "ratelimit", "throttl")
FAILED_STATUSES: frozenset[int] = frozenset({429, *range(500, 600)})
STOP_WORDS: tuple[str, ...] = ("stop", "running", "shutdown", "cancel", "closing", "quit")
STOP_CALLS: frozenset[str] = frozenset({"is_set", "wait"})
#: ``.wait`` sleeps with one argument (its timeout), ``.wait_for`` with two (predicate, timeout); asyncio's own are task waits.
WAIT_ARGS: dict[str, int] = {"wait": 1, "wait_for": 2}
TASK_WAIT_MODULE = "asyncio"
TIMEOUT_KEYWORDS: frozenset[str] = frozenset({"timeout", "seconds", "delay", "secs"})
#: How many assignments a sleep's amount is followed back through (``delay = slot - now``, ``now = self._monotonic()``).
RESOLVE_DEPTH = 3
CANARY_PATH = Path(__file__).with_name("control_flow_idioms_canary.txt")
CANARY_FUNCTIONS: tuple[str, ...] = ("OilPart._served", "OilSide._read_side", "BocpdSide.side_at")
MODULE_SCOPE = "<module>"
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
_LOOPS = (ast.For, ast.AsyncFor, ast.While)
type _Loop = ast.For | ast.AsyncFor | ast.While


class SleepSite(NamedTuple):
    """One loop that sleeps, or one pacing sleep outside a loop: its idiom, the function it sits in, its first line."""

    idiom: str
    function: str
    line: int


def node_name(node: ast.AST) -> str:
    """A Name's id or an Attribute's last part (``self._sleep`` -> ``_sleep``); empty for any other node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _has_word(name: str, words: Iterable[str]) -> bool:
    lowered = name.lower()
    return any(word in lowered for word in words)


def is_sleep(call: ast.Call) -> bool:
    """Whether ``call`` sleeps: a name ending in ``sleep``, or an Event / Condition wait given its timeout."""
    func, name = call.func, node_name(call.func)
    bare = name.lstrip("_").lower()  # MEASURED: "ends in sleep" read this module's own is_sleep(node) as a sleep
    if bare == "sleep" or (bare.endswith("_sleep") and not bare.startswith(PREDICATE_PREFIXES)):
        return True
    if name not in WAIT_ARGS or not isinstance(func, ast.Attribute) or node_name(func.value) == TASK_WAIT_MODULE:
        return False
    return len(call.args) >= WAIT_ARGS[name] or any(k.arg in TIMEOUT_KEYWORDS for k in call.keywords)


def _own(node: ast.AST, *, loops: bool = True) -> Iterator[ast.AST]:
    """Every node under ``node`` in its own scope: never inside a nested def, class or lambda; with ``loops=False``,
    never inside a nested loop either (a ``break`` there ends only that loop)."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _SCOPES) or (not loops and isinstance(child, _LOOPS)):
            continue
        yield child
        yield from _own(child, loops=loops)


def _scopes(node: ast.AST, prefix: str = "") -> Iterator[tuple[str, ast.AST]]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            yield f"{prefix}{child.name}", child
            yield from _scopes(child, f"{prefix}{child.name}.")
        elif isinstance(child, ast.ClassDef):
            yield from _scopes(child, f"{prefix}{child.name}.")
        else:
            yield from _scopes(child, prefix)


def _stop_flag(test: ast.expr) -> bool:
    if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
        return _stop_flag(test.operand)
    if isinstance(test, ast.BoolOp):
        return all(_stop_flag(value) for value in test.values)
    name = node_name(test.func) if isinstance(test, ast.Call) else node_name(test)
    return name in STOP_CALLS or (bool(name) and _has_word(name, STOP_WORDS))


def _failure_test(test: ast.expr) -> bool:
    for node in ast.walk(test):
        if _has_word(node_name(node), FAILURE_WORDS) or node_name(node) == "ok":
            return True
        if isinstance(node, ast.Constant) and type(node.value) is int and node.value in FAILED_STATUSES:
            return True
    return False


def _exits(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Return | ast.Break) for n in _own(node, loops=False))


def _continues(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Continue) for n in _own(node, loops=False))


def _in_failure_branch(sleep: ast.Call, loop: _Loop, parents: dict[ast.AST, ast.AST]) -> bool:
    node = parents.get(sleep)
    while node is not None and node is not loop:
        if isinstance(node, ast.ExceptHandler) or (isinstance(node, ast.If) and _failure_test(node.test) and _continues(node)):
            return True
        node = parents.get(node)
    return False


def _returns_in_try(loop: _Loop) -> bool:
    """The loop leaves on success: a ``try`` that returns / breaks, or an exit under a failure test (``if status != 429:
    break``). The second did not exist at first -- MEASURED: llm_agent_a1m.ask, a 429 back-off, read as a pager."""
    tries = (n for n in _own(loop, loops=False) if isinstance(n, ast.Try) and n.handlers)
    if any(isinstance(s, ast.Return | ast.Break) or _exits(s) for t in tries for s in t.body):
        return True
    return any(isinstance(n, ast.If) and _failure_test(n.test) and _exits(n) for n in _own(loop, loops=False))


def _assigned_lines(loop: _Loop) -> dict[str, int]:
    """Each name the loop assigns (tuple targets included), with the first line it does. Rule unchanged; the old form did
    not hold because it was a two-level conditional expression and read ``node.lineno`` on ast.AST (a mypy error)."""
    first: dict[str, int] = {}
    for node in _own(loop):
        for name in (n.id for target in _targets(node) for n in ast.walk(target) if isinstance(n, ast.Name)):
            first[name] = min(first.get(name, _line(node)), _line(node))
    return first


def _targets(node: ast.AST) -> list[ast.expr]:
    if isinstance(node, ast.Assign):
        return node.targets
    if isinstance(node, ast.AnnAssign):
        return [node.target]
    return []


def _carries_its_input(loop: _Loop) -> bool:
    """Whether a read in the loop takes a value the loop then moves on: a non-builtin call (or a ``for`` over it) reads a
    name at or before the line the loop reassigns it -- ``page(market, cursor)`` then ``cursor = ...``. A poll asks the
    same question each time; a backoff's ``min(delay * 2, cap)`` is arithmetic, not a read."""
    assigned = _assigned_lines(loop)
    for node in _own(loop):
        names = {n.id for read_input in _read_inputs(node) for n in ast.walk(read_input) if isinstance(n, ast.Name)}
        if any(name in assigned and _line(node) <= assigned[name] for name in names):
            return True
    return False


def _read_inputs(node: ast.AST) -> list[ast.expr]:
    """What a node reads from: a ``for``'s iterable, or a read call's arguments (never arithmetic, never the sleep). The
    rule is unchanged; the old form did not hold because it was a two-level conditional expression (CODING_STANDARDS 3)."""
    if isinstance(node, ast.For | ast.AsyncFor):
        return [node.iter]
    if isinstance(node, ast.Call) and node_name(node.func) not in BUILTIN_ARITHMETIC and not is_sleep(node):
        return [*node.args, *(keyword.value for keyword in node.keywords)]
    # A request built before the read counts as the read's input. Without it the rule did not hold -- MEASURED by the
    # one-definition guard on vrp_screen.fetch_dvol_daily: `params = {"start_timestamp": s, ...}` then `_result(m,
    # params)` hid the cursor `s`, and the pager read as a poll.
    named = assigned_name(node)
    if named is not None and isinstance(named[1], ast.Dict | ast.List | ast.Tuple | ast.Set):
        return [named[1]]
    return []


def _line(node: ast.AST) -> int:
    """A node's line, 0 when it has none -- the old ``node.lineno`` did not hold because mypy reads it on ast.AST as an
    attr-defined error."""
    return int(getattr(node, "lineno", 0))


def _pages(loop: _Loop) -> bool:
    """Whether the loop is a pager: it keeps what it reads (``out += rows``, ``rows.extend(page)``) or moves its read's
    input on (``_carries_its_input``). Keeping alone did not hold -- MEASURED on `--idioms` (2026-11-07): fills_since,
    edge_lab.fetch_ohlcv_rows and vrp_screen.fetch_dvol_daily end on a BOUNDARY test (``min(ts) < since_s``,
    ``cursor > end_ms``) shaped like a poll's answer test (``opens[-1] >= want``); what separates them is the cursor."""
    assigned = _assigned_lines(loop)
    for node in _own(loop):
        if isinstance(node, ast.AugAssign) and _keeps_a_read(node.value, assigned):
            return True
        if isinstance(node, ast.Call) and node_name(node.func) in ACCUMULATING_CALLS:
            return True
    return _carries_its_input(loop)


def _keeps_a_read(added: ast.expr, assigned: dict[str, int]) -> bool:
    """Whether ``x += added`` keeps data (a list, a comprehension, a name the loop read) rather than counting (a literal,
    or a name from outside the loop -- MEASURED: DemoAccount.filled's ``waited += POLL_S`` read as kept data, a timer)."""
    if isinstance(added, ast.Name):
        return added.id in assigned
    return not isinstance(added, ast.Constant)


def _ending(loop: _Loop) -> str | None:
    """POLL when the loop ends on an answer that ARRIVED, or waits for something to go; PAGE when it keeps what it reads
    while data comes. Two versions did not hold, each MEASURED by `--idioms` over the tree: any conditional exit as a poll
    read every pager as one (see PAGE); any absent-only exit as a page then read trade_engines.retire,
    warm_start.wait_for_exit and demo_account.assert_flat -- waits for a process or a position to GO -- as pagers."""
    exit_tests = [n.test for n in _own(loop, loops=False) if isinstance(n, ast.If) and not _stop_flag(n.test) and _exits(n)]
    runs_on = isinstance(loop, ast.While) and not (isinstance(loop.test, ast.Constant) and loop.test.value) and not _stop_flag(loop.test)
    if (exit_tests or runs_on) and _pages(loop):  # the cursor first: a boundary exit reads like an answer (see _pages)
        return PAGE
    if exit_tests or runs_on:
        return POLL
    if any(isinstance(s, ast.Return | ast.Break) for s in loop.body) and _continues(loop):
        return POLL
    return None


def _amount(call: ast.Call) -> ast.expr | None:
    if call.args:
        return call.args[-1]
    return next((k.value for k in call.keywords if k.arg in TIMEOUT_KEYWORDS), None)


def _reads_clock(expr: ast.AST, assigns: dict[str, ast.expr], depth: int) -> bool:
    for node in ast.walk(expr):
        if isinstance(node, ast.Call) and node_name(node.func).lstrip("_") in CLOCK_CALLS:
            return True
        if isinstance(node, ast.Name) and depth < RESOLVE_DEPTH and node.id in assigns and _reads_clock(assigns[node.id], assigns, depth + 1):
            return True
    return False


def _elapsed(expr: ast.AST | None, assigns: dict[str, ast.expr], depth: int = 0) -> bool:
    """Whether a sleep's amount is a clock read minus another time, followed back through the scope's assignments."""
    for node in ast.walk(expr) if expr is not None else ():  # rule unchanged; one line did not hold because E501
        if (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Sub)
            and (_reads_clock(node.left, assigns, depth) or _reads_clock(node.right, assigns, depth))
        ):
            return True
        if isinstance(node, ast.Name) and depth < RESOLVE_DEPTH and node.id in assigns and _elapsed(assigns[node.id], assigns, depth + 1):
            return True
    return False


def _loop_idiom(loop: _Loop, sleeps: list[ast.Call], parents: dict[ast.AST, ast.AST], assigns: dict[str, ast.expr]) -> str:
    if any(_in_failure_branch(s, loop, parents) for s in sleeps) or _returns_in_try(loop):
        return RETRY
    if (ending := _ending(loop)) is not None:
        return ending
    if isinstance(loop, ast.While):
        return SCHEDULE
    return PACE if any(_elapsed(_amount(s), assigns) for s in sleeps) else UNCLASSIFIED


def _judged(lines: Sequence[str], *nodes: ast.AST) -> bool:
    """Whether a node's line carries CLONE-OK. Rule unchanged; the old ``n.lineno`` did not hold because mypy reads it on
    ast.AST as an attr-defined error."""
    return any(0 < _line(n) <= len(lines) and CLONE_OK in lines[_line(n) - 1] for n in nodes)


def _enclosing_loop(node: ast.AST, scope: ast.AST, parents: dict[ast.AST, ast.AST]) -> _Loop | None:
    parent = parents.get(node)
    while parent is not None and parent is not scope:
        if isinstance(parent, _LOOPS):
            return parent
        parent = parents.get(parent)
    return None


def _scope_sites(function: str, scope: ast.AST, lines: Sequence[str], skip: Collection[ast.AST]) -> Iterator[SleepSite]:
    parents: dict[ast.AST, ast.AST] = dict.fromkeys(ast.iter_child_nodes(scope), scope)
    assigns: dict[str, ast.expr] = {}
    sleeps: list[ast.Call] = []
    for node in _own(scope):
        parents.update((child, node) for child in ast.iter_child_nodes(node))
        if (named := assigned_name(node)) is not None:
            assigns[named[0]] = named[1]
        elif isinstance(node, ast.Call) and is_sleep(node):
            sleeps.append(node)
    by_loop: dict[_Loop, list[ast.Call]] = {}
    for sleep in sleeps:
        loop = _enclosing_loop(sleep, scope, parents)
        if loop is not None:
            by_loop.setdefault(loop, []).append(sleep)
        elif _elapsed(_amount(sleep), assigns) and not _judged(lines, sleep):
            yield SleepSite(PACE, function, sleep.lineno)
    for loop, inside in by_loop.items():
        if loop not in skip and not _judged(lines, loop, *inside):
            yield SleepSite(_loop_idiom(loop, inside, parents, assigns), function, loop.lineno)


def sleep_sites(tree: ast.Module, lines: Sequence[str], skip: Collection[ast.AST] = ()) -> list[SleepSite]:
    """Every loop that sleeps in ``tree`` (and every pacing sleep outside a loop), in line order, each with its idiom;
    a loop in ``skip`` (a shape another row owns, the reconnect loop) and one judged ``CLONE-OK`` are left out."""
    sites = list(_scope_sites(MODULE_SCOPE, tree, lines, skip))
    for function, scope in _scopes(tree):
        sites.extend(_scope_sites(function, scope, lines, skip))
    return sorted(sites, key=lambda site: site.line)


def idiom_tags(sites: Iterable[SleepSite]) -> frozenset[str]:
    """One tag a site, ``<idiom>@<function>`` (``#2`` on the second of one idiom in one function): stable under edits
    elsewhere in the file, so a guard comparing tags before and after sees only the loop that was added."""
    tags: set[str] = set()
    for site in sites:
        if site.idiom == UNCLASSIFIED:
            continue
        base = f"{site.idiom}{TAG_SEPARATOR}{site.function}"
        tag, ordinal = base, 1
        while tag in tags:
            ordinal += 1
            tag = f"{base}{ORDINAL_SEPARATOR}{ordinal}"
        tags.add(tag)
    return frozenset(tags)


def tag_idiom(tag: str) -> str:
    """The idiom a tag names (``poll-loop@OilPart._served`` -> ``poll-loop``); any other structure is its own name."""
    return tag.split(TAG_SEPARATOR, 1)[0]


def canary_holds(text: str | None = None) -> bool:
    """Whether the detector still reads the three pre-fix candle looks as polls. False means it measures nothing."""
    source = CANARY_PATH.read_text(encoding="utf-8") if text is None else text
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return [(s.idiom, s.function) for s in sleep_sites(tree, source.splitlines())] == [(POLL, f) for f in CANARY_FUNCTIONS]
