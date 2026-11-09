"""
Telegram Subscription Domain Model

Persists Telegram alert subscriptions to database.

WHY separate table (not User.telegram_chat_id):
- Allows anonymous subscriptions (no PulsAI account required)
- Telegram user can subscribe without linking to email
- Simpler MVP - account linking can be added later

Sprint 2.Xd Enhancement: Per-symbol filtering
- subscribed_symbols: Array of symbols to receive alerts for
- NULL or [] = ALL symbols (backward compatible)

@see docs/01-business/ROADMAP.md - Sprint 2.4 Email Notifications
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.sqlalchemy_base import Base
from src.shared.utils.datetime_utils import utc_now


class TelegramSubscriptionModel(Base):
    """
    Telegram alert subscription.

    Stores Telegram chat IDs that want to receive signal alerts.
    Can optionally be linked to a PulsAI user account.
    """

    __tablename__ = "telegram_subscriptions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Telegram chat ID (unique identifier for the chat/user)
    # WHY BigInteger: Telegram chat IDs can exceed 32-bit int range
    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )

    # Optional: Username for display purposes
    username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Whether alerts are currently enabled
    alerts_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Economic calendar (FOMC/CPI/NFP) Telegram alerts — requires alerts_enabled
    econ_alerts_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Epic B opt-in: TG notification on every auto-order outcome (success + failure).
    # Defaults False so existing subscribers don't suddenly get auto-order chatter.
    # Auto-order audit_logs row is always written regardless of this flag.
    auto_order_notify_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Per-symbol filtering (Sprint 2.Xd)
    # WHY JSONB array: Simple, flexible, queryable with PostgreSQL operators
    # NULL or [] = ALL symbols (backward compatible with existing subscribers)
    # ["BTC/USDT", "ETH/USDT"] = Only receive alerts for these pairs
    subscribed_symbols: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )

    # Optional: Link to PulsAI user account
    # WHY optional: Allows anonymous subscriptions
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: utc_now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: utc_now(),
        onupdate=lambda: utc_now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        status = "enabled" if self.alerts_enabled else "disabled"
        return f"<TelegramSubscription chat_id={self.chat_id} {status}>"
