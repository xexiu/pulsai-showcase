"""Pure helpers for ``scripts/verify.sh`` type touch-gate and research bug ratchet, plus the per-source
debt counters (``count_noqa_comments``, ``silent_return_functions``) that a whole-tree ratchet test and
``scripts/check_touched_debt.py`` both call, so the two scopes can never count differently.

REUSE-AUDIT: no prior SoT for these parsers (bash grepped JSON/ANSI inline and
silently under-counted). Web/hook verify tests cover different surfaces.

Keep this module free of git/subprocess side effects so unit tests stay fast.
"""

from __future__ import annotations

import ast
import io
import json
import re
import sys
import tokenize
from collections.abc import Container, Iterable, Iterator, Sequence
from pathlib import Path

from src.shared.utils.json_rows import json_object

# SINGLE SOURCE for the basedpyright error gate (verify.sh step 2i AND ci.yml).
# The gate is TWO-SIDED: it fails when the count RISES (debt grew) and when it FALLS (debt was
# paid -- lock the gain by lowering this number). That is why the value must not be restated in
# a second file: a copy left behind does not fail once, it fails every later PR until someone
# finds the other file. Bash reads it via the ``baseline`` CLI command.
#
# NOW ZERO (2026-08-26, from 43). Every error was either fixed at the source or replaced by a
# located `# pyright: ignore[...]` carrying the measurement that justifies it, so a bare count
# is once again a meaningful signal rather than a debt allowance.
#
# The tracked task said to DELETE this constant once it reached zero. Keeping it at 0 instead,
# deliberately: deleting it means spelling "must be 0" separately in verify.sh and ci.yml, which
# is the two-copies problem this comment already warns about, and it would remove the upper half
# of the gate -- the half that fails the build the moment a new error appears. A zero-tolerance
# gate with one source is strictly stronger than no gate. Retire it only by retiring the check.
BASEDPYRIGHT_ERROR_BASELINE = 0

