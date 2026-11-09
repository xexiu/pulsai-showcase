"""
Legal bundle versioning: GET /me flags, POST /accept, protected routes, admin bump.

Integration tests (PostgreSQL). Behavior-focused: pending consent blocks backtests API.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient  # noqa: TC002
from sqlalchemy import text
from sqlalchemy.orm import Session  # noqa: TC002

from src.infrastructure.persistence.user_model import User


@pytest.fixture
def super_admin_headers_legal(client: TestClient, db_session: Session) -> dict[str, str]:
    """Super admin JWT for legal admin endpoints (isolated email)."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "legal_super@example.com",
            "password": "SuperSecure123!",
            "name": "Legal Super",
            "terms_consent": True,
            "data_processing_consent": True,
        },
    )
    user = db_session.query(User).filter(User.email == "legal_super@example.com").first()
    assert user is not None
    user.role = "super_admin"
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "legal_super@example.com",
            "password": "SuperSecure123!",
        },
    )
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.integration
class TestLegalConsentMeAndAccept:
    def test_me_pending_after_policy_bump_and_accept_clears(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "legal_user_flow@example.com",
                "password": "SecurePassword123!",
                "name": "Legal User",
                "terms_consent": True,
                "data_processing_consent": True,
            },
        )
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "legal_user_flow@example.com",
                "password": "SecurePassword123!",
            },
        )
        token = login.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        me1 = client.get("/api/v1/auth/me", headers=headers)
        assert me1.status_code == 200
        body1 = me1.json()["data"]
        assert body1["pending_legal_consent"] is False

        db_session.execute(text("UPDATE legal_policy SET required_legal_bundle_version = 2 WHERE id = 1"))
        db_session.commit()

        me2 = client.get("/api/v1/auth/me", headers=headers)
        assert me2.status_code == 200
        assert me2.json()["data"]["pending_legal_consent"] is True

        accept = client.post(
            "/api/v1/auth/me/legal-accept",
            headers=headers,
            json={"terms_consent": True, "data_processing_consent": True},
        )
        assert accept.status_code == 200
        assert accept.json()["data"]["pending_legal_consent"] is False

    def test_backtests_list_forbidden_when_pending_consent(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "legal_bt@example.com",
                "password": "SecurePassword123!",
                "name": "BT User",
                "terms_consent": True,
                "data_processing_consent": True,
            },
        )
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "legal_bt@example.com",
                "password": "SecurePassword123!",
            },
        )
        token = login.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        db_session.execute(text("UPDATE legal_policy SET required_legal_bundle_version = 5 WHERE id = 1"))
        db_session.commit()

        bt = client.get("/api/v1/backtests", headers=headers)
        assert bt.status_code == 403
        err = bt.json()["error"]
        assert err["code"] == "LEGAL_CONSENT_REQUIRED"

    def test_backtests_list_accepts_per_page_100_with_valid_consent(
        self,
        client: TestClient,
    ) -> None:
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "legal_bt_100@example.com",
                "password": "SecurePassword123!",
                "name": "BT User 100",
                "terms_consent": True,
                "data_processing_consent": True,
            },
        )
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "legal_bt_100@example.com",
                "password": "SecurePassword123!",
            },
        )
        token = login.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        bt = client.get("/api/v1/backtests?page=1&per_page=100", headers=headers)
        assert bt.status_code == 200


@pytest.mark.integration
class TestAdminLegalEndpoints:
    def test_require_reaccept_increments_version(
        self,
        client: TestClient,
        db_session: Session,
        super_admin_headers_legal: dict[str, str],
    ) -> None:
        before = client.get("/api/v1/admin/legal/status", headers=super_admin_headers_legal)
        assert before.status_code == 200
        v0 = before.json()["required_legal_bundle_version"]

        bumped = client.post(
            "/api/v1/admin/legal/require-reaccept",
            headers=super_admin_headers_legal,
        )
        assert bumped.status_code == 200
        v1 = bumped.json()["required_legal_bundle_version"]
        assert v1 == v0 + 1

        after = client.get("/api/v1/admin/legal/status", headers=super_admin_headers_legal)
        assert after.json()["required_legal_bundle_version"] == v1
