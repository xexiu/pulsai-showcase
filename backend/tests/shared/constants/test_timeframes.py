"""
TDD Tests for timeframe constants.

Timeframe constants define the duration of each candle type.

Phase 2 SoT (mandatory): VALID_TIMEFRAMES_SIGNAL_AND_TRAINING must be a subset of
TIMEFRAME_REGISTRY, and each such value must have a matching domain Timeframe enum member.
"""

from datetime import timedelta

from src.domain.enums import Timeframe as TimeframeEnum
from src.shared.constants.timeframes import (
    SUPPORTED_TIMEFRAME_VALUES,
    TIMEFRAME_DELTA,
    TIMEFRAME_MS,
    TIMEFRAME_REGISTRY,
    VALID_TIMEFRAMES_SIGNAL_AND_TRAINING,
    CandleOpenAlignment,
    get_last_closed_dt,
    get_supported_timeframes,
    last_closed_start_ms,
    period_start_ms,
    resolve_candle_open_alignment,
)


class TestValidTimeframesSoTAlignment:
    """
    Phase 2 mandatory tests: VALID_TIMEFRAMES_SIGNAL_AND_TRAINING and Timeframe enum.

    (a) Every value in VALID_TIMEFRAMES_SIGNAL_AND_TRAINING must be in TIMEFRAME_REGISTRY.
    (b) Every such value must have a matching Timeframe enum member (e.g. Timeframe("1h")).
    Guards against drift between registry, validation set, and domain enum.
    """

    def test_valid_timeframes_signal_and_training_subset_of_registry(self) -> None:
        """(a) Every value in VALID_TIMEFRAMES_SIGNAL_AND_TRAINING is in TIMEFRAME_REGISTRY."""
        registry_keys = set(TIMEFRAME_REGISTRY.keys())
        for tf in VALID_TIMEFRAMES_SIGNAL_AND_TRAINING:
            assert tf in registry_keys, f"{tf!r} is in VALID_TIMEFRAMES_SIGNAL_AND_TRAINING but not in TIMEFRAME_REGISTRY"

    def test_every_valid_timeframe_has_matching_domain_enum_member(self) -> None:
        """(b) Every value in VALID_TIMEFRAMES_SIGNAL_AND_TRAINING has a matching Timeframe enum."""
        for tf in VALID_TIMEFRAMES_SIGNAL_AND_TRAINING:
            parsed = TimeframeEnum(tf)
            assert parsed.value == tf, f"Timeframe({tf!r}).value should be {tf!r}, got {parsed.value!r}"

    def test_every_registry_key_has_matching_domain_enum_member(self) -> None:
        """Every TIMEFRAME_REGISTRY key must have a Timeframe enum member (incl. chart-only 3d/1w)."""
        for tf in TIMEFRAME_REGISTRY:
            parsed = TimeframeEnum(tf)
            assert parsed.value == tf

    def test_training_timeframes_ordered_includes_8h_and_12h(self) -> None:
        from src.shared.constants.timeframes import training_timeframes_ordered

        ordered = training_timeframes_ordered()
        assert "8h" in ordered
        assert "12h" in ordered
        assert ordered.index("8h") < ordered.index("12h") < ordered.index("1d")


