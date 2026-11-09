"""Behaviour tests for the deterministic carry leg clientOrderId (idempotency SoT).

These pin the DEDUP CONTRACT, not the formula:
  - same logical leg in the same window → same id (a retry dedups at the venue),
  - any change that means a DIFFERENT real order → different id (no false dedup),
  - a new rebalance window → different id (a genuine re-hedge is NOT suppressed),
  - the id is venue-safe (≤ strictest integrated ceiling) and carries the prefix.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.domain.services.carry_client_order_id import (
    build_carry_leg_client_order_id,
    carry_rebalance_window_bucket,
)
from src.shared.constants.carry import CARRY_CLIENT_ORDER_ID_PREFIX
from src.shared.constants.paper_trading import CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN


def _cid(**overrides: object) -> str:
    base: dict[str, object] = {
        "venue": "bitget",
        "symbol": "BTC/USDT:USDT",
        "side": "sell",
        "reduce_only": False,
        "bucket": "100",
    }
    base.update(overrides)
    return build_carry_leg_client_order_id(**base)  # type: ignore[arg-type]


def test_deterministic_same_inputs_same_id() -> None:
    assert _cid() == _cid()


def test_distinct_side_distinct_id() -> None:
    assert _cid(side="sell") != _cid(side="buy")


def test_distinct_symbol_leg_distinct_id() -> None:
    # spot BTC/USDT vs perp BTC/USDT:USDT are different legs → different ids.
    assert _cid(symbol="BTC/USDT") != _cid(symbol="BTC/USDT:USDT")


def test_distinct_reduce_only_distinct_id() -> None:
    assert _cid(reduce_only=True) != _cid(reduce_only=False)


def test_new_window_bucket_allows_rehedge() -> None:
    # A new rebalance window MUST yield a new id, else a legitimate re-hedge
    # would be silently suppressed by the venue as a duplicate.
    assert _cid(bucket="100") != _cid(bucket="101")


def test_distinct_venue_distinct_id() -> None:
    assert _cid(venue="bitget") != _cid(venue="binance")


def test_case_insensitive_venue_and_side() -> None:
    # Casing drift must NOT fork the id (would break dedup on retry).
    assert _cid(venue="BITGET", side="SELL") == _cid(venue="bitget", side="sell")


def test_venue_safe_length_and_prefix() -> None:
    cid = _cid()
    assert cid.startswith(CARRY_CLIENT_ORDER_ID_PREFIX)
    assert 0 < len(cid) <= CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN


def test_window_bucket_stable_within_window() -> None:
    # 12:00:00 is a 15-min window boundary; 12:14:59 is still inside it → same bucket,
    # so a retry within the window re-derives the same clientOid (dedup).
    start = datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC)
    same_window = datetime(2026, 6, 27, 12, 14, 59, tzinfo=UTC)
    assert carry_rebalance_window_bucket(start) == carry_rebalance_window_bucket(same_window)


def test_window_bucket_rotates_next_window() -> None:
    start = datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC)
    next_window = datetime(2026, 6, 27, 12, 15, 0, tzinfo=UTC)
    assert carry_rebalance_window_bucket(start) != carry_rebalance_window_bucket(next_window)


def test_window_bucket_feeds_a_valid_leg_id() -> None:
    # End-to-end: a window bucket produces a venue-safe, prefixed leg id.
    bucket = carry_rebalance_window_bucket(datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC))
    cid = build_carry_leg_client_order_id(venue="bitget", symbol="BTC/USDT:USDT", side="sell", reduce_only=False, bucket=bucket)
    assert cid.startswith(CARRY_CLIENT_ORDER_ID_PREFIX)
    assert 0 < len(cid) <= CCXT_OUTBOUND_CLIENT_ORDER_ID_MAX_LEN
