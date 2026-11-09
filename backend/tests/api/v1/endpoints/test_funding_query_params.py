"""Tests for the shared funding-carry query-param helpers (PulsAI Carry).

SoT for the monitor/backtest/paper endpoints' CSV parsing + leverage parsing.
"""

from __future__ import annotations

import src.application.dto.funding_query_params as qp
from src.application.dto.funding_query_params import (
    CARRY_MAX_LEVERAGE,
    DEFAULT_CARRY_DAYS,
    DEFAULT_CARRY_VENUES,
    MAX_CARRY_DAYS,
    MIN_CARRY_DAYS,
    parse_csv,
    parse_leverages,
)
from src.shared.constants.carry import (
    CARRY_MAX_LEVERAGE as _CARRY_MAX_LEVERAGE_CONST,
)
from src.shared.constants.carry import (
    DEFAULT_CARRY_DAYS as _DEFAULT_CARRY_DAYS_CONST,
)
from src.shared.constants.carry import (
    DEFAULT_CARRY_VENUES_CSV as _DEFAULT_CARRY_VENUES_CSV_CONST,
)
from src.shared.constants.carry import (
    MAX_CARRY_DAYS as _MAX_CARRY_DAYS_CONST,
)
from src.shared.constants.carry import (
    MIN_CARRY_DAYS as _MIN_CARRY_DAYS_CONST,
)


class TestParseCsv:
    def test_trims_and_drops_empties(self) -> None:
        assert parse_csv(" BTC , ETH ,,") == ["BTC", "ETH"]

    def test_empty_string_is_empty_list(self) -> None:
        assert parse_csv("") == []


class TestParseLeverages:
    def test_parses_positive_floats(self) -> None:
        assert parse_leverages("1,2,3,5,8") == [1.0, 2.0, 3.0, 5.0, 8.0]

    def test_skips_non_numeric_and_non_positive(self) -> None:
        assert parse_leverages("3, x, 0, -2, 5") == [3.0, 5.0]

    def test_empty_yields_empty(self) -> None:
        assert parse_leverages("") == []


class TestFundingQueryParamsConstantReExports:
    """Verify funding_query_params re-exports SoT constants from carry.py (not duplicate literals)."""

    def test_min_carry_days_matches_carry_constant(self) -> None:
        assert MIN_CARRY_DAYS == _MIN_CARRY_DAYS_CONST

    def test_max_carry_days_matches_carry_constant(self) -> None:
        assert MAX_CARRY_DAYS == _MAX_CARRY_DAYS_CONST

    def test_default_carry_days_matches_carry_constant(self) -> None:
        assert DEFAULT_CARRY_DAYS == _DEFAULT_CARRY_DAYS_CONST

    def test_carry_max_leverage_matches_carry_constant(self) -> None:
        assert CARRY_MAX_LEVERAGE == _CARRY_MAX_LEVERAGE_CONST

    def test_default_carry_venues_matches_csv_constant(self) -> None:
        assert DEFAULT_CARRY_VENUES == _DEFAULT_CARRY_VENUES_CSV_CONST

    def test_constants_available_at_module_level(self) -> None:
        # All symbols the endpoints import must be importable from this module
        required = [
            "CARRY_MAX_LEVERAGE",
            "DEFAULT_CARRY_DAYS",
            "DEFAULT_CARRY_VENUES",
            "MAX_CARRY_DAYS",
            "MIN_CARRY_DAYS",
            "parse_csv",
            "parse_leverages",
        ]
        for name in required:
            assert hasattr(qp, name), f"{name!r} missing from funding_query_params"


class TestResolveBases:
    """The three funding endpoints each normalise `symbols` the same way — and so must the prewarm.

    Duplicated verbatim in funding_backtest/monitor/paper before this helper existed, which is why
    the boot prewarm could seed a base set no real request ever asks for.
    """

    def test_uppercases_and_trims(self) -> None:
        assert qp.resolve_bases(" btc , eth ") == ["BTC", "ETH"]

    def test_caps_the_fanout_at_max_carry_bases(self) -> None:
        raw = ",".join(f"C{i}" for i in range(qp.MAX_CARRY_BASES + 5))
        assert len(qp.resolve_bases(raw)) == qp.MAX_CARRY_BASES

    def test_empty_is_empty(self) -> None:
        assert qp.resolve_bases("") == []


class TestResolveVenues:
    """`supported` is INJECTED: an application DTO must not import infrastructure to answer this."""

    def test_lowercases_and_keeps_only_supported(self) -> None:
        assert qp.resolve_venues("BINANCE, nope ,Bitget", ("binance", "bitget")) == ["binance", "bitget"]

    def test_drops_everything_unsupported(self) -> None:
        assert qp.resolve_venues("nope,alsonope", ("binance",)) == []

    def test_preserves_request_order_not_supported_order(self) -> None:
        assert qp.resolve_venues("bitget,binance", ("binance", "bitget")) == ["bitget", "binance"]