class TestTimeframeMs:
    """Test timeframe millisecond constants."""

    def test_1m_timeframe(self) -> None:
        """1 minute = 60,000 ms."""
        assert TIMEFRAME_MS["1m"] == 60 * 1000

    def test_5m_timeframe(self) -> None:
        """5 minutes = 300,000 ms."""
        assert TIMEFRAME_MS["5m"] == 5 * 60 * 1000

    def test_15m_timeframe(self) -> None:
        """15 minutes = 900,000 ms."""
        assert TIMEFRAME_MS["15m"] == 15 * 60 * 1000

    def test_30m_timeframe(self) -> None:
        """30 minutes = 1,800,000 ms."""
        assert TIMEFRAME_MS["30m"] == 30 * 60 * 1000

    def test_1h_timeframe(self) -> None:
        """1 hour = 3,600,000 ms."""
        assert TIMEFRAME_MS["1h"] == 60 * 60 * 1000

    def test_4h_timeframe(self) -> None:
        """4 hours = 14,400,000 ms."""
        assert TIMEFRAME_MS["4h"] == 4 * 60 * 60 * 1000

    def test_8h_timeframe(self) -> None:
        """8 hours = 28,800,000 ms."""
        assert TIMEFRAME_MS["8h"] == 8 * 60 * 60 * 1000

    def test_12h_timeframe(self) -> None:
        """12 hours = 43,200,000 ms."""
        assert TIMEFRAME_MS["12h"] == 12 * 60 * 60 * 1000

    def test_1d_timeframe(self) -> None:
        """1 day = 86,400,000 ms."""
        assert TIMEFRAME_MS["1d"] == 24 * 60 * 60 * 1000

    def test_1w_timeframe(self) -> None:
        """1 week = 604,800,000 ms."""
        assert TIMEFRAME_MS["1w"] == 7 * 24 * 60 * 60 * 1000

    def test_3d_timeframe(self) -> None:
        """3 days = 259,200,000 ms (Binance native ``3d`` interval)."""
        assert TIMEFRAME_MS["3d"] == 3 * 24 * 60 * 60 * 1000


class TestTimeframeDelta:
    """Test timeframe timedelta constants."""

    def test_1m_timedelta(self) -> None:
        """1 minute timedelta."""
        assert TIMEFRAME_DELTA["1m"] == timedelta(minutes=1)

    def test_5m_timedelta(self) -> None:
        """5 minutes timedelta."""
        assert TIMEFRAME_DELTA["5m"] == timedelta(minutes=5)

    def test_15m_timedelta(self) -> None:
        """15 minutes timedelta."""
        assert TIMEFRAME_DELTA["15m"] == timedelta(minutes=15)

    def test_30m_timedelta(self) -> None:
        """30 minutes timedelta."""
        assert TIMEFRAME_DELTA["30m"] == timedelta(minutes=30)

    def test_1h_timedelta(self) -> None:
        """1 hour timedelta."""
        assert TIMEFRAME_DELTA["1h"] == timedelta(hours=1)

    def test_4h_timedelta(self) -> None:
        """4 hours timedelta."""
        assert TIMEFRAME_DELTA["4h"] == timedelta(hours=4)

    def test_1d_timedelta(self) -> None:
        """1 day timedelta."""
        assert TIMEFRAME_DELTA["1d"] == timedelta(days=1)

    def test_1w_timedelta(self) -> None:
        """1 week timedelta."""
        assert TIMEFRAME_DELTA["1w"] == timedelta(weeks=1)

    def test_3d_timedelta(self) -> None:
        """3 days timedelta."""
        assert TIMEFRAME_DELTA["3d"] == timedelta(days=3)


class TestTimeframeConsistency:
    """Test that MS and DELTA are consistent."""

    def test_ms_and_delta_match(self) -> None:
        """Milliseconds and timedelta should represent the same duration."""
        for tf in TIMEFRAME_MS:
            ms_value = TIMEFRAME_MS[tf]
            delta_value = TIMEFRAME_DELTA[tf]
            delta_ms = int(delta_value.total_seconds() * 1000)
            assert ms_value == delta_ms, f"Mismatch for {tf}: {ms_value} != {delta_ms}"

    def test_all_timeframes_present(self) -> None:
        """All supported timeframes should be present in both dicts."""
        # DERIVED, never retyped. This line used to list the keys by hand, so every
        # registry addition broke it and was 'fixed' by adding the new value — a test
        # that mirrors the config cannot detect the config being wrong. What matters is
        # that the derived view and the registry AGREE.
        expected = set(TIMEFRAME_REGISTRY.keys())
        assert set(TIMEFRAME_MS.keys()) == expected
        assert set(TIMEFRAME_DELTA.keys()) == expected

    def test_registry_is_the_single_source_for_derived_maps(self) -> None:
        """MS and timedelta views should both derive from the canonical registry."""
        assert list(TIMEFRAME_REGISTRY.keys()) == SUPPORTED_TIMEFRAME_VALUES
        for timeframe, definition in TIMEFRAME_REGISTRY.items():
            assert TIMEFRAME_DELTA[timeframe] == definition.delta
            assert TIMEFRAME_MS[timeframe] == int(definition.delta.total_seconds() * 1000)


