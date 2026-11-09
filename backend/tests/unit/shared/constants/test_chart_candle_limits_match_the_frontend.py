"""The server's idea of the chart's candle `limit` must equal the front end's, or warming is moot.

WHY A CROSS-LANGUAGE TEST AND NOT A COMMENT. `MARKET_CHART_OHLCV_MAX_LIMIT` already carries
"(must match FE ``MARKET_OHLCV_API_MAX_CANDLES``)" in its comment, and nothing has ever checked
it. A mirror maintained by prose is a mirror that drifts silently; the only difference between
this module and that comment is that this one FAILS.

WHAT IT PROTECTS. The chart-indicators response cache is keyed by `limit` among other things, so
a warmer that warms the wrong limit warms a key no client requests and the user still pays the
cold path. Measured on prod 2026-09-06: 5m/4032 cold = 1308 ms, warm = 397 ms. If this file's
constants drift by even one, the warmer keeps reporting success while doing nothing useful --
the "silent emptiness reports ok" failure this repo has paid for repeatedly.

The FE numbers are parsed out of the TypeScript rather than restated here, so a change on that
side breaks this test instead of quietly breaking prod.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.shared.constants.calendar_monday_weekend_levels import MARKET_CHART_OHLCV_MAX_LIMIT
from src.shared.constants.chart_candle_limits import (
    CHART_LOWER_TF_MIN_HISTORY_DAYS,
    CHART_MIN_HISTORY_DAYS,
    FULL_CHART_CANDLE_FLOOR,
    TIMEFRAME_HISTORY_DAYS_OVERRIDES,
    full_chart_candle_limit,
)

_WEB = Path(__file__).resolve().parents[5] / "web" / "src" / "utils"
_LIMITS_TS = _WEB / "chart-time" / "limits.ts"
_CONSTANTS_TS = _WEB / "constants" / "extended.ts"


def _int_literal(source: Path, name: str) -> int:
    """The integer a TS `const NAME = 123;` binds, whether exported or module-private."""
    text = source.read_text(encoding="utf-8")
    match = re.search(rf"^(?:export\s+)?const\s+{re.escape(name)}\s*=\s*(\d+)\s*;", text, re.MULTILINE)
    if match is None:
        pytest.fail(
            f"{name} not found in {source.name}. It was renamed or restructured on the FE side, "
            "which is exactly the drift this test exists to catch -- re-read the TS and update "
            "the Python mirror rather than loosening this pattern."
        )
    return int(match.group(1))


class TestTheMirroredConstantsAgree:
    """Three values are mirrored into Python; each is checked against its TypeScript original."""

    def test_the_default_history_window_agrees(self) -> None:
        assert _int_literal(_CONSTANTS_TS, "CHART_MIN_HISTORY_DAYS") == CHART_MIN_HISTORY_DAYS

    def test_the_low_timeframe_history_window_agrees(self) -> None:
        """This is the one that makes 5m cost 4032 candles instead of 500."""
        assert _int_literal(_CONSTANTS_TS, "CHART_LOWER_TF_MIN_HISTORY_DAYS") == CHART_LOWER_TF_MIN_HISTORY_DAYS

    def test_the_candle_floor_agrees(self) -> None:
        assert _int_literal(_LIMITS_TS, "FULL_CHART_CANDLE_FLOOR") == FULL_CHART_CANDLE_FLOOR

    def test_the_api_cap_agrees(self) -> None:
        """PRE-EXISTING mirror, previously guarded only by a comment. Now it fails instead."""
        assert _int_literal(_CONSTANTS_TS, "MARKET_OHLCV_API_MAX_CANDLES") == MARKET_CHART_OHLCV_MAX_LIMIT

    def test_the_overridden_timeframes_agree(self) -> None:
        """Which timeframes get the deep window, not just how deep it is."""
        block = re.search(
            r"TIMEFRAME_HISTORY_DAYS_OVERRIDES[^=]*=\s*\{(.*?)\}",
            _CONSTANTS_TS.read_text(encoding="utf-8"),
            re.DOTALL,
        )
        assert block is not None, "TIMEFRAME_HISTORY_DAYS_OVERRIDES vanished from the FE constants"

        assert set(re.findall(r"'([^']+)'\s*:", block.group(1))) == set(TIMEFRAME_HISTORY_DAYS_OVERRIDES)


class TestTheDerivedLimits:
    """The formula, not just its inputs. These are the keys a warmer must warm."""

    @pytest.mark.parametrize(
        ("timeframe", "expected"),
        [
            ("5m", 4032),  # 288 bars/day x 14 days -- the expensive one, 1308 ms cold on prod
            ("15m", 1344),  # 96 x 14
            ("30m", 672),  # 48 x 14
            ("1h", 500),  # 24 x 2 = 48, so the 500 floor wins
            ("4h", 500),
            ("1d", 500),
        ],
    )
    def test_the_limit_matches_the_frontend_rule(self, timeframe: str, expected: int) -> None:
        assert full_chart_candle_limit(timeframe) == expected

    def test_no_derived_limit_exceeds_the_api_cap(self) -> None:
        """The endpoint rejects anything over the cap, so a warmer asking for more would 422."""
        for timeframe in ("5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"):
            assert full_chart_candle_limit(timeframe) <= MARKET_CHART_OHLCV_MAX_LIMIT

    def test_an_unknown_timeframe_raises_rather_than_defaulting(self) -> None:
        """A silent default is what makes this class of drift invisible."""
        with pytest.raises((ValueError, KeyError)):
            full_chart_candle_limit("13m")
