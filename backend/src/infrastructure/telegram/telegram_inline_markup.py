"""
Inline keyboard markup for Telegram (aiogram + send_alert_fresh HTTP).

WHY separate module:
- Keeps NotificationService and bot.py free of Telegram JSON shape details
- Telegram limits callback_data to 64 bytes; we validate once here
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from src.shared.constants.telegram import (
    TELEGRAM_CALLBACK_DATA_MAX_BYTES,
    TELEGRAM_EXPLAIN_CALLBACK_PREFIX,
)

# Button label (English; alerts are not i18n yet)
EXPLAIN_THIS_SIGNAL_LABEL = "Explain this signal"


def build_explain_signal_reply_markup(signal_id: str) -> dict[str, Any]:
    """
    Build reply_markup for sendMessage with one row: explain-this-signal callback.

    Args:
        signal_id: UUID string of the Signal row (same as DB primary key).

    Returns:
        Telegram API inline_keyboard dict.

    Raises:
        ValueError: If signal_id is not a UUID or callback_data would exceed 64 bytes.
    """
    normalized = str(UUID(signal_id))
    data = f"{TELEGRAM_EXPLAIN_CALLBACK_PREFIX}{normalized}"
    encoded = data.encode("utf-8")
    if len(encoded) > TELEGRAM_CALLBACK_DATA_MAX_BYTES:
        msg = "callback_data exceeds Telegram 64-byte limit"
        raise ValueError(msg)

    return {
        "inline_keyboard": [
            [{"text": EXPLAIN_THIS_SIGNAL_LABEL, "callback_data": data}],
        ],
    }


def try_build_explain_signal_reply_markup(signal_id: str) -> dict[str, Any] | None:
    """
    Same as build_explain_signal_reply_markup, but returns None if signal_id is invalid.

    Used for alerts so unit tests with non-UUID signal_id strings still send text-only.
    """
    try:
        return build_explain_signal_reply_markup(signal_id)
    except ValueError:
        return None


def parse_signal_id_from_explain_callback(callback_data: str) -> str | None:
    """
    Extract signal UUID from callback_data, or None if not our explain callback.
    """
    if not callback_data.startswith(TELEGRAM_EXPLAIN_CALLBACK_PREFIX):
        return None
    rest = callback_data[len(TELEGRAM_EXPLAIN_CALLBACK_PREFIX) :]
    if not rest:
        return None
    try:
        return str(UUID(rest))
    except ValueError:
        return None
