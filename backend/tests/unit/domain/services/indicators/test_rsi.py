"""The RSI home: one formula over three averages, five zero-loss policies, no fabricated bar-0 change.

IMPORTERS/CALLERS: pytest only. AFFECTED API: none. DATA SCHEMAS: none.

The contract every catalogued indicator keeps (causal, deterministic, no gap after the warm-up, the time budget) is in
test_indicator_contract.py; these pin what is RSI-specific -- the copies it replaced disagreed on exactly these, and
each disagreement moved values a stored model or label was built on. Moved here 2026-10-19 with the indicator: the
chart's RSI tests (tests/infrastructure/ml/test_chart_indicators.py) and ws_honest_daily_backtest's.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.domain.services.indicators.ema import ema_first_seeded
from src.domain.services.indicators.rma import rma_mean_seeded
from src.domain.services.indicators.rsi import (
    DEFAULT_RSI_PERIOD,
    cutler_rsi,
    cutler_rsi_of_changes,
    first_seeded_rsi,
    gains_losses,
    price_changes,
    rsi_from_averages,
    wilder_rsi,
    wilder_rsi_first_seeded,
)
from src.domain.services.indicators.trailing import trailing_mean

_P = DEFAULT_RSI_PERIOD


def _walk(n: int = 2_000, seed: int = 3) -> np.ndarray:
    return 100.0 + np.cumsum(np.random.default_rng(seed).normal(0.0, 1.0, n))


def _bits(x: np.ndarray) -> np.ndarray:
    return np.asarray(x, dtype=np.float64).view(np.uint64)


class TestTheChartsBehaviour:
    """The chart's RSI pane reads wilder_rsi (formerly infrastructure.ml.chart_indicators.calculate_rsi)."""

    def test_a_strong_downtrend_reads_oversold(self) -> None:
        rsi = wilder_rsi(np.array([100 - i * 1.5 for i in range(20)]), _P)

        assert rsi[~np.isnan(rsi)][-1] < 30

    def test_a_strong_uptrend_reads_overbought(self) -> None:
        rsi = wilder_rsi(np.array([100 + i * 1.5 for i in range(20)]), _P)

        assert rsi[~np.isnan(rsi)][-1] > 70

    def test_too_few_bars_give_no_rsi(self) -> None:
        assert np.isnan(wilder_rsi(np.array([100.0, 101.0, 102.0]), _P)).all()
        assert np.isnan(wilder_rsi(np.arange(1.0, _P + 1.0), _P)).all()  # period bars: still no change to seed with

    @pytest.mark.parametrize("variant", [wilder_rsi, wilder_rsi_first_seeded, cutler_rsi])
    def test_it_stays_between_0_and_100(self, variant: object) -> None:
        rsi = variant(_walk(), _P)  # type: ignore[operator]

        assert ((rsi[~np.isnan(rsi)] >= 0.0) & (rsi[~np.isnan(rsi)] <= 100.0)).all()


class TestTheWarmUp:
    def test_bar_0_has_no_price_change(self) -> None:
        changes = price_changes(np.array([10.0, 11.0, 10.5]))

        assert np.isnan(changes[0])
        np.testing.assert_array_equal(changes[1:], [1.0, -0.5])

    def test_wilder_and_cutler_start_at_bar_period_never_on_a_fabricated_flat_bar_0(self) -> None:
        close = _walk(50)

        for rsi in (wilder_rsi(close, _P), cutler_rsi(close, _P)):
            assert np.isnan(rsi[:_P]).all()
            assert np.isfinite(rsi[_P])

    def test_the_first_seeded_average_starts_at_the_first_change(self) -> None:
        rsi = wilder_rsi_first_seeded(_walk(50), _P, "hundred")

        assert np.isnan(rsi[0])
        assert np.isfinite(rsi[1:]).all()

    def test_a_missing_close_is_skipped_by_the_first_seeded_averages(self) -> None:
        close = _walk(60)
        gapped = close.copy()
        gapped[30] = np.nan

        rsi = wilder_rsi_first_seeded(gapped, _P, "hundred")

        assert np.isnan(rsi[30:32]).all()  # the two changes that touch the missing close
        assert np.isfinite(rsi[32:]).all()


