"""
Password Reset Token Domain Model

SQLAlchemy model for password reset tokens.

SECURITY DESIGN (OWASP Best Practices):
- Only HASHED token is stored (SHA-256), raw token sent via email
- Tokens expire after 30 minutes (configurable)
- Single-use: token invalidated after use
- New token request invalidates old tokens

Sprint 1.6b: Password Reset Flow
"""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.model_columns import owning_user_id, uuid_primary_key
from src.infrastructure.persistence.sqlalchemy_base import Base
from src.shared.utils.datetime_utils import utc_now


class PasswordResetTokenModel(Base):
    """
    Password reset token model.

    WHY HASH THE TOKEN?
    - If database is compromised, attacker can't use hashed tokens
    - Raw token is only known to the user (sent via email)
    - Similar security model to password hashing

    WORKFLOW:
    1. User requests reset → generate raw token, store hash
    2. Email contains raw token in reset link
    3. User submits raw token → hash it, compare with stored hash
    4. Match → allow password reset, mark token as used
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = uuid_primary_key()
    user_id: Mapped[str] = owning_user_id()
    token_hash: Mapped[str] = mapped_column(
        String(64),  # SHA-256 hex = 64 chars
        nullable=False,
        unique=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: utc_now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<PasswordResetToken user_id={self.user_id} expires_at={self.expires_at}>"

    @property
    def is_expired(self) -> bool:
        """Check if token has expired."""
        return utc_now() > self.expires_at

    @property
    def is_used(self) -> bool:
        """Check if token has been used."""
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not used)."""
        return not self.is_expired and not self.is_used
