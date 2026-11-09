"""`docs/CONFIGURATION.md` states the supported timeframes; this fails when that list goes stale.

WHY THIS EXISTS, precisely. On 2026-08-13 the agent was editing this exact table row for the
express purpose of adding the newly-registered timeframes, and typed
`5m,15m,30m,1h,4h,8h,12h,1d,3d,1w` — omitting `2h` and `6h`, the two the whole task was about. The
owner found it. In the same edit the `supported_exchanges` row was silently deleted.

That is the argument for the test. This is not a list a careful reader failed to notice; it is a
list a reader RETYPED WHILE CONCENTRATING ON IT and still got wrong. Prose cannot be derived from
`DEFAULT_SUPPORTED_TIMEFRAME_VALUES` at runtime, so the only honest option is an executable check
that reads the doc and compares — the same mechanism used for the `packages/shared` TS mirror.

Guard-the-guard: an earlier parity test of mine had a wrong repo-root path and SKIPPED every check
while reporting green, so the first assertion here is that the document was actually found.
"""

from __future__ import annotations

import re

import pytest

from src.shared.constants.timeframes import DEFAULT_SUPPORTED_TIMEFRAME_VALUES
from tests.helpers.api_paths import REPO_ROOT

#: parents: constants < shared < unit < tests < api < apps < REPO ROOT.
_DOC = REPO_ROOT / "docs" / "CONFIGURATION.md"


@pytest.fixture(scope="module")
def doc_text() -> str:
    assert _DOC.is_file(), (
        f"CONFIGURATION.md not found at {_DOC} — this guard is pointing at nothing and would pass forever. Fix the path before trusting a green run."
    )
    return _DOC.read_text(encoding="utf-8")


class TestTheGuardCanSeeItsTarget:
    def test_the_doc_is_readable_and_non_trivial(self, doc_text: str) -> None:
        assert len(doc_text) > 500

    def test_the_env_example_block_exists(self, doc_text: str) -> None:
        assert "SUPPORTED_TIMEFRAMES=" in doc_text, "the line this test checks is gone"


class TestTheDocumentedTimeframesMatchTheSoT:
    def test_the_env_example_lists_every_supported_timeframe(self, doc_text: str) -> None:
        """THE REGRESSION: this line said `...1h,4h,8h...` while the SoT had 2h and 6h."""
        match = re.search(r"^SUPPORTED_TIMEFRAMES=(.+)$", doc_text, re.MULTILINE)

        assert match, "no SUPPORTED_TIMEFRAMES= line in the env example"

        documented = [tf.strip() for tf in match.group(1).split(",") if tf.strip()]

        assert documented == list(DEFAULT_SUPPORTED_TIMEFRAME_VALUES), f"doc says {documented}, SoT says {list(DEFAULT_SUPPORTED_TIMEFRAME_VALUES)}"

    @pytest.mark.parametrize("timeframe", sorted(DEFAULT_SUPPORTED_TIMEFRAME_VALUES))
    def test_every_supported_timeframe_appears_somewhere_in_the_doc(self, doc_text: str, timeframe: str) -> None:
        assert re.search(rf"\b{re.escape(timeframe)}\b", doc_text), f"{timeframe} is a supported timeframe but is nowhere in CONFIGURATION.md"


class TestTheTradingDefaultsTableStaysComplete:
    """The `supported_exchanges` row was deleted by accident; nothing noticed."""

    @pytest.mark.parametrize(
        "setting",
        [
            "default_symbol",
            "default_timeframe",
            "default_exchange",
            "supported_symbols",
            "supported_timeframes",
            "supported_exchanges",
        ],
    )
    def test_the_setting_is_documented(self, doc_text: str, setting: str) -> None:
        assert f"`{setting}`" in doc_text
