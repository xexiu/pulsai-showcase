"""Tests for keep_in_sync_guard — a comment is not a synchronisation mechanism.

Owner, 2026-08-14:

    "Give someone state and they'll have a bug one day, but teach them how to represent state in
     two separate locations that have to be kept in sync and they'll have bugs for a lifetime."

MEASURED the same day: 8 live `keep in sync` comments in this repo, each a mirror whose only guard
is prose. Memory `a-mirror-needs-a-mechanism` records what one of them cost — `2h`/`6h` missing
from the TS timeframe mirror, filed under CHART_ONLY and described to the frontend as decoration,
while a sibling validator had drifted seven timeframes behind.

The guard is deliberately narrow: it fires only when an edit ADDS such a promise, and it releases
as soon as the same edit shows a mechanism (a parity/derivation marker). Fails open.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HOOKS = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("keep_in_sync_guard", _HOOKS / "keep_in_sync_guard.py")
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
sys.modules["keep_in_sync_guard"] = _mod
_spec.loader.exec_module(_mod)

promises_sync_without_mechanism = _mod.promises_sync_without_mechanism


def test_a_bare_keep_in_sync_comment_is_blocked() -> None:
    added = "# Public contact reasons — keep in sync with web contact i18n / Valibot enum.\nX = 1\n"

    assert promises_sync_without_mechanism(added) is True


def test_mirror_and_must_match_phrasings_are_caught_too() -> None:
    """The promise is the pattern, not one spelling of it."""
    for text in (
        "// FE mirror — must match the backend parser.\n",
        "# Mirror of TIMEFRAME_REGISTRY; keep these in sync.\n",
        "/* kept in sync with globals.css */\n",
    ):
        assert promises_sync_without_mechanism(text) is True, text


def test_a_parity_test_reference_releases_it() -> None:
    """Naming the executable check is exactly what the rule asks for."""
    added = (
        "# Mirror of TIMEFRAME_REGISTRY — kept honest by tests/unit/shared/constants/"
        "test_exchange_ids_parity.py, which reads the other file and fails on disagreement.\n"
    )

    assert promises_sync_without_mechanism(added) is False


def test_deriving_instead_of_copying_releases_it() -> None:
    """The better fix is no second location at all."""
    added = "# DERIVED from TIMEFRAME_MS at import time, so there is no second copy to drift.\n"

    assert promises_sync_without_mechanism(added) is False


def test_unrelated_content_is_untouched() -> None:
    assert promises_sync_without_mechanism("def add(a, b):\n    return a + b\n") is False


def test_reusing_an_existing_constant_is_mechanism_one_and_releases() -> None:
    """FALSE POSITIVE found 2026-08-14: the guard blocked its own author doing the right thing.

    The blocked text was `"Reuses the existing constant rather than restating 95.0 — a second copy
    of a risk threshold is precisely the mirror this repo keeps getting bitten by."` That sentence
    DESCRIBES the anti-pattern while doing the opposite, and "reuses the existing constant" IS
    mechanism 1 (remove the second location) — the guard just could not see it.

    A guard that blocks the correct fix teaches people to route around it.
    """
    for text in (
        "Reuses the existing constant rather than restating 95.0 — a second copy of a risk "
        "threshold is precisely the mirror this repo keeps getting bitten by.\n",
        "Imports the shared constant instead of a second copy.\n",
        "single source of truth: read from the constants module.\n",
    ):
        assert promises_sync_without_mechanism(text) is False, text


def test_merely_naming_the_anti_pattern_without_a_fix_still_blocks() -> None:
    """The release must require a MECHANISM, not just the word 'copy' appearing nearby."""
    text = "This mirror must be kept in sync by hand; a second copy is unfortunate but necessary.\n"

    assert promises_sync_without_mechanism(text) is True


def test_an_existing_comment_that_is_merely_moved_is_not_a_new_promise() -> None:
    """Only ADDED text is judged; the guard must not punish a refactor that carries one along.

    The caller passes added lines only, so an empty add is trivially clean — pinned so a future
    change to the extraction cannot start blocking every edit to a file that already has one.
    """
    assert promises_sync_without_mechanism("") is False


def test_the_word_sync_alone_is_not_a_promise() -> None:
    """`sync` appears constantly in async code; only the SYNC-THESE-COPIES promise counts."""
    for text in (
        "await session.sync()\n",
        "# syncs the websocket cursor forward\n",
        "SYNC_INTERVAL_MS = 500\n",
    ):
        assert promises_sync_without_mechanism(text) is False, text