# SINGLE SOURCE for the `noqa` count over apps/api/src, read by the whole-tree ratchet
# (tests/unit/architecture/test_noqa_ratchet.py). Two-sided like the basedpyright baseline: it fails
# when the count rises AND when it falls, so a paid-down suppression is locked in the same commit.
#
# Owner, 2026-09-17: "if someone touches a file, he MUST fix noqa if detected and lock the new lower
# baselines... MUST reach baseline 0 little by little". The ratchet alone only forbids growth; the
# half that makes the number walk down is the `noqa` row of scripts/check_touched_debt.py (pre-commit,
# verify.sh 2i-bis, CI): a touched src/ file must leave with ZERO suppressions. It counts with
# `count_noqa_comments` below, so the tree ratchet and the touch rule can never disagree on a count.
#
# 546 measured 2026-09-17; 542 after wave 3's exemptions were paid at the source; 539 after the
# touch-gate caught its FIRST file -- cert_run_tasks, touched by C-2, carried an S603 suppression.
# That rule fires on every subprocess call and cannot be satisfied except by suppressing it, so it
# was settled ONCE in pyproject with the measurement (three sites, all `sys.executable` + literal
# argv + shell=False) and all three per-line exemptions went with it. This is the walk to zero the
# owner asked for: each touch pays its file, and the number only moves down.
# 539 -> 536 (2026-09-17, same day): the touch-gate fired again, this time on lane_rows, which the
# MinTRL moments made me edit. Its three suppressions were paid, not carried: the bottom-of-file
# re-export block moved up with the other imports (E402 gone outright), and the two TC001 became
# one per-file-ignore carrying the test that proves the imports must exist at runtime.
# 474 -> 305 (2026-09-18), and the reason it moved by 169 in one commit is that the suppressions
# were never the defect: the LINTER was misconfigured. TC001/TC002 say "defer this import", but a
# FastAPI route parameter typed `Annotated[AsyncSession, Depends(get_db)]` is resolved at request
# time, so deferring it breaks the app. ruff has a setting for exactly that, and it was unset.
# Measured with suppressions disabled: 344 findings across src before
# `flake8-type-checking.runtime-evaluated-*`, 137 after. One config block, 169 directives redundant.
#
# THE BLOCKER RECORDED HERE BEFORE WAS FALSE, and the correction matters more than the number. This
# comment used to say 7 files carried MALFORMED directives -- a code followed by prose, read as a
# bare suppression -- hiding 67 real violations. Probed against ruff 0.15.6 rather than believed: a
# line carrying a directive for E501 followed by prose still REPORTED an unused import on the same
# line, and one naming F401 still suppressed only F401. The prose is ignored and only the named
# codes are suppressed. There were no hidden violations. What the config DID expose was six TC004s,
# four of them the same name imported twice (once eagerly, once deferred) -- all fixed at the
# source, none suppressed.
#
# 48 findings remain under src/api and they stay: module-level DI aliases are plain assignments
# executed at import time, so the name really is needed at runtime and no decorator setting reaches
# a module-level statement. See tests/unit/architecture/
# test_type_checking_is_configured_not_suppressed.py, which ratchets that count in both directions.
#
# 474 -> 329, not to 305, and the gap is the TOUCH-GATE doing its job. That gate refuses any
# touched src file still carrying a suppression -- the owner's walk-to-zero rule, which says that
# touching a file means cleaning it ENTIRELY. A config-driven sweep does not respect that boundary:
# it removes what the config made redundant and leaves what is structurally required, so a mixed
# file ends up touched and non-zero. Eleven files were therefore RETURNED to HEAD rather than
# committed half-swept, and they keep their directives until a slice can pay them properly:
#
#   * ten route modules whose remaining suppression sits on a module-level DI alias or a
#     non-decorated helper, which no decorator setting can reach;
#   * `indicator_chart_capabilities.py`, which sits between two tools that disagree -- ruff's TC006
#     REQUIRES the quoted form in `cast("RenderMode", ...)`, and vulture then cannot see the name
#     used at all and reports the import dead at 90% confidence. Unquoting satisfies vulture and
#     fails ruff. The clean answer is a documented vulture whitelist entry, and
#     `vulture_whitelist.py` is carrying another developer's uncommitted work, so staging it would
#     sweep in changes that are not mine.
#
# 69 files went in fully clean. The remainder is counted honestly here rather than hidden.
#
# 329 -> 321: four of the eleven held-back files PAID their non-TC suppression at the source, which
# released their TC ones with it. `funding_backtest`, `funding_monitor`, `funding_paper` and
# `market_insights_routes` each carried an `ARG001` on a route parameter that exists PURELY as an
# auth gate -- the dependency runs, nothing reads the user. Renaming it `_current_user` / `_user`
# is what ruff's dummy-variable convention already recognises, so the rule stops firing without a
# suppression, and it is the spelling the admin routes use anyway (`_user: AdminUser`). FastAPI
# injects by ANNOTATION, never by parameter name, so nothing about the dependency or the OpenAPI
# surface moves. Seven files remain held back.
# 315 -> 296: MEASURED, and the gap is the point. Nineteen suppressions had already been paid
# at the source while this constant still read 315, so the ratchet had been sitting on 19 free
# slots -- exactly the headroom `.claude/rules/investigate-before-changing-a-gate.md` exists to
# refuse. Only ONE of the nineteen was paid by the commit that lowered this line (a `TC001` on
# `model_candidate_upload_service.StorageBackend`, which is annotation-only under
# `from __future__ import annotations` and belonged in a TYPE_CHECKING block all along); the
# other eighteen were paid earlier and never locked in. That is why
# `test_the_baseline_is_current_so_progress_is_recorded` asserts the DROP as well as the rise:
# a one-sided ratchet silently converts every repayment into future headroom.
#
# 290 -> 289, 2026-09-21: `SignalRepositoryProtocol.get_paginated`'s PLR0913 suppression, paid by
# grouping its seven filter/sort arguments into a frozen `SignalListQuery` rather than by adding a
# `src/domain/ports` ignore. Measured as exactly one: two full runs BEFORE the change passed this
# test at 290.
#
# 272 -> 271, 2026-09-23 (CALCENRICH-1): `fast_feature_calculator_calculate_all.py`'s
# SIM108 suppression paid by converting the if/else into the ternary ruff wanted -- touched while
# wiring the opt-in TV-rule-stance step into the same file, so the touch-gate owed it.
#
# 271 -> 270, 2026-09-23: `chart_rsi_divergence_display.py` carried one suppression that went with
# its rewrite onto the shared pivot detector (515903ec4), and that commit never locked the gain.
# Measured per file against a detached worktree of the pre-session tree, NOT the working tree.
#
# 270 -> 267, same day, and the reason CORRECTS the line above. The working tree read 267 because
# `indicator_chart_capabilities.py` had lost three directives -- which the entry above called
# "uncommitted edits". They were verify.sh's OWN output: step 1 runs `ruff check ... --fix`, whose
# RUF100 deletes every directive the config has made redundant, and nobody had committed the result.
# Proven, not inferred: a clean worktree of HEAD, after one `./scripts/verify.sh`, held 27 files
# byte-identical to the 27 "foreign" dirty files in the shared tree. Committed with this line.
#
# 267 -> 266, 2026-09-25 (TOOLTIP-LIVE-1 touched `signal_pubsub_payload.py`): its TC001 suppression
# was a type-only import; it moved under TYPE_CHECKING instead of being suppressed.
#
# 266 -> 264, 2026-09-25 (AUDIT-LEGACY-1 and INSAMPLE-DOOR-1): the audit port's too-many-arguments
# suppression on list_logs is gone -- its ten keywords are the AuditLogQuery TypedDict -- and the
# select-confirm task's went when allow_in_sample moved inside `windows`.
#
# 264 -> 262, 2026-09-25 (HEATMAP-COLD-1): both liquidation-heatmap query services imported `User`
# for an annotation only; the import moved under TYPE_CHECKING instead of being suppressed.
#
# 262 -> 253, 2026-09-26 (BACKTEST-WINDOW-SOT-1): the three backtest routes' eight TC001/TC002
# import suppressions became per-file pyproject entries (FastAPI resolves those annotations at
# runtime -- the models_promote_rollback precedent), and run_backtest's C901/PLR0912/PLR0915 went
# because the handler was decomposed, not silenced.
#
# 252 -> 251, 2026-09-28 (Bulkowski actionable-alerts fix, 2ebeb39b9): the dispatch service's
# `NewsSentimentAlertDirection` import was annotation-only; it moved under TYPE_CHECKING instead of
# being suppressed (TC001). Measured: origin/master 252, HEAD 251.
#
# 251 -> 250, 2026-09-30 (LOG-POOL-LEAK, a0b124571): ohlcv_service's PLC0414 suppression on the
# merge_chart_display_frames re-export went -- the name is in the module's __all__, which is what makes it
# public. Measured by test_noqa_ratchet on the gate run: 250.
#
# 249 -> 245, 2026-10-02 (RETRAIN-LOOP touched training_tasks_job.py): its unused, F401-suppressed
# `import redis as sync_redis` was deleted (no test patches it any more) and its PLR0912 went because the
# lock-skip cancel moved into _cancel_skipped_duplicate; 2 more had left unrecorded. Measured: 245.
#
# 245 -> 244, 2026-10-03 (LOG-NOISE touched incremental_chart_feature_compute.py): its TC002-suppressed
# `import polars as pl` was annotation-only and moved under TYPE_CHECKING. Measured by test_noqa_ratchet: 244.
#
# 244 -> 243, 2026-10-03 (EDGE-BOOK-REBAL touched edge_book_execution_ccxt.py): the executor's
# ARG002-suppressed `user` parameter is now released with `del user` and a reason. Measured: 243.
#
# 243 -> 241, 2026-10-03 (CG-FLOW-OI touched the derivatives-flow and taker-flow query services): each
# had a TC001-suppressed `User` import used only in annotations; both moved under TYPE_CHECKING.
# Measured by test_noqa_ratchet on the full verify of fe19d85ee: 241.
# 241 -> 239, 2026-10-03: the counter now counts DIRECTIVES, not comments that mention noqa; the two src
# comments it stopped counting were prose (bulkowski_pattern_event_proxies, hyperliquid_whale_position_store).
# 223 -> 222 (2026-10-06, P1-8); 222 -> 219 (2026-10-08, stacking_trainer: fake F401 import + two ARG002 gone);
# 219 -> 218 (2026-10-09, P3-0d: the connection service's ccxt import moved under TYPE_CHECKING, its TC002 noqa gone).
# 218 -> 214 (2026-10-09, P3-0d batches A + B: TC001/TC002 imports moved under TYPE_CHECKING, an S108 path now tmp_path).
# 214 -> 211 (2026-10-10, P2-1g: backtest_baselines' two and backtest_run_helpers' one TC001 import under TYPE_CHECKING).
# 211 -> 210 (2026-10-11, TF-1M touched timeframes.py: its RUF002 noqa went with the en dash it excused).
# 210 -> 208 (2026-10-16, GATE-RED: measured at c9f50859d; the 10-15/16 slices paid two on touch).
# 208 -> 207 (2026-10-18, S2a LIQ-ONE: run_compound_backtest's C901 / PLR0915 noqa gone with its split; clean S2a tree).
# 207 -> 199 (2026-10-18, STOP-GAP: the lab callers' dead BLE001 noqa became logged tracebacks; clean tree).
# 191 -> 187 (2026-10-23, 8c trainers: random_forest_trainer 3 -> 0 and xgboost_trainer 1 -> 0 -- the fold fit's ARG002
# pair became a del, the rest left with the methods that moved into the bases; measured by test_noqa_ratchet).
# 187 -> 186 (2026-10-23, SWITCH-LUCK-CHECK touched block_bootstrap: its S311 noqa became a per-file pyproject entry with
# the measured reason -- a seeded stream is what a reproducible resample needs; measured by test_noqa_ratchet).
# 186 -> 182 (2026-10-24, LIVE-SOL-BOTH's gate run: four src directives gone in the 10-23 / 10-24 commits and never locked;
# measured by test_noqa_ratchet on the tree that commit carries).
NOQA_BASELINE = 181

