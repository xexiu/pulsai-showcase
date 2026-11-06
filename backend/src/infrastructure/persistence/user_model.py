"""
User Domain Model

SQLAlchemy model for user accounts.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.enums import RegistrationSource
from src.infrastructure.persistence.sqlalchemy_base import Base
from src.shared.constants.themes import DEFAULT_USER_THEME
from src.shared.utils.datetime_utils import utc_now

# =============================================================================
# Enumerations
# =============================================================================


class UserRole(StrEnum):
    """
    User role enumeration for type-safe role checks.

    WHY this enum:
    - Prevents typos ("super_amdin" vs "super_admin") = security bug
    - IDE autocomplete and type checking
    - Single source of truth for role values
    - Values MUST match database SqlEnum exactly

    USAGE:
        # Before (typo-prone):
        if user.role != "super_admin":

        # After (type-safe):
        if user.role != UserRole.SUPER_ADMIN:
    """

    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

    def is_admin(self) -> bool:
        """
        Check if role has admin privileges.

        Returns True for ADMIN and SUPER_ADMIN.
        """
        return self in (UserRole.ADMIN, UserRole.SUPER_ADMIN)

    def is_super_admin(self) -> bool:
        """
        Check if role is super_admin (highest privilege).

        Returns True only for SUPER_ADMIN.
        """
        return self == UserRole.SUPER_ADMIN


# =============================================================================
# SQLAlchemy Model
# =============================================================================


class User(Base):
    """User account model."""

    __tablename__ = "users"

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
    password_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,  # OAuth users may not have password
    )
    # OAuth fields (Sprint 2.4b)
    # WHY separate fields: User can link multiple OAuth providers later
    # oauth_provider: Which OAuth provider was used (e.g., "google")
    # oauth_id: The provider's unique user ID (immutable, used for login)
    oauth_provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    oauth_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(
        SqlEnum("user", "admin", "super_admin", name="user_role"),
        default="user",
        nullable=False,
    )
    subscription_tier: Mapped[str] = mapped_column(
        SqlEnum("free", "starter", "pro", "elite", name="subscription_tier"),
        default="free",
        nullable=False,
    )
    # Stripe linkage (Sprint 3.4); set via Checkout + webhooks
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    # How the user signed up (direct, vip_launch, invitation, campaign, …)
    # WHY: Analytics and campaign attribution; VIP code at register → vip_launch
    # values_callable: DB stores enum values ('direct', 'vip_launch'); SA defaults to names (DIRECT) → LookupError on login.
    registration_source: Mapped[str] = mapped_column(
        SqlEnum(
            RegistrationSource,
            name="registration_source",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=RegistrationSource.DIRECT.value,
        nullable=False,
    )
    # GDPR Mandatory Consents (both required at registration)
    # WHY: GDPR Art. 7 requires explicit, informed, freely-given consent for data processing
    # User is not created unless both are explicitly true
    terms_consent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="User explicitly agreed to Terms of Service",
    )
    data_processing_consent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="User explicitly consented to GDPR data processing (Art. 7)",
    )
    # GDPR Optional Marketing Consent
    # WHY: Marketing is legitimate interest (Art. 6(1)(f)), not required; explicit opt-in preferred
    # NULL = no choice made (user skipped field)
    # true = user opted in
    # false = user explicitly opted out
    marketing_consent: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        default=None,
        doc="User opted in (true) / out (false) of marketing. NULL = no choice made.",
    )
    # Audit Trail Timestamps (read-only, auto-set on insert)
    # WHY: GDPR Art. 30 requires records of when and how consent was obtained
    # Timestamps are immutable audit trail for compliance verification
    terms_consent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: utc_now(),
        doc="Timestamp when user agreed to Terms of Service",
    )
    data_processing_consent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: utc_now(),
        doc="Timestamp when user consented to data processing",
    )
    marketing_consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        doc="Timestamp when user opted in/out of marketing. NULL if marketing_consent=NULL",
    )
    #: User acknowledged ADR-009 full-auto risks before enabling full_auto automations.
    full_auto_trading_consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        doc="When user accepted full-auto trading safeguards (nullable until consent)",
    )
    #: Set on every password reset/change. Access tokens issued before this instant are
    #: rejected at auth time (global session invalidation — revokes an attacker's other
    #: sessions when the victim resets). NULL for users who never changed their password.
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        doc="Last password reset/change; tokens with iat before this are revoked",
    )
    # Minimum legal bundle version the user has actively accepted (terms + privacy re-confirm).
    # Compared to legal_policy.required_legal_bundle_version; if lower, app must block sensitive API.
    legal_bundle_version_accepted: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        doc="Last accepted legal bundle version (aligned with global policy row)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    locale: Mapped[str] = mapped_column(
        String(5),
        default="es",
        nullable=False,
    )
    # User settings stored as JSON for flexibility
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=lambda: {
            "email_notifications": True,
            "signal_alerts": False,
            "weekly_summary": True,
            "theme": DEFAULT_USER_THEME,
            "timezone": "Europe/Madrid",
            "chart_timezone": None,
            "billing_currency": "eur",
            "chart_symbol": None,
            "chart_timeframe": None,
            "chart_viewport": None,
        },
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: utc_now(),
        nullable=False,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: utc_now(),
        nullable=False,
        doc="Single source of truth for account inactivity tracking; updated on successful auth activity.",
    )
    inactivity_warning_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
        doc="When PulsAI emailed the user about long-term inactivity pending deletion.",
    )
    scheduled_deletion_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
        nullable=True,
        doc="Deletion deadline measured from inactivity warning send time; cleared on new activity.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: utc_now(),
        onupdate=lambda: utc_now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        oauth_info = f" ({self.oauth_provider})" if self.oauth_provider else ""
        return f"<User {self.email}{oauth_info}>"
