"""Behavior tests for carry strategy constants and enums (shared/constants/carry.py).

Verifies values, derivations, and enum member contracts so downstream consumers
(paper engine, backtester, admin routes) can safely import without surprises.
"""

from __future__ import annotations

from src.shared.constants.carry import (
    CARRY_ADVERSE_LOOKBACK_DAYS,
    CARRY_DEFAULT_MMR,
    CARRY_MAX_LEVERAGE,
    CARRY_QTY_EPS,
    CARRY_ROUNDTRIP_FEE_PCT,
    CARRY_TAKER_FEE_PCT,
    CARRY_VENUES,
    DEFAULT_CARRY_DAYS,
    DEFAULT_CARRY_VENUES_CSV,
    HOURS_PER_YEAR,
    MAX_CARRY_DAYS,
    MIN_CARRY_DAYS,
    CarryPositionStatus,
    CarryTickStatus,
)
from src.shared.constants.fees import BITGET_TAKER_FEE


class TestCarryTimeConstants:
    def test_hours_per_year_is_365_times_24(self) -> None:
        assert HOURS_PER_YEAR == 365.0 * 24.0

    def test_hours_per_year_is_float(self) -> None:
        assert isinstance(HOURS_PER_YEAR, float)


class TestCarryNumericGuards:
    def test_qty_eps_is_1e_9(self) -> None:
        assert CARRY_QTY_EPS == 1e-9

    def test_default_mmr_is_half_percent(self) -> None:
        assert CARRY_DEFAULT_MMR == 0.005

    def test_max_leverage_is_20(self) -> None:
        assert CARRY_MAX_LEVERAGE == 20.0


class TestCarryFeeDerivation:
    def test_taker_fee_pct_derived_from_bitget_taker_fee(self) -> None:
        """CARRY_TAKER_FEE_PCT must equal BITGET_TAKER_FEE * 100 (no hardcoding)."""
        assert CARRY_TAKER_FEE_PCT == BITGET_TAKER_FEE * 100

    def test_taker_fee_pct_is_0_10(self) -> None:
        """0.001 * 100 = 0.10 percent."""
        assert CARRY_TAKER_FEE_PCT == 0.10

    def test_roundtrip_fee_pct_is_0_30(self) -> None:
        assert CARRY_ROUNDTRIP_FEE_PCT == 0.30


class TestCarryDayBounds:
    def test_default_carry_days(self) -> None:
        assert DEFAULT_CARRY_DAYS == 365

    def test_min_carry_days(self) -> None:
        assert MIN_CARRY_DAYS == 7

    def test_max_carry_days(self) -> None:
        assert MAX_CARRY_DAYS == 1095

    def test_min_less_than_default_less_than_max(self) -> None:
        assert MIN_CARRY_DAYS < DEFAULT_CARRY_DAYS < MAX_CARRY_DAYS


class TestCarryVenues:
    def test_carry_venues_contains_bitget_and_binance(self) -> None:
        assert "bitget" in CARRY_VENUES
        assert "binance" in CARRY_VENUES

    def test_carry_venues_is_frozenset(self) -> None:
        assert isinstance(CARRY_VENUES, frozenset)

    def test_default_carry_venues_csv_is_string(self) -> None:
        assert isinstance(DEFAULT_CARRY_VENUES_CSV, str)

    def test_adverse_lookback_days_is_90(self) -> None:
        assert CARRY_ADVERSE_LOOKBACK_DAYS == 90


class TestCarryPositionStatus:
    """Enum values must match CarryPositionModel.status column literals exactly."""

    def test_active_value(self) -> None:
        assert CarryPositionStatus.ACTIVE == "active"
        assert CarryPositionStatus.ACTIVE.value == "active"

    def test_flat_value(self) -> None:
        assert CarryPositionStatus.FLAT == "flat"
        assert CarryPositionStatus.FLAT.value == "flat"

    def test_halted_value(self) -> None:
        assert CarryPositionStatus.HALTED == "halted"
        assert CarryPositionStatus.HALTED.value == "halted"

    def test_all_three_members_exist(self) -> None:
        members = {m.value for m in CarryPositionStatus}
        assert members == {"active", "flat", "halted"}

    def test_str_enum_equality_with_string(self) -> None:
        """StrEnum: members compare equal to their string values directly."""
        assert CarryPositionStatus.ACTIVE == "active"


class TestCarryTickStatus:
    """All carry tick result statuses are present and have correct values."""

    def test_idle_value(self) -> None:
        assert CarryTickStatus.IDLE == "idle"

    def test_ran_value(self) -> None:
        assert CarryTickStatus.RAN == "ran"

    def test_halted_value(self) -> None:
        assert CarryTickStatus.HALTED == "halted"

    def test_error_value(self) -> None:
        assert CarryTickStatus.ERROR == "error"

    def test_kill_switch_value(self) -> None:
        assert CarryTickStatus.KILL_SWITCH == "kill_switch"

    def test_disabled_value(self) -> None:
        assert CarryTickStatus.DISABLED == "disabled"

    def test_venue_not_supported_value(self) -> None:
        assert CarryTickStatus.VENUE_NOT_SUPPORTED == "venue_not_supported"

    def test_no_credentials_value(self) -> None:
        assert CarryTickStatus.NO_CREDENTIALS == "no_credentials"

    def test_all_carry_tick_status_members_present(self) -> None:
        expected = {
            "idle",
            "ran",
            "halted",
            "error",
            "kill_switch",
            "disabled",
            "venue_not_supported",
            "no_credentials",
            "no_hyperliquid_credentials",
            "equity_read_failed",
            "wallet_preflight_failed",
            "insufficient_funds",
        }
        assert {m.value for m in CarryTickStatus} == expected
