"""Tests for centralized chart pattern reference stats and prompt contract."""

from __future__ import annotations

import pytest

from src.shared.chart_pattern_reference_stats import (
    ALL_PATTERN_REFERENCE_STATS,
    PRIMARY_PATTERN_REFERENCE_STATS,
    SECONDARY_PATTERN_REFERENCE_STATS,
    build_chart_analysis_reference_system_prompt,
    build_mock_chart_analysis_response,
)


def test_chart_pattern_prompt_uses_precise_metric_names() -> None:
    prompt = build_chart_analysis_reference_system_prompt()

    assert "percentage meeting price target" in prompt
    assert 'generic "success rate"' in prompt
    assert "Head & Shoulders (Top): 93% success" not in prompt


def test_primary_reference_stats_include_publicly_sourced_patterns() -> None:
    names = {stat.name for stat in PRIMARY_PATTERN_REFERENCE_STATS}

    assert "Triple Bottom" in names
    assert "Double Bottom (Eve & Adam subtype reference)" in names
    assert "Inverse Head & Shoulders" in names
    assert "Ascending Triangle (upward breakout)" in names


def test_secondary_reference_stats_capture_downgraded_patterns() -> None:
    names = {stat.name for stat in SECONDARY_PATTERN_REFERENCE_STATS}

    assert "Falling Wedge (upward breakout)" in names
    assert "Descending Triangle (downward breakout)" in names
    assert "Head & Shoulders Top" in names


def test_mock_response_avoids_generic_success_rate_wording() -> None:
    response = build_mock_chart_analysis_response()

    assert "percentage meeting price target 72%" in response
    assert "success rate" not in response


def test_every_primary_and_secondary_has_expected_side_from_avg_move() -> None:
    """ALL SoT Bulkowski patterns carry polarity — rise=+1, decline=-1."""
    # 2026-09-04: 8 -> 11. This number is a canary against SILENT additions, not a cap: the loop
    # below is the real assertion, and it proves each of the three new patterns carries a polarity
    # its avg_move_label agrees with. A stat added without one fails here rather than shipping a
    # pattern the model reads with no direction.
    assert len(ALL_PATTERN_REFERENCE_STATS) == 11
    for stat in ALL_PATTERN_REFERENCE_STATS:
        label = stat.avg_move_label.lower()
        if "decline" in label:
            assert stat.expected_side == -1, stat.name
        elif "rise" in label:
            assert stat.expected_side == 1, stat.name
        else:
            pytest.fail(f"unexpected avg_move_label on {stat.name}: {stat.avg_move_label!r}")
