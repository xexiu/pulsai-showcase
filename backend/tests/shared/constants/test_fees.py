"""
TDD Tests for fee constants.

Fee constants are CRITICAL for accurate backtesting and P&L calculations.
Different exchanges have different fee structures.

@see Plan Phase 2.6 - 4 places with fee definitions
"""

from src.shared.constants.fees import (
    BINANCE_MAKER_FEE,
    BINANCE_TAKER_FEE,
    BITGET_MAKER_FEE,
    BITGET_TAKER_FEE,
    DEFAULT_FEE_RATE,
    DEFAULT_ROUNDTRIP_COST,
    DEFAULT_SLIPPAGE,
    DEFAULT_TURNOVER_COST_PER_SIDE,
)
from src.shared.math.cost_floor import round_trip_cost_fraction


class TestFeeConstants:
    """Test fee constants are correctly defined."""

    def test_default_fee_rate(self) -> None:
        """
        Default fee rate for backtesting.

        WHY 0.001 (0.1%)?
        - Conservative estimate covering most scenarios
        - Binance taker is 0.1%, maker can be lower with BNB
        """
        assert DEFAULT_FEE_RATE == 0.001

    def test_default_slippage(self) -> None:
        """
        Default slippage for backtesting.

        WHY 0.0003 (0.03%)?
        - Must match the runtime backtester fee registry
        - Shared constants should describe the actual backend execution model
        """
        assert DEFAULT_SLIPPAGE == 0.0003

    def test_binance_fees(self) -> None:
        """
        Binance fee structure.

        Source: https://www.binance.com/en/fee/schedule
        Standard tier (no BNB discount):
        - Taker: 0.1%
        - Maker: 0.1%
        """
        assert BINANCE_TAKER_FEE == 0.001
        assert BINANCE_MAKER_FEE == 0.001

    def test_bitget_fees(self) -> None:
        """
        Bitget fee structure.

        Source: https://www.bitget.com/fee
        Standard tier:
        - Taker: 0.1%
        - Maker: 0.1%
        """
        assert BITGET_TAKER_FEE == 0.001
        assert BITGET_MAKER_FEE == 0.001


class TestFeeRealism:
    """Test that fees are realistic for accurate backtesting."""

    def test_fees_are_percentage_not_absolute(self) -> None:
        """Fees should be expressed as decimals (0.001 = 0.1%)."""
        assert 0 < DEFAULT_FEE_RATE < 0.01  # Between 0% and 1%
        assert 0 < DEFAULT_SLIPPAGE < 0.01

    def test_total_trading_cost_realistic(self) -> None:
        """
        Total cost per trade should be realistic.

        A round trip (buy + sell) costs:
        - Entry: fee + slippage
        - Exit: fee + slippage
        Total: 2 * (fee + slippage) = 2 * (0.001 + 0.0003) = 0.0026 = 0.26%

        This matches real-world observations for major pairs.
        """
        assert round_trip_cost_fraction(BINANCE_TAKER_FEE, DEFAULT_SLIPPAGE) == DEFAULT_ROUNDTRIP_COST
        assert DEFAULT_ROUNDTRIP_COST == 2.0 * (BINANCE_TAKER_FEE + DEFAULT_SLIPPAGE)
        assert 0.002 <= DEFAULT_ROUNDTRIP_COST <= 0.005  # 0.2% to 0.5%

    def test_turnover_per_side_is_fee_sot_not_magic_0010(self) -> None:
        """Edge-hunt ``COST=0.0010`` must alias DEFAULT_FEE_RATE (not a second literal)."""
        assert DEFAULT_TURNOVER_COST_PER_SIDE == DEFAULT_FEE_RATE
        assert DEFAULT_TURNOVER_COST_PER_SIDE == 0.001
        # Full long-flat cycle via |Δpos| charges two sides → 20 bps (no slip).
        assert 2.0 * DEFAULT_TURNOVER_COST_PER_SIDE == 0.002
        # Conservative RT with slip is strictly higher (26 bps).
        assert DEFAULT_ROUNDTRIP_COST > 2.0 * DEFAULT_TURNOVER_COST_PER_SIDE
