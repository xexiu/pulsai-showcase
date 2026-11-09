"""The wealth arm of the plausibility floor has to actually fire.

`implausible_metrics` is documented as a PHYSICAL POSSIBILITY check — "a compounding path that
exploded" — not a quality bar. At `WEALTH_IMPLAUSIBLE_MULT = 1e6` it was barely one: measured over
615 hunt cells carrying a capital pair it rejected 5 (0.8%) and waved through 53,299x and 40,568x.
The cells that triggered the 2026-08-13 funding investigation (7,249x, 5,471x) passed it untouched.

At 1e4 it rejects 12 (2.0%). The corpus window is ~5.6 years, so 1e4 is 393%/yr sustained — nothing
real compounds like that, and 98% of cells are still judged on merit rather than on this floor.

These tests pin the BEHAVIOUR either side of the boundary, not the constant, so a future move has to
be a deliberate change to what passes rather than an accidental one.
"""

from __future__ import annotations

import math

import pytest

from src.domain.services.edge_lifecycle.gate import (
    WEALTH_IMPLAUSIBLE_MULT,
    GateMetrics,
    implausible_metrics,
)

#: Believable metrics, so only the capital pair is under test.
_SANE = GateMetrics(ic=0.02, sr=1.1, dsr=0.6, fold_stab=0.6)


def _reasons(multiple: float) -> list[str]:
    return implausible_metrics(_SANE, initial_capital=10_000.0, final_capital=10_000.0 * multiple)


class TestTheFloorRejectsWhatCannotHappen:
    @pytest.mark.parametrize("multiple", [1.06e151, 1e9, 5.3e4, 4.1e4, 1.1e4])
    def test_an_impossible_multiple_is_rejected(self, multiple: float) -> None:
        """5.3e4 and 4.1e4 are real cells the 1e6 floor let through."""
        reasons = _reasons(multiple)

        assert any("wealth=" in r for r in reasons), f"{multiple:.3g}x passed the floor"

    def test_a_diverged_path_is_rejected_as_non_finite(self) -> None:
        reasons = implausible_metrics(_SANE, initial_capital=10_000.0, final_capital=math.inf)

        assert any("non-finite" in r for r in reasons)


class TestTheFloorLeavesRealBooksAlone:
    @pytest.mark.parametrize("multiple", [0.0, 0.5, 1.0, 2.5, 10.0, 100.0, 1_000.0, 9_000.0])
    def test_a_survivable_multiple_is_not_flagged_on_wealth(self, multiple: float) -> None:
        """Including a total loss (0x) — losing money is not IMPLAUSIBLE, it is common."""
        assert not [r for r in _reasons(multiple) if "wealth=" in r]

    def test_the_boundary_itself_passes(self) -> None:
        """Strictly greater-than, so a cell sitting exactly on the floor is not rejected."""
        assert not [r for r in _reasons(WEALTH_IMPLAUSIBLE_MULT) if "wealth=" in r]


class TestUnknownIsNeverImplausible:
    @pytest.mark.parametrize(("initial", "final"), [(None, 50_000.0), (10_000.0, None), (None, None), (0.0, 50_000.0)])
    def test_a_missing_capital_pair_cannot_trip_the_floor(self, initial: float | None, final: float | None) -> None:
        """An unmeasured field is UNKNOWN, not a violation — the module's stated contract."""
        reasons = implausible_metrics(_SANE, initial_capital=initial, final_capital=final)

        assert not [r for r in reasons if "wealth=" in r]
