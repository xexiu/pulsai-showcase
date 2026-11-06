"""
Execution defaults shared across demo simulation and backtest fee SoT.

Demo uses Decimal paths; `fees.DEFAULT_FEE_RATE` is the canonical float used by backtests.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from src.shared.constants.fees import DEFAULT_FEE_RATE

DEFAULT_DEMO_TAKER_FEE_RATE: Final[Decimal] = Decimal(str(DEFAULT_FEE_RATE))
