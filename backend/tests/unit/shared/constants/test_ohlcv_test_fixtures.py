"""OHLCV fixture id SoT."""

from __future__ import annotations

from src.shared.constants.ohlcv_test_fixtures import (
    alignment_ohlcv_fixture_specs,
    build_ohlcv_fixture_id,
)
from src.shared.constants.timeframes import ALIGNMENT_TIMEFRAMES_ORDER


def test_build_ohlcv_fixture_id_slug() -> None:
    assert build_ohlcv_fixture_id(symbol="BTC/USDT", timeframe="1h", limit=500) == "btc_usdt_1h_500"


def test_alignment_specs_cover_all_alignment_timeframes() -> None:
    specs = alignment_ohlcv_fixture_specs()
    assert len(specs) == len(ALIGNMENT_TIMEFRAMES_ORDER)
    assert [s.timeframe for s in specs] == list(ALIGNMENT_TIMEFRAMES_ORDER)
