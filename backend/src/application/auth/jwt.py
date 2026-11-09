"""
JWT Token Service

Handles JWT token creation and validation.
Following security guidelines from docs/07-security/SECURITY_GUIDELINES.md
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import jwt
from pydantic import BaseModel, ConfigDict

from src.infrastructure.config.settings import settings
from src.shared.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)

# Token types
TokenType = Literal["access", "refresh"]


class TokenPayload(BaseModel):
    """
    Decoded token payload.

    WHY Pydantic: Validates token data at construction.
    """

    model_config = ConfigDict(from_attributes=True)

    sub: str  # User ID
    type: TokenType
    exp: datetime
    iat: datetime
    jti: str | None = None  # JWT ID (for refresh tokens)
    # Refresh only: whether new auth cookies should use persistent Max-Age (mirrors login remember_me).
    persist_refresh: bool = True


class TokenPair(BaseModel):
    """
    Access and refresh token pair.

    WHY Pydantic: Validates token pair data.
    """

    model_config = ConfigDict(from_attributes=True)

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 0  # Seconds until access token expires


class JWTService:
    """
    Service for JWT token operations.

    Access tokens: Short-lived (15-30 min), for API authentication
    Refresh tokens: Long-lived (7 days), for getting new access tokens
    """

    def __init__(
        self,
        secret_key: str | None = None,
        access_token_expire_minutes: int | None = None,
        refresh_token_expire_days: int | None = None,
    ) -> None:
        """
        Initialize JWT service.

        Args:
            secret_key: JWT signing key (defaults to settings.secret_key)
            access_token_expire_minutes: Access token lifetime
            refresh_token_expire_days: Refresh token lifetime
        """
        self.secret_key = secret_key or settings.secret_key
        self.access_token_expire_minutes = access_token_expire_minutes or settings.access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days or settings.refresh_token_expire_days
        self.algorithm = "HS256"

    def create_access_token(
        self,
        user_id: str,
        additional_claims: dict[str, Any] | None = None,
    ) -> str:
        """
        Create short-lived access token.

        Args:
            user_id: User's unique identifier.
            additional_claims: Optional additional claims to include.

        Returns:
            Encoded JWT access token.
        """
        now = utc_now()
        expire = now + timedelta(minutes=self.access_token_expire_minutes)

        payload: dict[str, object] = {
            "sub": user_id,
            "type": "access",
            "iat": now,
            "exp": expire,
            "jti": str(uuid4()),  # Unique ID for logout/revocation (blacklist)
        }

        if additional_claims:
            payload.update(additional_claims)

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return str(token)

    def create_refresh_token(self, user_id: str, *, persist_refresh: bool = True) -> str:
        """
        Create long-lived refresh token.

        Args:
            user_id: User's unique identifier.
            persist_refresh: Stored as claim ``prm``; rotation preserves cookie persistence policy.

        Returns:
            Encoded JWT refresh token.
        """
        now = utc_now()
        expire = now + timedelta(days=self.refresh_token_expire_days)

        payload: dict[str, object] = {
            "sub": user_id,
            "type": "refresh",
            "iat": now,
            "exp": expire,
            "jti": str(uuid4()),  # Unique ID for revocation tracking
            "prm": persist_refresh,
        }

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return str(token)

    def create_token_pair(
        self,
        user_id: str,
        additional_claims: dict[str, Any] | None = None,
        *,
        persist_refresh: bool = True,
    ) -> TokenPair:
        """
        Create both access and refresh tokens.

        Args:
            user_id: User's unique identifier.
            additional_claims: Optional claims for access token.
            persist_refresh: Encoded on refresh token for cookie Max-Age policy across rotation.

        Returns:
            TokenPair with access_token, refresh_token, and metadata.
        """
        access_token = self.create_access_token(user_id, additional_claims)
        refresh_token = self.create_refresh_token(user_id, persist_refresh=persist_refresh)

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=self.access_token_expire_minutes * 60,  # Convert to seconds
        )

    def verify_token(
        self,
        token: str,
        expected_type: TokenType = "access",
    ) -> TokenPayload | None:
        """
        Verify and decode JWT token.

        Args:
            token: The JWT token to verify.
            expected_type: Expected token type ("access" or "refresh").

        Returns:
            TokenPayload if valid, None if invalid or wrong type.
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )

            # Check token type
            if payload.get("type") != expected_type:
                logger.debug("jwt rejected: type %r, expected %r", payload.get("type"), expected_type)
                return None

            exp_raw = payload.get("exp")
            iat_raw = payload.get("iat")
            if exp_raw is None or iat_raw is None:
                logger.debug("jwt rejected: missing exp or iat claim")
                return None

            exp_dt = exp_raw if isinstance(exp_raw, datetime) else datetime.fromtimestamp(exp_raw, tz=UTC)
            iat_dt = iat_raw if isinstance(iat_raw, datetime) else datetime.fromtimestamp(iat_raw, tz=UTC)

            prm_raw = payload.get("prm")
            persist_refresh = True if prm_raw is None else bool(prm_raw)

            return TokenPayload(
                sub=payload["sub"],
                type=payload["type"],
                exp=exp_dt,
                iat=iat_dt,
                jti=payload.get("jti"),
                persist_refresh=persist_refresh,
            )

        except jwt.PyJWTError as exc:
            # The reason only (expired, bad signature, malformed) -- never the token itself.
            logger.debug("jwt rejected: %s", type(exc).__name__)
            return None


# Global instance for dependency injection
jwt_service = JWTService()