class TestSupportedTimeframeFiltering:
    """Settings should treat configured timeframes as a validated registry filter."""

    def test_returns_all_registry_timeframes_when_config_is_empty(self) -> None:
        """Blank config should fall back to the canonical registry ordering."""
        assert get_supported_timeframes("") == SUPPORTED_TIMEFRAME_VALUES

    def test_preserves_order_and_deduplicates_known_timeframes(self) -> None:
        """Configured values should be a stable subset of the canonical registry."""
        assert get_supported_timeframes("4h,1h,4h,15m") == ["4h", "1h", "15m"]


class TestTimeframeHelpers:
    """Time alignment helpers (SoT for period-boundary math)."""

    def test_get_last_closed_dt_rejects_unknown_timeframe(self) -> None:
        """BEHAVIOR: Unknown timeframe must raise ValueError (fail fast), not fall back to a default."""
        import pytest

        with pytest.raises(ValueError, match=r"Unsupported timeframe"):
            get_last_closed_dt("not-a-timeframe")

    def test_period_start_ms_returns_current_period_start(self) -> None:
        """BEHAVIOR: period_start_ms(now_ms, tf_ms) = start of forming candle (SoT for fetcher/market)."""
        tf_1h_ms = TIMEFRAME_MS["1h"]
        # 2026-03-16 11:30:00 UTC -> period start 11:00 UTC
        # 11:30 UTC = 11*3600 + 30*60 = 41400 sec since midnight; use a fixed epoch ms
        from datetime import UTC, datetime

        at_1130_utc = datetime(2026, 3, 16, 11, 30, 0, tzinfo=UTC)
        now_ms = int(at_1130_utc.timestamp() * 1000)
        got = period_start_ms(now_ms, tf_1h_ms)
        expected_11_utc_ms = int(datetime(2026, 3, 16, 11, 0, 0, tzinfo=UTC).timestamp() * 1000)
        assert got == expected_11_utc_ms, "11:30 UTC with 1h tf should give 11:00 UTC period start"

    def test_last_closed_start_ms_returns_previous_period_start(self) -> None:
        """BEHAVIOR: last_closed_start_ms(now_ms, tf_ms) = start of last closed candle (exclude forming)."""
        tf_1h_ms = TIMEFRAME_MS["1h"]
        from datetime import UTC, datetime

        at_1130_utc = datetime(2026, 3, 16, 11, 30, 0, tzinfo=UTC)
        now_ms = int(at_1130_utc.timestamp() * 1000)
        got = last_closed_start_ms(now_ms, tf_1h_ms)
        expected_10_utc_ms = int(datetime(2026, 3, 16, 10, 0, 0, tzinfo=UTC).timestamp() * 1000)
        assert got == expected_10_utc_ms, "11:30 UTC with 1h tf should give 10:00 UTC last closed"

    def test_last_closed_start_ms_all_supported_timeframes(self) -> None:
        """
        BEHAVIOR: last_closed_start_ms is correct for every supported TF (5m, 15m, 30m, 1h, 4h, 1d, 1w).

        Dynamic per-TF formula must yield the previous period start for each.
        @see SIGNAL_CANDLE_TIMEZONE_ARCHITECTURE.md §6; CODING_STANDARDS §9.
        """
        from datetime import UTC, datetime

        # 2026-03-16 14:10 UTC — not on a boundary for most TFs
        at_1410_utc = datetime(2026, 3, 16, 14, 10, 0, tzinfo=UTC)
        now_ms = int(at_1410_utc.timestamp() * 1000)

        expectations = [
            ("5m", datetime(2026, 3, 16, 14, 5, 0, tzinfo=UTC)),  # 14:05 bar closed
            (
                "15m",
                datetime(2026, 3, 16, 13, 45, 0, tzinfo=UTC),
            ),  # 13:45–14:00 bar closed  # noqa: RUF003
            ("30m", datetime(2026, 3, 16, 13, 30, 0, tzinfo=UTC)),  # 13:30 bar closed
            ("1h", datetime(2026, 3, 16, 13, 0, 0, tzinfo=UTC)),  # 13:00 bar closed
            (
                "4h",
                datetime(2026, 3, 16, 8, 0, 0, tzinfo=UTC),
            ),  # 08:00–12:00 bar closed  # noqa: RUF003
            ("1d", datetime(2026, 3, 15, 0, 0, 0, tzinfo=UTC)),  # previous day 00:00
            # Binance 3d opens on the epoch+1d grid (not pure epoch). At 2026-03-16
            # 14:10 the forming bar opened 2026-03-15; last closed opened 2026-03-12.
            ("3d", datetime(2026, 3, 12, 0, 0, 0, tzinfo=UTC)),
            # 2026-03-16 is a Monday; the last *closed* weekly bar opens the prior
            # Monday (2026-03-09). Binance weekly candles open Monday 00:00 UTC, NOT
            # the epoch-aligned Thursday boundary (1970-01-01 was a Thursday).
            ("1w", datetime(2026, 3, 9, 0, 0, 0, tzinfo=UTC)),
        ]
        for timeframe, expected_dt in expectations:
            tf_ms = TIMEFRAME_MS[timeframe]
            got_ms = last_closed_start_ms(now_ms, tf_ms)
            expected_ms = int(expected_dt.timestamp() * 1000)
            assert got_ms == expected_ms, f"last_closed_start_ms({timeframe}) at 14:10 should be {expected_dt}, got ms={got_ms}"