#: a terminal colour code; public since 2026-11-03 -- engine_watch strips the live engine's log lines with it
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")

#: Trees the basedpyright touch-gate may check. ``src/`` was the only member until 2026-09-10.
#:
#: ``src/research/`` was added on owner instruction ("basedpyright-on-research ... add it
#: also") after a measured hole: ``llm_market_decision.py`` carried an UNDEFINED NAME
#: (``MIN_ABS_T_FOR_SIGNAL``) on the branch a weak IC takes, so the 8h, 6h and 1d runs each
#: raised a NameError immediately before printing their verdict — the band log shows their cert
#: lines with no VERDICT after them. ruff's bug-class pass (verify 2j) and mypy (verify 2k) do
#: cover research; basedpyright did not, and it was the tool that caught the scipy ``.statistic``
#: stub gap in that same file.
#:
#: A TUPLE, not a widened single prefix: the two trees are gated for different reasons, and a
#: future third should be a readable list entry rather than a regex nobody wants to parse.
_TYPECHECKED_PREFIXES = ("apps/api/src/", "apps/api/src/research/")

#: Research lint findings by path: the lab lives at src/research since 2026-10-03 (was scripts/research), its
#: tests under tests/. Production src/ is never a research finding.
_RESEARCH_FINDING_RE = re.compile(r"^(src/research|scripts|tests)/")
_API_DIR = Path(__file__).resolve().parents[3]
_LAB_TOP = "research"


