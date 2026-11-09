"""Behavior tests for the perp funding accrual overlay.

Guards the cost the engine omits: longs PAY positive funding, shorts RECEIVE it, only
settlements inside the hold window count, and the overlay is a strict no-op when not
applied (charge-funding-OFF == byte-identical nets).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.infrastructure.ml.backtester_funding import (
    apply_funding_overlay,
    funding_pnl_for_position,
    total_funding_pnl,
)
from src.infrastructure.ml.backtester_types import Trade


def _make_trade(*, direction: int, size: float, net_pnl: float, entry: str | None, exit_: str | None) -> Trade:
    return Trade(
        entry_price=100.0,
        exit_price=101.0,
        direction=direction,
        size=size,
        entry_fee=0.1,
        exit_fee=0.1,
        slippage_cost=0.05,
        gross_pnl=net_pnl + 0.25,
        net_pnl=net_pnl,
        entry_time=entry,
        exit_time=exit_,
    )


def _ts(hour: int) -> datetime:
    """Midnight 2026-01-01 UTC + ``hour`` hours (supports hour >= 24 for next-day settlements)."""
    return datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC) + timedelta(hours=hour)


# --------------------------------------------------------------------------- #
# funding_pnl_for_position
# --------------------------------------------------------------------------- #


def test_long_pays_positive_funding() -> None:
    """Long over two +0.01% settlements pays -(0.0002) * notional."""
    rates = [(_ts(8), 0.0001), (_ts(16), 0.0001)]
    pnl = funding_pnl_for_position(entry_time=_ts(0), exit_time=_ts(24), direction=1, notional=10_000.0, funding_rates=rates)
    assert pnl == pytest.approx(-0.0002 * 10_000.0)


def test_short_receives_positive_funding() -> None:
    """Short over the same settlements RECEIVES funding (positive P&L) — the tailwind."""
    rates = [(_ts(8), 0.0001), (_ts(16), 0.0001)]
    pnl = funding_pnl_for_position(entry_time=_ts(0), exit_time=_ts(24), direction=-1, notional=10_000.0, funding_rates=rates)
    assert pnl == pytest.approx(+0.0002 * 10_000.0)


def test_only_settlements_inside_window_count() -> None:
    """Window is (entry, exit]: entry is exclusive, exit inclusive; outside excluded."""
    rates = [(_ts(0), 1.0), (_ts(8), 0.0001), (_ts(24), 0.0002), (_ts(32), 9.0)]
    # entry=0 excludes the 1.0 at t0; exit=24 includes the 0.0002 at t24; 9.0 at t32 excluded.
    pnl = funding_pnl_for_position(entry_time=_ts(0), exit_time=_ts(24), direction=1, notional=1_000.0, funding_rates=rates)
    assert pnl == pytest.approx(-(0.0001 + 0.0002) * 1_000.0)


def test_empty_rates_is_zero() -> None:
    assert funding_pnl_for_position(entry_time=_ts(0), exit_time=_ts(24), direction=1, notional=1_000.0, funding_rates=[]) == 0.0


def test_negative_funding_rate_flips_sign() -> None:
    """Negative funding: a LONG receives (positive P&L)."""
    rates = [(_ts(8), -0.0003)]
    pnl = funding_pnl_for_position(entry_time=_ts(0), exit_time=_ts(16), direction=1, notional=1_000.0, funding_rates=rates)
    assert pnl == pytest.approx(+0.0003 * 1_000.0)


@pytest.mark.parametrize("direction", [0, 2, -2])
def test_rejects_invalid_direction(direction: int) -> None:
    with pytest.raises(ValueError, match="direction must be"):
        funding_pnl_for_position(entry_time=_ts(0), exit_time=_ts(8), direction=direction, notional=1.0, funding_rates=[])


def test_rejects_negative_notional() -> None:
    with pytest.raises(ValueError, match="notional must be non-negative"):
        funding_pnl_for_position(entry_time=_ts(0), exit_time=_ts(8), direction=1, notional=-1.0, funding_rates=[])


def test_rejects_exit_before_entry() -> None:
    with pytest.raises(ValueError, match="exit_time must be"):
        funding_pnl_for_position(entry_time=_ts(8), exit_time=_ts(0), direction=1, notional=1.0, funding_rates=[])


# --------------------------------------------------------------------------- #
# apply_funding_overlay
# --------------------------------------------------------------------------- #


def test_overlay_sets_funding_and_adjusts_net() -> None:
    rates = [(_ts(8), 0.0001), (_ts(16), 0.0001)]
    trade = _make_trade(direction=1, size=10_000.0, net_pnl=50.0, entry="2026-01-01T00:00:00+00:00", exit_="2026-01-01T23:59:59+00:00")
    [out] = apply_funding_overlay([trade], rates)
    assert out.funding_pnl == pytest.approx(-0.0002 * 10_000.0)
    assert out.net_pnl == pytest.approx(50.0 + out.funding_pnl)


def test_overlay_empty_rates_is_byte_identical_noop() -> None:
    trade = _make_trade(direction=1, size=10_000.0, net_pnl=50.0, entry="2026-01-01T00:00:00+00:00", exit_="2026-01-01T20:00:00+00:00")
    [out] = apply_funding_overlay([trade], [])
    assert out.funding_pnl == 0.0
    assert out.net_pnl == 50.0


def test_overlay_trade_without_timestamps_is_noop() -> None:
    rates = [(_ts(8), 0.0001)]
    trade = _make_trade(direction=1, size=10_000.0, net_pnl=50.0, entry=None, exit_=None)
    [out] = apply_funding_overlay([trade], rates)
    assert out.funding_pnl == 0.0
    assert out.net_pnl == 50.0


def test_overlay_does_not_mutate_input() -> None:
    rates = [(_ts(8), 0.0001)]
    trade = _make_trade(direction=1, size=10_000.0, net_pnl=50.0, entry="2026-01-01T00:00:00+00:00", exit_="2026-01-01T16:00:00+00:00")
    apply_funding_overlay([trade], rates)
    assert trade.funding_pnl == 0.0
    assert trade.net_pnl == 50.0


def test_overlay_short_gets_tailwind() -> None:
    """A short held over positive funding ends with a HIGHER net than gross-of-funding."""
    rates = [(_ts(8), 0.0002), (_ts(16), 0.0002)]
    trade = _make_trade(direction=-1, size=5_000.0, net_pnl=-10.0, entry="2026-01-01T00:00:00+00:00", exit_="2026-01-01T20:00:00+00:00")
    [out] = apply_funding_overlay([trade], rates)
    assert out.funding_pnl > 0.0
    assert out.net_pnl > trade.net_pnl


def test_total_funding_pnl_sums_overlay() -> None:
    rates = [(_ts(8), 0.0001)]
    trades = [
        _make_trade(direction=1, size=10_000.0, net_pnl=5.0, entry="2026-01-01T00:00:00+00:00", exit_="2026-01-01T16:00:00+00:00"),
        _make_trade(direction=-1, size=10_000.0, net_pnl=5.0, entry="2026-01-01T00:00:00+00:00", exit_="2026-01-01T16:00:00+00:00"),
    ]
    out = apply_funding_overlay(trades, rates)
    # long pays -1.0, short receives +1.0 → nets to ~0 across the pair.
    assert total_funding_pnl(out) == pytest.approx(0.0)
    assert total_funding_pnl(trades) == 0.0  # pre-overlay
