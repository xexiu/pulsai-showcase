"""Functions that return None down several paths WITHOUT emitting are capped and may only fall.

Owner, 2026-09-07: *"why hook werent firing and blocking you??? WHY?¿? Fix hooks in paralel"* --
after a day in which every defect found was invisible in its own logs.

THE SHAPE, measured on `_get_from_redis` the same day. It returned None when the cache was
absent, None when the frame was empty, and None when it held fewer closed bars than asked. Three
different situations -- a cold cache, a healthy miss, and a cache STRUCTURALLY too small to ever
answer -- collapsed into one silent `return None`, and only the third is a defect. It survived
long enough to be found by dumping a Redis blob by hand, because nothing anywhere said which of
the three had happened.

REUSE-AUDIT: considered tests/unit/architecture/test_blind_except_ratchet.py -- the same
instrument for the sibling failure (a swallowed EXCEPTION rather than a swallowed BRANCH), and
this mirrors its structure deliberately rather than inventing a second shape; not extending it
because BLE001 is a ruff rule about `except`, and no ruff rule expresses "returns None several
ways and tells nobody". Considered apps/api/scripts/check_clone_baseline.py and
python_file_size_baseline.json -- the same ratchet pattern as a verify step; not extending
because those measure duplication and length and this needs an AST walk. Considered
.claude/hooks/observability_claim_needs_a_signal_guard.py (mine, today) -- it blocks the CLAIM
that a defect is visible; this counts the code that makes such claims necessary. Complementary:
one polices what is said, the other what exists. The name-similar files the reuse check offered
(alembic `*_return_*` migrations, delete_low_return_backtests.py, FINDINGS_*_returns_*.md) all
match "return" in the FINANCIAL sense and are unrelated.

MEASURED 2026-09-07 on `src/`: 7,673 functions, of which 315 return None down two or more paths.
203 of those emit nothing at all; 112 already log something.

WHY A RATCHET AND NOT A RULE. Most of the 203 are correct -- a predicate returning None for
"unknown" owes no one a log line. Turning this into a hard rule would fail the build 203 times
and be switched off by the first person it inconvenienced, which is the argument
`test_blind_except_ratchet` makes about its own 344. So this pins the number: it does not demand
the debt be paid, it demands it stop growing.

LOWERING THE BASELINE IS THE POINT. When a silent fall-through gains a log line, this fails with
"below baseline" and the number is edited DOWN in the same commit -- so the file records progress
rather than only forbidding regress. That already happened once: `_get_from_redis` gained
`_warn_cache_too_small_once` in commit 46e496178.
"""

from __future__ import annotations

import ast
from pathlib import Path

from src.lib.quality_gates.verify_gate_helpers import MIN_SILENT_PATHS, silent_return_functions
from tests.helpers.api_paths import production_src_py

_SRC = Path(__file__).resolve().parents[3] / "src"

