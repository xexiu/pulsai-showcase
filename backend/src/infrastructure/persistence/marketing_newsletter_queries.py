"""Single source of truth for weekly marketing newsletter audience selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import Select, String, asc, cast, func, literal, select, union_all

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from src.infrastructure.persistence.newsletter_subscriber_model import NewsletterSubscriberModel
from src.infrastructure.persistence.user_model import User

MarketingRecipientKind = Literal["subscriber", "user"]


@dataclass(frozen=True)
class MarketingNewsletterRecipient:
    """Recipient payload used by sync workers for weekly marketing sends."""

    email: str
    recipient_kind: MarketingRecipientKind
    user_id: str | None
    subscriber_id: str | None
    user_name: str | None
    locale: str | None


def _combined_marketing_newsletter_recipients_subquery(*, after_email: str | None) -> Any:
    """Combined audience rows with cursor filtering applied before dedupe."""
    unsubscribed_email_exists = (
        select(NewsletterSubscriberModel.id)
        .where(NewsletterSubscriberModel.email == User.email)
        .where(NewsletterSubscriberModel.unsubscribed_at.is_not(None))
        .exists()
    )

    subscriber_rows = (
        select(
            NewsletterSubscriberModel.email.label("email"),
            cast(User.id, String()).label("user_id"),
            cast(NewsletterSubscriberModel.id, String()).label("subscriber_id"),
            User.name.label("user_name"),
            User.locale.label("locale"),
            literal("subscriber").label("recipient_kind"),
            literal(1).label("priority"),
        )
        .select_from(NewsletterSubscriberModel)
        .outerjoin(User, User.email == NewsletterSubscriberModel.email)
        .where(NewsletterSubscriberModel.unsubscribed_at.is_(None))
    )
    if after_email is not None:
        subscriber_rows = subscriber_rows.where(NewsletterSubscriberModel.email > after_email)

    user_rows = (
        select(
            User.email.label("email"),
            cast(User.id, String()).label("user_id"),
            literal(None, type_=String()).label("subscriber_id"),
            User.name.label("user_name"),
            User.locale.label("locale"),
            literal("user").label("recipient_kind"),
            literal(2).label("priority"),
        )
        .select_from(User)
        .where(User.is_active.is_(True))
        .where(User.marketing_consent.is_(True))
        .where(~unsubscribed_email_exists)
    )
    if after_email is not None:
        user_rows = user_rows.where(User.email > after_email)

    return union_all(subscriber_rows, user_rows).subquery()


def select_marketing_newsletter_recipients_batch(
    *,
    after_email: str | None,
    limit: int,
) -> Select[Any]:
    """
    Keyset page of marketing newsletter recipients ordered by normalized email.

    Audience rules:
    - newsletter_subscribers with ``unsubscribed_at IS NULL`` are eligible
    - users with ``marketing_consent = true`` are eligible
    - if both exist for the same email, keep one row and prefer subscriber unsubscribe semantics
    - if a newsletter row exists with ``unsubscribed_at IS NOT NULL``, exclude that email entirely
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")

    combined = _combined_marketing_newsletter_recipients_subquery(after_email=after_email)
    return (
        select(
            combined.c.email,
            combined.c.user_id,
            combined.c.subscriber_id,
            combined.c.user_name,
            combined.c.locale,
            combined.c.recipient_kind,
        )
        .distinct(combined.c.email)
        .order_by(asc(combined.c.email), asc(combined.c.priority))
        .limit(limit)
    )


def select_marketing_newsletter_recipients_count() -> Select[Any]:
    """Count deduped marketing newsletter recipients."""
    combined = _combined_marketing_newsletter_recipients_subquery(after_email=None)
    return select(func.count(func.distinct(combined.c.email)))


def sync_list_marketing_newsletter_recipients_batch(
    session: Session,
    *,
    after_email: str | None,
    limit: int,
) -> list[MarketingNewsletterRecipient]:
    """Sync helper for Celery marketing newsletter batches."""
    stmt = select_marketing_newsletter_recipients_batch(
        after_email=after_email,
        limit=limit,
    )
    rows = session.execute(stmt).mappings().all()
    return [
        MarketingNewsletterRecipient(
            email=row["email"],
            recipient_kind=row["recipient_kind"],
            user_id=row["user_id"],
            subscriber_id=row["subscriber_id"],
            user_name=row["user_name"],
            locale=row["locale"],
        )
        for row in rows
    ]
