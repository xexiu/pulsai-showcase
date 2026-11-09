"""Perp side filter: long-only / short-only / both when not in spot mode."""

import pytest

from src.infrastructure.ml.backtester_capital import should_skip_signal
from src.shared.constants.backtest_leverage import PerpAllowedSides


@pytest.mark.parametrize(
    ("spot_mode", "sides", "signal", "expected"),
    [
        (True, PerpAllowedSides.BOTH, 1, None),
        (True, PerpAllowedSides.BOTH, -1, "short_spot"),
        (True, PerpAllowedSides.LONG_ONLY, -1, "short_spot"),
        (False, PerpAllowedSides.BOTH, 1, None),
        (False, PerpAllowedSides.BOTH, -1, None),
        (False, PerpAllowedSides.LONG_ONLY, 1, None),
        (False, PerpAllowedSides.LONG_ONLY, -1, "perp_side_filtered"),
        (False, PerpAllowedSides.SHORT_ONLY, 1, "perp_side_filtered"),
        (False, PerpAllowedSides.SHORT_ONLY, -1, None),
    ],
)
def test_should_skip_signal_perp_allowed_sides(
    spot_mode: bool,
    sides: PerpAllowedSides,
    signal: int,
    expected: str | None,
) -> None:
    out = should_skip_signal(
        signal,
        open_positions=[],
        available_balance=1_000_000.0,
        spot_mode=spot_mode,
        max_open_positions=5,
        realistic_mode=True,
        margin_required_usd=1.0,
        perp_allowed_sides=sides,
    )
    assert out == expected