def production_src_targets() -> list[str]:
    """Every top-level entry of src/ except the research lab, as cwd-relative (apps/api) paths.

    The full mypy/basedpyright gates scan THESE, not ``src``: the lab keeps its own crash-class and bug-class
    ratchets, and pyright's ``exclude`` cannot carve it out -- it also silences files passed EXPLICITLY, which
    is how touched lab files are type-checked at commit (measured 2026-10-03: 0 files analyzed).
    """
    src = _API_DIR / "src"
    return sorted(
        f"src/{entry.name}" for entry in src.iterdir() if entry.name not in {_LAB_TOP, "__pycache__"} and (entry.is_dir() or entry.suffix == ".py")
    )


def normalize_typecheck_relpaths(raw_paths: Iterable[str]) -> list[str]:
    """Map repo-root git paths to ``apps/api``-cwd relpaths inside a type-checked tree.

    Renamed from ``normalize_api_src_relpaths`` when ``src/research/`` joined the gate: the
    old name said ``src`` and would have become a lie the moment the second prefix landed, which
    is precisely the drift this repo keeps paying for.
    """
    relpaths: set[str] = set()
    for raw in raw_paths:
        path = raw.strip()
        if not path.startswith(_TYPECHECKED_PREFIXES):
            continue
        if not path.endswith(".py"):
            continue
        relpaths.add(path[len("apps/api/") :])
    return sorted(relpaths)


