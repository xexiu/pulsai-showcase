"""
SoT tests: user notification email eligibility (signal alerts vs weekly digest).

Unit: compiled SQL references the same JSON keys as GET/PATCH /auth/me/settings.
Integration: PostgreSQL JSON semantics (explicit false vs missing key vs inactive user).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from src.infrastructure.persistence.user_model import User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
from src.infrastructure.persistence.notification_preference_queries import (
    USER_SETTINGS_KEY_EMAIL_NOTIFICATIONS,
    USER_SETTINGS_KEY_SIGNAL_ALERTS,
    USER_SETTINGS_KEY_WEEKLY_SUMMARY,
    select_users_eligible_for_signal_email_alerts,
    select_users_eligible_for_weekly_digest_email,
)


def _compile(stmt: object) -> str:
    """literal_binds so JSON keys appear in SQL (behavior contract for SoT tests)."""
    return str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_settings_key_constants_match_auth_profile_contract() -> None:
    """Regression: keys must stay aligned with User.settings and auth_profile UserSettingsData."""
    assert USER_SETTINGS_KEY_SIGNAL_ALERTS == "signal_alerts"
    assert USER_SETTINGS_KEY_WEEKLY_SUMMARY == "weekly_summary"
    assert USER_SETTINGS_KEY_EMAIL_NOTIFICATIONS == "email_notifications"


def test_signal_email_select_includes_elite_or_staff_and_settings_keys() -> None:
    sql = _compile(select_users_eligible_for_signal_email_alerts())
    assert USER_SETTINGS_KEY_SIGNAL_ALERTS in sql
    assert USER_SETTINGS_KEY_EMAIL_NOTIFICATIONS in sql
    assert "elite" in sql
    assert "admin" in sql
    assert "super_admin" in sql
    assert USER_SETTINGS_KEY_WEEKLY_SUMMARY not in sql


def test_weekly_digest_select_filters_on_weekly_summary_and_master_email_keys() -> None:
    sql = _compile(select_users_eligible_for_weekly_digest_email())
    assert USER_SETTINGS_KEY_WEEKLY_SUMMARY in sql
    assert USER_SETTINGS_KEY_EMAIL_NOTIFICATIONS in sql
    assert USER_SETTINGS_KEY_SIGNAL_ALERTS not in sql


def test_weekly_and_signal_selects_are_distinct_queries() -> None:
    a = _compile(select_users_eligible_for_signal_email_alerts())
    b = _compile(select_users_eligible_for_weekly_digest_email())
    assert a != b


@pytest.mark.integration
def test_signal_email_eligibility_requires_elite_or_staff(model_db_session: Session) -> None:
    """Per-signal email list: Elite (or admin) + JSON prefs; free tier excluded even if JSON true."""
    elite_on = User(
        id=str(uuid4()),
        email="elite_sig_on@example.com",
        password_hash="h",
        subscription_tier="elite",
        settings={
            "email_notifications": True,
            "signal_alerts": True,
        },
    )
    elite_off = User(
        id=str(uuid4()),
        email="elite_sig_off@example.com",
        password_hash="h",
        subscription_tier="elite",
        settings={
            "email_notifications": True,
            "signal_alerts": False,
        },
    )
    free_json_on = User(
        id=str(uuid4()),
        email="free_sig_on@example.com",
        password_hash="h",
        subscription_tier="free",
        settings={
            "email_notifications": True,
            "signal_alerts": True,
        },
    )
    admin_on = User(
        id=str(uuid4()),
        email="admin_sig_on@example.com",
        password_hash="h",
        role="admin",
        subscription_tier="free",
        settings={
            "email_notifications": True,
            "signal_alerts": True,
        },
    )
    inactive_elite = User(
        id=str(uuid4()),
        email="inactive_elite@example.com",
        password_hash="h",
        subscription_tier="elite",
        is_active=False,
        settings={"signal_alerts": True, "email_notifications": True},
    )
    elite_missing_keys = User(
        id=str(uuid4()),
        email="elite_defaults_json@example.com",
        password_hash="h",
        subscription_tier="elite",
        settings={},
    )
    model_db_session.add_all([elite_on, elite_off, free_json_on, admin_on, inactive_elite, elite_missing_keys])
    model_db_session.commit()

    rows = model_db_session.execute(select_users_eligible_for_signal_email_alerts()).scalars().all()
    emails = {u.email for u in rows}

    assert "elite_sig_on@example.com" in emails
    assert "admin_sig_on@example.com" in emails
    assert "elite_defaults_json@example.com" in emails
    assert "elite_sig_off@example.com" not in emails
    assert "free_sig_on@example.com" not in emails
    assert "inactive_elite@example.com" not in emails


@pytest.mark.integration
def test_weekly_digest_eligibility_behavior(model_db_session: Session) -> None:
    included = User(
        id=str(uuid4()),
        email="weekly_on_defaults@example.com",
        password_hash="h",
    )
    weekly_off = User(
        id=str(uuid4()),
        email="weekly_off@example.com",
        password_hash="h",
        settings={
            "email_notifications": True,
            "signal_alerts": True,
            "weekly_summary": False,
        },
    )
    model_db_session.add_all([included, weekly_off])
    model_db_session.commit()

    rows = model_db_session.execute(select_users_eligible_for_weekly_digest_email()).scalars().all()
    emails = {u.email for u in rows}

    assert "weekly_on_defaults@example.com" in emails
    assert "weekly_off@example.com" not in emails


@pytest.mark.integration
def test_weekly_digest_uses_top_level_weekly_summary_not_nested_notifications(
    model_db_session: Session,
) -> None:
    """SoT is ``settings.weekly_summary``; nested ``notifications.weekly_digest`` is ignored."""
    nested_only = User(
        id=str(uuid4()),
        email="nested_only_digest@example.com",
        password_hash="h",
        settings={
            "notifications": {"weekly_digest": True},
            "email_notifications": True,
        },
    )
    nested_true_but_top_false = User(
        id=str(uuid4()),
        email="nested_true_top_false@example.com",
        password_hash="h",
        settings={
            "notifications": {"weekly_digest": True},
            "weekly_summary": False,
            "email_notifications": True,
        },
    )
    model_db_session.add_all([nested_only, nested_true_but_top_false])
    model_db_session.commit()

    rows = model_db_session.execute(select_users_eligible_for_weekly_digest_email()).scalars().all()
    emails = {u.email for u in rows}

    assert "nested_only_digest@example.com" in emails
    assert "nested_true_top_false@example.com" not in emails
