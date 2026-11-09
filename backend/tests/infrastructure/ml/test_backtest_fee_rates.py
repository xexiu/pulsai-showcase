"""resolve_backtest_spot_fee_rates matches CryptoBacktester fee resolution."""

from __future__ import annotations

from src.domain.enums import Exchange
from src.infrastructure.ml.backtest_fee_rates import resolve_backtest_spot_fee_rates
from src.infrastructure.ml.fee_config import default_fee_config_service


def test_binance_taker_matches_service() -> None:
    fee_rate, slip = resolve_backtest_spot_fee_rates(
        Exchange.BINANCE,
        use_taker_fees=True,
    )
    fees = default_fee_config_service.get_spot_fees(Exchange.BINANCE, None)
    assert fee_rate == fees.taker_fee
    assert slip == fees.slippage


def test_binance_maker_when_not_taker() -> None:
    fee_rate, slip = resolve_backtest_spot_fee_rates(
        Exchange.BINANCE,
        use_taker_fees=False,
    )
    fees = default_fee_config_service.get_spot_fees(Exchange.BINANCE, None)
    assert fee_rate == fees.maker_fee
    assert slip == fees.slippage
