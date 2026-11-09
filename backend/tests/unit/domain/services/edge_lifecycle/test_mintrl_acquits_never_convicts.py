"""MinTRL may clear a book on fewer trades than the flat floor; it may never re-condemn one.

Owner, 2026-09-18: *"i think that your too strict/very conservative with the policy/gates/metrics"*.
He is right, and the measurement says where. `min_track_record_length` at 95% confidence prices a
MODEST Sharpe at thousands of observations:

    prod 1d v2   281-303 confirm trades   needs 3,089-5,520
    4h  v411     738 confirm trades       needs more than it has (and its Sharpe is negative)

Every cert written since 2026-09-17 carries the moments, so a grader that lets MinTRL DECIDE would
silently re-tier the corpus's only `candidate` down to `nice_to_have` on a bar nothing has ever
cleared. Thinness is a disclosure beside the money, not a verdict that erases it, so the closed
form is allowed to ACQUIT (a strong book needs fewer trades) and never to convict.
"""

from __future__ import annotations

from typing import Any

from src.domain.services.edge_lifecycle.capital_cert_headline import MIN_TRADES_FOR_SHARPE
from src.domain.services.edge_lifecycle.cell_measurability import is_thin_sample

#: 1d: annualized = per-trade * sqrt(trades per year). The cert records the factor it used.
_ANNUALIZATION_1D = 19.105


def _cell(*, trades: int, annualized_sharpe: float, skew: float = 0.0, kurtosis: float = 3.0) -> dict[str, Any]:
    return {
        "num_trades": trades,
        "sharpe_ratio": annualized_sharpe,
        "annualization_factor": _ANNUALIZATION_1D,
        "return_skew": skew,
        "return_kurtosis": kurtosis,
    }


class TestMinTrlNeverConvicts:
    def test_a_book_past_the_flat_floor_stays_measurable_though_mintrl_wants_thousands(self) -> None:
        """prod v2's shape: 300 trades at a modest Sharpe. MinTRL wants ~3,000 — it does not decide."""
        cell = _cell(trades=300, annualized_sharpe=0.5)
        assert is_thin_sample(cell) is False

    def test_a_large_losing_sample_is_not_called_thin_by_mintrl(self) -> None:
        """v411's shape: 738 trades, negative Sharpe. The MONEY gate excludes it; thinness does not."""
        cell = _cell(trades=738, annualized_sharpe=-0.62)
        assert is_thin_sample(cell) is False

    def test_the_flat_floor_still_convicts_a_genuinely_small_sample(self) -> None:
        cell = _cell(trades=MIN_TRADES_FOR_SHARPE - 1, annualized_sharpe=0.5)
        assert is_thin_sample(cell) is True


class TestMinTrlStillAcquits:
    def test_a_very_strong_book_clears_thinness_below_the_flat_floor(self) -> None:
        """The information the floor cannot express: at a high Sharpe a handful of trades suffices."""
        cell = _cell(trades=30, annualized_sharpe=12.0)
        assert is_thin_sample(cell) is False

    def test_a_cell_without_moments_falls_back_to_the_floor(self) -> None:
        assert is_thin_sample({"num_trades": 30}) is True
        assert is_thin_sample({"num_trades": MIN_TRADES_FOR_SHARPE}) is False

    def test_an_unknown_trade_count_is_still_thin(self) -> None:
        assert is_thin_sample({}) is True
