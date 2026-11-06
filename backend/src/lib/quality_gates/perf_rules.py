"""The performance / pandas ratchet rows: loop and comprehension findings, pandas-vet / NumPy codes, row-wise pandas shapes.

IMPORTERS/CALLERS: src/lib/quality_gates/standards_rules.py (PERF_RULES is appended to its rule table), tests/scripts/test_standards_rules.py.
AFFECTED API: none (library). DATA SCHEMAS: none (rows are Rule values; baselines are measured counts over HEAD).

REUSE-AUDIT: moved from standards_rules.py (a 421-effective-line file over the 400 cap) along the seam "the PERF-RATCHET rows";
Rule comes from rule_spec, the counters from pandas_debt; no logic and no baseline changed.
"""

from __future__ import annotations

from typing import Final

from src.lib.quality_gates.concept_definitions import in_scope
from src.lib.quality_gates.pandas_debt import loop_sites, runtime_debt_lines
from src.lib.quality_gates.rule_spec import Rule

#: Ruff's loop / comprehension performance rules (researched 2026-10-14 in ruff 0.15's rule index): perflint, the
#: refurb loop rules (repeated append, writes / set mutations / readlines in a loop, unused enumerate), the
#: comprehension rules, RUF015 (first element by allocation) / RUF017 (quadratic list flattening), and the pylint
#: lookups-in-a-loop. Most are selected in pyproject and so already clean in product code; the lab waiver hides the rest.
PERF_LOOP_CODES: Final = ("PERF", "FURB113", "FURB122", "FURB129", "FURB142", "FURB148", "C4", "RUF015", "RUF017", "PLR1733", "PLR1736", "PLW3301")
#: pandas-vet / NumPy codes that are about speed or correctness. NOT PD008 / PD009 (.at / .iat -> .loc / .iloc: the
#: scalar accessors are the FASTER ones) nor the style-only PD003 / PD004 / PD010 / PD012 / PD013 / PD015.
PANDAS_VET_CODES: Final = ("PD002", "PD011", "PD101", "NPY")

