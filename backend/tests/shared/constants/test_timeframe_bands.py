"""LTF vs HTF as ONE source of truth, and 2h / 6h exist.

Owner, 2026-08-12: *"lower timeframes are 5m,15m,30m,1h,2h and Higher timeframes are
4h,6h,8h,12h,1d ... SoT, centralized ... so later can train ML on HTF / on LTF shared SoT from
BE"*.

WHY A BAND SoT AND NOT A LITERAL AT EACH CALL SITE. The edge-hunt rules already say "the FULL grid
4h/8h/12h/1d" in prose, and that prose is retyped into scripts as tuple literals. Today cost a day
proving what a retyped ladder does: `CAPITAL_MODES` held spot/3x/5x/8x while the rule mandated
spot+3..8x, so **4x, 6x and 7x had never been computed in any of 38 certs** — and the two sweeps
that read it by array position silently covered 2 and 3 lanes. A band that is DERIVED cannot drift
from the band that is DECLARED.

2h and 6h both divide a UTC day evenly (12 and 4 buckets), so `CandleOpenAlignment.EPOCH` is
correct for them exactly as it is for 4h/8h/12h — no new alignment strategy, which is what makes
this a safe addition rather than the calendar-timeframe problem the registry docstring warns about.
"""

from __future__ import annotations

import pytest

from src.shared.constants.timeframe_bands import (
    HIGHER_TIMEFRAMES,
    LOWER_TIMEFRAMES,
    band_for_timeframe,
    is_higher_timeframe,
)
from src.shared.constants.timeframes import (
    _DEFAULT_EXCLUDED_TIMEFRAMES,
    ALIGNMENT_TIMEFRAMES_ORDER,
    BANDED_TIMEFRAMES_ORDER,
    DEFAULT_SUPPORTED_TIMEFRAME_VALUES,
    SUPPORTED_TIMEFRAME_VALUES,
    TIMEFRAME_LABELS,
    TIMEFRAME_REGISTRY,
    VALID_TIMEFRAMES_SIGNAL_AND_TRAINING,
    TimeframeBand,
    build_public_timeframe_options,
    get_timeframe_ms,
)


class TestTheNewTimeframesExist:
    @pytest.mark.parametrize("timeframe", ["2h", "6h"])
    def test_it_is_in_the_registry(self, timeframe: str) -> None:
        assert timeframe in TIMEFRAME_REGISTRY

    def test_2h_is_two_hours_and_6h_is_six(self) -> None:
        hour_ms = get_timeframe_ms("1h")

        assert get_timeframe_ms("2h") == 2 * hour_ms
        assert get_timeframe_ms("6h") == 6 * hour_ms

    @pytest.mark.parametrize("timeframe", ["2h", "6h"])
    def test_it_divides_a_day_evenly_so_epoch_alignment_is_correct(self, timeframe: str) -> None:
        """The property that makes EPOCH alignment right — and that 3d lacks."""
        day_ms = get_timeframe_ms("1d")

        assert day_ms % get_timeframe_ms(timeframe) == 0


class TestTheBandsAreExactlyWhatWasSpecified:
    def test_lower_timeframes(self) -> None:
        """Owner, 2026-10-11: *"ALL must be for 1min timeframe ... add 1min to LTF"*."""
        assert LOWER_TIMEFRAMES == ("1m", "5m", "15m", "30m", "1h", "2h")

    def test_higher_timeframes(self) -> None:
        assert HIGHER_TIMEFRAMES == ("4h", "6h", "8h", "12h", "1d")

    def test_the_bands_do_not_overlap(self) -> None:
        assert not set(LOWER_TIMEFRAMES) & set(HIGHER_TIMEFRAMES)

    def test_every_band_member_is_a_real_registry_timeframe(self) -> None:
        """A band naming a timeframe the system cannot resolve is a crash waiting for a caller."""
        for timeframe in (*LOWER_TIMEFRAMES, *HIGHER_TIMEFRAMES):
            assert timeframe in TIMEFRAME_REGISTRY, timeframe

    def test_the_bands_are_ordered_shortest_first(self) -> None:
        """Ordering is part of the contract: grids and reports iterate these and must be stable."""
        for band in (LOWER_TIMEFRAMES, HIGHER_TIMEFRAMES):
            durations = [get_timeframe_ms(tf) for tf in band]
            assert durations == sorted(durations), band

    def test_every_lower_is_strictly_shorter_than_every_higher(self) -> None:
        """The names have to mean what they say — 'higher' must actually be longer."""
        assert max(get_timeframe_ms(t) for t in LOWER_TIMEFRAMES) < min(get_timeframe_ms(t) for t in HIGHER_TIMEFRAMES)


class TestBandLookup:
    @pytest.mark.parametrize("timeframe", ["1m", "5m", "15m", "30m", "1h", "2h"])
    def test_lower_timeframes_resolve_to_lower(self, timeframe: str) -> None:
        assert is_higher_timeframe(timeframe) is False
        assert band_for_timeframe(timeframe) == "ltf"

    @pytest.mark.parametrize("timeframe", ["4h", "6h", "8h", "12h", "1d"])
    def test_higher_timeframes_resolve_to_higher(self, timeframe: str) -> None:
        assert is_higher_timeframe(timeframe) is True
        assert band_for_timeframe(timeframe) == "htf"

    @pytest.mark.parametrize("timeframe", ["3d", "1w", "nonsense", ""])
    def test_a_timeframe_in_neither_band_is_none_not_a_guess(self, timeframe: str) -> None:
        """3d and 1w are real timeframes and belong to NEITHER training band (1m joined LTF 2026-10-11).

        None, never a default: silently bucketing an unlisted timeframe into one band is how a
        model gets trained on a grid nobody chose.
        """
        assert band_for_timeframe(timeframe) is None
        assert is_higher_timeframe(timeframe) is None