class TestTheZeroLossPolicies:
    """A run with no down bar has average loss 0: each policy is the value some caller's stored data was built on."""

    @pytest.mark.parametrize(
        ("policy", "expected"),
        [("hundred", 100.0), ("hundred_or_fifty", 100.0), ("hundred_or_zero", 100.0), ("rs_hundred", 100.0 - 100.0 / 101.0)],
    )
    def test_a_run_of_gains_only(self, policy: str, expected: float) -> None:
        rsi = wilder_rsi(np.arange(1.0, 40.0), _P, policy)  # type: ignore[arg-type]

        assert rsi[-1] == expected

    def test_nan_leaves_a_run_of_gains_without_an_rsi(self) -> None:
        assert np.isnan(cutler_rsi(np.arange(1.0, 40.0), _P, "nan")[-1])

    @pytest.mark.parametrize(("policy", "expected"), [("hundred", 100.0), ("hundred_or_fifty", 50.0), ("hundred_or_zero", 0.0)])
    def test_a_flat_market(self, policy: str, expected: float) -> None:
        assert cutler_rsi(np.full(40, 7.0), _P, policy)[-1] == expected  # type: ignore[arg-type]

    def test_ta_libs_convention_reads_a_pure_uptrend_100_and_a_pure_downtrend_0(self) -> None:
        """ws_honest_daily_backtest's RSI (the former compute_rsi): Cutler, hundred_or_zero."""
        up = cutler_rsi(np.arange(1.0, 40.0), _P, "hundred_or_zero")
        down = cutler_rsi(np.arange(40.0, 1.0, -1.0), _P, "hundred_or_zero")

        assert up[-1] == 100.0
        assert down[-1] == 0.0
        assert np.isnan(up[:_P]).all()


class TestTheFusedKernelsAreTheSharedRecursions:
    """wilder_rsi and first_seeded_rsi each fuse a home recursion with the formula in one numba pass for speed; pinned
    bit-equal to composing them, so the fused copy can never drift from rma / ema."""

    @pytest.mark.parametrize("period", [2, 14, 50])
    def test_wilder_rsi_is_rma_mean_seeded_then_the_formula(self, period: int) -> None:
        close = _walk()
        gains, losses = gains_losses(price_changes(close))
        averages = rma_mean_seeded(np.vstack((gains, losses)), period, 1, period)

        np.testing.assert_array_equal(_bits(wilder_rsi(close, period)), _bits(rsi_from_averages(averages[0], averages[1])))

    @pytest.mark.parametrize("span", [3, 14, 30])
    def test_first_seeded_rsi_is_the_ema_recursion_then_the_formula(self, span: int) -> None:
        close = _walk()
        gains, losses = gains_losses(price_changes(close))
        composed = rsi_from_averages(ema_first_seeded(gains, span), ema_first_seeded(losses, span), "nan")

        np.testing.assert_array_equal(_bits(first_seeded_rsi(close, 2.0 / (span + 1.0))), _bits(composed))

    def test_cutler_rsi_is_the_trailing_mean_then_the_formula(self) -> None:
        close = _walk()
        gains, losses = gains_losses(price_changes(close))
        composed = rsi_from_averages(trailing_mean(gains, _P), trailing_mean(losses, _P), "nan")

        np.testing.assert_array_equal(_bits(cutler_rsi(close, _P)), _bits(composed))


class TestChanges:
    def test_rsi_of_price_changes_is_cutler_rsi(self) -> None:
        close = _walk()

        np.testing.assert_array_equal(_bits(cutler_rsi_of_changes(price_changes(close), _P)), _bits(cutler_rsi(close, _P)))

    def test_a_block_of_series_is_each_row_on_its_own(self) -> None:
        """The panel callers (richer_features, xs_ml_zoo) pass coins x bars."""
        block = np.vstack([np.diff(_walk(seed=s), prepend=np.nan) for s in range(3)])

        expected = np.vstack([cutler_rsi_of_changes(row, _P) for row in block])
        np.testing.assert_array_equal(_bits(cutler_rsi_of_changes(block, _P)), _bits(expected))
