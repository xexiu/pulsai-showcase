"""Behavior tests for `shared.utils.decimal_safe` coercion helpers.

Single SoT for safe `Decimal` / `int` coercion from untrusted JSON-ish input
(CCXT dicts, API payloads, env strings). Replaces two duplicated `_decimal_or_none`
helpers previously in `domain/services/ccxt_fee_hints.py` and
`infrastructure/exchange/adapters/bitget_futures.py`.
"""

from __future__ import annotations

from decimal import Decimal

from src.shared.utils.decimal_safe import (
    decimal_or_none,
    float_or_none,
    int_or_default,
    int_or_none,
    positive_decimal_or_none,
)


class TestDecimalOrNone:
    def test_none_returns_none(self) -> None:
        assert decimal_or_none(None) is None

    def test_integer_returns_decimal(self) -> None:
        assert decimal_or_none(5) == Decimal(5)

    def test_float_preserves_precision_via_str_coercion(self) -> None:
        assert decimal_or_none(0.1) == Decimal("0.1")

    def test_numeric_string_parsed(self) -> None:
        assert decimal_or_none("0.0006") == Decimal("0.0006")

    def test_scientific_string_parsed(self) -> None:
        assert decimal_or_none("1e-6") == Decimal("0.000001")

    def test_non_numeric_string_returns_none(self) -> None:
        assert decimal_or_none("not a number") is None

    def test_arbitrary_object_returns_none(self) -> None:
        class Opaque:
            def __str__(self) -> str:
                return "opaque"

        assert decimal_or_none(Opaque()) is None

    def test_empty_string_returns_none(self) -> None:
        assert decimal_or_none("") is None


class TestIntOrNone:
    def test_none_returns_none(self) -> None:
        assert int_or_none(None) is None

    def test_integer_returns_integer(self) -> None:
        assert int_or_none(125) == 125

    def test_integer_string_parsed(self) -> None:
        assert int_or_none("125") == 125

    def test_decimal_string_truncated_to_int(self) -> None:
        """CCXT occasionally returns "125.0" for leverage max — we want 125, not a raise."""
        assert int_or_none("125.0") == 125

    def test_float_truncated_to_int(self) -> None:
        assert int_or_none(125.7) == 125

    def test_non_numeric_string_returns_none(self) -> None:
        assert int_or_none("not a number") is None

    def test_empty_string_returns_none(self) -> None:
        assert int_or_none("") is None

    def test_bool_returns_none_like_float_or_none(self) -> None:
        """A JSON ``true`` in a count field is UNMEASURED, never the count 1.

        ``bool`` subclasses ``int``, so ``int(True)`` is ``1`` — the flattering
        reading. ``float_or_none`` already refuses it; this pins the same
        contract on the int side, which is what let three research modules
        keep a private bool-rejecting copy instead of using this SoT.
        """
        assert int_or_none(True) is None
        assert int_or_none(False) is None


class TestFloatOrNone:
    """SoT for safe ``float`` coercion (used by Redis-snapshot codecs).

    Replaces the duplicated ``_coerce_optional_float`` helpers that previously
    lived in ``infrastructure/cache/macro_snapshot_cache.py`` and
    ``infrastructure/cache/fred_macro_series_cache.py``.
    """

    def test_none_returns_none(self) -> None:
        assert float_or_none(None) is None

    def test_integer_returns_float(self) -> None:
        assert float_or_none(5) == 5.0

    def test_float_passes_through(self) -> None:
        assert float_or_none(3.14) == 3.14

    def test_numeric_string_parsed(self) -> None:
        assert float_or_none("19.5") == 19.5

    def test_scientific_string_parsed(self) -> None:
        assert float_or_none("1e-3") == 0.001

    def test_non_numeric_string_returns_none(self) -> None:
        assert float_or_none("not a number") is None

    def test_boolean_returns_none(self) -> None:
        """bool is a subclass of int in Python; we explicitly reject it so a
        stray JSON ``true`` does not silently coerce to 1.0."""
        assert float_or_none(True) is None
        assert float_or_none(False) is None

    def test_arbitrary_object_returns_none(self) -> None:
        class Opaque:
            pass

        assert float_or_none(Opaque()) is None


class TestPositiveDecimalOrNone:
    def test_none_returns_none(self) -> None:
        assert positive_decimal_or_none(None) is None

    def test_zero_returns_none(self) -> None:
        assert positive_decimal_or_none(0) is None
        assert positive_decimal_or_none("0") is None
        assert positive_decimal_or_none("0.0") is None

    def test_negative_returns_none(self) -> None:
        assert positive_decimal_or_none(-1) is None
        assert positive_decimal_or_none("-0.5") is None

    def test_positive_returns_decimal(self) -> None:
        assert positive_decimal_or_none("1.25") == Decimal("1.25")
        assert positive_decimal_or_none(3) == Decimal(3)

    def test_garbage_returns_none(self) -> None:
        assert positive_decimal_or_none("not a number") is None
        assert positive_decimal_or_none("") is None


class TestIntOrDefault:
    """Pins the two ways `int_or_default` deliberately differs from `int_or_none`."""

    def test_a_bool_is_not_a_number(self) -> None:
        # int(True) == 1 in Python. In an int-typed artifact field a JSON `true` means the payload
        # is malformed, so the caller's default is the honest answer.
        assert int_or_default(True, 7) == 7
        assert int_or_default(False, 7) == 7

    def test_it_always_returns_an_int_never_none(self) -> None:
        assert int_or_default(None, 3) == 3
        assert int_or_default(object(), 3) == 3

    def test_it_truncates_floats(self) -> None:
        assert int_or_default(4.9, 0) == 4

    def test_it_reads_integer_strings(self) -> None:
        assert int_or_default("42", 0) == 42

    def test_a_non_integer_string_falls_back(self) -> None:
        assert int_or_default("4.9", 11) == 11
        assert int_or_default("", 11) == 11

    def test_the_default_defaults_to_zero(self) -> None:
        assert int_or_default("nope") == 0
