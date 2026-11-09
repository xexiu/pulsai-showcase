"""
Single source of truth: which users receive email signal alerts vs weekly digest.

WHY centralized:
- Async API path (UserRepository) and sync Celery worker (email_tasks) must use
  identical JSON key paths and default semantics, or users see wrong toggles / miss digests.
- GET/PATCH ``/api/v1/auth/me/settings`` uses the same keys on ``User.settings``.

Default semantics (match ``auth_profile`` and ``User`` model defaults):
- Key missing or JSON null → treated as enabled (opt-out only when explicitly ``false``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Select, asc, or_, select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from src.domain.enums import SubscriptionTier
from src.infrastructure.persistence.user_model import User, UserRole

USER_SETTINGS_KEY_EMAIL_NOTIFICATIONS = "email_notifications"
USER_SETTINGS_KEY_SIGNAL_ALERTS = "signal_alerts"
USER_SETTINGS_KEY_WEEKLY_SUMMARY = "weekly_summary"


def _settings_json_true_or_missing(key: str) -> Any:
    """True if settings[key] is boolean true or absent/null (API default-on)."""
    return or_(
        User.settings[key].as_boolean().is_(True),
        User.settings[key].is_(None),
    )


def _email_signal_alerts_sql_or_predicate() -> Any:
    """SQLAlchemy OR predicate: mirrors ``user_may_receive_email_signal_alerts``."""
    return or_(
        User.subscription_tier == SubscriptionTier.ELITE.value,
        User.role.in_((UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value)),
    )


def select_users_eligible_for_signal_email_alerts() -> Select[Any]:
    """
    Users who should receive per-signal email alerts (Resend).

    Filters: active, Elite tier or staff (admin/super_admin), master email on,
    signal_alerts on (or default). Mirrors ``user_may_receive_email_signal_alerts``.
    """
    return (
        select(User)
        .where(User.is_active.is_(True))
        .where(_email_signal_alerts_sql_or_predicate())
        .where(_settings_json_true_or_missing(USER_SETTINGS_KEY_SIGNAL_ALERTS))
        .where(_settings_json_true_or_missing(USER_SETTINGS_KEY_EMAIL_NOTIFICATIONS))
    )


def select_users_eligible_for_weekly_digest_email() -> Select[Any]:
    """
    Users who should receive the scheduled weekly digest (Celery + Resend).

    Filters: active, master email on, weekly_summary on (or default).
    """
    return (
        select(User)
        .where(User.is_active.is_(True))
        .where(_settings_json_true_or_missing(USER_SETTINGS_KEY_WEEKLY_SUMMARY))
        .where(_settings_json_true_or_missing(USER_SETTINGS_KEY_EMAIL_NOTIFICATIONS))
    )


def select_users_eligible_for_weekly_digest_email_batch(
    *,
    after_user_id: str | None,
    limit: int,
) -> Select[Any]:
    """
    Keyset page of weekly-digest recipients (stable ``ORDER BY users.id``).

    WHY: Celery must not ``SELECT *`` all subscribers into memory when counts are large.
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")
    stmt = select_users_eligible_for_weekly_digest_email()
    if after_user_id is not None:
        stmt = stmt.where(User.id > after_user_id)
    return stmt.order_by(asc(User.id)).limit(limit)


def sync_list_users_eligible_for_weekly_digest_email_batch(
    session: Session,
    *,
    after_user_id: str | None,
    limit: int,
) -> list[User]:
    """
    Sync: one keyset page of weekly-digest recipients (psycopg2 session).

    Used by Celery weekly digest; wraps ``select_users_eligible_for_weekly_digest_email_batch``.
    """
    stmt = select_users_eligible_for_weekly_digest_email_batch(
        after_user_id=after_user_id,
        limit=limit,
    )
    result = session.execute(stmt)
    return list(result.scalars().all())
