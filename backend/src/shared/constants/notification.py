"""
Shared notification result keys (SoT for API contract).

WHY this module exists:
- NotificationService.notify_signal() returns a dict with fixed keys.
- API endpoint (signals.py) and any consumer must use the same keys.
- No magic strings in notification_service or callers.

@see CODING_STANDARDS.md §12 (Constants and Magic Numbers)
"""

from __future__ import annotations

# Result keys returned by NotificationService.notify_signal()
NOTIFICATION_KEY_TELEGRAM_SENT = "telegram_sent"
NOTIFICATION_KEY_TELEGRAM_FAILED = "telegram_failed"
NOTIFICATION_KEY_EMAIL_SENT = "email_sent"
NOTIFICATION_KEY_EMAIL_FAILED = "email_failed"
NOTIFICATION_KEY_EMAIL_RATE_LIMITED = "email_rate_limited"

# Inner keys returned by _send_telegram_alerts / _send_email_alerts
NOTIFICATION_INNER_KEY_SENT = "sent"
NOTIFICATION_INNER_KEY_FAILED = "failed"
NOTIFICATION_INNER_KEY_RATE_LIMITED = "rate_limited"


def notification_result_skeleton() -> dict[str, int]:
    """Return the default notification result dict with all keys set to 0. SoT for structure."""
    return {
        NOTIFICATION_KEY_TELEGRAM_SENT: 0,
        NOTIFICATION_KEY_TELEGRAM_FAILED: 0,
        NOTIFICATION_KEY_EMAIL_SENT: 0,
        NOTIFICATION_KEY_EMAIL_FAILED: 0,
        NOTIFICATION_KEY_EMAIL_RATE_LIMITED: 0,
    }


__all__ = [
    "NOTIFICATION_INNER_KEY_FAILED",
    "NOTIFICATION_INNER_KEY_RATE_LIMITED",
    "NOTIFICATION_INNER_KEY_SENT",
    "NOTIFICATION_KEY_EMAIL_FAILED",
    "NOTIFICATION_KEY_EMAIL_RATE_LIMITED",
    "NOTIFICATION_KEY_EMAIL_SENT",
    "NOTIFICATION_KEY_TELEGRAM_FAILED",
    "NOTIFICATION_KEY_TELEGRAM_SENT",
    "notification_result_skeleton",
]
