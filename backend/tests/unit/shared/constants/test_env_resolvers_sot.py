"""The env-var resolvers that were copied into FOUR CONSTANTS modules.

REUSE-AUDIT: searched `src/shared/constants/` for an existing env/resolve/coerce helper module —
there is none, so this consolidates rather than forks. Considered leaving the copies in place and
rejected it: the whole point of a constants module is to be the single source of truth, and the
duplication was sitting inside the four files whose job that is.

MEASURED 2026-08-26 (`analyze kind=clones`, min_similarity 0.9), two similarity-1.00 clusters:

    _resolve_positive_int / _resolve_non_negative_int / _resolve_non_negative_float
        ohlcv_sources.py, signal_freshness.py, spike_alert.py
    _resolve_positive_float
        observability_metrics.py, ohlcv_sources.py

The owner named this exact shape: *"a CONST bla can be repeted in lots of files instead of SoT,
centralized."*

The FOURTH file was found by the pre-write clone guard, not by grep — a name search for
`_resolve_positive_int` never reaches a module that only copied the float one. That guard shipped
hours earlier in this same session, and this is its first real catch.

Five resolvers, ONE kernel. Writing four near-identical functions in the module whose purpose is to
delete near-identical functions would have re-created the cluster one directory over — so the
parsing/flooring lives in `_resolve_number` and the public four are thin typed wrappers that exist
for the type signature (int vs float) and for readability at the call site.
"""

from __future__ import annotations

import pytest  # noqa: TC002 - runtime fixture type

from src.shared.constants._env_resolvers import (
    env_source,
    resolve_non_negative_float,
    resolve_non_negative_int,
    resolve_positive_float,
    resolve_positive_int,
)


class TestPositiveInt:
    def test_a_valid_value_is_used(self) -> None:
        assert resolve_positive_int(env={"X": "42"}, var="X", default=7) == 42

    def test_a_missing_var_falls_back(self) -> None:
        assert resolve_positive_int(env={}, var="X", default=7) == 7

    def test_a_non_numeric_value_falls_back(self) -> None:
        assert resolve_positive_int(env={"X": "abc"}, var="X", default=7) == 7

    def test_zero_falls_back_because_the_floor_is_one(self) -> None:
        assert resolve_positive_int(env={"X": "0"}, var="X", default=7) == 7

    def test_one_is_accepted_at_the_floor(self) -> None:
        assert resolve_positive_int(env={"X": "1"}, var="X", default=7) == 1

    def test_a_negative_value_falls_back(self) -> None:
        assert resolve_positive_int(env={"X": "-3"}, var="X", default=7) == 7


class TestNonNegativeInt:
    def test_zero_is_allowed(self) -> None:
        """The difference from positive-int, and the reason both exist."""
        assert resolve_non_negative_int(env={"X": "0"}, var="X", default=7) == 0

    def test_a_negative_value_falls_back(self) -> None:
        assert resolve_non_negative_int(env={"X": "-1"}, var="X", default=7) == 7

    def test_a_float_string_falls_back(self) -> None:
        """`int("1.5")` raises — the value is malformed for an int setting, so the default wins."""
        assert resolve_non_negative_int(env={"X": "1.5"}, var="X", default=7) == 7


class TestPositiveFloat:
    def test_a_valid_value_is_used(self) -> None:
        assert resolve_positive_float(env={"X": "2.5"}, var="X", default=1.0) == 2.5

    def test_zero_falls_back_because_the_floor_is_strictly_above_zero(self) -> None:
        assert resolve_positive_float(env={"X": "0"}, var="X", default=1.0) == 1.0

    def test_a_tiny_positive_value_is_accepted(self) -> None:
        assert resolve_positive_float(env={"X": "0.001"}, var="X", default=1.0) == 0.001


class TestNonNegativeFloat:
    def test_zero_is_allowed(self) -> None:
        assert resolve_non_negative_float(env={"X": "0"}, var="X", default=1.0) == 0.0

    def test_a_negative_value_falls_back(self) -> None:
        assert resolve_non_negative_float(env={"X": "-0.5"}, var="X", default=1.0) == 1.0


class TestTheEnvironmentSource:
    def test_an_explicit_mapping_is_used_as_given(self) -> None:
        assert env_source({"A": "1"}) == {"A": "1"}

    def test_none_means_the_real_process_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every caller passes `env=None` in production; the injectable mapping is for tests."""
        monkeypatch.setenv("PULSAI_ENV_RESOLVER_PROBE", "5")

        assert resolve_positive_int(env=None, var="PULSAI_ENV_RESOLVER_PROBE", default=7) == 5


class TestTheCallersStillBehaveIdentically:
    """The consolidation must be invisible at the call sites — same values, same fallbacks.

    Each case reads the module's OWN env-var constant rather than a hardcoded string. The first
    draft guessed the names, and two of the three guesses were wrong — a magic string in a test
    proves only that the default path works (CODING_STANDARDS §12).
    """

    def test_ohlcv_source_cooldown_reads_its_var(self) -> None:
        from src.shared.constants.ohlcv_sources import (
            BINANCE_OHLCV_SOURCE_COOLDOWN_ENV_VAR,
            resolve_binance_ohlcv_source_cooldown_seconds,
        )

        assert resolve_binance_ohlcv_source_cooldown_seconds({BINANCE_OHLCV_SOURCE_COOLDOWN_ENV_VAR: "17"}) == 17

    def test_ohlcv_source_cooldown_floors_at_the_default(self) -> None:
        from src.shared.constants.ohlcv_sources import (
            BINANCE_OHLCV_SOURCE_COOLDOWN_ENV_VAR,
            resolve_binance_ohlcv_source_cooldown_seconds,
        )

        assert resolve_binance_ohlcv_source_cooldown_seconds({BINANCE_OHLCV_SOURCE_COOLDOWN_ENV_VAR: "0"}) > 0

    def test_signal_freshness_watch_interval(self) -> None:
        from src.shared.constants.signal_freshness import (
            SIGNAL_FRESHNESS_WATCH_INTERVAL_ENV_VAR,
            resolve_signal_freshness_watch_interval_seconds,
        )

        assert resolve_signal_freshness_watch_interval_seconds({SIGNAL_FRESHNESS_WATCH_INTERVAL_ENV_VAR: "13"}) == 13

    def test_spike_alert_min_samples(self) -> None:
        from src.shared.constants.spike_alert import (
            SPIKE_ALERT_MIN_SAMPLES_ENV_VAR,
            resolve_spike_alert_min_samples,
        )

        assert resolve_spike_alert_min_samples({SPIKE_ALERT_MIN_SAMPLES_ENV_VAR: "9"}) == 9

    def test_observability_metrics_still_resolves_a_float(self) -> None:
        """The fourth file the clone guard found — its float resolver must be unchanged too."""
        from src.shared.constants.observability_metrics import _resolve_positive_float

        assert _resolve_positive_float(env={"X": "2.5"}, var="X", default=1.0) == 2.5
        assert _resolve_positive_float(env={"X": "0"}, var="X", default=1.0) == 1.0
