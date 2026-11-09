"""
Authentication Register Endpoint - GDPR Consent Tests (TDD First)

PRO tests covering GDPR-compliant consent handling:
- Both mandatory consents (terms + data processing) required and must be true
- Optional marketing consent (can be true, false, or omitted)
- Persistence: All consent fields stored in database + timestamps auto-set
- Validation: Reject if terms_consent or data_processing_consent are missing or false
- Audit trail: Verify timestamps recorded correctly

Following TDD: These tests are written FIRST before implementation.
Using sync TestClient (FastAPI handles async internally).

CONSENT CONTRACT: See docs/02-technical/CONSENT_CONTRACT.md
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.infrastructure.persistence.user_model import User

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session


class TestRegisterConsentValidation:
    """Test request validation for consent fields in POST /auth/register."""

    def test_register_with_both_mandatory_consents_required(self, client: TestClient) -> None:
        """
        Both mandatory consents (terms + data_processing) MUST be true.
        Marketing consent is optional.
        Scenario: Register with both mandatory=true + optional marketing
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "consent_both@example.com",
                "password": "SecureP@ssword123",
                "name": "Consent User",
                "terms_consent": True,
                "data_processing_consent": True,
                "marketing_consent": True,
            },
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["email"] == "consent_both@example.com"

    def test_register_without_marketing_consent_field(self, client: TestClient) -> None:
        """
        Marketing consent is optional: can omit the field entirely.
        Scenario: Register with mandatory consents only (no marketing field)
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "consent_no_marketing@example.com",
                "password": "SecureP@ssword123",
                "name": "No Marketing User",
                "terms_consent": True,
                "data_processing_consent": True,
            },
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["email"] == "consent_no_marketing@example.com"

    def test_register_marketing_consent_false_is_valid(self, client: TestClient) -> None:
        """
        Marketing consent = false (explicit opt-out) is valid and persisted.
        Scenario: User explicitly declines marketing communications
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "consent_no_marketing_opt@example.com",
                "password": "SecureP@ssword123",
                "name": "Opt Out User",
                "terms_consent": True,
                "data_processing_consent": True,
                "marketing_consent": False,
            },
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["email"] == "consent_no_marketing_opt@example.com"

    def test_register_missing_terms_consent_field(self, client: TestClient) -> None:
        """
        Missing terms_consent field must be rejected (400 BAD_REQUEST).
        Scenario: User submits registration without terms_consent field
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "missing_terms@example.com",
                "password": "SecureP@ssword123",
                "data_processing_consent": True,
            },
        )

        # Either 400 (FastAPI validation) or 422 (Pydantic validation)
        assert response.status_code in (400, 422)

    def test_register_terms_consent_false_rejected(self, client: TestClient) -> None:
        """
        terms_consent=false (or not True) must be rejected.
        FastAPI/Pydantic returns 422 for field validator failures (not 400).
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "terms_false@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": False,
                "data_processing_consent": True,
            },
        )

        assert response.status_code == 422
        err = response.json()["error"]
        assert "terms_consent" in err["message"].lower()

    def test_register_terms_consent_null_rejected(self, client: TestClient) -> None:
        """
        terms_consent=null/None must be rejected (400 BAD_REQUEST).
        Scenario: Malformed JSON or user agent sends null
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "terms_null@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": None,
                "data_processing_consent": True,
            },
        )

        # Either 400 (FastAPI custom) or 422 (Pydantic validation)
        assert response.status_code in (400, 422)

    def test_register_missing_data_processing_consent_field(self, client: TestClient) -> None:
        """
        Missing data_processing_consent field must be rejected (400 BAD_REQUEST).
        Scenario: User submits registration without data_processing_consent field
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "missing_processing@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": True,
            },
        )

        # Either 400 (FastAPI validation) or 422 (Pydantic validation)
        assert response.status_code in (400, 422)

    def test_register_data_processing_consent_false_rejected(self, client: TestClient) -> None:
        """
        data_processing_consent=false (or not True) must be rejected.
        FastAPI/Pydantic returns 422 for field validator failures.
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "processing_false@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": True,
                "data_processing_consent": False,
            },
        )

        assert response.status_code == 422
        err = response.json()["error"]
        assert "data_processing_consent" in err["message"].lower()

    def test_register_data_processing_consent_null_rejected(self, client: TestClient) -> None:
        """
        data_processing_consent=null/None must be rejected (400 BAD_REQUEST).
        Scenario: Malformed JSON or user agent sends null
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "processing_null@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": True,
                "data_processing_consent": None,
            },
        )

        # Either 400 (FastAPI custom) or 422 (Pydantic validation)
        assert response.status_code in (400, 422)

    def test_register_invalid_marketing_consent_type(self, client: TestClient) -> None:
        """
        marketing_consent must be boolean if provided (not string, int, etc.).
        Note: Pydantic coerces "yes"/"no" to bool; use a string that does not coerce.
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "marketing_string@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": True,
                "data_processing_consent": True,
                "marketing_consent": "not-a-bool",
            },
        )

        assert response.status_code == 422


class TestRegisterConsentPersistence:
    """Test that consent fields are correctly persisted to database."""

    def test_register_persists_all_consent_fields_when_valid(self, client: TestClient, db_session: Session) -> None:
        """
        All consent fields (both mandatory + optional) must be persisted to user record.
        Scenario: Register with all three consents, verify they're in database
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "persist_all@example.com",
                "password": "SecureP@ssword123",
                "name": "Persist All",
                "terms_consent": True,
                "data_processing_consent": True,
                "marketing_consent": True,
            },
        )

        assert response.status_code == 201

        # Verify in database
        user = db_session.query(User).filter_by(email="persist_all@example.com").first()
        assert user is not None
        assert user.terms_consent is True
        assert user.data_processing_consent is True
        assert user.marketing_consent is True

    def test_register_persists_mandatory_consents_without_marketing(self, client: TestClient, db_session: Session) -> None:
        """
        When marketing_consent is omitted, it should be stored as NULL in database.
        Scenario: Register with mandatory consents only, verify marketing=NULL
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "persist_mandatory@example.com",
                "password": "SecureP@ssword123",
                "name": "Mandatory Only",
                "terms_consent": True,
                "data_processing_consent": True,
            },
        )

        assert response.status_code == 201

        # Verify in database
        user = db_session.query(User).filter_by(email="persist_mandatory@example.com").first()
        assert user is not None
        assert user.terms_consent is True
        assert user.data_processing_consent is True
        assert user.marketing_consent is None  # NULL when omitted

    def test_register_persists_explicit_marketing_opt_out(self, client: TestClient, db_session: Session) -> None:
        """
        When marketing_consent=false, it should be stored as false (not NULL).
        Scenario: Register with explicit opt-out, verify marketing=false
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "persist_opt_out@example.com",
                "password": "SecureP@ssword123",
                "name": "Opt Out",
                "terms_consent": True,
                "data_processing_consent": True,
                "marketing_consent": False,
            },
        )

        assert response.status_code == 201

        # Verify in database
        user = db_session.query(User).filter_by(email="persist_opt_out@example.com").first()
        assert user is not None
        assert user.marketing_consent is False