# PERF-RATCHET (owner, 2026-10-14: "a ratchet like ruff, linters, duplicates ... to detect performance, pandas ...
# for loop -> flat list, etc"; researched first -- pandas_debt.py's docstring). Counted past the lab waiver and past
# suppression comments: a suppressed slow loop is still a slow loop.
PERF_RULES: Final[tuple[Rule, ...]] = (
    Rule(
        "perf-loops",
        "loop / comprehension performance findings (PERF, FURB loop rules, C4, RUF015 / RUF017 flatten, PL loop lookups)",
        in_scope,
        None,
        "Build it with a comprehension / dict comprehension, flatten with itertools.chain.from_iterable (never sum(lists, [])), "
        "extend instead of repeated append, hoist try / lookups out of the loop -- or vectorise it (numpy / polars / numba).",
        # 225 over HEAD 2026-10-14 (3,697 files), past the lab waiver and suppressions;
        # -> 222 (10-16 lock) -> 215 (10-17 lock) -> 214 (10-18 lock) -> 211 (10-18, STOP-GAP; clean tree)
        # -> 209 (10-19, EXIT-WEIGHTED-TRAIL; clean tree)
        # -> 208 (10-19 GIT-CLEAN-1 C: ladder87's coin ladder extends instead of appending in a loop).
        # -> 205 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 3 of its findings).
        # -> 198 (10-20 8f FIFO-BLIND lock, measured at the commit's own tree).
        # -> 197 (10-22 ZOO-STACK lock, measured at the commit's own tree).
        # -> 196 (10-24 lock, LIVE-SOL-BOTH's gate run, measured on the tree that commit carries).
        196,
        PERF_LOOP_CODES,
        preview=True,
        waived=True,
        ignore_noqa=True,
    ),
    Rule(
        "pandas-vet",
        "pandas / NumPy speed and correctness findings (PD002 inplace, PD011 .values, PD101 nunique, NPY)",
        in_scope,
        None,
        "to_numpy() over .values, assign instead of inplace=True, a cheap constant check over nunique(), np.random.default_rng.",
        # measured over HEAD 2026-10-14 (3,697 files), past the lab waiver and suppressions; -> 154 (10-17 lock) -> 134 (10-18 STOP-GAP)
        # -> 133 (10-19, EXIT-WEIGHTED-TRAIL: long_signal_a's .values gone with its pandas SMA; clean tree)
        # -> 121 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 12 of its findings).
        # -> 117 (10-20 8f FIFO-BLIND lock, measured at the commit's own tree).
        # -> 115 (10-23 lock, measured at 9952f6df1).
        115,
        PANDAS_VET_CODES,
        waived=True,
        ignore_noqa=True,
    ),
    Rule(
        "pandas-loop",
        "row-wise / growth-in-loop pandas shapes (iterrows, apply, concat / np.append in a loop, .loc / .iat in a loop, ...)",
        in_scope,
        lambda tree, _source: [line for line, _kind in loop_sites(tree)],
        "Vectorise: numpy / polars expressions, numba @njit(cache=True) for a true loop; collect the parts and concat ONCE.",
        # 2,382 before the shapes were tightened by sampling -> 1210 (10-16 lock) -> 1206 (10-16 paydown)
        # -> 1202 (10-19 lock, measured on the clean 8b-RSI tree).
        # -> 1188 (10-19 8b-ATR part 2: the ATR loops and .iloc walks numpy, top-q weights vectorised; at the commit's own tree).
        # -> 1187 (10-19 GIT-CLEAN-1: gb_pine's exported-tree check walks the rows as numpy, not one eval a row).
        # -> 1179 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 8 of its findings).
        # -> 1178 (10-23 lock, measured at 9952f6df1).
        # -> 1177 (10-24 lock, LIVE-SOL-BOTH's gate run, measured on the tree that commit carries).
        # -> 1176 (10-28 ENGINE-PERF-BUGS: rolling_origin_cadence_validator's per-date .loc walk is numpy rows; commit's tree).
        # -> 1175 (11-01 MEXC-OUT lock, measured by verify at b4a6185b0).
        1175,  # measured over HEAD 2026-10-14 (3,697 files); -> 1204 (10-17 lock) -> 1203 (10-18 STOP-GAP)
    ),
    Rule(
        "pandas-undeclared",
        "lines running pandas with no verified edge (types need none)",
        in_scope,
        None,
        "Write it with numpy / polars / numba -- or, where an SoT hands you a DataFrame, name that callee on the line "
        "after PANDAS-OK: (its own signature must take or return pandas).",
        # ONE-MEASURE, 2026-10-15: runtime_debt over HEAD (the line regex read 8,011) -> 3359 -> 3351 (10-16) -> 3338 (10-17 lock)
        # -> 3336 (10-18 lock, measured on the clean S2a tree: PANDAS-OUT 1/2's chart walk).
        # -> 3333 (10-18, GIT-CLEAN 2: binance_vision_metrics / data_1m / sltp_multicoin / arm87_model paid on touch; clean tree).
        # -> 3316 (10-18, STOP-GAP: the regime gate on arrays, buy-and-hold's one home, the touched lab loaders; clean tree).
        # -> 3313 (10-18, PANDAS-OUT 3: bar_parity compares the engine's numpy bars; clean tree).
        # -> 3312 (10-18, PANDAS-OUT 4: mexc_bars merges its REST pages as numpy rows, the frame built once).
        # -> 3306 (10-19 lock, measured on the clean 8b-RSI tree).
        # -> 3295 (10-19 8b-ATR lock, measured at the commit's own HEAD: 8b-RSI had read the previous HEAD's blobs).
        # -> 3281 (10-19 8b-ATR part 2: the ATR copies' pandas, four breakout frames one, tv / edge_lab boundaries one each).
        # -> 3278 (10-19 GIT-CLEAN-1: article_ml / gb_pine read the bars through one perp5m_bars).
        # -> 3276 (10-19 GIT-CLEAN-1 B: the demo-ledger frame built where EC.event_gaps takes it, a no-op to_datetime gone).
        # -> 3269 (10-19 GIT-CLEAN-1 C: ladder87's date shifts on the standard library, the coin stacks one helper each).
        # -> 3222 (10-19 ARCHIVE-EXEMPT: _archive/ left the scope, 47 of its findings).
        # -> 3192 (10-20 8f FIFO-BLIND: the scout batches on fetch_oos_bars, trend_scalp's crossings numpy).
        # -> 3187 (10-22 ZOO-STACK: the z12 walk-forward on numpy, the panel screen's hour of day; at the commit's own tree).
        # -> 3170 (10-23 lock, measured at 9952f6df1).
        # -> 3165 (10-24 lock, LIVE-SOL-BOTH's gate run, measured on the tree that commit carries).
        # -> 3161 (10-28 ENGINE-PERF-BUGS: the cadence validator's two frames numpy, an earlier fall of 2; commit's tree).
        # -> 3154 (10-29 NEWS-ARMS: macro_break_5m (arm 48, KILL) moved to _archive/, its 7 left the scope).
        # -> 3153 (11-01 MEXC-OUT lock, measured by verify at b4a6185b0).
        3153,
        path_sites=runtime_debt_lines,
    ),
)
