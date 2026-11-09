"""
TDD tests for shared symbol/timeframe validation (Phase 2 §7.4).

validate_symbol_timeframe(symbol, timeframe) must accept valid inputs and raise
ValueError with clear messages for invalid symbol (no "/") or invalid timeframe.

Audit §13.1: "Tests that validation accepts/rejects same set as today" — we lock
the accept set by parametrizing over VALID_TIMEFRAMES_SIGNAL_AND_TRAINING.
"""

import pytest

from src.shared.constants.timeframes import VALID_TIMEFRAMES_SIGNAL_AND_TRAINING
from src.shared.validation import validate_symbol_timeframe


class TestValidateSymbolTimeframeValid:
    """Valid inputs must not raise."""

    def test_valid_btc_usdt_1h_does_not_raise(self) -> None:
        """Valid symbol and timeframe must not raise."""
        validate_symbol_timeframe("BTC/USDT", "1h")

    def test_valid_eth_usdt_4h_does_not_raise(self) -> None:
        """Another valid pair and timeframe."""
        validate_symbol_timeframe("ETH/USDT", "4h")

    def test_valid_symbol_with_timeframe_1d_does_not_raise(self) -> None:
        """1d is in VALID_TIMEFRAMES_SIGNAL_AND_TRAINING."""
        validate_symbol_timeframe("BTC/USDT", "1d")

    @pytest.mark.parametrize("timeframe", sorted(VALID_TIMEFRAMES_SIGNAL_AND_TRAINING))
    def test_every_valid_timeframe_accepted_no_raise(self, timeframe: str) -> None:
        """Regression: validator accepts exactly VALID_TIMEFRAMES_SIGNAL_AND_TRAINING (same set as today)."""
        validate_symbol_timeframe("BTC/USDT", timeframe)


class TestValidateSymbolTimeframeInvalidSymbol:
    """Invalid symbol (no '/') must raise ValueError with message containing 'symbol' or 'format'."""

    def test_symbol_without_slash_raises(self) -> None:
        """Symbol without '/' must raise ValueError."""
        with pytest.raises(ValueError, match=r"(?i)symbol|format") as exc_info:
            validate_symbol_timeframe("BTCUSDT", "1h")
        msg = str(exc_info.value).lower()
        assert "symbol" in msg or "format" in msg

    def test_empty_symbol_raises(self) -> None:
        """Empty symbol has no '/'."""
        with pytest.raises(ValueError, match=r"(?i)symbol|format") as exc_info:
            validate_symbol_timeframe("", "1h")
        msg = str(exc_info.value).lower()
        assert "symbol" in msg or "format" in msg


class TestValidateSymbolTimeframeInvalidTimeframe:
    """Invalid timeframe must raise ValueError with message containing 'timeframe' or 'valid'."""

    def test_unknown_timeframe_raises(self) -> None:
        """A timeframe outside VALID_TIMEFRAMES_SIGNAL_AND_TRAINING must raise.

        The example must be one that can NEVER become valid. This test used "6h" until 6h was
        added as a real HTF band member — the fourth stale test in this repo that had pinned a
        plausible timeframe as its example of an impossible one. A fixture that can be promoted
        into production data turns a correct change into a red build, so the string is asserted
        to be outside the set rather than assumed to be.
        """
        unknown = "not-a-timeframe"
        assert unknown not in VALID_TIMEFRAMES_SIGNAL_AND_TRAINING

        with pytest.raises(ValueError, match=r"(?i)timeframe|valid") as exc_info:
            validate_symbol_timeframe("BTC/USDT", unknown)
        msg = str(exc_info.value).lower()
        assert "timeframe" in msg or "valid" in msg

    def test_a_registry_timeframe_outside_both_bands_raises(self) -> None:
        """1w is in the registry but is NOT a training band member, so it must raise.

        This test pinned `1m` until 1m joined the LTF band (owner, 2026-10-11) -- the same stale-
        example trap the test above records for 6h. `1w` is the durable choice: it is excluded from
        the research sweep too (a week candle leaves too few bars for an honest split).
        """
        assert "1w" not in VALID_TIMEFRAMES_SIGNAL_AND_TRAINING

        with pytest.raises(ValueError, match=r"(?i)timeframe|valid") as exc_info:
            validate_symbol_timeframe("BTC/USDT", "1w")
        msg = str(exc_info.value).lower()
        assert "timeframe" in msg or "valid" in msg

    def test_1m_is_accepted_since_it_joined_the_ltf_band(self) -> None:
        """Owner, 2026-10-11: 1m is a training band member, so signal/backtest validation takes it."""
        validate_symbol_timeframe("BTC/USDT", "1m")