class TestRegisterConsentTimestamps:
    """Test that consent audit trail timestamps are auto-set correctly."""

    def test_register_sets_terms_consent_timestamp(self, client: TestClient, db_session: Session) -> None:
        """
        terms_consent_at timestamp must be auto-set on user creation (NOW()).
        Scenario: Register, verify terms_consent_at is set to current time
        """
        before = datetime.now(UTC)

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "ts_terms@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": True,
                "data_processing_consent": True,
            },
        )

        after = datetime.now(UTC)
        assert response.status_code == 201

        # Verify timestamp in database
        user = db_session.query(User).filter_by(email="ts_terms@example.com").first()
        assert user is not None
        assert user.terms_consent_at is not None
        # Allow 1 second clock skew
        assert before <= user.terms_consent_at <= after

    def test_register_sets_data_processing_consent_timestamp(self, client: TestClient, db_session: Session) -> None:
        """
        data_processing_consent_at timestamp must be auto-set on user creation (NOW()).
        Scenario: Register, verify data_processing_consent_at is set to current time
        """
        before = datetime.now(UTC)

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "ts_processing@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": True,
                "data_processing_consent": True,
            },
        )

        after = datetime.now(UTC)
        assert response.status_code == 201

        # Verify timestamp in database
        user = db_session.query(User).filter_by(email="ts_processing@example.com").first()
        assert user is not None
        assert user.data_processing_consent_at is not None
        # Allow 1 second clock skew
        assert before <= user.data_processing_consent_at <= after

    def test_register_sets_marketing_consent_timestamp_when_true(self, client: TestClient, db_session: Session) -> None:
        """
        marketing_consent_at timestamp must be auto-set when marketing_consent=true.
        Scenario: Register with marketing_consent=true, verify timestamp is set
        """
        before = datetime.now(UTC)

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "ts_marketing_optin@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": True,
                "data_processing_consent": True,
                "marketing_consent": True,
            },
        )

        after = datetime.now(UTC)
        assert response.status_code == 201

        # Verify timestamp in database
        user = db_session.query(User).filter_by(email="ts_marketing_optin@example.com").first()
        assert user is not None
        assert user.marketing_consent_at is not None
        # Allow 1 second clock skew
        assert before <= user.marketing_consent_at <= after

    def test_register_sets_marketing_consent_timestamp_when_false(self, client: TestClient, db_session: Session) -> None:
        """
        marketing_consent_at timestamp must be auto-set when marketing_consent=false.
        Scenario: Register with marketing_consent=false, verify timestamp is set
        """
        before = datetime.now(UTC)

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "ts_marketing_optout@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": True,
                "data_processing_consent": True,
                "marketing_consent": False,
            },
        )

        after = datetime.now(UTC)
        assert response.status_code == 201

        # Verify timestamp in database
        user = db_session.query(User).filter_by(email="ts_marketing_optout@example.com").first()
        assert user is not None
        assert user.marketing_consent_at is not None
        # Allow 1 second clock skew
        assert before <= user.marketing_consent_at <= after

    def test_register_no_marketing_consent_timestamp_when_omitted(self, client: TestClient, db_session: Session) -> None:
        """
        marketing_consent_at timestamp must be NULL when marketing_consent field is omitted.
        Scenario: Register without marketing field, verify marketing_consent_at=NULL
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "ts_marketing_omitted@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": True,
                "data_processing_consent": True,
            },
        )

        assert response.status_code == 201

        # Verify timestamp in database
        user = db_session.query(User).filter_by(email="ts_marketing_omitted@example.com").first()
        assert user is not None
        assert user.marketing_consent_at is None


class TestRegisterConsentResponsePayload:
    """Test that consent fields are returned in 201 CREATED response."""

    def test_register_response_includes_consent_fields(self, client: TestClient) -> None:
        """
        Response (201) must include all consent fields in user object.
        Scenario: Register with all consents, verify they're in response body
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "response_all@example.com",
                "password": "SecureP@ssword123",
                "name": "Response Test",
                "terms_consent": True,
                "data_processing_consent": True,
                "marketing_consent": True,
            },
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["terms_consent"] is True
        assert data["data_processing_consent"] is True
        assert data["marketing_consent"] is True

    def test_register_response_includes_consent_timestamps(self, client: TestClient) -> None:
        """
        Response (201) must include all consent timestamp fields in user object.
        Scenario: Register, verify timestamps are in response
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "response_ts@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": True,
                "data_processing_consent": True,
                "marketing_consent": True,
            },
        )

        assert response.status_code == 201
        data = response.json()["data"]
        assert "terms_consent_at" in data
        assert "data_processing_consent_at" in data
        assert "marketing_consent_at" in data
        assert data["terms_consent_at"] is not None
        assert data["data_processing_consent_at"] is not None
        assert data["marketing_consent_at"] is not None


class TestRegisterConsentEdgeCases:
    """Test edge cases and boundary conditions for consent handling."""

    def test_register_both_consents_required_cannot_skip_either(self, client: TestClient) -> None:
        """
        Both mandatory consents are independently required.
        Scenario: Submit with terms but missing data_processing (should fail)
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "edge_one@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": True,
                # Missing: data_processing_consent
            },
        )

        # Should fail validation
        assert response.status_code in (400, 422)

    def test_register_multiple_consent_violations_detected(self, client: TestClient) -> None:
        """
        When multiple consent fields are missing/invalid, error is clear.
        Scenario: Submit with both consents false
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "edge_both_false@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": False,
                "data_processing_consent": False,
            },
        )

        # Should fail validation (422 from Pydantic validators)
        assert response.status_code == 422

    def test_register_marketing_consent_separate_from_validation(self, client: TestClient) -> None:
        """
        Marketing consent failure should not affect mandatory consent validation.
        Scenario: Valid mandatory consents + invalid marketing type (should fail on marketing only)
        """
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "edge_marketing@example.com",
                "password": "SecureP@ssword123",
                "terms_consent": True,
                "data_processing_consent": True,
                "marketing_consent": 123,  # Invalid: not boolean
            },
        )

        # Should fail on marketing validation (422 from Pydantic type error)
        assert response.status_code == 422
