"""
Single source for SPOT fee_rate + slippage used by CryptoBacktester and buy-and-hold baselines.

WHY: Baselines must use the same exchange fee resolution as live backtests (no magic numbers).
"""

from __future__ import annotations

from src.domain.enums import Exchange  # noqa: TC001
from src.infrastructure.ml.fee_config import FeeConfigService, default_fee_config_service
from src.shared.constants.backtest import DEFAULT_BACKTEST_USE_TAKER_FEES


def resolve_backtest_spot_fee_rates(
    exchange: Exchange,
    *,
    use_taker_fees: bool = DEFAULT_BACKTEST_USE_TAKER_FEES,
    fee_config_service: FeeConfigService | None = None,
) -> tuple[float, float]:
    """
    Return (fee_rate, slippage_rate) matching CryptoBacktester.__init__.

    Args:
        exchange: Trading venue.
        use_taker_fees: If True, use taker fee; else maker (same as backtester).
        fee_config_service: Optional inject for tests.

    Returns:
        fee_rate: Per-leg fee as fraction of position notional.
        slippage_rate: Slippage fraction passed to calculate_trade_pnl.
    """
    service = fee_config_service if fee_config_service is not None else default_fee_config_service
    fees = service.get_spot_fees(exchange, None)
    fee_rate = fees.taker_fee if use_taker_fees else fees.maker_fee
    return fee_rate, fees.slippage