#: Measured 2026-09-07 at 203, immediately AFTER `_get_from_redis` gained its fall-through
#: warning -- so the baseline already reflects one payment rather than being set at the peak.
#: Only ever edited DOWNWARD, in the commit that adds the missing signal.
#: 203 was STALE BY 22 and nobody knew. Measured 2026-09-07 by running this module's own
#: predicate against a detached HEAD worktree and diffing the name sets: master already stood at
#: 181, so a 22-function improvement had landed unrecorded and the gate had been sitting 22 paths
#: above the real tree -- silently permitting regress it was written to catch.
#:
#: That is exactly what `test_the_baseline_is_current_so_progress_is_recorded` exists for, and it
#: is worth noting the failure message pointed the wrong way at first read: it said "fell to 182",
#: which invites the conclusion that the current change removed 21 signals. It removed none. Only
#: the two-tree diff distinguished "my change improved things" from "the bar was never lowered".
#:
#: 182 = master's 181 + `oldest_timestamp_ms`, which is deliberately silent: it is a pure
#: unit-conversion predicate on the hottest read in the app, and its three None paths all mean
#: "this frame cannot answer" -- a question its CALLER already logs about, once per shape.
#: 170 (2026-09-08), and the move DOWN from 182 is two separate things, both measured:
#:
#: 1. `_previous_open_interest` gained a warning on the path that is genuinely OUR defect -- a
#:    value we wrote ourselves that will not parse -- while the cold-cache path stays silent
#:    because it is normal. That is the payment this ratchet asks for, made once.
#: 2. `_is_procedure` (now in src/lib/quality_gates/verify_gate_helpers.py) removed a false-positive CLASS: 16 functions annotated `-> None`, whose
#:    bare early `return`s were counted as silent answers although those functions return no
#:    value on ANY path, success included.
#:
#: Net effect is a STRICTER gate: 186 flagged before, 170 after, on a tree that gained work.
#: 170 -> 165, measured 2026-09-12. The gain came from the DRY-1 consolidation: five private
#: `_float_or_none` copies each returned None on an unparsed value and were replaced by the one
#: `decimal_safe` SoT. The ratchet demands the lower number be recorded in the same commit, so the
#: headroom cannot silently absorb the next regression.
#: 165 -> 164, measured 2026-09-16, and the route there is worth recording because the number was
#: WRONG IN THE OTHER DIRECTION first. The gate failed at 166 against a 165 baseline, and the
#: obvious reading -- "the change I just made added one" -- was false. A two-tree diff (this
#: module's own predicate, run against a detached worktree of the tree before that session's five
#: commits) returned `head=166 before=166, added=0 removed=0`: the tree had ALREADY been at 166 for
#: some time and the regression was never recorded, so master was red before anyone looked.
#:
#: Raising the baseline to 166 would have rubber-stamped that. Instead the debt was PAID, which is
#: what this file asks for: `broker_queue_sync._extract_task_name` and
#: `_extract_task_name_from_unacked_value` each collapsed FOUR situations into one `None` -- not
#: JSON, wrong container, no headers object, task missing or not a string -- while both callers
#: deliberately treat None as "leave it alone". So an unreadable message is kept on the queue side
#: and, on the unacked side, re-pushed by Kombu at every visibility timeout: the exact recycle loop
#: that module exists to close, running with nothing anywhere saying so. They now share one
#: latched `record_unparseable_broker_message_once`, and the count fell by two.
#: 164 -> 160, 2026-09-24, measured by a two-tree diff (this predicate over HEAD blobs vs the
#: working tree): HEAD already stood at 162 -- the bar was stale by 2 again, an improvement nobody
#: recorded -- and this commit removes 2 more with nothing added. The 2 (CARRY-COMBO-CERT-1 touch
#: payment): registry_leaf_capital_cert_rows' `_funding_spot_bh_final` and `_funding_book_final`
#: each hand-rolled the bool-safe number parse behind two `return None`s; both now call the
#: `decimal_safe.float_or_none` SoT.
#: 160 -> 159, 2026-09-25 (INSAMPLE-CONFIRM-1 touched cert_evidence_window.py): `window_bars`
#: returned None for an unrecognised timeframe without a word; that path now logs a warning, the
#: open-window path stays quiet because an open confirm window is normal.
#: 159 -> 158, 2026-09-25 (HEATMAP-COLD-1 touched sync_ccxt_exchange.py): `ip_ban_expiry` dropped
#: an expired ban without a word, so calls to a venue that had banned us resumed with no record of
#: when; the lapse now logs, the never-banned path stays quiet.
#: 158 -> 157, 2026-09-25 (ADMIN-SLOW-1 touched admin_model_inventory_service.py):
#: `_version_from_bundle_metadata` dropped an unreadable bundle and a non-integer version without
#: a word; both now log with the prefix, the version-less metadata path stays quiet (it is normal).
#: 157 -> 156, 2026-10-01 (ATR-LOOKAHEAD touched backtester_apply_trade_levels.py): `_safe_float` returned None
#: down three branches; a missing or non-numeric row cell is an absent level there, not an error, so it now parses
#: into one value and returns once -- same results on every case (int, float, numeric/non-numeric string, NaN, inf).
#: 156 -> 154, 2026-10-02, measured by the full suite on the verify of a609a92af's successor (the day's commits;
#: not attributed per function).
#: 133 -> 132, 2026-10-05 (P1-9b touched taker_delta_burst.py): `detect_taker_delta_burst` returned None for a
#: dead tape exactly as for an ordinary bar; the no-spread path now warns, the two healthy misses stay quiet.
#: 130 -> 129 on the P1-1 commit (refactor(money): money_ledger's private _parse_window_bound, which swallowed an
#: unparseable bound, deleted for the money_ledger_ruin SoT that logs it).
# 144 -> 133 (2026-10-05); 133 -> 132 P1-9b; 132 -> 130 P1-0b (MTM DD, deadline warning);
# 129 -> 123 (2026-10-09, P3-0d batches A + B: silent-returning dead code deleted, two reject paths now log).
# 123 -> 122 (2026-10-09, P2-1 disclosure: the payload trade-book reader's two silent None paths became one record reader).
# 118 -> 117 (2026-10-16, GATE-RED: measured at c9f50859d).
# 117 -> 116 (2026-10-18, S2a LIQ-ONE: create_and_record_trade logs its no-fill-bar path; measured on the clean S2a tree).
# 116 -> 115 (2026-10-18, S2b: heuristic_suggested_position_fraction's two silent None paths are one; clean S2b tree).
# 115 -> 114 (2026-10-18, STOP-GAP, measured on the clean STOP-GAP tree).
# 113 -> 111 (2026-10-29, NEWS-ARMS calendar fix: the econ-calendar row builder logs each skip, _match_te its FRED
# fallback; measured on the commit's tree).
# 110 -> 108 (2026-11-08, measured on HEAD c769be53e in a clean worktree: an earlier commit's fall, never locked).
# 108 -> 107 (2026-11-08, PREDICT-LAST-ROW touched regressor_vol_range_inference.py: latest_positive_regressor_range_ratio's
# two silent None paths are one masked read -- None still means no positive finite bar, pinned by five cases).
SILENT_RETURN_BASELINE = 107


