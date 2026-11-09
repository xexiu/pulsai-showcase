"""One declaration of the four ModelSpec coordinates, and one band check instead of 89.

Owner, 2026-09-11: "shouldnt we jsut use an parent class (base class) and everything extends from
it (sot) and ONLY overwrite if needs something custom??? :S"

WHAT THESE PIN, and why each case exists rather than being obvious:

* **the split is real** -- `ModelIdentity` rejects a missing coordinate, `ModelIdentityOptional`
  accepts all four missing. Measured, the corpus needs BOTH: `symbol` is declared 80x required
  and 19x defaulted, `timeframe` 66 / 23, `model_type` 12 / 20. A single base class would have to
  be wrong for one of those populations.
* **the band check is the payoff** -- `timeframe` is redeclared 89 times across 594 models, so any
  one of those declarations can quietly accept `3d` or `1m`. One validator, read from
  `timeframe_bands`, is the thing 89 careful authors could not achieve.
* **the band is DERIVED, not retyped** -- the test asserts membership against
  `HIGHER_TIMEFRAMES` / `LOWER_TIMEFRAMES` themselves, so adding a member to the registry changes
  the test's expectation with no edit here. `.claude/rules/full-htf-grid-always.md` exists because
  four prose sources hand-listed the HTF band and dropped `6h` for two weeks.
* **absent is not invalid** -- the optional variant shares the validator, so `None` must pass
  through untouched. Rejecting it would make every historical row unrepresentable.

REUSE-AUDIT: no existing test covers schema field optionality (`test_response_model_matches_return`
checks handler/response agreement; `test_signal_list_carries_model_identity` asserts a signal ROW
carries provenance, not how a schema declares it). Nothing here re-lists a timeframe band.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.shared.constants.timeframe_bands import HIGHER_TIMEFRAMES, LOWER_TIMEFRAMES
from src.shared.dto.model_identity import MODEL_TIMEFRAMES, ModelIdentity, ModelIdentityOptional

_VALID = {"symbol": "BTC/USDT", "timeframe": "1d", "version": 51, "model_type": "stacking"}


class TestTheRequiredVariant:
    def test_all_four_coordinates_round_trip(self) -> None:
        identity = ModelIdentity(**_VALID)

        assert (identity.symbol, identity.timeframe, identity.version, identity.model_type) == (
            "BTC/USDT",
            "1d",
            51,
            "stacking",
        )

    @pytest.mark.parametrize("missing", ["symbol", "timeframe", "version", "model_type"])
    def test_any_missing_coordinate_is_refused(self, missing: str) -> None:
        """Four coordinates address a book; three address a SET of them.

        `model_type` is in this list deliberately: versions are allocated per model_type, so
        `btc_usdt_1d v2` exists under three of them and a layout scan picks `bagging_regression`.
        """
        payload = {k: v for k, v in _VALID.items() if k != missing}

        with pytest.raises(ValidationError):
            ModelIdentity(**payload)

    @pytest.mark.parametrize("blank", ["symbol", "timeframe", "model_type"])
    def test_an_empty_string_is_not_a_coordinate(self, blank: str) -> None:
        """`min_length=1` matters: '' satisfies a bare `str` and then becomes a path segment."""
        with pytest.raises(ValidationError):
            ModelIdentity(**{**_VALID, blank: ""})


class TestTheBandCheckThatReplaces89Declarations:
    @pytest.mark.parametrize("timeframe", sorted(MODEL_TIMEFRAMES))
    def test_every_band_member_is_accepted(self, timeframe: str) -> None:
        """Derived from the registry, so a new band member needs no edit here."""
        assert ModelIdentity(**{**_VALID, "timeframe": timeframe}).timeframe == timeframe

    @pytest.mark.parametrize("timeframe", ["3d", "1w", "7h", "", "1D"])
    def test_a_non_band_timeframe_is_refused(self, timeframe: str) -> None:
        """`3d`/`1w` are chart-only -- neither is a model slot. (`1m` joined LTF on 2026-10-11.)

        `1D` is here because case-drift is the silent version of this bug: it looks right and
        matches nothing.
        """
        with pytest.raises(ValidationError):
            ModelIdentity(**{**_VALID, "timeframe": timeframe})

    def test_the_band_is_read_from_the_registry_not_retyped(self) -> None:
        """If this module ever hard-codes members, this fails the moment the registry changes."""
        assert frozenset(HIGHER_TIMEFRAMES) | frozenset(LOWER_TIMEFRAMES) == MODEL_TIMEFRAMES
        assert MODEL_TIMEFRAMES, "an empty band would make every timeframe invalid, silently"


class TestTheOptionalVariant:
    def test_every_coordinate_may_be_absent(self) -> None:
        """Responses and history rows: "no recorded model_type" is data, not a guess."""
        identity = ModelIdentityOptional()

        assert (identity.symbol, identity.timeframe, identity.version, identity.model_type) == (
            None,
            None,
            None,
            None,
        )

    def test_a_present_timeframe_is_still_band_checked(self) -> None:
        """Optional must not mean unvalidated -- that is how `3d` would reach a response."""
        with pytest.raises(ValidationError):
            ModelIdentityOptional(timeframe="3d")

    def test_a_present_valid_timeframe_passes(self) -> None:
        assert ModelIdentityOptional(timeframe="4h").timeframe == "4h"
