"""Standards rules that had no gate: one spec each -- scope, per-file count, remedy, measured tree baseline.

IMPORTERS/CALLERS: scripts/check_touched_debt.py (one touch row per rule: a touched file lowers its count, a new file
brings none), scripts/verify.sh step 2f-std (``--tree``: every rule's total over HEAD, a rise or an unrecorded fall
fails), tests/scripts/test_standards_rules.py. AFFECTED API: none (library + CLI). DATA SCHEMAS: reads git blobs; the ruff
and basedpyright rows read the tracked files on disk (the basedpyright tree pass is ~56 s of the run, measured 2026-10-18).

STANDARDS-GATE-MAP (owner, 2026-10-12: "ONLY duplicated or ALL violations??? DRY, SRP, SOLID, ARCHITECTURE_PATTERNS,
DDD_PATTERNS, coding-standards"). docs/04-structural/STANDARDS_GATE_MAP.md maps every rule of those documents to the
gate that enforces it; the MECHANICAL rows that had none are counted here, each by the shape the rule names, so a new
one is one Rule entry -- never a new gate script.

REUSE-AUDIT: check_touched_debt's Metric + ratchet_touch.touch_violations (the one touch-to-lower rule) and
concept_definitions.sources_at_ref / in_scope (the scope and the one-round-trip git read) are reused. Considered
check_file_size_baseline.effective_line_count: a FILE count (imports and the module docstring discounted); a function
needs its own span, and keeps that rule's choice that comments count.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from src.lib.quality_gates.concept_definitions import GENERIC_NAME_LAB, in_scope, sources_at_ref
from src.lib.quality_gates.perf_rules import PANDAS_VET_CODES, PERF_LOOP_CODES, PERF_RULES
from src.lib.quality_gates.ratchet_touch import git
from src.lib.quality_gates.rule_spec import (
    API_ROOT,
    LAB_TESTS_PREFIX,
    LAB_WAIVER_PATTERNS,
    InstrumentUnavailableError,
    Rule,
    lab_waiver_codes,
    parsed,
    pyright_tree_total,
    ruff_binary,
    ruff_findings,
    ruff_tree_total,
)
from src.lib.quality_gates.standards_ast_rules import (
    MAX_FUNCTION_LINES,
    MAX_PROTOCOL_METHODS,
    fat_protocols,
    global_statements,
    io_properties,
    lab_silent_returns,
    long_functions,
    mutable_value_objects,
    nested_ternaries,
    numba_loop_reuse,
    numeric_http_status,
    print_calls,
    type_suppressions,
)

#: The names importers read from here; the rule shapes and the ruff / basedpyright instruments live in rule_spec / perf_rules.
__all__ = (
    "LAB_WAIVER_PATTERNS",
    "PANDAS_VET_CODES",
    "PERF_LOOP_CODES",
    "RULES",
    "InstrumentUnavailableError",
    "Rule",
    "measured_totals",
    "pyright_tree_total",
    "ruff_binary",
    "ruff_findings",
    "ruff_tree_total",
    "tree_totals",
)
_REPO: Final = API_ROOT.parents[1]
PRODUCT_PREFIX: Final = "apps/api/src/"
#: Gate tooling runs under the hooks' bare interpreter: the lab prefix is concept_definitions' (pinned to RESEARCH_ROOT_REL).
LAB_PREFIX: Final = GENERIC_NAME_LAB
CLI_PREFIX: Final = "apps/api/src/scripts/"
VALUE_OBJECTS: Final = "apps/api/src/domain/value_objects/"
#: No AST rule reads the tests (sources_at_ref is src + scripts); the ruff rows judge them, so the tree lists them.
TESTS_PREFIX: Final = "apps/api/tests/"
#: Every signature annotation ruff checks (ANN101 / ANN102 are removed from ruff). ANN401 stays with explicit_any: an
#: explicit Any is a type written down, only an unspecific one, and that ratchet counts every reference to it.
ANNOTATION_CODES: Final = ("ANN001", "ANN002", "ANN003", "ANN201", "ANN202", "ANN204", "ANN205", "ANN206")
#: basedpyright's unknown-type rules: a value whose type no checker can name, so nothing downstream of it is checked.
UNKNOWN_TYPE_RULES: Final = (
    "reportUnknownParameterType",
    "reportUnknownArgumentType",
    "reportUnknownVariableType",
    "reportUnknownMemberType",
    "reportUnknownLambdaType",
    "reportMissingParameterType",
    "reportMissingTypeArgument",
)


def _lab(path: str) -> bool:
    return path.startswith(LAB_PREFIX) and path.endswith(".py")


def _product(path: str) -> bool:
    return in_scope(path) and path.startswith(PRODUCT_PREFIX) and not path.startswith(LAB_PREFIX)


def _product_not_cli(path: str) -> bool:
    return _product(path) and not path.startswith(CLI_PREFIX)


def _signatures_judged(path: str) -> bool:
    """ANN-GATE (owner, 2026-10-18: "enforce annotations everywhere"): product code, CLIs, the lab, ops scripts and tests."""
    return in_scope(path) or (path.startswith(TESTS_PREFIX) and path.endswith(".py"))


#: Baselines measured over HEAD (3,666 files) on 2026-10-12, the day each rule got its gate.
_BASE_RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "nested-ternary",
        "nested conditional expressions",
        in_scope,
        nested_ternaries,
        "Use guard clauses / an if-elif or a lookup (CODING_STANDARDS 3.1).",
        # 99 -> 98, 2026-10-15 (train_model_data's epoch unit) -> 96 (10-16 paydown) -> 95 (10-17 lock)
        # -> 94 (10-18 lock, measured on the clean S2a tree: S1 / SAME-VALUE / S2a paydowns).
        # -> 89 (10-19 lock, measured on the clean 8b-RSI tree).
        # -> 88 (10-19 8b-ATR lock, measured at the commit's own HEAD: 8b-RSI had read the previous HEAD's blobs).
        # -> 84 (10-19 8b-ATR part 2: chandelier x2 dead branch, ts_rule_zoo label, lux bias; at the commit's own tree).
        # -> 83 (10-19 an earlier fall left unlocked, measured at the commit's own tree).
        # -> 81 (10-22 ZOO-STACK lock, measured at the commit's own tree).
        80,
    ),
    Rule(
        "type-suppression",
        "`type: ignore` / `pyright: ignore` comments",
        in_scope,
        type_suppressions,
        "Type it (a TypedDict, a Protocol, a narrowing) instead of switching the check off.",
        # 397 -> 391, 2026-10-15 (njit_cached: the thin-stop kernels; train_model_data) -> 389 (10-16 lock) -> 383 -> 381 (10-17 lock)
        # -> 376 (10-18 lock, measured on the clean S2a tree: S1 / SAME-VALUE / S2a paydowns).
        # -> 365 (10-19 lock, measured on the clean 8b-RSI tree).
        # -> 363 (10-19 8b-ATR lock, measured at the commit's own HEAD: 8b-RSI had read the previous HEAD's blobs).
        # -> 361 (10-19 SOL-RESTART-DIVERGENCE lock, measured at the commit's own tree).
        # -> 360 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 1 of its findings).
        # -> 359 (10-20 8f FIFO-BLIND lock, measured at the commit's own tree).
        # -> 357 (10-22 ZOO-STACK lock, measured at the commit's own tree).
        # -> 356 (10-23 lock, measured at 9952f6df1).
        355,
    ),
    Rule(
        "numba-loop-reuse",
        "reused for-targets in @njit / @jit functions",
        in_scope,
        numba_loop_reuse,
        "Give each loop its own variable (CODING_STANDARDS 8.3).",
        # -> 37 (10-19 lock, measured on the clean 8b-RSI tree).
        # -> 35 (10-19 8b-ATR lock, measured at the commit's own HEAD: 8b-RSI had read the previous HEAD's blobs).
        # -> 34 (10-23 lock, measured at 9952f6df1).
        34,
    ),
    Rule(
        "long-function",
        f"functions over {MAX_FUNCTION_LINES} effective lines",
        in_scope,
        long_functions,
        "Split by responsibility (CODING_STANDARDS 9.1).",
        # 295 -> 292, 2026-10-15 (pipeline run state, fit's sample weights, the CLI parser groups) -> 291 (10-16 lock) -> 285 (10-17 lock)
        # -> 282 (10-18 lock, measured on the clean S2a tree: S1 / SAME-VALUE / S2a paydowns).
        # -> 278 (10-18, S2d: determine_exit, post_backtest_run and the worker's run split by responsibility; clean S2d tree).
        # -> 271 (10-18, STOP-GAP: the walk-forward runner, the lab mains it touched and the sweep batch split; clean tree).
        # -> 269 (10-18, 8g IMPORTANCE-ALWAYS: the training files it touched; clean tree).
        # -> 262 (10-19 lock, measured on the clean 8b-RSI tree).
        # -> 261 (10-19 8b-ATR part 2: ts_rule_zoo.main split; at the commit's own tree).
        # -> 258 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 3 of its findings).
        # -> 254 (10-20 8f FIFO-BLIND: the stress registry dispatch, the scout batches split; at the commit's own tree).
        # -> 249 (10-22 ZOO-STACK lock, measured at the commit's own tree).
        # -> 247 (10-23 lock, measured at 9952f6df1).
        246,
    ),
    # global-statement: 113 -> 110 (10-17 lock)
    # global-statement: 110 -> 109 (10-18, DB-POOL-TRACE: database.py's session-maker cache owns its state; clean tree).
    # -> 108 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 1 of its findings).
    Rule("global-statement", "`global` statements", in_scope, global_statements, "Pass the state in, or own it in an object (DIP).", 107),
    Rule(
        "numeric-http-status",
        "HTTP statuses written as bare ints",
        _product,
        numeric_http_status,
        "Use fastapi.status names (CODING_STANDARDS 12).",
        25,  # 29 -> 27 (10-16 lock) -> 25 (10-20 8f FIFO-BLIND lock, measured at the commit's own tree)
    ),
    # print-call: 46 -> 40 (10-22 ZOO-STACK lock, measured at the commit's own tree).
    Rule("print-call", "`print` calls in product code", _product_not_cli, print_calls, "Log it (the log watch reads the logger, not stdout).", 40),
    Rule(
        "fat-protocol", f"Protocols / ABCs over {MAX_PROTOCOL_METHODS} methods", _product, fat_protocols, "Split the interface by client (ISP).", 13
    ),
    Rule(
        "mutable-value-object",
        "value-object dataclasses not frozen",
        lambda p: p.startswith(VALUE_OBJECTS),
        mutable_value_objects,
        "@dataclass(frozen=True): a value object is immutable.",
        0,
    ),
    Rule(
        "io-property", "@property bodies doing I/O", _product, io_properties, "Make it a method -- an attribute read must not hide a round trip.", 1
    ),
    # SGM-2: the lab and docstrings, counted by ruff (noqa and per-file ignores respected, as ruff reads them)
    Rule(
        "lab-complexity",
        "lab complexity findings (C901 / PLR0912 / PLR0915)",
        _lab,
        None,
        "Split the function by responsibility (SRP).",
        # -> 220 (10-19 8b-ATR part 2: ts_rule_zoo.main split; at the commit's own tree).
        # -> 215 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 5 of its findings).
        # -> 210 (10-20 8f FIFO-BLIND: the touched scout / stress mains split; at the commit's own tree).
        # -> 207 (10-22 ZOO-STACK lock, measured at the commit's own tree).
        206,  # 246 -> 243 (10-17 lock) -> 233 (10-18 STOP-GAP) -> 221 (10-19 EXIT-WEIGHTED-TRAIL: the parity ports it touched split)
        ("C901", "PLR0912", "PLR0915"),
        waived=True,
    ),
    Rule(
        "lab-silent-failure",
        "lab swallowed exceptions (BLE001 / S110 / S112)",
        _lab,
        None,
        "Catch the exception you mean; say so when you skip one.",
        # -> 175 (10-19 lock, measured on the clean 8b-RSI tree).
        # -> 168 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 7 of its findings).
        # -> 161 (10-20 8f FIFO-BLIND: the scout batches catch DETECTOR_CANNOT_RUN / httpx.HTTPError; at the commit's own tree).
        # -> 158 (10-22 ZOO-STACK lock: an earlier fall left unlocked, measured at the commit's own tree).
        # -> 157 (10-23 lock, measured at 9952f6df1).
        157,  # 179 -> 178 (10-18 STOP-GAP) -> 177 (10-19 EXIT-WEIGHTED-TRAIL: the edge_lab SMC lane raises LaneSeriesError)
        ("BLE001", "S110", "S112"),
        waived=True,
    ),
    Rule(
        "lab-silent-return",
        "lab functions returning None down 2+ paths, emitting nothing",
        _lab,
        lab_silent_returns,
        "Emit on the path that matters, or raise.",
        # 110 -> 108 (10-18, GIT-CLEAN 2: binance_vision_metrics / data_1m / sltp_multicoin / arm87_model paid on touch; clean tree)
        # -> 107 (10-18, STOP-GAP; clean tree).
        # -> 105 (10-19 lock, measured on the clean 8b-RSI tree).
        # -> 104 (10-19 8b-ATR lock, measured at the commit's own HEAD: 8b-RSI had read the previous HEAD's blobs).
        # -> 103 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 1 of its findings).
        # -> 100 (10-20 8f FIFO-BLIND lock, measured at the commit's own tree).
        99,
    ),
    Rule(
        "lab-magic-number",
        "lab magic values in comparisons (PLR2004)",
        _lab,
        None,
        "Name the threshold (CODING_STANDARDS 12).",
        # 1437 -> 1430 (10-16 lock) -> 1429 (10-16 paydown) -> 1426 (10-17 lock)
        # -> 1423 (10-18 lock, GIT-CLEAN 2).
        # -> 1406 (10-18, STOP-GAP: the 500-bar floor, the F3 thresholds, the sweep's IC floor named; backfill reads the
        # resolver's MAX_FLAT_BAR_SHARE; clean tree).
        # -> 1313 (10-19 lock, measured on the clean 8b-RSI tree).
        # -> 1300 (10-19 8b-ATR part 2: ts_rule_zoo / mom_trail_stop / supertrend / edge_lab thresholds named).
        # -> 1299 (10-19 GIT-CLEAN-1: gb_pine's CLI an argparse, no argv index compared).
        # -> 1296 (10-19 GIT-CLEAN-1 C: meta_wt_screen's 7/10 + t bar and script_b40's win_low95 floor named).
        # -> 1281 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 15 of its findings).
        # -> 1252 (10-20 8f FIFO-BLIND: the rule-book cell's four copies one home, the touched thresholds named).
        # -> 1246 (10-22 ZOO-STACK: 3 named in the touched files, 3 an earlier fall left unlocked; at the commit's own tree).
        1241,  # MEASURED 1406 -> 1327 on the clean tree (10-19 EXIT-WEIGHTED-TRAIL: the touched parity thresholds named)
        ("PLR2004",),
        waived=True,
    ),
    Rule(
        "lab-bug-class",
        "lab blocking calls in async, SQL built from strings, eval (ASYNC / S608 / S307)",
        _lab,
        None,
        "Await the async API, bind SQL parameters, parse with ast.literal_eval.",
        26,
        ("ASYNC", "S608", "S307"),
        waived=True,
    ),
    Rule(
        "missing-docstring",
        "public classes / functions without a docstring (D101 / D103)",
        _product,
        None,
        "Say what it is for (CODING_STANDARDS 6).",
        # 560 -> 559 (10-14) -> 545 (10-15, config_training_helpers) -> 536 (10-16 lock) -> 528 (concept_definitions) -> 525 (10-17 lock)
        # -> 518 (10-18 lock, measured on the clean S2a tree: S1 / SAME-VALUE / S2a paydowns).
        # -> 515 (10-18, S2b: three sizing definitions documented; clean S2b tree).
        # -> 507 (10-18, S2d: the eight BacktestRequest validators documented; clean S2d tree).
        # -> 504 (10-18, STOP-GAP: the recompute gate's three entry points documented; clean tree).
        # -> 501 (10-19, 8b-EMA part 1: titan's three public functions documented; at the commit's own tree).
        # -> 500 (10-19 measured at the commit's own tree).
        # -> 499 (10-20 8f FIFO-BLIND lock, measured at the commit's own tree).
        # -> 496 (10-23 lock, measured at 9952f6df1).
        494,
        ("D101", "D103"),
    ),
    Rule(
        "deep-nesting",
        "blocks nested too deep (PLR1702)",
        in_scope,
        None,
        "Return early or extract a function (CODING_STANDARDS 3).",
        # -> 34 (10-22 ZOO-STACK lock, measured at the commit's own tree).
        34,  # 45 -> 40 (10-19, EXIT-WEIGHTED-TRAIL: the parity loops it touched vectorised or split; clean tree)
        ("PLR1702",),
        preview=True,
    ),
    # ANN-GATE (owner, 2026-10-18: "you CAN'T commit if you didn't add the annotation on params"). Product code is at 0
    # (mypy strict + ruff ANN); the count is the lab's and the tests', which pyproject exempts, counted through every
    # exemption and past noqa. The lab's ANN001 / ANN201 / ANN202 moved here from lab-ruff, one row per finding.
    Rule(
        "missing-annotation",
        "unannotated parameters / returns (ANN001-ANN206)",
        _signatures_judged,
        None,
        "Annotate the signature with the domain type (CODING_STANDARDS 5.1): a parameter says what it takes, a return "
        "what it gives -- a TypedDict / dataclass / Protocol for a shape, never a bare dict or Any.",
        # 2277 over HEAD 2026-10-18 (src + scripts + tests, 6,530 tracked files): lab 1,106 + tests 1,170 + ops scripts 1, product 0.
        # -> 2274 (10-18, STOP-GAP: the lab callers it touched annotated; clean tree).
        # -> 2259 (10-18, 8g IMPORTANCE-ALWAYS: the training files it touched; clean tree).
        # -> 2249 (10-19, 8b-ATR part 2: the touched lab files' helpers annotated; at the commit's own tree).
        # -> 2243 (10-19, 8b-EMA part 1: the llm reuse test's fixture typed; at the commit's own tree).
        # -> 2235 (10-19, GIT-CLEAN-1 C: meta_wt_screen's barrier kernel typed).
        # -> 2203 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 29 of its findings; test_check_clone_baseline typed, 3).
        # -> 2181 (10-20 8f FIFO-BLIND: the touched lab and test signatures typed; at the commit's own tree).
        # -> 2179 (10-20 8f roster-stub leak: the roster-swap tests' monkeypatch typed; at the commit's own tree).
        # -> 2177 (10-22 ZOO-STACK lock, measured at the commit's own tree).
        # -> 2169 (10-23 lock, measured at 9952f6df1).
        2151,
        ANNOTATION_CODES,
        everywhere=True,
        ignore_noqa=True,
    ),
    Rule(
        "unknown-type",
        "values of unknown type (basedpyright reportUnknown* / reportMissingTypeArgument)",
        _product,
        None,
        "Name the type where inference cannot (an empty container, a None start, a bare list / dict, an untyped "
        "library's return): annotate that one binding, or give the payload a TypedDict / dataclass (CODING_STANDARDS 5.1).",
        # 3348 over HEAD 2026-10-18 (2,058 product files, 448 holding one; twice, 56 s each): member 1,192, variable 1,078,
        # argument 1,050, lambda 28 -- parameter / missing-parameter / type-argument 0 (mypy strict holds those).
        # -> 3274 (10-18, STOP-GAP: the regime gate on arrays, the touched lab callers and the touched gate files typed; clean tree).
        # -> 3268 (10-18, 8g IMPORTANCE-ALWAYS: the training files it touched; clean tree).
        # -> 3242 (10-18, LIVE-VENUE-PRICES: lighter_ws / binance_klines / trade_stream frames through json_rows; clean tree).
        # -> 3235 (10-18, PANDAS-OUT 4: mexc_bars' kline payload through json_rows, its page list typed: 7 -> 0).
        # -> 3222 (10-19 lock, measured on the clean 8b-RSI tree).
        # -> 3193 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 29 of its findings; read in the main checkout's venv).
        # -> 3185 (10-20 HEAD-RED: carry_execution_ccxt's wallet reads typed through json_object / float_or_none; main venv).
        # -> 3178 (10-20 8f FIFO-BLIND: the joblib seam typed object, the backtest prediction wrapper typed; main venv).
        # -> 3147 (10-22 ZOO-STACK lock, measured at the commit's own tree).
        # -> 3108 (10-23 lock, measured at 9952f6df1; 3152 before the 8c trainer move ca1503cc0, 3108 after it).
        # -> 3087 (10-28 ENGINE-PERF-BUGS lock, measured on the tree that commit carries).
        # -> 3082 (11-01 MEXC-OUT lock, verify at b4a6185b0); -> 3081 (11-03 i5 lock, verify --fast at 8cce53570).
        3081,  # -> 3230 (10-19 EXIT-WEIGHTED-TRAIL: untyped jit gone, pl.any_horizontal, be87 floats; clean tree)
        pyright_rules=UNKNOWN_TYPE_RULES,
    ),
    *PERF_RULES,
)


def _lab_or_tests(path: str) -> bool:
    return _lab(path) or path.startswith(LAB_TESTS_PREFIX)


def _unowned_lab_codes(rules: tuple[Rule, ...]) -> tuple[str, ...]:
    """The waived codes no other lab row counts (a row's code owns every code it prefixes: ASYNC owns ASYNC240)."""
    owned = [c for r in rules if r.waived or r.everywhere for c in r.ruff_codes]
    return tuple(code for code in lab_waiver_codes() if not any(code.startswith(o) for o in owned))


# 10-24 lock, every row above and lab-ruff below (LIVE-SOL-BOTH's gate run, the tree that commit carries): nested-ternary
# 80, type-suppression 355, long-function 246, lab-complexity 206, lab-silent-return 99, lab-magic-number 1241,
# missing-docstring 494, missing-annotation 2151, unknown-type 3089 (3088 at 8321f931a's own tree, global-statement 107), lab-ruff 6674.
#: RUFF-RESEARCH (owner, 2026-10-13: "ruff should pass over it also"): the lab left ruff's exclude, and every finding
#: it already carried is waived per code in pyproject -- this row counts the waived codes no row above owns.
RULES: Final[tuple[Rule, ...]] = (
    *_BASE_RULES,
    Rule(
        "lab-ruff",
        "lab ruff findings the pyproject waiver hides (every waived code no row above owns)",
        _lab_or_tests,
        None,
        "Fix the finding where you touch the file (a sys.path import becomes a package import, a magic value a named "
        "constant, ...); drop a code from the waiver in pyproject when its count reaches 0 -- never add one.",
        # 8124 (10-13) -> 8115 (unlocked paydown) -> 7971 (perf-loops / pandas-vet own codes) -> 7966 (10-14 paydown)
        # -> 7951 (10-16 lock) -> 7888 (10-16 paydown) -> 7622 (10-17 lock: RUFF-FORMAT-LAB and the 10-17 paydowns)
        # -> 7619 (10-18 lock, measured on the clean S2a tree: PANDAS-OUT 1/2's lab ruff fixes).
        # -> 7607 (10-18 lock, GIT-CLEAN 2: the touched lab files paid down).
        # -> 7219 (10-18, ANN-GATE, measured on the clean merged tree): ANN001 / ANN201 / ANN202 moved to missing-annotation;
        # the lab tests the touch row judged are now in the tree too, counted through the lab waiver only, so a lab test is
        # no longer charged the tests' own conventions (290 unused-fixture ARG / ERA001 findings).
        # -> 7111 (10-18, STOP-GAP: fourteen lab scripts run as modules, no sys.path bootstrap; clean tree).
        # -> 6975 (10-19 lock, measured on the clean 8b-RSI tree).
        # -> 6964 (10-19 8b-ATR part 2: casts quoted in ts_rule_zoo, src imports lifted, shim lines split, an import sorted).
        # -> 6957 (10-19 GIT-CLEAN-1: article_ml / gb_pine / test_article_ml imports lifted, long lines split, an assert split).
        # -> 6948 (10-19 GIT-CLEAN-1 B: the mexc_demo report tests' compound asserts split, an import sorted).
        # -> 6937 (10-19 GIT-CLEAN-1 C: arm-87 / arm-38 imports one alias a line, long lines split, test lint fixed).
        # -> 6878 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 59 of its findings).
        # -> 6748 (10-20 8f FIFO-BLIND: sys.path bootstraps and blanket noqa gone from the touched lab; at the commit's own tree).
        # -> 6686 (10-22 ZOO-STACK: 9 paid in the touched z12 files, the rest an earlier fall left unlocked; commit's tree).
        # -> 6683 (10-23 lock, measured at 9952f6df1).
        # -> 6669 (10-28 ENGINE-PERF-BUGS lock, measured on the tree that commit carries).
        # -> 6663 (10-29 NEWS-ARMS: macro_break_5m (arm 48, KILL) moved to _archive/, its 6 left the scope).
        # -> 6661 (11-01 MEXC-OUT lock, verify at b4a6185b0); -> 6660 (11-03: the bot port's unused args, verify --fast at 8cce53570).
        6660,  # -> 7010 (10-19 EXIT-WEIGHTED-TRAIL: the touched parity ports + model_feed paid down; clean tree)
        _unowned_lab_codes(_BASE_RULES),
        waived=True,
        ignore_noqa=True,
    ),
)


def tree_totals(sources: Mapping[str, str], rules: tuple[Rule, ...] = RULES) -> dict[str, int]:
    """Each AST / regex rule's total over ``sources`` (path -> text); ruff-backed rules stay 0 here."""
    totals = dict.fromkeys((r.key for r in rules), 0)
    for path, source in sources.items():
        tree = None
        for rule in rules:
            if not rule.applies(path):
                continue
            if rule.path_sites is not None:
                totals[rule.key] += len(rule.path_sites(path, source))
            elif rule.sites is not None:
                tree = tree if tree is not None else parsed(source)
                totals[rule.key] += 0 if tree is None else len(rule.tree_sites(tree, source))
    return totals


def tracked_tests(repo: Path) -> list[str]:
    """Every test module tracked at HEAD (the ruff rows judge tests; no AST rule reads them)."""
    listing = git(repo, "ls-tree", "-r", "-z", "--name-only", "HEAD", "--", TESTS_PREFIX).decode().split("\0")
    return [path for path in listing if path.endswith(".py")]


def measured_totals(repo: Path) -> dict[str, int]:
    """Every rule's total over HEAD: AST rules from the blobs, ruff and basedpyright rules over the tracked files on disk."""
    sources = sources_at_ref(repo, "HEAD")
    tracked = {*sources, *tracked_tests(repo)}
    totals = tree_totals(sources)
    totals.update({rule.key: ruff_tree_total(rule, repo, tracked) for rule in RULES if rule.ruff_codes})
    totals.update({rule.key: pyright_tree_total(rule, repo, tracked) for rule in RULES if rule.pyright_rules})
    return totals


def ratchet_standards(repo: Path) -> int:
    """Print every rule's total over HEAD against its baseline; 1 when one rose or fell unrecorded, else 0."""
    totals = measured_totals(repo)
    code = 0
    for rule in RULES:
        total = totals[rule.key]
        print(f"{rule.key}: {total} {rule.unit} (baseline {rule.baseline})")
        if total != rule.baseline:
            code = 1
            verb = (
                "ROSE -- pay it down, never raise the baseline" if total > rule.baseline else "fell -- lower its baseline in RULES to lock the gain"
            )
            print(f"  {verb}")
    return code


def list_findings(paths: list[str], rules: tuple[Rule, ...] = RULES) -> int:
    """Print every rule's findings in ``paths`` (apps/api-relative or repo-relative files, as they are on disk), one
    ``L<line> ...`` per finding -- what a touched file's row counts, located. 0 always (a listing, not a gate)."""
    for given in paths:
        rel = given if given.startswith("apps/api/") else f"apps/api/{given}"
        source = (API_ROOT.parents[1] / rel).read_text(encoding="utf-8")
        for rule in rules:
            found = rule.locate(rel, source) if rule.applies(rel) else []
            if found:
                print(f"{rel}  {rule.key}: {len(found)} {rule.unit}")
                print("".join(f"    {line}\n" for line in found), end="")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry (verify step 2f-std); ``--list PATH ...`` prints each rule's findings in those files instead."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--repo-root", type=Path, default=_REPO)
    parser.add_argument("--list", nargs="+", metavar="PATH", help="print where each rule's findings are in these files")
    args = parser.parse_args(argv)
    return list_findings(args.list) if args.list else ratchet_standards(args.repo_root)


if __name__ == "__main__":
    sys.exit(main())