class TestWeeklyMondayAlignment:
    """
    BEHAVIOR: weekly candle boundaries align to Monday 00:00 UTC (exchange convention),
    not the epoch-aligned Thursday boundary.

    Root cause this guards: ``(now_ms // tf_ms) * tf_ms`` anchors weekly buckets to the
    Unix epoch (1970-01-01, a Thursday). Binance/most exchanges open weekly candles on
    Monday, so the naive floor mislabels the week — the chart then drops the genuinely
    closed Monday week as if it were still forming.

    @see docs/02-technical/CHART_OHLCV_FORMING_BAR_POLICY.md
    """

    def test_period_start_ms_weekly_opens_on_monday(self) -> None:
        """Forming weekly bar opens on the Monday of the current week (UTC), not Thursday."""
        from datetime import UTC, datetime

        # 2026-06-01 is a Monday; 18:00 UTC is mid-week.
        now_ms = int(datetime(2026, 6, 1, 18, 0, 0, tzinfo=UTC).timestamp() * 1000)
        got = period_start_ms(now_ms, TIMEFRAME_MS["1w"])
        expected = int(datetime(2026, 6, 1, 0, 0, 0, tzinfo=UTC).timestamp() * 1000)
        assert got == expected, "weekly forming bar must open Monday 2026-06-01 00:00 UTC"

    def test_last_closed_start_ms_weekly_is_previous_monday(self) -> None:
        """REGRESSION (1w chart gap): last closed weekly bar is the prior Monday week.

        On Mon 2026-06-01 the week of Mon 2026-05-25 has fully closed (it ended
        2026-06-01 00:00). The buggy epoch-floor returned 2026-05-21 (Thu), which
        dropped the closed 05-25 week from the chart.
        """
        from datetime import UTC, datetime

        now_ms = int(datetime(2026, 6, 1, 18, 0, 0, tzinfo=UTC).timestamp() * 1000)
        got = last_closed_start_ms(now_ms, TIMEFRAME_MS["1w"])
        expected = int(datetime(2026, 5, 25, 0, 0, 0, tzinfo=UTC).timestamp() * 1000)
        assert got == expected, "last closed weekly bar must be Monday 2026-05-25, not the Thursday epoch boundary"

    def test_get_last_closed_dt_weekly_returns_a_monday(self) -> None:
        """``get_last_closed_dt('1w')`` must always land on a Monday (weekday() == 0)."""
        got = get_last_closed_dt("1w")
        assert got.weekday() == 0, f"weekly last-closed open must be a Monday, got {got} (weekday={got.weekday()})"
        assert got.hour == 0, "weekly bar opens at 00:00 UTC (hour)"
        assert got.minute == 0, "weekly bar opens at 00:00 UTC (minute)"
        assert got.second == 0, "weekly bar opens at 00:00 UTC (second)"

    def test_sub_week_timeframes_unchanged_by_monday_anchor(self) -> None:
        """The Monday anchor must be a no-op for every sub-week TF (identical to epoch floor).

        4 days (epoch→Monday offset) is a whole multiple of 1m/5m/15m/30m/1h/4h/1d, so
        the anchored floor must equal the plain epoch floor for those timeframes.
        """
        from datetime import UTC, datetime

        now_ms = int(datetime(2026, 6, 1, 18, 37, 0, tzinfo=UTC).timestamp() * 1000)
        for timeframe in ("1m", "5m", "15m", "30m", "1h", "4h", "1d"):
            tf_ms = TIMEFRAME_MS[timeframe]
            assert period_start_ms(now_ms, tf_ms) == (now_ms // tf_ms) * tf_ms, (
                f"{timeframe}: Monday anchor must not change epoch-aligned sub-week buckets"
            )


