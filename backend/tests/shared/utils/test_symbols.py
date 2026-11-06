"""
TDD Tests for symbol conversion utilities.

These tests define the EXPECTED BEHAVIOR for symbol format conversions.
The implementation must satisfy these tests.

Symbol formats in PulsAI:
- Standard: "BTC/USDT" (exchange format, used in most places)
- Safe key: "btc_usdt" (cache keys, filenames, model names)
- URL: "btc-usdt" (URL-safe for API routes)
- Short: "BTC" (display only, removes /USDT suffix)

@see Plan Phase 2.1 - 45 occurrences across 24 files
"""

from src.shared.utils.symbols import (
    symbol_from_safe_key,
    symbol_from_url,
    symbol_short,
    symbol_to_safe_key,
)


class TestSymbolToSafeKey:
    """
    Test symbol_to_safe_key: BTC/USDT -> btc_usdt

    Used for: cache keys, filenames, model names, Optuna study names
    Found in: 16 occurrences across infrastructure/cache/keys.py,
              scripts/train_model_persistence.py, workers/tasks/, etc.
    """

    def test_standard_symbol_to_safe_key(self) -> None:
        """Standard USDT pair conversion."""
        assert symbol_to_safe_key("BTC/USDT") == "btc_usdt"
        assert symbol_to_safe_key("ETH/USDT") == "eth_usdt"
        assert symbol_to_safe_key("SOL/USDT") == "sol_usdt"

    def test_lowercase_input_normalized(self) -> None:
        """Lowercase input should still produce lowercase output."""
        assert symbol_to_safe_key("btc/usdt") == "btc_usdt"

    def test_mixed_case_input_normalized(self) -> None:
        """Mixed case input should be normalized to lowercase."""
        assert symbol_to_safe_key("Btc/Usdt") == "btc_usdt"

    def test_non_usdt_pairs(self) -> None:
        """Other quote currencies should work."""
        assert symbol_to_safe_key("BTC/BUSD") == "btc_busd"
        assert symbol_to_safe_key("ETH/BTC") == "eth_btc"

    def test_already_safe_key_is_idempotent(self) -> None:
        """
        If input is already safe key format, output should match.

        WHY: Some code paths may accidentally pass safe key format.
        """
        assert symbol_to_safe_key("btc_usdt") == "btc_usdt"


class TestSymbolFromSafeKey:
    """
    Test symbol_from_safe_key: btc_usdt -> BTC/USDT

    Used for: Converting cache keys back to exchange format
    Found in: 7 occurrences in workers/tasks/, main.py, etc.
    """

    def test_safe_key_to_standard(self) -> None:
        """Safe key to standard format."""
        assert symbol_from_safe_key("btc_usdt") == "BTC/USDT"
        assert symbol_from_safe_key("eth_usdt") == "ETH/USDT"

    def test_uppercase_input_handled(self) -> None:
        """Uppercase input should still work."""
        assert symbol_from_safe_key("BTC_USDT") == "BTC/USDT"

    def test_round_trip_conversion(self) -> None:
        """to_safe_key -> from_safe_key should be identity (uppercase)."""
        original = "BTC/USDT"
        safe = symbol_to_safe_key(original)
        restored = symbol_from_safe_key(safe)
        assert restored == original


class TestSymbolFromUrl:
    """
    Test symbol_from_url: btc-usdt -> BTC/USDT

    Used for: API route parameters like /models/btc-usdt/1h
    Found in: 18 occurrences in api/routes/admin/models*.py, signals.py
    """

    def test_url_to_standard(self) -> None:
        """URL format to standard format."""
        assert symbol_from_url("btc-usdt") == "BTC/USDT"
        assert symbol_from_url("eth-usdt") == "ETH/USDT"

    def test_uppercase_url_handled(self) -> None:
        """Uppercase URL input should work."""
        assert symbol_from_url("BTC-USDT") == "BTC/USDT"

    def test_mixed_case_url_handled(self) -> None:
        """Mixed case should be normalized."""
        assert symbol_from_url("Btc-Usdt") == "BTC/USDT"


class TestSymbolShort:
    """
    Test symbol_short: BTC/USDT -> BTC

    Used for: Display purposes (Telegram messages, notifications)
    Found in: 4 occurrences in notification_service.py, telegram_formatters.py
    """

    def test_usdt_pair_short(self) -> None:
        """Remove /USDT suffix."""
        assert symbol_short("BTC/USDT") == "BTC"
        assert symbol_short("ETH/USDT") == "ETH"
        assert symbol_short("SOL/USDT") == "SOL"

    def test_non_usdt_pair_unchanged(self) -> None:
        """Non-USDT pairs should keep the full base currency."""
        # This removes /USDT or USDT, not other suffixes
        assert symbol_short("ETH/BTC") == "ETH/BTC"

    def test_already_short_unchanged(self) -> None:
        """Already short symbol should be unchanged."""
        assert symbol_short("BTC") == "BTC"

    def test_perpetual_suffix_handled(self) -> None:
        """
        USDT perpetual format should be handled.

        WHY: Some exchanges use BTCUSDT format without slash.
        """
        assert symbol_short("BTCUSDT") == "BTC"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_string_handled(self) -> None:
        """Empty string should return empty string, not crash."""
        assert symbol_to_safe_key("") == ""
        assert symbol_from_safe_key("") == ""
        assert symbol_from_url("") == ""
        assert symbol_short("") == ""

    def test_whitespace_stripped(self) -> None:
        """Whitespace should be handled gracefully."""
        assert symbol_to_safe_key(" BTC/USDT ") == "btc_usdt"
        assert symbol_from_safe_key(" btc_usdt ") == "BTC/USDT"

    def test_special_characters_in_symbol(self) -> None:
        """
        Special characters should be handled.

        WHY: Some symbols have numbers (1000PEPE/USDT)
        """
        assert symbol_to_safe_key("1000PEPE/USDT") == "1000pepe_usdt"
        assert symbol_from_safe_key("1000pepe_usdt") == "1000PEPE/USDT"
