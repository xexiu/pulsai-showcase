import pytest

from src.shared.constants.backtest_leverage import (
    BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE,
    BACKTEST_TIERED_MMR_HIGH,
    BACKTEST_TIERED_MMR_LOW,
    BACKTEST_TIERED_MMR_NOTIONAL_THRESHOLD_USD,
    OWNER_COIN_LANES,
    BacktestPerpMmrMode,
    effective_perp_maintenance_margin_mode,
    owner_lanes_up_to,
    resolve_backtest_linear_mmr,
)


@pytest.mark.parametrize(
    ("cap", "lanes"),
    [(25, (10, 20, 25)), (5, (5,)), (50, OWNER_COIN_LANES), (20, (10, 20)), (None, OWNER_COIN_LANES)],
)
def test_the_owner_lanes_stop_at_the_coins_venue_cap(cap: int | None, lanes: tuple[int, ...]) -> None:
    """Lighter's SOL is 25x (owner 2026-10-16): 10 / 20 / 25x, never 30-50x; an unknown cap keeps every lane."""
    assert owner_lanes_up_to(cap) == lanes


def test_resolve_backtest_linear_mmr_flat_mode_stays_flat() -> None:
    assert (
        resolve_backtest_linear_mmr(
            1_000.0,
            BacktestPerpMmrMode.FLAT,
            tiered_mmr_server_allowed=True,
        )
        == BACKTEST_LINEAR_MAINTENANCE_MARGIN_RATE
    )


def test_resolve_backtest_linear_mmr_tiered_low_and_high() -> None:
    assert (
        resolve_backtest_linear_mmr(
            BACKTEST_TIERED_MMR_NOTIONAL_THRESHOLD_USD,
            BacktestPerpMmrMode.TIERED,
            tiered_mmr_server_allowed=True,
        )
        == BACKTEST_TIERED_MMR_LOW
    )
    assert (
        resolve_backtest_linear_mmr(
            BACKTEST_TIERED_MMR_NOTIONAL_THRESHOLD_USD + 1.0,
            BacktestPerpMmrMode.TIERED,
            tiered_mmr_server_allowed=True,
        )
        == BACKTEST_TIERED_MMR_HIGH
    )


def test_effective_mode_coerces_tiered_to_flat_when_server_off() -> None:
    assert (
        effective_perp_maintenance_margin_mode(
            BacktestPerpMmrMode.TIERED,
            tiered_mmr_server_allowed=False,
        )
        == BacktestPerpMmrMode.FLAT
    )