class TestThreeDayBinanceAlignment:
    """
    BEHAVIOR: Binance ``3d`` candle opens use epoch + 1 day, not pure epoch floor.

    Live Binance BTCUSDT 3d opens (verified 2026-08-09) are always ``floor_eq=False``
    with ``delta=86400000`` vs naive ``(now // 3d) * 3d``. Bitget ``3d`` uses a
    different phase — PulsAI OHLCV/chart SoT is Binance-canonical (same choice as
    weekly Monday alignment).
    """

    def test_period_start_ms_matches_binance_open_grid(self) -> None:
        """Forming 3d bar open matches a real Binance open (2026-08-09 00:00 UTC)."""
        from datetime import UTC, datetime

        # Mid-bar on the Binance 3d that opened Sunday 2026-08-09.
        now_ms = int(datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC).timestamp() * 1000)
        got = period_start_ms(now_ms, TIMEFRAME_MS["3d"])
        expected = int(datetime(2026, 8, 9, 0, 0, 0, tzinfo=UTC).timestamp() * 1000)
        assert got == expected

    def test_last_closed_start_ms_is_prior_binance_3d_open(self) -> None:
        """Last closed 3d bar is the prior Binance open (2026-08-06), not epoch floor."""
        from datetime import UTC, datetime

        now_ms = int(datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC).timestamp() * 1000)
        got = last_closed_start_ms(now_ms, TIMEFRAME_MS["3d"])
        expected = int(datetime(2026, 8, 6, 0, 0, 0, tzinfo=UTC).timestamp() * 1000)
        assert got == expected

    def test_naive_epoch_floor_is_wrong_for_binance_3d(self) -> None:
        """REGRESSION: pure epoch floor must not be used for 3d (off by 1 day)."""
        from datetime import UTC, datetime

        open_ms = int(datetime(2026, 8, 9, 0, 0, 0, tzinfo=UTC).timestamp() * 1000)
        tf_ms = TIMEFRAME_MS["3d"]
        naive = (open_ms // tf_ms) * tf_ms
        assert naive != open_ms
        assert period_start_ms(open_ms, tf_ms) == open_ms

    def test_3d_excluded_from_signal_and_training_set(self) -> None:
        """Chart/product TF first — same posture as 1w (not in live signal alignment)."""
        assert "3d" not in VALID_TIMEFRAMES_SIGNAL_AND_TRAINING
        assert "3d" in TIMEFRAME_REGISTRY

    def test_3d_in_default_supported_product_list(self) -> None:
        from src.shared.constants.timeframes import DEFAULT_SUPPORTED_TIMEFRAME_VALUES

        assert "3d" in DEFAULT_SUPPORTED_TIMEFRAME_VALUES
        assert DEFAULT_SUPPORTED_TIMEFRAME_VALUES.index("1d") < DEFAULT_SUPPORTED_TIMEFRAME_VALUES.index("3d")
        assert DEFAULT_SUPPORTED_TIMEFRAME_VALUES.index("3d") < DEFAULT_SUPPORTED_TIMEFRAME_VALUES.index("1w")


class TestIsIntradayTimeframe:
    """BEHAVIOR: multi-day TFs (1d/3d/1w) are not intraday; sub-day TFs are."""

    def test_sub_day_is_intraday(self) -> None:
        from src.shared.constants.timeframes import is_intraday_timeframe

        for tf in ("5m", "1h", "4h", "8h", "12h"):
            assert is_intraday_timeframe(tf) is True, tf

    def test_multi_day_is_not_intraday(self) -> None:
        from src.shared.constants.timeframes import is_intraday_timeframe

        for tf in ("1d", "3d", "1w"):
            assert is_intraday_timeframe(tf) is False, tf

    def test_unknown_fails_fast(self) -> None:
        import pytest

        from src.shared.constants.timeframes import is_intraday_timeframe

        with pytest.raises(ValueError, match="Unsupported timeframe"):
            is_intraday_timeframe("not-a-timeframe")


class TestCandleOpenAlignmentRegistry:
    """
    BEHAVIOR + EXTENSIBILITY GUARD: every registry timeframe must declare an alignment the
    boundary math can resolve, so adding a TF is pure data and a half-added one fails loudly.

    This is the architectural safety net for "is it ready for 3m/30s/1M?":
    - Any new fixed-duration TF (3m, 30s, …) defaults to EPOCH and just works.
    - A TF declaring an alignment with no implemented anchor (e.g. a future calendar month)
      makes ``period_start_ms`` raise here in CI instead of silently dropping candles.
    """

    def test_every_registry_timeframe_resolves_a_period_start(self) -> None:
        """period_start_ms must not KeyError for any declared timeframe (anchor implemented)."""
        now_ms = 1_900_000_000_000  # arbitrary fixed epoch-ms
        for timeframe, definition in TIMEFRAME_REGISTRY.items():
            got = period_start_ms(now_ms, definition.milliseconds)
            assert got <= now_ms, f"{timeframe}: period start must be at or before now"
            assert now_ms - got < definition.milliseconds, f"{timeframe}: now must fall within the resolved bucket"

    def test_weekly_declares_monday_alignment(self) -> None:
        """1w must opt into Monday alignment; this is what fixed the chart gap."""
        assert TIMEFRAME_REGISTRY["1w"].open_alignment is CandleOpenAlignment.WEEKLY_MONDAY

    def test_3d_declares_binance_alignment(self) -> None:
        """3d must opt into Binance epoch+1d alignment (naive epoch floor is off by 1 day)."""
        assert TIMEFRAME_REGISTRY["3d"].open_alignment is CandleOpenAlignment.THREE_DAY_BINANCE

    def test_sub_week_timeframes_default_to_epoch_alignment(self) -> None:
        """Every fixed-duration sub-week TF stays EPOCH-aligned (no Monday anchor)."""
        for timeframe in ("1m", "5m", "15m", "30m", "1h", "4h", "1d"):
            assert TIMEFRAME_REGISTRY[timeframe].open_alignment is CandleOpenAlignment.EPOCH, (
                f"{timeframe}: sub-week timeframe must default to EPOCH alignment"
            )

    def test_unregistered_duration_resolves_to_epoch(self) -> None:
        """An ad-hoc/unregistered duration (e.g. a future 3m before it's added) floors at epoch."""
        three_minutes_ms = 3 * 60 * 1000
        assert resolve_candle_open_alignment(three_minutes_ms) is CandleOpenAlignment.EPOCH

    def test_registered_durations_resolve_to_their_declared_alignment(self) -> None:
        """resolve_candle_open_alignment is registry-driven for every supported timeframe."""
        for definition in TIMEFRAME_REGISTRY.values():
            assert resolve_candle_open_alignment(definition.milliseconds) is definition.open_alignment
