"""Health shared constants — admin summary latency window SoT."""

from src.shared.constants.health import HEALTH_SUMMARY_LATENCY_PERIOD_HOURS


def test_health_summary_latency_period_hours_covers_daily_and_below_tfs() -> None:
    """WHEN ops review inference latency THEN lookback spans at least one 1d close."""
    assert HEALTH_SUMMARY_LATENCY_PERIOD_HOURS == 24
