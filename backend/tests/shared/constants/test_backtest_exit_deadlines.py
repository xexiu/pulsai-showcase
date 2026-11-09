"""Tests for the backtest barrier-exit deadline policy + advisory."""

from __future__ import annotations

from src.shared.constants.backtest_exit_deadlines import (
    BARRIER_EXIT_STRATEGIES,
    build_barrier_deadline_warning,
    is_barrier_strategy,
    recommended_barrier_deadline,
)


class TestBarrierStrategyClassification:
    def test_in_sync_with_exit_strategy_enum(self) -> None:
        """BARRIER set == ExitStrategy values minus fixed_holding/raw_signal.

        Guards the string-based set (kept stringy to avoid a shared->infra import)
        against enum drift: a new ExitStrategy must be deliberately classified here.
        """
        from src.infrastructure.ml.backtester_types import ExitStrategy

        non_barrier = {ExitStrategy.FIXED_HOLDING.value, ExitStrategy.RAW_SIGNAL.value}
        expected = {strategy.value for strategy in ExitStrategy} - non_barrier
        assert expected == BARRIER_EXIT_STRATEGIES

    def test_is_barrier_strategy(self) -> None:
        assert is_barrier_strategy("atr_based")
        assert is_barrier_strategy("fixed_tpsl")
        assert not is_barrier_strategy("fixed_holding")  # holding IS the strategy
        assert not is_barrier_strategy("raw_signal")  # exits on opposite signal
        assert not is_barrier_strategy("nonsense")


class TestRecommendedBarrierDeadline:
    def test_fast_timeframe_floor_is_generous(self) -> None:
        # 5m: a 4-bar deadline (~20 min) starves a 2% barrier -> floor is much higher.
        assert recommended_barrier_deadline("5m") == 24

    def test_one_hour_floor(self) -> None:
        assert recommended_barrier_deadline("1h") == 8

    def test_unknown_timeframe_uses_default_floor(self) -> None:
        assert recommended_barrier_deadline("3m") == 8

    def test_case_insensitive(self) -> None:
        assert recommended_barrier_deadline("1H") == recommended_barrier_deadline("1h")

    def test_clamped_to_per_timeframe_max(self) -> None:
        from src.shared.backtest_holding_periods_bounds import resolve_backtest_holding_periods_max

        for timeframe in ("1m", "5m", "15m", "30m", "1h", "4h", "1d"):
            assert recommended_barrier_deadline(timeframe) <= resolve_backtest_holding_periods_max(timeframe)

    def test_every_trainable_timeframe_has_an_explicit_floor(self) -> None:
        """A missing row is not a crash -- it is the 8-bar default, silently.

        Measured 2026-10-11, before 1m had a row: the capital cert's barrier timeout for a 1m book
        was 8 bars (8 minutes) against 5m's 24 bars (2 hours), and nothing reported it.
        """
        from src.shared.constants.backtest_exit_deadlines import RECOMMENDED_BARRIER_MIN_DEADLINE_BY_TIMEFRAME
        from src.shared.constants.timeframes import VALID_TIMEFRAMES_SIGNAL_AND_TRAINING

        missing = sorted(VALID_TIMEFRAMES_SIGNAL_AND_TRAINING - set(RECOMMENDED_BARRIER_MIN_DEADLINE_BY_TIMEFRAME))

        assert not missing, f"trainable timeframes on the silent default deadline: {missing}"

    def test_1m_floor_is_5m_floor_in_wall_clock(self) -> None:
        """DERIVED from 5m by bars-per-day scaling (24 bars x 5 = 120 = the same 2 hours)."""
        from src.shared.constants.timeframes import TIMEFRAME_MS

        assert recommended_barrier_deadline("1m") * TIMEFRAME_MS["1m"] == recommended_barrier_deadline("5m") * TIMEFRAME_MS["5m"]


class TestBuildBarrierDeadlineWarning:
    def test_warns_when_barrier_deadline_too_tight(self) -> None:
        # The user's exact case: atr_based on 1h left at the default holding of 4.
        warning = build_barrier_deadline_warning(timeframe="1h", exit_strategy="atr_based", holding_periods=4)
        assert warning is not None
        assert "atr_based" in warning
        assert "timeout" in warning
        assert "8" in warning  # recommended minimum for 1h

    def test_no_warning_when_deadline_adequate(self) -> None:
        assert build_barrier_deadline_warning(timeframe="1h", exit_strategy="atr_based", holding_periods=8) is None
        assert build_barrier_deadline_warning(timeframe="1h", exit_strategy="atr_based", holding_periods=50) is None

    def test_no_warning_for_non_barrier_strategy(self) -> None:
        # fixed_holding's deadline IS the intended exit -> no advisory.
        assert build_barrier_deadline_warning(timeframe="5m", exit_strategy="fixed_holding", holding_periods=4) is None
        assert build_barrier_deadline_warning(timeframe="5m", exit_strategy="raw_signal", holding_periods=4) is None
