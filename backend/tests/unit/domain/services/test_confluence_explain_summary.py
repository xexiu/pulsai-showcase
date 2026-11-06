"""Behavior tests for the multi-timeframe confluence summary (explainer-facing).

Unlike the worker's detect_confluence (which returns None unless there's an
agreeing majority worth a Telegram push), this summary ALWAYS describes the
co-temporal set — including disagreement — because the explainer must surface a
conflicted picture, not hide it.
"""

from __future__ import annotations

import pytest

from src.domain.services.confluence_explain_summary import (
    ConfluenceLeg,
    summarize_confluence,
)


def _legs(*pairs: tuple[str, str, float]) -> list[ConfluenceLeg]:
    return [ConfluenceLeg(timeframe=tf, action=a, confidence=c) for tf, a, c in pairs]


def test_unanimous_buy() -> None:
    summary = summarize_confluence("BTC/USDT", _legs(("1h", "BUY", 0.8), ("4h", "BUY", 0.6), ("1d", "BUY", 0.7)))
    assert summary.dominant_action == "BUY"
    assert summary.is_unanimous is True
    assert summary.is_conflicted is False
    assert summary.agreeing_count == 3
    assert summary.total == 3
    assert summary.mean_confidence == pytest.approx(0.7)


def test_majority_with_dissent_is_conflicted_but_has_dominant() -> None:
    summary = summarize_confluence("BTC/USDT", _legs(("15m", "BUY", 0.9), ("1h", "BUY", 0.7), ("4h", "SELL", 0.8)))
    assert summary.dominant_action == "BUY"
    assert summary.is_unanimous is False
    assert summary.is_conflicted is True  # both BUY and SELL present
    assert summary.agreeing_count == 2
    assert summary.mean_confidence == pytest.approx(0.8)  # mean over the 2 BUY legs


def test_even_buy_sell_split_is_mixed() -> None:
    summary = summarize_confluence("ETH/USDT", _legs(("1h", "BUY", 0.6), ("4h", "SELL", 0.9)))
    assert summary.dominant_action == "MIXED"
    assert summary.is_conflicted is True
    assert summary.is_unanimous is False


def test_hold_majority() -> None:
    summary = summarize_confluence("BTC/USDT", _legs(("1h", "HOLD", 0.5), ("4h", "HOLD", 0.6), ("1d", "BUY", 0.9)))
    assert summary.dominant_action == "HOLD"
    assert summary.is_conflicted is False  # no BUY+SELL clash (HOLD+BUY only)
    assert summary.agreeing_count == 2


def test_single_leg_is_unanimous() -> None:
    summary = summarize_confluence("BTC/USDT", _legs(("1h", "SELL", 0.75)))
    assert summary.dominant_action == "SELL"
    assert summary.is_unanimous is True
    assert summary.total == 1
    assert summary.mean_confidence == pytest.approx(0.75)


def test_legs_are_sorted_by_timeframe_order() -> None:
    summary = summarize_confluence("BTC/USDT", _legs(("1d", "BUY", 0.6), ("5m", "BUY", 0.6), ("1h", "BUY", 0.6)))
    assert [leg.timeframe for leg in summary.legs] == ["5m", "1h", "1d"]


def test_unknown_timeframe_sorts_last_without_error() -> None:
    summary = summarize_confluence("BTC/USDT", _legs(("99z", "BUY", 0.6), ("1h", "BUY", 0.6)))
    assert [leg.timeframe for leg in summary.legs] == ["1h", "99z"]


def test_empty_legs_returns_neutral_summary() -> None:
    summary = summarize_confluence("BTC/USDT", [])
    assert summary.total == 0
    assert summary.dominant_action == "HOLD"
    assert summary.is_unanimous is False
    assert summary.is_conflicted is False
    assert summary.mean_confidence == 0.0
