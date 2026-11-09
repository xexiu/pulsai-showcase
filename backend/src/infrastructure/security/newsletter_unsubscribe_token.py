"""
Signed tokens for logged-out newsletter unsubscribe links.

Uses itsdangerous (already a dependency) with the app secret_key.
"""

from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.infrastructure.config.settings import settings

_SALT = "newsletter-unsub-v1"
_DEFAULT_MAX_AGE_SECONDS = 90 * 24 * 3600
# Reject trivially short ids (tokens must bind to real newsletter_subscribers.id).
_MIN_SUBSCRIBER_ID_LEN = 8


def create_newsletter_unsubscribe_token(subscriber_id: str) -> str:
    """Build a time-limited token bound to newsletter_subscribers.id."""
    serializer = URLSafeTimedSerializer(settings.secret_key, salt=_SALT)
    return serializer.dumps({"sid": subscriber_id})


def parse_newsletter_unsubscribe_token(
    token: str,
    *,
    max_age_seconds: int = _DEFAULT_MAX_AGE_SECONDS,
) -> str | None:
    """
    Validate token and return subscriber id, or None if invalid/expired.

    Callers should treat None as a silent no-op for idempotent unsubscribe.
    """
    serializer = URLSafeTimedSerializer(settings.secret_key, salt=_SALT)
    try:
        data = serializer.loads(token, max_age=max_age_seconds)
    except BadSignature, SignatureExpired:
        return None
    sid = data.get("sid")
    if not isinstance(sid, str) or len(sid) < _MIN_SUBSCRIBER_ID_LEN:
        return None
    return sid
