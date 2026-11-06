"""
TDD Tests for trading constants (SoT Phase 1.2).

DEFAULT_SYMBOLS must be a list and equal to [DEFAULT_SYMBOL] so OHLCVModel sync
and other consumers use one source.
"""

from src.shared.constants import DEFAULT_SYMBOL, DEFAULT_SYMBOLS


class TestDefaultSymbols:
    """Test DEFAULT_SYMBOLS is list and equals [DEFAULT_SYMBOL]."""

    def test_default_symbols_is_list(self) -> None:
        """DEFAULT_SYMBOLS must be a list (used as default for sync_ohlcv_data(symbols=None))."""
        assert isinstance(DEFAULT_SYMBOLS, list)

    def test_default_symbols_equals_single_default_symbol(self) -> None:
        """DEFAULT_SYMBOLS must be [DEFAULT_SYMBOL] for single source of truth."""
        assert DEFAULT_SYMBOLS == [DEFAULT_SYMBOL]

    def test_default_symbols_exported_from_shared_constants(self) -> None:
        """DEFAULT_SYMBOLS must be importable from src.shared.constants."""
        import src.shared.constants as sc

        assert hasattr(sc, "DEFAULT_SYMBOLS")
