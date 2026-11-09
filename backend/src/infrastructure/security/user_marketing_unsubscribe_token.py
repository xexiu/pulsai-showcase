"""Signed tokens for logged-out user marketing unsubscribe links."""

from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from src.infrastructure.config.settings import settings

_SALT = "user-marketing-unsub-v1"
_DEFAULT_MAX_AGE_SECONDS = 90 * 24 * 3600
_MIN_USER_ID_LEN = 8


def create_user_marketing_unsubscribe_token(user_id: str) -> str:
    """Build a time-limited token bound to ``users.id``."""
    serializer = URLSafeTimedSerializer(settings.secret_key, salt=_SALT)
    return serializer.dumps({"uid": user_id})


def parse_user_marketing_unsubscribe_token(
    token: str,
    *,
    max_age_seconds: int = _DEFAULT_MAX_AGE_SECONDS,
) -> str | None:
    """Validate token and return ``users.id`` or ``None`` when invalid/expired."""
    serializer = URLSafeTimedSerializer(settings.secret_key, salt=_SALT)
    try:
        data = serializer.loads(token, max_age=max_age_seconds)
    except BadSignature, SignatureExpired:
        return None
    user_id = data.get("uid")
    if not isinstance(user_id, str) or len(user_id) < _MIN_USER_ID_LEN:
        return None
    return user_id
