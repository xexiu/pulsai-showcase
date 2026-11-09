"""Tests for Telegram inline explain button markup (callback_data limits)."""

from src.infrastructure.telegram.telegram_inline_markup import (
    build_explain_signal_reply_markup,
    parse_signal_id_from_explain_callback,
    try_build_explain_signal_reply_markup,
)
from src.shared.constants.telegram import TELEGRAM_EXPLAIN_CALLBACK_PREFIX


def test_build_explain_signal_reply_markup_shape() -> None:
    sid = "550e8400-e29b-41d4-a716-446655440000"
    markup = build_explain_signal_reply_markup(sid)
    row = markup["inline_keyboard"][0][0]
    assert row["text"] == "Explain this signal"
    assert row["callback_data"] == f"{TELEGRAM_EXPLAIN_CALLBACK_PREFIX}{sid}"


def test_try_build_returns_none_for_invalid_id() -> None:
    assert try_build_explain_signal_reply_markup("not-a-uuid") is None


def test_parse_signal_id_from_explain_callback() -> None:
    sid = "550e8400-e29b-41d4-a716-446655440000"
    assert parse_signal_id_from_explain_callback(f"e:{sid}") == sid
    assert parse_signal_id_from_explain_callback("other") is None
