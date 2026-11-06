"""SoT thresholds for inner live-signal pipeline warnings."""

from __future__ import annotations

import pytest

from src.shared.constants.live_signal_latency import (
    LIVE_SIGNAL_INNER_LATENCY_WARN_ENSEMBLE_MS,
    LIVE_SIGNAL_INNER_LATENCY_WARN_SINGLE_MODEL_MS,
    live_signal_inner_latency_warn_ms,
    live_signal_latency_other_ms,
)


def test_live_signal_inner_latency_warn_ms_single_vs_ensemble() -> None:
    assert live_signal_inner_latency_warn_ms(n_bundles=1) == LIVE_SIGNAL_INNER_LATENCY_WARN_SINGLE_MODEL_MS
    assert live_signal_inner_latency_warn_ms(n_bundles=2) == LIVE_SIGNAL_INNER_LATENCY_WARN_ENSEMBLE_MS


class TestTheLoggedBreakdownAccountsForTheWholeTotal:
    """A breakdown that does not sum to its total misdirects whoever reads it.

    Owner, 2026-09-02, on a real production warning line:
      "Signal generation exceeded 75ms: 320.5ms ... model=0.1ms, features=51.9ms, predict=0.9ms"
      "0.1+51.9+0.9 isnot 320.3ms... :S"
    """

    def test_the_owners_exact_line_attributes_the_missing_millis(self) -> None:
        other = live_signal_latency_other_ms(elapsed_ms=320.5, model_ms=0.1, feature_ms=51.9, step_ms=0.9)

        assert other == pytest.approx(267.6), "the 83% nobody was measuring must be named"

    @pytest.mark.parametrize(
        ("elapsed", "model", "feature", "step"),
        [
            (320.5, 0.1, 51.9, 0.9),
            (75.0, 25.0, 25.0, 25.0),
            (1000.0, 0.0, 0.0, 0.0),
            (52.9, 0.1, 51.9, 0.9),
        ],
    )
    def test_the_four_terms_always_reconstruct_the_total(self, elapsed: float, model: float, feature: float, step: float) -> None:
        other = live_signal_latency_other_ms(elapsed_ms=elapsed, model_ms=model, feature_ms=feature, step_ms=step)

        assert model + feature + step + other == pytest.approx(elapsed)

    def test_a_negative_remainder_is_reported_not_hidden(self) -> None:
        """Sub-timers that overlap or round past the total are a real defect; clamping would hide it."""
        other = live_signal_latency_other_ms(elapsed_ms=10.0, model_ms=5.0, feature_ms=5.0, step_ms=5.0)

        assert other == pytest.approx(-5.0)