def parse_basedpyright_counts(payload: str) -> tuple[int | None, int | None]:
    """Return ``(errors, warnings)`` from basedpyright ``--outputjson``, or Nones."""
    try:
        data = json_object(json.loads(payload))
    except json.JSONDecodeError:
        return None, None
    summary = None if data is None else json_object(data.get("summary"))
    if summary is None:
        return None, None
    errors = summary.get("errorCount")
    warnings = summary.get("warningCount")
    if not isinstance(errors, int) or not isinstance(warnings, int):
        return None, None
    return errors, warnings


def count_research_bug_findings(concise_text: str) -> int:
    """Count ruff concise findings under ``scripts/`` or ``tests/`` after stripping ANSI."""
    count = 0
    for raw_line in concise_text.splitlines():
        line = ANSI_ESCAPE_RE.sub("", raw_line).strip()
        if not line:
            continue
        if _RESEARCH_FINDING_RE.match(line) is None:
            continue
        count += 1
    return count


#: A suppression DIRECTIVE: a hash then noqa (optionally a colon and codes), or the file-level ruff/flake8 form.
#: Not a comment that merely names noqa -- measured 2026-10-03, 2 such prose comments in src and 8 in this
#: module were counted, so documenting the noqa gate "owed" a reduction of debt that did not exist.
_NOQA_DIRECTIVE = re.compile(r"#\s*(?:(?:ruff|flake8)\s*:\s*)?noqa(?![\w-])", re.IGNORECASE)


def count_noqa_comments(source: str) -> int:
    """`noqa` COMMENTS in one source text -- a string or docstring that mentions noqa is not one.

    Tokenized rather than grepped: this repo's docstrings discuss `# noqa` constantly (this one
    does), and a text match would count every explanation as a suppression. Source that will not
    tokenize counts 0 here; ruff and mypy refuse that file long before this gate matters.
    """
    return count_comments_matching(source, _NOQA_DIRECTIVE)


def count_comments_matching(source: str, directive: re.Pattern[str]) -> int:
    """COMMENTS in one source text that match ``directive`` -- the one tokenize loop the noqa row and the
    type-suppression standards rule share (a docstring that mentions a directive is not one)."""
    return len(comment_lines_matching(source, directive))


def comment_lines_matching(source: str, directive: re.Pattern[str]) -> list[int]:
    """The 1-based line of each comment count_comments_matching counts (standards_rules' --list prints them)."""
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    try:
        return [tok.start[0] for tok in tokens if tok.type == tokenize.COMMENT and directive.search(tok.string)]
    except SyntaxError, tokenize.TokenError:
        return []


def classes_in(tree: ast.AST) -> Iterator[ast.ClassDef]:
    """Every class definition in ``tree``, nested ones included."""
    return (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef))


def line_span(node: ast.AST) -> range:
    """The physical lines ``node`` occupies (a node without an end line occupies its first)."""
    first = getattr(node, "lineno", 0)
    return range(first, (getattr(node, "end_lineno", None) or first) + 1)


def counted_lines(rows: Sequence[str], span: Iterable[int], skip: Container[int]) -> int:
    """The non-blank lines of ``span`` (1-based into ``rows``) outside ``skip`` -- a docstring, an import list."""
    return sum(1 for line in span if line not in skip and rows[line - 1].strip())


#: Two is the threshold, not one, and that is the load-bearing choice. A single `return None` is
#: an ordinary "not found" and says everything a caller needs. It is the SECOND silent path that
#: destroys information: from outside, two distinct situations become one answer, and a caller
#: cannot tell a healthy miss from a defect. `_get_from_redis` had three.
MIN_SILENT_PATHS = 2


