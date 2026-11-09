"""Behavior: activation-time snapshot gates (slice-06 promotion / compound v2)."""

from __future__ import annotations

import pytest

from src.domain.services.trading_automation_activation_snapshot import (
    validate_promoted_market_type_matches_backtest,
    validate_snapshot_executable_for_activation,
)
from src.shared.constants.exchanges import MARKET_TYPE_SPOT, MARKET_TYPE_SWAP
from src.shared.exceptions import ValidationError


def test_compound_v2_requires_swap_market() -> None:
    snap = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "config": {"market_type": MARKET_TYPE_SPOT},
        "compound_leg_schedule_v2": [{"leverage": 2}],
    }
    with pytest.raises(ValidationError) as exc:
        validate_snapshot_executable_for_activation(snap)
    assert exc.value.details is not None
    assert exc.value.details.get("activation_violation") == "compound_v2_requires_swap_market"


def test_compound_v2_ok_when_swap() -> None:
    snap = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "config": {"market_type": MARKET_TYPE_SWAP, "leverage": 2},
        "compound_leg_schedule_v2": [{"leverage": 3}],
    }
    validate_snapshot_executable_for_activation(snap)


def test_empty_compound_v2_skips_market_check() -> None:
    snap = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "config": {"market_type": MARKET_TYPE_SPOT},
        "compound_leg_schedule_v2": [],
    }
    validate_snapshot_executable_for_activation(snap)


def test_promoted_market_drift_raises() -> None:
    snap = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "config": {"market_type": MARKET_TYPE_SWAP, "leverage": 2},
    }
    run_cfg = {"market_type": MARKET_TYPE_SPOT}
    with pytest.raises(ValidationError) as exc:
        validate_promoted_market_type_matches_backtest(
            strategy_snapshot=snap,
            backtest_run_config=run_cfg,
        )
    assert exc.value.details is not None
    assert exc.value.details.get("activation_violation") == "market_type_drift_from_backtest"


def test_promoted_market_match_ok() -> None:
    snap = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "config": {"market_type": MARKET_TYPE_SPOT},
    }
    validate_promoted_market_type_matches_backtest(
        strategy_snapshot=snap,
        backtest_run_config={"market_type": MARKET_TYPE_SPOT},
    )
