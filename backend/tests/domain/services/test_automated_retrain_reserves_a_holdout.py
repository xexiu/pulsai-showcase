"""An automated retrain must DECIDE about its holdout, or it refuses itself at progress 0.

DISMISSAL-CHECK: not a hypothesis (shared infra) -- this pins the production retraining path. No
signal, angle or edge is proposed.

MEASURED IN PRODUCTION, 2026-09-03. The whole `training_jobs` table is EIGHT rows and every one
carries status FAILED at `progress=0`. Seven of them were created in a single sweep at
2026-08-25 21:46:18-20 (4h, 4h, 6h, 6h, 8h, 12h, 1d) and every one died with the same message:

    refusing to train with no holdout: reserve an out-of-sample window by passing a
    data-end cutoff (YYYY-MM-DD), or state explicitly that this run trains up to now.

So the fleet's automatic retraining is not slow or backed up -- it is INERT, and has been since
at least 2026-08-25. Health fires, `check_all_triggers` / `check_critical_triggers` send
`train_model_task`, a PENDING row is written, and the holdout gate refuses it instantly.

THE GATE IS RIGHT; THE CALLER NEVER ANSWERS IT. `training_holdout_policy` refuses only
FORGETTING -- either choice is accepted. But `_finalize_retrain_config` copies the previous run's
config snapshot and re-targets it, and that snapshot carries no `data_end` and no `no_holdout`.
Nothing on the automated path ever makes the decision, so the gate can only ever refuse.

WHY THIS IS A MONEY DEFECT, not a plumbing one. It is the reason a degraded model STAYS
deployed: the trigger fires, the operator sees a job created, and nothing retrains. It is also
consistent with what prod's signal table shows -- several deployed versions emitting a single
constant action across every bar they have ever seen.

THE CUTOFF MUST SCALE WITH THE TIMEFRAME, which is the same rule this session applied to the
CERT ranker, the SELECT harness and the rolling-Sharpe window. A holdout is only useful if it
holds enough BARS to be measurable, and a fixed number of days holds 288x more 5m bars than 1d
bars. `days_for_bars` is the shared helper for exactly that conversion.

WHAT THIS TEST DOES NOT CLAIM: that a retrain will now SUCCEED. It pins that the run reaches the
model instead of being refused before it starts. Training can still fail on its own merits, and
that would be a different, honest failure.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.domain.services.training_holdout_policy import (
    HOLDOUT_MIN_BARS,
    HOLDOUT_MIN_DAYS,
    automated_retrain_data_end,
    has_holdout_decision,
    parse_data_end_cutoff,
)
from src.shared.constants.timeframe_bands import HIGHER_TIMEFRAMES, LOWER_TIMEFRAMES
from src.shared.constants.timeframes import bars_per_day

#: Both training bands, derived from the registry -- never hand-listed.
ALL_BANDS = (*LOWER_TIMEFRAMES, *HIGHER_TIMEFRAMES)

#: A fixed clock, so the assertions are about the RULE and not about the day the suite runs.
FROZEN_NOW = datetime(2026, 9, 3, 12, 30, 0, tzinfo=UTC)


class TestTheAutomatedPathNowDecides:
    @pytest.mark.parametrize("timeframe", ALL_BANDS)
    def test_a_cutoff_is_produced_for_every_banded_timeframe(self, timeframe: str) -> None:
        """The exact failure in prod: no cutoff, so the gate refuses before training starts."""
        cutoff = automated_retrain_data_end(timeframe, now=FROZEN_NOW)
        assert has_holdout_decision(data_end=cutoff, no_holdout=False)

    @pytest.mark.parametrize("timeframe", ALL_BANDS)
    def test_the_cutoff_is_a_parseable_date_in_the_past(self, timeframe: str) -> None:
        """A cutoff the pipeline cannot parse would be a false holdout, which is worse."""
        parsed = parse_data_end_cutoff(automated_retrain_data_end(timeframe, now=FROZEN_NOW))
        assert parsed is not None
        assert parsed < FROZEN_NOW


class TestTheReservedWindowScalesWithTheTimeframe:
    @pytest.mark.parametrize("timeframe", ALL_BANDS)
    def test_the_window_holds_at_least_the_minimum_bars(self, timeframe: str) -> None:
        """A holdout too short to hold bars is a holdout in name only."""
        parsed = parse_data_end_cutoff(automated_retrain_data_end(timeframe, now=FROZEN_NOW))
        assert parsed is not None
        reserved_days = (FROZEN_NOW - parsed).total_seconds() / 86_400.0
        assert reserved_days * bars_per_day(timeframe) >= HOLDOUT_MIN_BARS

    @pytest.mark.parametrize("timeframe", ALL_BANDS)
    def test_the_window_is_never_shorter_than_the_recency_floor(self, timeframe: str) -> None:
        """On 5m, 100 bars is about eight hours -- real in bars, meaningless as a market sample."""
        parsed = parse_data_end_cutoff(automated_retrain_data_end(timeframe, now=FROZEN_NOW))
        assert parsed is not None
        assert (FROZEN_NOW - parsed).days >= HOLDOUT_MIN_DAYS

    def test_a_daily_window_is_wider_than_an_hourly_one(self) -> None:
        """The whole point: the same bar count costs far more calendar on a slower timeframe."""
        daily = parse_data_end_cutoff(automated_retrain_data_end("1d", now=FROZEN_NOW))
        hourly = parse_data_end_cutoff(automated_retrain_data_end("1h", now=FROZEN_NOW))
        assert daily is not None
        assert hourly is not None
        assert daily < hourly


class TestItRefusesWhatItCannotAnswer:
    def test_an_unknown_timeframe_raises_rather_than_guessing(self) -> None:
        """Guessing a cutoff for an unlisted timeframe is how a false holdout gets reserved."""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            automated_retrain_data_end("not-a-timeframe", now=FROZEN_NOW)