def _is_procedure(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True when the function is annotated ``-> None`` and so returns no value at all.

    A DETECTOR DEFECT, found 2026-09-08 by hitting it: `append_forward_tape` is annotated
    ``-> None`` and uses two bare `return`s as early exits from three write strategies. The
    scanner counted them as silent answers, but this function has no answer to give -- the
    caller receives `None` on EVERY path, including the successful one, so the premise "two
    situations collapse into one indistinguishable answer" is vacuous here.

    Measured across `src/`: 16 of 186 flagged functions are procedures. Excluding them lowers the
    baseline rather than raising it, so the gate gets STRICTER on the code where a fall-through
    can actually hide something -- a function that returns a value on its success path.
    """
    returns = function.returns
    return isinstance(returns, ast.Constant) and returns.value is None


def _module_loggers(tree: ast.AST) -> frozenset[str]:
    """The names a module binds to ``logging.getLogger(...)`` at its top level -- its loggers, whatever it calls them
    (609 modules say `logger`; mexc_demo says `LOG`). SILENT-LOG, 2026-10-16: a function logging through `LOG` was
    read as silent."""
    body = tree.body if isinstance(tree, ast.Module) else []
    names: set[str] = set()
    for node in body:
        if isinstance(node, ast.Assign | ast.AnnAssign) and isinstance(node.value, ast.Call) and ast.unparse(node.value.func) == "logging.getLogger":
            names.update(t.id for t in (node.targets if isinstance(node, ast.Assign) else [node.target]) if isinstance(t, ast.Name))
    return frozenset(names)


def _emits(function: ast.AST, loggers: frozenset[str] = frozenset()) -> bool:
    """True when the function body contains anything that would reach an operator.

    Deliberately generous: any mention of `logger`/`logging`, a metric helper, or a raise. A
    function that RAISES is not silent -- the caller learns something -- so it is not counted
    even though it never logs.
    """
    for node in ast.walk(function):
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in {"logger", "logging", *loggers}:
            return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id.startswith(("emit_", "record_", "observe_", "increment_", "track_"))
        ):
            return True
    return False


def silent_return_functions(tree: ast.AST) -> list[str]:
    """Functions in ``tree`` returning None down >= MIN_SILENT_PATHS paths while emitting nothing.

    ONE predicate, two scopes: tests/unit/architecture/test_silent_return_ratchet.py counts it over
    the whole of src/ (the number may only fall), scripts/check_touched_debt.py counts it per touched
    file (whoever touches a file pays its share down). Moved here from that test on 2026-09-24 so
    the touch gate could call it without a gate script importing a test module.
    """
    found: list[str] = []
    loggers = _module_loggers(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        silent_paths = sum(
            1
            for child in ast.walk(node)
            if isinstance(child, ast.Return) and (child.value is None or (isinstance(child.value, ast.Constant) and child.value.value is None))
        )
        if silent_paths >= MIN_SILENT_PATHS and not _is_procedure(node) and not _emits(node, loggers):
            found.append(node.name)
    return found


def _cli_normalize_stdin() -> int:
    paths = [line.rstrip("\n") for line in sys.stdin]
    for rel in normalize_typecheck_relpaths(paths):
        print(rel)
    return 0


def _cli_parse_bp_stdin() -> int:
    payload = sys.stdin.read()
    errors, warnings = parse_basedpyright_counts(payload)
    if errors is None or warnings is None:
        print("unparseable")
        return 2
    print(f"{errors} {warnings}")
    return 0


def _cli_production_src() -> int:
    print(" ".join(production_src_targets()))
    return 0


def _cli_baseline() -> int:
    print(BASEDPYRIGHT_ERROR_BASELINE)
    return 0


def _cli_count_research_stdin() -> int:
    print(count_research_bug_findings(sys.stdin.read()))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI for bash: ``normalize-src`` | ``parse-bp`` | ``count-research`` | ``baseline`` | ``production-src``."""
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(
            "usage: verify_gate_helpers.py normalize-src|parse-bp|count-research|baseline|production-src",
            file=sys.stderr,
        )
        return 2
    command = args[0]
    if command == "normalize-src":
        return _cli_normalize_stdin()
    if command == "parse-bp":
        return _cli_parse_bp_stdin()
    if command == "count-research":
        return _cli_count_research_stdin()
    if command == "baseline":
        return _cli_baseline()
    if command == "production-src":
        return _cli_production_src()
    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