def _silent_return_functions() -> list[str]:
    """Qualified names of functions returning None down >= MIN_SILENT_PATHS paths, emitting nothing."""
    found: list[str] = []
    for path in production_src_py(_SRC):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError, UnicodeDecodeError:
            continue
        found.extend(f"{path.relative_to(_SRC)}::{name}" for name in silent_return_functions(tree))
    return found


def test_silent_return_paths_in_production_do_not_grow() -> None:
    """A new function that swallows two branches into one None must pay for itself with a signal."""
    found = _silent_return_functions()
    count = len(found)

    assert count <= SILENT_RETURN_BASELINE, (
        f"silent-return functions rose to {count}, above the {SILENT_RETURN_BASELINE} baseline.\n"
        f"A function returning None down {MIN_SILENT_PATHS}+ paths with nothing logged makes a "
        f"defect indistinguishable from a healthy miss -- that is how the cache tier stayed dead "
        f"for a full chart window.\nEither emit something on the path that matters, or raise.\n"
        f"Sample of the current set: {found[-5:]}"
    )


def test_the_baseline_is_current_so_progress_is_recorded() -> None:
    """Below baseline means a signal was added — edit the number DOWN in that same commit.

    Without this half the ratchet only forbids regress and silently tolerates a stale, generous
    bar, which is how a ratchet stops measuring anything.
    """
    count = len(_silent_return_functions())

    assert count >= SILENT_RETURN_BASELINE, (
        f"silent-return functions fell to {count}, below the {SILENT_RETURN_BASELINE} baseline — "
        f"good. Lower SILENT_RETURN_BASELINE to {count} in this commit so the gain is locked in."
    )
