"""The frontend's timeframe mirror must not drift from the backend registry.

THE QUESTION THIS ANSWERS (owner, 2026-08-13): *"I thought this was SoT, centralized — BE is the
SoT and feeds the FE via app config?"*

It is, at RUNTIME: `GET /config/public` serves `timeframes`, `ms` and `label` built from
`TIMEFRAME_REGISTRY`. But a TypeScript union and a `Record<Timeframe, …>` are COMPILE-TIME — they
cannot be produced from a runtime response — so `packages/shared` necessarily keeps a static copy.
Its only safeguard was a comment reading "Keep milliseconds in sync with … timeframes.py".

A comment is not a mechanism. It drifted the moment 2h/6h were added: the shared registry left
them in `CHART_ONLY_TIMEFRAME_MS`, labelled "not exposed as trading timeframes", while the backend
had already made them trainable, default-supported and served. The frontend was being told two
real trading timeframes were chart decoration.

This test is the mechanism. It reads the committed TypeScript and fails when it disagrees with the
registry, so the copy can exist without being able to rot.
"""

from __future__ import annotations

import re

import pytest

from src.shared.constants.timeframes import (
    DEFAULT_SUPPORTED_TIMEFRAME_VALUES,
    TIMEFRAME_LABELS,
    TIMEFRAME_MS,
    TIMEFRAME_REGISTRY,
)
from tests.helpers.api_paths import REPO_ROOT

# constants -> shared -> unit -> tests -> api -> apps -> REPO ROOT = parents[6].
#
# Pinned by the guard test below because I got this wrong TWICE — first `parents[4].parent`, then
# `parents[5]`, both resolving to `apps/packages/shared`. The first version also SKIPPED when the
# path missed, so all six checks reported green while verifying nothing. A parity guard that skips
# when it cannot find its counterpart is a guard that silently does not exist, which is exactly
# the failure mode it was written to catch. It now fails loudly instead.
_REPO_ROOT = REPO_ROOT
_SHARED = _REPO_ROOT / "packages" / "shared" / "src"
_REGISTRY_TS = _SHARED / "constants" / "timeframe-registry.ts"
_COMMON_TS = _SHARED / "types" / "common.ts"


def test_the_guard_can_actually_see_the_shared_package() -> None:
    """Guard the guard: if these paths stop resolving, every check below is vacuous."""
    assert _REGISTRY_TS.is_file(), f"shared timeframe registry not found at {_REGISTRY_TS}"
    assert _COMMON_TS.is_file(), f"shared common types not found at {_COMMON_TS}"


def _block(text: str, opener: str) -> str:
    """The `{ … }` body that follows `opener`, or `[ … ]` for an array literal."""
    start = text.index(opener) + len(opener)
    close = "]" if opener.rstrip().endswith("[") else "}"
    return text[start : text.index(close, start)]


def _quoted(fragment: str) -> list[str]:
    return re.findall(r"'([^']+)'", fragment)


@pytest.fixture(scope="module")
def registry_ts() -> str:
    """Read the committed mirror. No skip-if-missing: see the guard test above."""
    return _REGISTRY_TS.read_text(encoding="utf-8")


class TestTheSharedMirrorMatchesTheRegistry:
    def test_registry_ms_covers_exactly_the_backend_timeframes(self, registry_ts: str) -> None:
        keys = [k for k in _quoted(_block(registry_ts, "TIMEFRAME_REGISTRY_MS = {")) if k in TIMEFRAME_MS or len(k) <= 4]

        assert set(keys) == set(TIMEFRAME_REGISTRY), "packages/shared TIMEFRAME_REGISTRY_MS has drifted from the backend TIMEFRAME_REGISTRY"

    def test_labels_cover_exactly_the_backend_labels(self, registry_ts: str) -> None:
        keys = _quoted(_block(registry_ts, "TIMEFRAME_LABELS: Record<RegistryTimeframe, string> = {"))
        # Labels alternate key/value in the quoted scan; keys are the registry members.
        assert {k for k in keys if k in TIMEFRAME_LABELS} == set(TIMEFRAME_LABELS)

    def test_default_supported_matches_the_backend_default(self, registry_ts: str) -> None:
        keys = _quoted(_block(registry_ts, "DEFAULT_SUPPORTED_TIMEFRAMES = ["))

        assert keys == list(DEFAULT_SUPPORTED_TIMEFRAME_VALUES), (
            "packages/shared DEFAULT_SUPPORTED_TIMEFRAMES has drifted from DEFAULT_SUPPORTED_TIMEFRAME_VALUES"
        )

    def test_chart_only_never_claims_a_real_trading_timeframe(self, registry_ts: str) -> None:
        """THE REGRESSION: 2h and 6h sat in CHART_ONLY while the backend traded them.

        `CHART_ONLY_TIMEFRAME_MS` is documented as durations NOT in the backend product registry.
        Anything the registry actually knows about must never appear there, or the frontend
        classifies a tradable timeframe as pivot/countdown decoration.
        """
        chart_only = set(_quoted(_block(registry_ts, "CHART_ONLY_TIMEFRAME_MS = {")))

        assert not (chart_only & set(TIMEFRAME_REGISTRY)), (
            f"CHART_ONLY_TIMEFRAME_MS claims backend registry timeframes: {sorted(chart_only & set(TIMEFRAME_REGISTRY))}"
        )

    def test_the_timeframe_union_covers_the_registry(self) -> None:
        text = _COMMON_TS.read_text(encoding="utf-8")
        match = re.search(r"export type Timeframe\s*=\s*(.+?);", text, re.DOTALL)
        assert match is not None, "Timeframe union not found in packages/shared types/common.ts"

        members = set(re.findall(r"'([^']+)'", match.group(1)))

        assert members == set(TIMEFRAME_REGISTRY), "the shared Timeframe union has drifted from TIMEFRAME_REGISTRY"


class TestTheDurationsAgree:
    def test_every_shared_duration_equals_the_backend_milliseconds(self, registry_ts: str) -> None:
        """A wrong ms value is worse than a missing key: charts silently mis-bucket candles."""
        body = _block(registry_ts, "TIMEFRAME_REGISTRY_MS = {")
        for key, expression in re.findall(r"'([^']+)':\s*([^,]+),", body):
            if key not in TIMEFRAME_MS:
                continue

            assert eval(expression.strip()) == TIMEFRAME_MS[key], f"{key} ms disagrees with the backend"  # noqa: S307
