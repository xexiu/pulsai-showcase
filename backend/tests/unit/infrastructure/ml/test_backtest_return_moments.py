"""The Sharpe's own distribution shape, recorded beside it — so MinTRL can replace a magic 100.

REUSE-AUDIT: `src.shared.math.return_distribution_moments.moments_from_returns` is the SoT for
sample skew and Pearson kurtosis and is CALLED, not reimplemented; `min_track_record_length`
(same package family) is the consumer this unblocks. No moment computation is added to the
backtester itself.

WHY THIS EXISTS. `gate.MIN_TRADES_FOR_SHARPE = 100` is hand-picked -- its own docstring justifies
it with a single case (a 30-trade book at SR 4.48 returning +0.01 total). Owner, 2026-08-15:
"why that magic number? who made that?" MEASURED in reply: on the 1d timeframe ALONE, books in
this corpus range from 13 to 2,286 trades, so a flat 100 measures neither the timeframe nor the
evidence -- only how often a signal happens to fire.

`min_track_record_length` already sits in `src/domain/services/` and answers the question
properly: how many observations does THIS Sharpe need, given its own skew and kurtosis. It could
not be used because nothing recorded those two moments per cell.

THE COUPLING IS THE WHOLE POINT. `calculate_metrics` computes
`sharpe_ratio = mean(net_returns) / std(net_returns) * annualization_factor`. The moments MUST
come from `net_returns` -- that exact array -- or MinTRL is handed a statistic describing a
different series than the Sharpe it is deflating. That is "pair a statistic with a cell it does
not describe", the trap that cost this corpus a wrongly-killed money-maker.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from src.domain.services.min_track_record_length import min_track_record_length
from src.shared.math.return_distribution_moments import moments_from_returns


class TestTheMomentsDescribeTheSameSeriesAsTheSharpe:
    """Both are computed from `net_returns`; a test pins that they agree on one array."""

    def test_a_symmetric_series_reports_near_zero_skew(self) -> None:
        rng = np.random.default_rng(7)
        net_returns = rng.normal(0.01, 0.05, 500)

        moments = moments_from_returns(net_returns.tolist())

        assert abs(moments.skew) < 0.5
        assert 2.0 < moments.kurtosis < 4.5

    def test_a_fat_left_tail_is_visible_in_the_moments(self) -> None:
        """A book with one -40% bar and many small wins — the shape MinTRL must see."""
        net_returns = [0.01] * 99 + [-0.40]

        moments = moments_from_returns(net_returns)

        assert moments.skew < -3.0, "a single deep loss must show as strong negative skew"
        assert moments.kurtosis > 10.0, "and as heavy tails"

    def test_too_few_samples_fall_back_to_gaussian_rather_than_inventing_a_shape(self) -> None:
        moments = moments_from_returns([0.01, 0.02])

        assert moments.skew == 0.0
        assert moments.kurtosis == 3.0


class TestWhatMinTrlActuallyDemands:
    """MinTRL answers in OBSERVATIONS, so it must be fed the PER-OBSERVATION Sharpe.

    CORRECTION, and it inverts the conclusion this file first shipped with. The original version
    passed ANNUALISED Sharpes (1.5, 2.9) to a function that answers in observations, got 3-32, and
    concluded "the flat 100 is too STRICT by 3x to 25x". That is the same defect this very module
    documents at the top — pairing a statistic with a series it does not describe — committed an
    hour after writing a test asserting the coupling matters.

    RE-MEASURED with `sr_obs = ann_sr / sqrt(bars_per_year)`:

        ann SR   tf    sr_obs   skew  kurt   MinTRL   flat
           2.9   1d    0.1518    0.0   3.0      120    100
           2.9   1d    0.1518   -3.0  15.0      181    100
           1.5   1d    0.0785    0.0   3.0      441    100
           1.5   1d    0.0785   -3.0  15.0      553    100
         0.628   1d    0.0329    0.0   3.0    2,507    100
           1.5   4h    0.0321    0.0   3.0    2,636    100

    The flat 100 is too LENIENT, not too strict — by 1.2x to 25x. Only the corpus's best book
    (VRP dvol_mom, ann SR 2.9) is anywhere near it, and even that needs 120-181.

    `btc_usdt_1d/lightgbm/v41` needs ~2,507 and has 76. Its cells genuinely ARE thin, and the gate
    refusing them was RIGHT — for a reason nobody had computed.
    """

    def test_the_requirement_is_stated_in_the_same_units_as_the_sharpe(self) -> None:
        """A per-observation Sharpe of 0.152 (ann 2.9 on 1d) needs ~120 observations, not 3."""
        needed = min_track_record_length(sharpe=2.9 / math.sqrt(365), skew=0.0, kurtosis=3.0)

        assert needed is not None
        assert 100 < needed < 200, f"got {needed:.0f}"

    def test_a_fat_tailed_book_at_the_same_sharpe_needs_more(self) -> None:
        """One number cannot serve both shapes — that is the whole argument against the flat 100."""
        per_obs = 1.5 / math.sqrt(365)
        clean = min_track_record_length(sharpe=per_obs, skew=0.0, kurtosis=3.0)
        fat = min_track_record_length(sharpe=per_obs, skew=-3.0, kurtosis=15.0)

        assert clean is not None
        assert fat is not None
        assert fat > clean

    def test_the_flat_floor_is_too_lenient_for_an_ordinary_book(self) -> None:
        """THE CORRECTED FINDING. An annualised Sharpe of 1.5 on 1d needs ~441 observations; the
        flat floor waves it through at 100."""
        needed = min_track_record_length(sharpe=1.5 / math.sqrt(365), skew=0.0, kurtosis=3.0)

        assert needed is not None
        assert needed > 100, f"MinTRL demands {needed:.0f}, the flat floor demands 100"

    def test_the_measured_v41_shape_is_genuinely_thin(self) -> None:
        """`btc_usdt_1d/lightgbm/v41` tops out at 76 trades. I first reported it needs 9 and is
        wrongly refused. It needs ~2,507 — the refusal was correct, uncomputed."""
        needed = min_track_record_length(sharpe=0.628 / math.sqrt(365), skew=0.0, kurtosis=3.0)

        assert needed is not None
        assert needed > 76, "76 observations is not enough for this Sharpe"

    def test_a_sharpe_at_or_below_the_benchmark_is_unanswerable_not_zero(self) -> None:
        """No track record length proves a book beats a bar it does not clear."""
        assert min_track_record_length(sharpe=0.0, skew=0.0, kurtosis=3.0) is None

    @pytest.mark.parametrize("missing", ["sharpe", "skew", "kurtosis"])
    def test_a_missing_moment_yields_none_rather_than_a_guess(self, missing: str) -> None:
        kwargs: dict[str, float | None] = {"sharpe": 1.5, "skew": 0.0, "kurtosis": 3.0}
        kwargs[missing] = None

        assert min_track_record_length(**kwargs) is None  # type: ignore[arg-type]
