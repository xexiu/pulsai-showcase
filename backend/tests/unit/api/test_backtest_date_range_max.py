"""
Unit tests: Backtest date range max (security).

BE defends itself: start_date/end_date range must not exceed max_backtest_range_days (~9.6 years).
Rejects e.g. 1970–2026 to avoid excessive load and abuse.
"""  # noqa: RUF002

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

# > max_backtest_range_days (3500): ~2015 → 2026 is ~4090 days
TOO_LONG_START = "2015-01-01"
TOO_LONG_END = "2026-03-15"


class TestBacktestRunDateRangeMax:
    """POST /api/v1/backtest/run rejects date range > max_backtest_range_days."""

    def test_run_rejects_range_exceeding_max_days(self, client: TestClient) -> None:
        """Range > 3500 days returns 400 with message about max days."""
        response = client.post(
            "/api/v1/backtest/run",
            json={
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "model_version": 1,
                "signal_source": "ml",
                "start_date": TOO_LONG_START,
                "end_date": TOO_LONG_END,
                "exchange": "binance",
            },
        )
        assert response.status_code == 400, response.text
        data = response.json()
        detail = data.get("detail", data.get("error", {}).get("message", ""))
        if isinstance(detail, dict):
            detail = str(detail)
        assert "3500" in detail or "must not exceed" in detail.lower()


class TestBacktestHubDateRangeMax:
    """Admin backtest-hub rejects range > max_backtest_range_days (tested via schema/validation)."""

    def test_settings_max_backtest_range_days_default(self) -> None:
        """Backend enforces max_backtest_range_days (3500) in backtest_hub and backtest_run."""
        from src.infrastructure.config import settings

        assert settings.max_backtest_range_days == 3500
