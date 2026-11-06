"""SoT: demo Decimal taker fee matches canonical float default in fees constants."""

from decimal import Decimal

from src.shared.constants.fees import DEFAULT_FEE_RATE as FEES_DEFAULT_TAKER_FLOAT
from src.shared.constants.trading_execution_defaults import DEFAULT_DEMO_TAKER_FEE_RATE


def test_demo_taker_fee_decimal_matches_fees_module_float() -> None:
    assert Decimal(str(FEES_DEFAULT_TAKER_FLOAT)) == DEFAULT_DEMO_TAKER_FEE_RATE
