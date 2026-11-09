"""SoT: ML confidence percent display decimals (chart_json + FE parity)
and confidence_pct_to_threshold helper.
"""

from __future__ import annotations

import pytest

from src.shared.constants.confidence import (
    DEFAULT_MIN_SIGNAL_CONFIDENCE_PERCENT,
    DEFAULT_MIN_SIGNAL_CONFIDENCE_THRESHOLD,
    ML_CONFIDENCE_PERCENT_DISPLAY_DECIMALS,
    confidence_pct_to_threshold,
    format_ml_signal_confidence_percent_display,
)


def test_ml_confidence_percent_display_decimals_matches_chart_json_contract() -> None:
    assert ML_CONFIDENCE_PERCENT_DISPLAY_DECIMALS == 1
    assert round(0.547 * 100, ML_CONFIDENCE_PERCENT_DISPLAY_DECIMALS) == 54.7
    assert round(0.855 * 100, ML_CONFIDENCE_PERCENT_DISPLAY_DECIMALS) == 85.5
    assert round(0.431 * 100, ML_CONFIDENCE_PERCENT_DISPLAY_DECIMALS) == 43.1


def test_format_ml_signal_confidence_percent_display_matches_rounding() -> None:
    assert format_ml_signal_confidence_percent_display(0.557) == "55.7%"
    assert format_ml_signal_confidence_percent_display(0.547) == "54.7%"
    assert format_ml_signal_confidence_percent_display(1.0) == "100.0%"
    assert format_ml_signal_confidence_percent_display(0.0) == "0.0%"
    # Live 1d SELL fixture: integer `.0%` wrongly showed 56%; SoT is one decimal.
    assert format_ml_signal_confidence_percent_display(0.5550089671669447) == "55.5%"


class TestConfidencePctToThreshold:
    """confidence_pct_to_threshold(pct) -> float (SoT for pct/100 conversion)."""

    def test_reproduces_default_threshold_constant(self) -> None:
        """Helper must match the canonical DEFAULT_MIN_SIGNAL_CONFIDENCE_THRESHOLD derivation."""
        assert confidence_pct_to_threshold(DEFAULT_MIN_SIGNAL_CONFIDENCE_PERCENT) == DEFAULT_MIN_SIGNAL_CONFIDENCE_THRESHOLD

    def test_50_pct_returns_0_5(self) -> None:
        assert confidence_pct_to_threshold(50.0) == pytest.approx(0.5)

    def test_100_pct_returns_1_0(self) -> None:
        assert confidence_pct_to_threshold(100.0) == pytest.approx(1.0)

    def test_0_pct_returns_0_0(self) -> None:
        assert confidence_pct_to_threshold(0.0) == pytest.approx(0.0)

    def test_65_pct_returns_0_65(self) -> None:
        assert confidence_pct_to_threshold(65.0) == pytest.approx(0.65)

    def test_75_5_pct_returns_0_755(self) -> None:
        assert confidence_pct_to_threshold(75.5) == pytest.approx(0.755)

    def test_returns_float(self) -> None:
        assert isinstance(confidence_pct_to_threshold(50), float)
