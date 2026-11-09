"""in_daily_window: a minute of the day inside [start, end), the window running across midnight when its end is not after
its start -- equal to the two-branch test it replaced (liquidity_targets' sessions) on every pair of a grid.

IMPORTERS/CALLERS: pytest. AFFECTED API: none. DATA SCHEMAS: none.
"""

from __future__ import annotations

import itertools

import numpy as np

from src.domain.enums import MINUTES_PER_DAY
from src.domain.services.daily_window import in_daily_window


def _two_branch(minute: np.ndarray, start: int, end: int) -> np.ndarray:
    """The test liquidity_targets wrote inline before this home existed."""
    if start < end:
        return (minute >= start) & (minute < end)
    return (minute >= start) | (minute < end)


def test_it_equals_the_two_branch_test_on_every_pair_of_a_grid() -> None:
    minute = np.arange(MINUTES_PER_DAY, dtype=np.int64)
    for start, end in itertools.product(range(0, MINUTES_PER_DAY, 35), repeat=2):
        assert (in_daily_window(minute, start, end) == _two_branch(minute, start, end)).all(), (start, end)


def test_a_window_across_midnight_holds_the_late_and_the_early_minutes() -> None:
    minute = np.array([19 * 60 + 59, 20 * 60, 23 * 60 + 59, 0, 2 * 60 + 59, 3 * 60], dtype=np.int64)

    assert in_daily_window(minute, 20 * 60, 3 * 60).tolist() == [False, True, True, True, True, False]
