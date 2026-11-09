"""Training timeframe policies must cover every signal/training registry timeframe."""

from src.infrastructure.config.training import TRAINING_TIMEFRAME_POLICIES, get_training_timeframe_policy
from src.shared.constants.timeframes import TIMEFRAME_MS, VALID_TIMEFRAMES_SIGNAL_AND_TRAINING


class TestTrainingTimeframePolicies:
    def test_every_valid_training_timeframe_has_explicit_policy(self) -> None:
        for tf in VALID_TIMEFRAMES_SIGNAL_AND_TRAINING:
            assert tf in TRAINING_TIMEFRAME_POLICIES, f"missing training policy for {tf!r}"
            policy = get_training_timeframe_policy(tf)
            assert policy.threshold_pct > 0
            assert policy.holding_periods > 0


class TestThe1mPolicyIsDerivedFrom5m:
    """1m joined the LTF band on 2026-10-11; its label policy is DERIVED, never invented.

    1m labels the same one-hour forward move that 5m labels: the horizon is 5m's 12 bars scaled by
    bars-per-day (x5), and the same wall-clock window sees the same forward-return distribution, so
    5m's threshold carries over unchanged.
    """

    def test_1m_label_horizon_covers_the_same_wall_clock_as_5m(self) -> None:
        one_minute = get_training_timeframe_policy("1m")
        five_minute = get_training_timeframe_policy("5m")

        assert one_minute.holding_periods * TIMEFRAME_MS["1m"] == five_minute.holding_periods * TIMEFRAME_MS["5m"]

    def test_1m_label_threshold_equals_5m_because_the_window_is_the_same(self) -> None:
        assert get_training_timeframe_policy("1m").threshold_pct == get_training_timeframe_policy("5m").threshold_pct
