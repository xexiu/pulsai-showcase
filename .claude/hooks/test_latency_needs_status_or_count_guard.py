#!/usr/bin/env python3
"""The guard must catch the three real 2026-09-06 messages, and release the honest ones.

REUSE-AUDIT: considered .claude/hooks/test_absence_needs_search_guard.py and
.claude/hooks/test_finding_needs_todo_guard.py (same self-running harness shape, which is why
this file copies their structure rather than inventing one) and
apps/api/tests/hooks/test_kill_needs_ruin_reason_guard.py. Each tests a DIFFERENT guard's
predicate; a test module cannot be shared between guards without testing something it does not
import. Not extending; the harness pattern is reused, the fixtures are specific.

Every fixture below is a paraphrase of text this agent actually produced, or acted on, that day.
A guard justified by invented examples is a guard tuned to nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from latency_needs_status_or_count_guard import verdict  # noqa: E402

#: The guard as a SUBPROCESS. The unit tests above exercise `verdict` directly, which is how
#: this guard shipped never having fired: 12 green tests against a predicate, and a main() that
#: handed the payload dict to a function taking a path. Driving the real entry point is the only
#: way to catch that class.
GUARD = Path(__file__).with_name('latency_needs_status_or_count_guard.py')


class TestItCatchesTheRealFailures:
    def test_the_401_table_presented_as_warm_latency(self) -> None:
        """The actual defect: curl -o /dev/null, no token, every row an HTTP 401 of 130 bytes."""
        text = (
            "Measuring the exact requests the FE now makes on prod:\n"
            "  5m limit=4032  first=167ms  second=171ms\n"
            "  15m limit=1344 first=128ms  second=128ms\n"
            "That is the fix, measured: the chart-indicators request now answers in 167 ms."
        )

        assert verdict(text) is True

    def test_a_cold_reading_with_no_provenance(self) -> None:
        text = (
            "The /api/v1/market/chart-indicators endpoint measured 10 ms cold, "
            "so a written reason is enough."
        )

        assert verdict(text) is True

    def test_a_percentile_with_no_sample_count(self) -> None:
        text = "The endpoint p95 is 0.211s, over its 0.2s budget, so the writes are slow."

        assert verdict(text) is True


class TestItReleasesTheHonestForms:
    def test_a_status_code_beside_the_number(self) -> None:
        text = (
            "GET /api/v1/market/chart-indicators?timeframe=5m -> HTTP 200, 930 KB, "
            "1045 ms cold against 250 ms warm."
        )

        assert verdict(text) is False

    def test_a_sample_count_beside_the_percentile(self) -> None:
        text = "db INSERT endpoint window: n=67, p50 61 ms, p95 207 ms, p99 516 ms."

        assert verdict(text) is False

    def test_naming_the_error_path_explicitly(self) -> None:
        """Disclosing that the reading was a rejection is the behaviour to encourage."""
        text = (
            "Every row in that ohlcv table was an unauthenticated request, so the 130 ms "
            "readings timed the rejection and not the handler."
        )

        assert verdict(text) is False

    def test_a_422_named_as_such(self) -> None:
        text = "The route answered 422 in 10 ms because the endpoint got no query parameters."

        assert verdict(text) is False


class TestItStaysOutOfUnrelatedTimings:
    def test_a_test_suite_duration_is_not_an_endpoint_claim(self) -> None:
        """Without the endpoint condition this would fire on every green test run."""
        text = "20816 passed in 187.52s. All verification checks passed."

        assert verdict(text) is False

    def test_a_build_step_duration(self) -> None:
        text = "Feature calculator perf baseline: median=82.2052ms, all scenarios within baseline."

        assert verdict(text) is False

    def test_prose_with_no_numbers(self) -> None:
        text = "The chart-indicators endpoint is warmed by the prewarm task on every tick."

        assert verdict(text) is False

    def test_empty_text(self) -> None:
        assert verdict("") is False


def _run() -> int:
    failures = 0
    for cls in (
        TestItCatchesTheRealFailures,
        TestItReleasesTheHonestForms,
        TestItStaysOutOfUnrelatedTimings,
    ):
        instance = cls()
        for name in sorted(dir(instance)):
            if not name.startswith("test_"):
                continue
            try:
                getattr(instance, name)()
            except AssertionError:
                failures += 1
                print(f"FAIL {cls.__name__}.{name}")
    print("all latency-guard tests passed" if failures == 0 else f"{failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run())


class TestItHasNoBlockBudget:
    """It shipped with MAX_BLOCKS = 2 enforced. That was the defect, not the safety.

    A sweep on 2026-09-06 measured this as the ONLY one of twelve budgeted guards that actually
    honoured its cap -- the rest declare the constant and ignore it, per the owner's rule that a
    hook "MUST fire ALWAYS not stay silent after X blocks".

    Worse here than elsewhere: nothing scoped `blocks` to a session, so the state file outlives
    the conversation and the third stop EVER would have been the last -- on this machine and on
    any clone carrying that file. A guard that goes quiet is indistinguishable from one that
    agrees with you.
    """

    UNPROVENANCED = "The /api/v1/market/chart-indicators endpoint answered in 1045 ms."

    def _run(self, tmp_path: Path, text: str, state: Path) -> int:
        import json
        import os
        import subprocess
        import sys

        transcript = tmp_path / "t.jsonl"
        transcript.write_text(
            json.dumps({"type": "user", "message": {"content": "go"}})
            + "\n"
            + json.dumps(
                {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}
            )
            + "\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [sys.executable, str(GUARD)],
            input=json.dumps({"transcript_path": str(transcript), "session_id": "budget-test"}),
            capture_output=True,
            text=True,
            check=False,
            env=dict(os.environ, LATENCY_STATUS_STATE=str(state)),
        )
        return proc.returncode

    def test_it_still_fires_on_the_sixth_attempt(self, tmp_path: Path) -> None:
        """Six is well past the old cap of two, and past any plausible replacement for it."""
        state = tmp_path / "s.json"

        codes = [self._run(tmp_path, self.UNPROVENANCED, state) for _ in range(6)]

        assert codes[0] == 2, "must block the unprovenanced latency claim"
        assert codes[-1] == 2, "no budget: it fires until the number carries its provenance"

    def test_adding_the_status_code_releases_it(self, tmp_path: Path) -> None:
        """The ONLY exit is fixing the thing it names -- not outlasting it."""
        state = tmp_path / "s.json"
        self._run(tmp_path, self.UNPROVENANCED, state)

        fixed = "The /api/v1/market/chart-indicators endpoint answered HTTP 200 in 1045 ms."

        assert self._run(tmp_path, fixed, state) == 0

    def test_the_tally_is_never_compared_against_a_cap(self) -> None:
        """Guards the reversal: a future edit restoring `blocks >= MAX_BLOCKS` fails here.

        Asserts on the COMPARISON, not on the word. The first draft asserted "MAX_BLOCKS" was
        absent from the file and failed against this class's own docstring, which explains the
        constant on purpose. Banning a word bans discussion of it; the defect is the branch.
        """
        import re

        source = GUARD.read_text(encoding="utf-8")

        comparisons = re.findall(r"^[^#\n]*\b\w*blocks\w*\s*[<>]=?\s*\w+", source, re.MULTILINE | re.IGNORECASE)

        assert not comparisons, f"the tally became a limit again: {comparisons}"
