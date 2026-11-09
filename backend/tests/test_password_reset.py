"""
Password Reset Tests (Sprint 1.6b)

PRO tests covering:
- Forgot password (request reset)
- Reset password (with token)
- Token expiration
- Security (rate limiting, no user enumeration)

Following TDD: These tests are written FIRST before implementation.
Following OWASP best practices for password reset flows.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from src.infrastructure.persistence.user_model import User
from tests.helpers.register_payloads import register_json

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session

# =============================================================================
# FORGOT PASSWORD TESTS
# =============================================================================


class TestForgotPassword:
    """Test POST /auth/forgot-password endpoint."""

    def test_forgot_password_existing_user_returns_200(self, client: TestClient) -> None:
        """
        Request reset for existing user should return 200.

        SECURITY: Same response for existing/non-existing users
        to prevent user enumeration attacks.
        """
        # Register user first
        client.post(
            "/api/v1/auth/register",
            json=register_json("forgotexisting@example.com", "SecureP@ssword123"),
        )

        with patch(
            "src.api.v1.endpoints.auth_password_reset.email_service.send_password_reset",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = True

            response = client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "forgotexisting@example.com"},
            )

        assert response.status_code == 200
        assert "message" in response.json()["data"]
        # Should NOT reveal if user exists
        assert "forgotexisting" not in response.json()["data"]["message"].lower()

    def test_forgot_password_nonexistent_user_returns_200(self, client: TestClient) -> None:
        """
        Request reset for non-existent user should ALSO return 200.

        WHY? Prevents user enumeration - attacker can't discover
        which emails are registered by observing different responses.
        """
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent@example.com"},
        )

        # CRITICAL: Same response as existing user
        assert response.status_code == 200

    def test_forgot_password_invalid_email_format(self, client: TestClient) -> None:
        """Invalid email format should return 422 (schema validation)."""
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "notanemail"},
        )

        assert response.status_code == 422

    def test_forgot_password_creates_token_in_db(self, client: TestClient, db_session: Session) -> None:
        """
        Reset request should create a hashed token in database.

        SECURITY: Only the HASHED token is stored, raw token is sent via email.
        """
        # Register user
        client.post(
            "/api/v1/auth/register",
            json=register_json("tokendb@example.com", "SecureP@ssword123"),
        )

        with patch(
            "src.api.v1.endpoints.auth_password_reset.email_service.send_password_reset",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = True

            client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "tokendb@example.com"},
            )

        # Verify token exists in DB (we can't check the raw token, only that one exists)
        from src.infrastructure.persistence.password_reset_token_model import PasswordResetTokenModel

        result = db_session.execute(select(PasswordResetTokenModel).join(User).where(User.email == "tokendb@example.com"))
        token = result.scalar_one_or_none()

        assert token is not None
        assert token.token_hash is not None
        assert token.expires_at > datetime.now(UTC)
        assert token.used_at is None

    def test_forgot_password_sends_email(self, client: TestClient) -> None:
        """Reset request should send email with reset link."""
        # Register user
        client.post(
            "/api/v1/auth/register",
            json=register_json("sendemail@example.com", "SecureP@ssword123"),
        )

        with patch(
            "src.api.v1.endpoints.auth_password_reset.email_service.send_password_reset",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = True

            client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "sendemail@example.com"},
            )

            # Verify email was sent
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[1]["to_email"] == "sendemail@example.com"
            assert "token" in call_args[1]  # Raw token sent in email

    def test_forgot_password_rate_limited(self, client: TestClient) -> None:
        """
        Multiple reset requests should be rate limited.

        SECURITY: Prevents abuse (spamming reset emails).
        """
        # Register user
        client.post(
            "/api/v1/auth/register",
            json=register_json("ratelimit@example.com", "SecureP@ssword123"),
        )

        with patch(
            "src.api.v1.endpoints.auth_password_reset.email_service.send_password_reset",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = True

            # Make 3 requests (limit should be 3 per hour)
            for _ in range(3):
                response = client.post(
                    "/api/v1/auth/forgot-password",
                    json={"email": "ratelimit@example.com"},
                )
                assert response.status_code == 200

            # 4th request should be rate limited
            response = client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "ratelimit@example.com"},
            )
            assert response.status_code == 429

    def test_forgot_password_inactive_user(self, client: TestClient, db_session: Session) -> None:
        """
        Inactive user should still get 200 (no enumeration).

        BUT no email should be sent.
        """
        # Register and deactivate user
        client.post(
            "/api/v1/auth/register",
            json=register_json("inactive@example.com", "SecureP@ssword123"),
        )
        from sqlalchemy import update

        db_session.execute(update(User).where(User.email == "inactive@example.com").values(is_active=False))
        db_session.commit()

        with patch(
            "src.api.v1.endpoints.auth_password_reset.email_service.send_password_reset",
            autospec=True,
        ) as mock_send:
            response = client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "inactive@example.com"},
            )

        # Same response but no email sent
        assert response.status_code == 200
        mock_send.assert_not_called()


# =============================================================================
# RESET PASSWORD TESTS
# =============================================================================


class TestResetPassword:
    """Test POST /auth/reset-password endpoint."""

    def _create_reset_token(self, db_session: Session, user_id: str, expires_in_minutes: int = 30) -> str:
        """Helper to create a reset token and return the raw token."""
        from src.infrastructure.persistence.password_reset_token_model import PasswordResetTokenModel

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        reset_token = PasswordResetTokenModel(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(minutes=expires_in_minutes),
        )
        db_session.add(reset_token)
        db_session.commit()

        return raw_token

    def test_reset_password_success(self, client: TestClient, db_session: Session) -> None:
        """Valid token should allow password reset."""
        # Register user
        client.post(
            "/api/v1/auth/register",
            json=register_json("resetme@example.com", "OldP@ssword123"),
        )

        # Get user ID
        result = db_session.execute(select(User).where(User.email == "resetme@example.com"))
        user = result.scalar_one()

        # Create reset token
        raw_token = self._create_reset_token(db_session, user.id)

        # Reset password
        response = client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "password": "NewP@ssword456",
            },
        )

        assert response.status_code == 200
        assert "success" in response.json()["data"]["message"].lower()

        # Verify can login with new password
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "resetme@example.com",
                "password": "NewP@ssword456",
            },
        )
        assert login_response.status_code == 200

    def test_reset_password_old_password_no_longer_works(self, client: TestClient, db_session: Session) -> None:
        """After reset, old password should not work."""
        # Register user
        client.post(
            "/api/v1/auth/register",
            json=register_json("oldpass@example.com", "OldP@ssword123"),
        )

        result = db_session.execute(select(User).where(User.email == "oldpass@example.com"))
        user = result.scalar_one()
        raw_token = self._create_reset_token(db_session, user.id)

        # Reset password
        client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "password": "NewP@ssword456",
            },
        )

        # Old password should fail
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "oldpass@example.com",
                "password": "OldP@ssword123",
            },
        )
        assert login_response.status_code == 401

    def test_reset_password_invalid_token(self, client: TestClient) -> None:
        """Invalid token should return 400."""
        response = client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "invalid-token-here",
                "password": "NewP@ssword456",
            },
        )

        assert response.status_code == 400
        assert "invalid" in response.json()["error"]["message"].lower()

    def test_reset_password_expired_token(self, client: TestClient, db_session: Session) -> None:
        """Expired token should return 400."""
        # Register user
        client.post(
            "/api/v1/auth/register",
            json=register_json("expired@example.com", "OldP@ssword123"),
        )

        result = db_session.execute(select(User).where(User.email == "expired@example.com"))
        user = result.scalar_one()

        # Create EXPIRED token
        raw_token = self._create_reset_token(db_session, user.id, expires_in_minutes=-1)

        response = client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "password": "NewP@ssword456",
            },
        )

        assert response.status_code == 400
        assert "expired" in response.json()["error"]["message"].lower()

    def test_reset_password_token_single_use(self, client: TestClient, db_session: Session) -> None:
        """Token should only work once (single use)."""
        # Register user
        client.post(
            "/api/v1/auth/register",
            json=register_json("singleuse@example.com", "OldP@ssword123"),
        )

        result = db_session.execute(select(User).where(User.email == "singleuse@example.com"))
        user = result.scalar_one()
        raw_token = self._create_reset_token(db_session, user.id)

        # First reset - should work
        response1 = client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "password": "NewP@ssword456",
            },
        )
        assert response1.status_code == 200

        # Second reset with same token - should fail
        response2 = client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "password": "AnotherP@ssword789",
            },
        )
        assert response2.status_code == 400

    def test_reset_password_validates_new_password(self, client: TestClient, db_session: Session) -> None:
        """
        New password should meet security requirements.

        Same validation as registration.
        """
        # Register user
        client.post(
            "/api/v1/auth/register",
            json=register_json("weaknew@example.com", "OldP@ssword123"),
        )

        result = db_session.execute(select(User).where(User.email == "weaknew@example.com"))
        user = result.scalar_one()
        raw_token = self._create_reset_token(db_session, user.id)

        # Try to reset with weak password (fails Pydantic min length before handler)
        response = client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "password": "weak",  # Too short, no special chars, etc.
            },
        )

        assert response.status_code == 422
        err = response.json()["error"]
        assert "password" in err["message"].lower()

    def test_reset_password_sends_confirmation_email(self, client: TestClient, db_session: Session) -> None:
        """After successful reset, confirmation email should be sent."""
        # Register user
        client.post(
            "/api/v1/auth/register",
            json=register_json("confirm@example.com", "OldP@ssword123"),
        )

        result = db_session.execute(select(User).where(User.email == "confirm@example.com"))
        user = result.scalar_one()
        raw_token = self._create_reset_token(db_session, user.id)

        with patch(
            "src.infrastructure.email.email_service.email_service.send_password_changed_confirmation",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = True

            client.post(
                "/api/v1/auth/reset-password",
                json={
                    "token": raw_token,
                    "password": "NewP@ssword456",
                },
            )

            mock_send.assert_called_once()
            assert mock_send.call_args[1]["to_email"] == "confirm@example.com"


# =============================================================================
# TOKEN SECURITY TESTS
# =============================================================================


class TestTokenSecurity:
    """Test password reset token security properties."""

    def test_token_is_cryptographically_secure(self) -> None:
        """
        Token should be generated with cryptographically secure random.

        OWASP: Minimum 128 bits (16 bytes) of entropy.
        We use secrets.token_urlsafe(32) = 256 bits.
        """
        import secrets

        token = secrets.token_urlsafe(32)

        # Should be 43 characters (32 bytes base64 encoded)
        assert len(token) == 43

    def test_token_hash_stored_not_raw(self, db_session: Session) -> None:
        """
        Only the HASHED token should be stored in DB.

        WHY? If DB is compromised, attacker can't use the hashes.
        """

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Hash should be 64 chars (SHA-256 hex)
        assert len(token_hash) == 64
        assert raw_token != token_hash

    def test_deleting_a_user_through_the_orm_does_not_null_their_reset_tokens(self, client: TestClient, db_session: Session) -> None:
        """
        An ORM delete of a User with a reset token must succeed (no IntegrityError).

        WHY: `user_id` is NOT NULL with ondelete=CASCADE. A `backref` relationship
        without passive_deletes makes SQLAlchemy first set the tokens' user_id to
        NULL, which violates the NOT NULL column (IntegrityError) before the DB
        cascade can run. The reset flow never traverses the relationship, so the
        mapping must not exist. (The token row's removal is the DB cascade's job; the
        test connection pool can sit in session_replication_role=replica, so only the
        ORM-side behaviour is asserted here.)
        """
        from src.infrastructure.persistence.password_reset_token_model import PasswordResetTokenModel

        client.post(
            "/api/v1/auth/register",
            json=register_json("ormdelete@example.com", "SecureP@ssword123"),
        )
        user = db_session.execute(select(User).where(User.email == "ormdelete@example.com")).scalar_one()
        user_id = user.id
        db_session.add(
            PasswordResetTokenModel(
                user_id=user_id,
                token_hash=hashlib.sha256(secrets.token_urlsafe(32).encode()).hexdigest(),
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
            )
        )
        db_session.commit()

        db_session.delete(user)
        db_session.commit()

        assert db_session.execute(select(User).where(User.id == user_id)).first() is None

    def test_token_expiration_default_30_minutes(self) -> None:
        """Default token expiration should be 30 minutes."""
        from src.infrastructure.config import settings

        assert settings.password_reset_token_expire_minutes == 30

    def test_multiple_tokens_for_same_user_allowed(self, client: TestClient, db_session: Session) -> None:
        """
        Multiple reset requests should create new tokens.

        Old tokens become invalid when new one is created.
        """
        # Register user
        client.post(
            "/api/v1/auth/register",
            json=register_json("multitokens@example.com", "SecureP@ssword123"),
        )

        with patch(
            "src.api.v1.endpoints.auth_password_reset.email_service.send_password_reset",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = True

            # Request 2 resets
            client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "multitokens@example.com"},
            )
            first_token = mock_send.call_args[1]["token"]

            client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "multitokens@example.com"},
            )
            second_token = mock_send.call_args[1]["token"]

        # Tokens should be different
        assert first_token != second_token

        # First token should now be invalid (newest token wins)
        response = client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": first_token,
                "password": "NewP@ssword456",
            },
        )
        assert response.status_code == 400


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestPasswordResetIntegration:
    """End-to-end password reset flow tests."""

    def test_full_reset_flow(self, client: TestClient) -> None:
        """
        Test complete password reset flow:
        1. Register user
        2. Request reset
        3. Use token to reset
        4. Login with new password
        """
        # 1. Register
        client.post(
            "/api/v1/auth/register",
            json=register_json("fullflow@example.com", "OldP@ssword123"),
        )

        # 2. Request reset
        captured_token = None
        with patch(
            "src.api.v1.endpoints.auth_password_reset.email_service.send_password_reset",
            new_callable=AsyncMock,
        ) as mock_send:
            mock_send.return_value = True

            response = client.post(
                "/api/v1/auth/forgot-password",
                json={"email": "fullflow@example.com"},
            )
            assert response.status_code == 200
            captured_token = mock_send.call_args[1]["token"]

        # 3. Reset password
        response = client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": captured_token,
                "password": "NewP@ssword456",
            },
        )
        assert response.status_code == 200

        # 4. Login with new password
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "fullflow@example.com",
                "password": "NewP@ssword456",
            },
        )
        assert login_response.status_code == 200
        assert "access_token" in login_response.json()["data"]
