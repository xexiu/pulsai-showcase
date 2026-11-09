"""SoT tests for marketing newsletter audience selection."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from src.infrastructure.persistence.marketing_newsletter_queries import (
    MarketingNewsletterRecipient,
    select_marketing_newsletter_recipients_batch,
    sync_list_marketing_newsletter_recipients_batch,
)
from src.infrastructure.persistence.newsletter_subscriber_model import NewsletterSubscriberModel
from src.infrastructure.persistence.user_model import User
from src.shared.utils.datetime_utils import utc_now


def _compile(stmt: object) -> str:
    return str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_marketing_newsletter_batch_query_uses_email_keyset_and_unsubscribe_guard() -> None:
    sql = _compile(select_marketing_newsletter_recipients_batch(after_email=None, limit=100))
    assert "ORDER BY anon_1.email ASC" in sql
    assert "LIMIT 100" in sql
    assert "anon_1.email >" not in sql
    assert "marketing_consent" in sql
    assert "unsubscribed_at IS NOT NULL" in sql
    assert "DISTINCT ON (anon_1.email)" in sql
    assert "row_number()" not in sql.lower()


def test_marketing_newsletter_batch_query_supports_cursor() -> None:
    sql = _compile(
        select_marketing_newsletter_recipients_batch(
            after_email="m@example.com",
            limit=25,
        )
    )
    assert "newsletter_subscribers.email > 'm@example.com'" in sql
    assert "users.email > 'm@example.com'" in sql
    assert "LIMIT 25" in sql


@pytest.mark.integration
def test_marketing_newsletter_audience_dedupes_and_newsletter_unsubscribe_wins(
    model_db_session,
) -> None:
    subscriber_only = NewsletterSubscriberModel(
        id=str(uuid4()),
        email="subscriber_only@example.com",
        source="landing",
        is_lead=False,
    )
    user_only = User(
        id=str(uuid4()),
        email="user_only@example.com",
        password_hash="h",
        marketing_consent=True,
        locale="en",
        name="User Only",
    )
    duplicate_user = User(
        id=str(uuid4()),
        email="duplicate@example.com",
        password_hash="h",
        marketing_consent=True,
        locale="es",
        name="Duplicate User",
    )
    duplicate_subscriber = NewsletterSubscriberModel(
        id=str(uuid4()),
        email="duplicate@example.com",
        source="blog",
        is_lead=False,
    )
    unsubscribed_subscriber = NewsletterSubscriberModel(
        id=str(uuid4()),
        email="blocked@example.com",
        source="x",
        is_lead=False,
        unsubscribed_at=utc_now(),
    )
    blocked_user = User(
        id=str(uuid4()),
        email="blocked@example.com",
        password_hash="h",
        marketing_consent=True,
        locale="en",
        name="Blocked User",
    )
    marketing_off = User(
        id=str(uuid4()),
        email="marketing_off@example.com",
        password_hash="h",
        marketing_consent=False,
    )
    inactive_user = User(
        id=str(uuid4()),
        email="inactive@example.com",
        password_hash="h",
        marketing_consent=True,
        is_active=False,
    )

    model_db_session.add_all(
        [
            subscriber_only,
            user_only,
            duplicate_user,
            duplicate_subscriber,
            unsubscribed_subscriber,
            blocked_user,
            marketing_off,
            inactive_user,
        ]
    )
    model_db_session.commit()

    rows = sync_list_marketing_newsletter_recipients_batch(
        model_db_session,
        after_email=None,
        limit=20,
    )

    assert rows == sorted(rows, key=lambda row: row.email)
    emails = {row.email for row in rows}
    assert "subscriber_only@example.com" in emails
    assert "user_only@example.com" in emails
    assert "duplicate@example.com" in emails
    assert "blocked@example.com" not in emails
    assert "marketing_off@example.com" not in emails
    assert "inactive@example.com" not in emails

    duplicate_row = next(row for row in rows if row.email == "duplicate@example.com")
    assert duplicate_row.recipient_kind == "subscriber"
    assert duplicate_row.subscriber_id == duplicate_subscriber.id
    assert duplicate_row.user_id == duplicate_user.id
    assert duplicate_row.user_name == "Duplicate User"
    assert duplicate_row.locale == "es"

    user_only_row = next(row for row in rows if row.email == "user_only@example.com")
    assert user_only_row.recipient_kind == "user"
    assert user_only_row.subscriber_id is None
    assert user_only_row.user_id == user_only.id
    assert user_only_row.user_name == "User Only"
    assert user_only_row.locale == "en"


@pytest.mark.integration
def test_marketing_newsletter_audience_batches_with_email_cursor(model_db_session) -> None:
    rows = [
        User(id=str(uuid4()), email="a@example.com", password_hash="h", marketing_consent=True),
        User(id=str(uuid4()), email="m@example.com", password_hash="h", marketing_consent=True),
        User(id=str(uuid4()), email="z@example.com", password_hash="h", marketing_consent=True),
    ]
    model_db_session.add_all(rows)
    model_db_session.commit()

    first = sync_list_marketing_newsletter_recipients_batch(
        model_db_session,
        after_email=None,
        limit=2,
    )
    second = sync_list_marketing_newsletter_recipients_batch(
        model_db_session,
        after_email=first[-1].email,
        limit=2,
    )

    assert [row.email for row in first] == ["a@example.com", "m@example.com"]
    assert [row.email for row in second] == ["z@example.com"]


def test_marketing_newsletter_recipient_is_orderable_by_email() -> None:
    items = [
        MarketingNewsletterRecipient(
            email="b@example.com",
            recipient_kind="user",
            user_id="u2",
            subscriber_id=None,
            user_name=None,
            locale=None,
        ),
        MarketingNewsletterRecipient(
            email="a@example.com",
            recipient_kind="subscriber",
            user_id=None,
            subscriber_id="s1",
            user_name=None,
            locale=None,
        ),
    ]

    assert [item.email for item in sorted(items, key=lambda row: row.email)] == [
        "a@example.com",
        "b@example.com",
    ]
