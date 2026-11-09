"""SQLAlchemy mapping for the newsletter_subscriber table.

Lives in ``infrastructure/persistence`` per DDD_PATTERNS.md §"Infrastructure Layer".
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.sqlalchemy_base import Base
from src.shared.utils.datetime_utils import utc_now


class NewsletterSubscriberModel(Base):
    """
    Newsletter subscriber (waitlist / landing signup).

    Email is stored normalized (lowercase, stripped) for deduplication.
    Source indicates attribution (e.g. landing, google, x, direct).
    is_lead=True: one of the first LEAD_CAP subscribers (VIP launch seat);
    is_lead=False: normal newsletter subscriber after cap.
    """

    __tablename__ = "newsletter_subscribers"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="landing",
    )
    is_lead: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: utc_now(),
        nullable=False,
    )
    # When set, do not send marketing broadcasts; transactional emails may still apply.
    unsubscribed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    def __repr__(self) -> str:
        return f"<NewsletterSubscriber email={self.email!r} source={self.source!r} is_lead={self.is_lead}>"
