"""bar_level_touch: a long is reached by the bar's low, a short by its high, a flat book never -- in python and inside a
compiled kernel alike; a price within TOUCH_REL_TOL of a level touches it (TOUCH-TIE); a stop only ever tightens.

IMPORTERS / CALLERS: none (a test module). AFFECTED API: src/shared/math/bar_level_touch (level_touched, price_reached,
tightened, TOUCH_REL_TOL). DATA SCHEMAS: none.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest

from src.shared.math.bar_level_touch import TOUCH_REL_TOL, level_touched, price_reached, target_reached, tightened
from src.shared.utils.numba_jit import njit_cached

if TYPE_CHECKING:
    from numpy.typing import NDArray

LONG, SHORT, FLAT = 1, -1, 0


@pytest.mark.parametrize(
    ("side", "low", "high", "level", "want"),
    [
        (LONG, 98.0, 103.0, 98.0, True),  # the low reaches the long's stop exactly
        (LONG, 98.5, 103.0, 98.0, False),  # the low stays above it; a high far away does not count
        (SHORT, 97.0, 102.0, 102.0, True),  # the high reaches the short's stop exactly
        (SHORT, 97.0, 101.5, 102.0, False),  # the high stays under it; a low far away does not count
        (FLAT, 0.0, 1e9, 50.0, False),  # no position, no touch
    ],
)
def test_the_adverse_extreme_decides(side: int, low: float, high: float, level: float, want: bool) -> None:
    assert level_touched(side, low, high, level) is want


@njit_cached
def _first_touch(side: int, lows: NDArray[np.float64], highs: NDArray[np.float64], level: float) -> int:
    for t in range(len(lows)):
        if level_touched(side, lows[t], highs[t], level):
            return t
    return -1


def test_a_compiled_kernel_calls_it() -> None:
    lows, highs = np.array([99.0, 98.4, 97.9, 96.0]), np.array([99.5, 100.0, 99.0, 98.0])
    assert _first_touch(LONG, lows, highs, 98.0) == 2
    assert _first_touch(SHORT, lows, highs, 100.0) == 1
    assert _first_touch(FLAT, lows, highs, 98.0) == -1


#: TOUCH-TIE (2026-10-14): entry 0.1960 + 0.0008 came out 0.19680000000000003, one float step past the 0.1968 it stands for
TIED_LEVEL, TIED_PRICE = 0.1960 + 0.0008, 0.1968


@pytest.mark.parametrize(
    ("direction", "price", "level", "want"),
    [
        (1, 103.0, 103.0, True),  # up to it: reached at the level
        (1, 102.9, 103.0, False),  # up to it: short of it
        (-1, 97.0, 97.0, True),  # down to it: reached at the level
        (-1, 97.1, 97.0, False),  # down to it: short of it
        (1, TIED_PRICE, TIED_LEVEL, True),  # the float step past the price is a touch
        (-1, TIED_LEVEL, TIED_PRICE, True),
    ],
)
def test_a_price_reaches_a_level_moving_toward_it_ties_included(direction: int, price: float, level: float, want: bool) -> None:
    assert price_reached(direction, price, level) is want


def test_the_tie_is_the_relative_tolerance_and_nothing_wider() -> None:
    level = 100.0
    assert price_reached(1, level - level * TOUCH_REL_TOL, level)
    assert not price_reached(1, level - 2e-6, level)


def test_level_touched_honours_the_same_tie() -> None:
    """The lab walks' stop touch now reads the one rule: a long's low one float step above its stop touches it."""
    assert level_touched(LONG, TIED_LEVEL, 1.0, TIED_PRICE)
    assert level_touched(SHORT, 0.0, TIED_PRICE, TIED_LEVEL)


@pytest.mark.parametrize(
    ("side", "low", "high", "level", "want"),
    [
        (LONG, 98.0, 103.0, 103.0, True),  # the high reaches the long's target exactly
        (LONG, 90.0, 102.9, 103.0, False),  # a low far away does not count
        (SHORT, 97.0, 110.0, 97.0, True),  # the low reaches the short's target exactly
        (SHORT, 97.1, 102.0, 97.0, False),  # a high far away does not count
        (LONG, 0.0, TIED_PRICE, TIED_LEVEL, True),  # the tie, as for every other touch
        (FLAT, 0.0, 1e9, 50.0, False),  # no position, no target
    ],
)
def test_a_target_is_reached_by_the_favourable_extreme(side: int, low: float, high: float, level: float, want: bool) -> None:
    assert target_reached(side, low, high, level) is want


@pytest.mark.parametrize(
    ("stop", "level", "side", "want"),
    [
        (95.0, 100.0, LONG, 100.0),  # a long's stop moves up
        (100.0, 95.0, LONG, 100.0),  # never down
        (105.0, 100.0, SHORT, 100.0),  # a short's stop moves down
        (100.0, 105.0, SHORT, 100.0),  # never up
    ],
)
def test_a_stop_only_tightens(stop: float, level: float, side: int, want: float) -> None:
    assert tightened(stop, level, side) == want