class TestTheBandIsDECLAREDOnceOnTheRegistry:
    """The band is a field on TimeframeDefinition; these lists are VIEWS of it.

    The first version of `timeframe_bands.py` declared its own `_LOWER_RAW` / `_HIGHER_RAW`
    tuples — a second copy of the registry, free to drift from it, which is the very defect the
    module was written to prevent one level up.
    """

    def test_the_exported_bands_are_derived_from_the_registry_field(self) -> None:
        assert tuple(tf for tf, d in TIMEFRAME_REGISTRY.items() if d.band is TimeframeBand.LOWER) == LOWER_TIMEFRAMES
        assert tuple(tf for tf, d in TIMEFRAME_REGISTRY.items() if d.band is TimeframeBand.HIGHER) == HIGHER_TIMEFRAMES

    def test_every_banded_registry_entry_is_exported_in_exactly_one_band(self) -> None:
        """No banded timeframe can be declared and then left out of both exported views."""
        banded = {tf for tf, d in TIMEFRAME_REGISTRY.items() if d.band is not None}

        assert banded == set(LOWER_TIMEFRAMES) | set(HIGHER_TIMEFRAMES)
        assert not set(LOWER_TIMEFRAMES) & set(HIGHER_TIMEFRAMES)


class TestABandedTimeframeIsActuallyLIVE:
    """THE REGRESSION: 2h and 6h were added to the registry and to NOTHING else.

    They looked shipped and were inert — no label (a bare `KeyError` the first time
    `/config/public` was served), missing from the default supported list (so no OHLCV sync and
    invisible to the frontend), missing from the training set (untrainable) and missing from the
    cron alignment order (their closes never fired). Four separate lists, each retyped by hand.

    These assertions are written over EVERY banded timeframe, not just 2h/6h: a test that names
    only today's additions cannot catch tomorrow's.
    """

    @pytest.mark.parametrize("timeframe", ["2h", "6h"])
    def test_the_new_timeframes_are_banded(self, timeframe: str) -> None:
        assert band_for_timeframe(timeframe) is not None

    def test_every_banded_timeframe_can_be_trained_and_generate_signals(self) -> None:
        assert set(LOWER_TIMEFRAMES) | set(HIGHER_TIMEFRAMES) == VALID_TIMEFRAMES_SIGNAL_AND_TRAINING

    def test_the_cron_notices_the_close_of_every_banded_timeframe_prod_serves(self) -> None:
        """A timeframe prod serves and generates signals on, whose close nothing watches, never fires.

        The cron's list is the banded timeframes prod SERVES, not every banded one: 1m is trainable
        (owner, 2026-10-11) but deliberately not served, and a cron that watched it would generate
        and store signals for a timeframe prod has no OHLCV for.
        """
        served_banded = [tf for tf in BANDED_TIMEFRAMES_ORDER if tf not in _DEFAULT_EXCLUDED_TIMEFRAMES]

        assert list(ALIGNMENT_TIMEFRAMES_ORDER) == served_banded

    def test_every_banded_timeframe_is_served_by_default_except_the_named_opt_in_set(self) -> None:
        """No prod env var sets SUPPORTED_TIMEFRAMES (all 72 checked), so the default list IS prod.

        The only banded timeframes kept off it are the NAMED opt-in exclusions, and that set is
        exactly {1m}: the prod DB volume filled up once, and a 1m OHLCV sync is 1,440 rows per
        symbol per day -- so 1m is trainable and researchable, and served only when an operator
        opts in through SUPPORTED_TIMEFRAMES. A second banded timeframe silently missing from the
        default surface is the 2h/6h defect this class exists for, and fails here.
        """
        unserved_banded = VALID_TIMEFRAMES_SIGNAL_AND_TRAINING - set(DEFAULT_SUPPORTED_TIMEFRAME_VALUES)

        assert unserved_banded == _DEFAULT_EXCLUDED_TIMEFRAMES
        assert frozenset({"1m"}) == _DEFAULT_EXCLUDED_TIMEFRAMES

    def test_1m_is_trainable_but_stays_out_of_every_prod_surface(self) -> None:
        """Training and research take 1m; /config/public, the OHLCV sync and the cron do not."""
        assert "1m" in VALID_TIMEFRAMES_SIGNAL_AND_TRAINING
        assert "1m" not in DEFAULT_SUPPORTED_TIMEFRAME_VALUES
        assert "1m" not in ALIGNMENT_TIMEFRAMES_ORDER


class TestPublicConfigCannotKeyError:
    def test_every_registry_timeframe_has_a_label(self) -> None:
        """`build_public_timeframe_options` indexes TIMEFRAME_LABELS[tf] directly.

        The original guard only checked the harmless direction (a label for a timeframe that does
        not exist). A registry entry with no label is the one that breaks: GET /config/public
        raises KeyError and the entire frontend fails to boot.
        """
        assert set(TIMEFRAME_REGISTRY) == set(TIMEFRAME_LABELS)

    def test_public_options_render_for_the_whole_registry(self) -> None:
        options = build_public_timeframe_options(SUPPORTED_TIMEFRAME_VALUES)

        assert {option.value for option in options} == set(TIMEFRAME_REGISTRY)
        assert all(option.label for option in options)
