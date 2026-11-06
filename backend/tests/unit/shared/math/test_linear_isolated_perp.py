"""Golden checks for isolated linear liquidation formulas (ADR-013 §6)."""

from __future__ import annotations

import pytest

from src.shared.math.linear_isolated_perp import (
    bankruptcy_price_linear_isolated,
    liquidation_price_linear_isolated_long,
    liquidation_price_linear_isolated_short,
)


@pytest.mark.parametrize(("direction", "expected"), [(1, 90.0), (-1, 110.0)])
def test_the_bankruptcy_price_is_where_the_isolated_margin_is_used_up(direction: int, expected: float) -> None:
    bankrupt = bankruptcy_price_linear_isolated(100.0, 10, direction)

    assert bankrupt == pytest.approx(expected)
    liq = (liquidation_price_linear_isolated_long if direction > 0 else liquidation_price_linear_isolated_short)(100.0, 10, 0.004)
    assert direction * (100.0 - liq) < direction * (100.0 - bankrupt)  # the liquidation triggers before it


def test_liquidation_long_leverage_10_mmr_point_zero_zero_four() -> None:
    entry = 100.0
    leverage = 10
    mmr = 0.004
    assert liquidation_price_linear_isolated_long(entry, leverage, mmr) == pytest.approx(90.4)


def test_liquidation_short_leverage_10_mmr_point_zero_zero_four() -> None:
    entry = 100.0
    leverage = 10
    mmr = 0.004
    assert liquidation_price_linear_isolated_short(entry, leverage, mmr) == pytest.approx(109.6)


def test_liquidation_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError, match="entry_price"):
        liquidation_price_linear_isolated_long(0.0, 10, 0.004)
    with pytest.raises(ValueError, match="leverage"):
        liquidation_price_linear_isolated_long(100.0, 0, 0.004)
