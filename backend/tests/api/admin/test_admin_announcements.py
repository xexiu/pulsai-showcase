"""Admin announcement broadcast routes: preview + send + super_admin safety."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.infrastructure.persistence.newsletter_subscriber_model import NewsletterSubscriberModel
from src.infrastructure.persistence.user_model import User
from src.shared.utils.datetime_utils import utc_now

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

#: The limiter is a fixed window per UTC minute: two requests straddling a minute boundary land in two buckets and the
#: second is never limited (driven: 12:00:59.9 -> 12:01:00.1 answers 200, 200). Each 429 test pins the limiter's clock
#: mid-minute so its requests always share one bucket.
_LIMITER_CLOCK = "src.infrastructure.rate_limiting.public_rate_limit.utc_now"
_MID_MINUTE = datetime(2026, 10, 11, 12, 0, 30, tzinfo=UTC)


@pytest.fixture
def admin_headers(client: TestClient, db_session) -> dict[str, str]:
    """Create an admin user and return auth headers."""
    from sqlalchemy import update

    client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin-announcements@pulsai.com",
            "password": "AdminSecure123!",
            "name": "Admin User",
            "terms_consent": True,
            "data_processing_consent": True,
        },
    )

    stmt = update(User).where(User.email == "admin-announcements@pulsai.com").values(role="admin")
    db_session.execute(stmt)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin-announcements@pulsai.com", "password": "AdminSecure123!"},
    )
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def super_admin_headers(client: TestClient, db_session) -> dict[str, str]:
    """Create a super_admin user and return auth headers."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "superadmin-announcements@pulsai.com",
            "password": "SuperSecure123!",
            "name": "Super Admin",
            "terms_consent": True,
            "data_processing_consent": True,
        },
    )

    user = db_session.query(User).filter(User.email == "superadmin-announcements@pulsai.com").first()
    assert user is not None
    user.role = "super_admin"
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "superadmin-announcements@pulsai.com",
            "password": "SuperSecure123!",
        },
    )
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def second_super_admin_headers(client: TestClient, db_session) -> dict[str, str]:
    """Create a second super_admin user and return auth headers."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "superadmin-announcements-2@pulsai.com",
            "password": "SuperSecure123!",
            "name": "Super Admin Two",
            "terms_consent": True,
            "data_processing_consent": True,
        },
    )

    user = db_session.query(User).filter(User.email == "superadmin-announcements-2@pulsai.com").first()
    assert user is not None
    user.role = "super_admin"
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "superadmin-announcements-2@pulsai.com",
            "password": "SuperSecure123!",
        },
    )
    token = response.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestAdminAnnouncementPreview:
    def test_preview_requires_super_admin(
        self,
        client: TestClient,
        admin_headers: dict[str, str],
    ) -> None:
        response = client.post(
            "/api/v1/admin/announcements/preview",
            json={
                "kind": "service",
                "subject": "Maintenance",
                "body": "Maintenance window tonight.",
            },
            headers=admin_headers,
        )

        assert response.status_code == 403

    def test_preview_returns_sanitized_html_and_recipient_count(
        self,
        client: TestClient,
        db_session,
        super_admin_headers: dict[str, str],
    ) -> None:
        db_session.add_all(
            [
                User(
                    id=str(uuid4()),
                    email="active-user@pulsai.dev",
                    password_hash="h",
                    is_active=True,
                ),
                User(
                    id=str(uuid4()),
                    email="inactive-user@pulsai.dev",
                    password_hash="h",
                    is_active=False,
                ),
                User(
                    id=str(uuid4()),
                    email=f"deleted.{uuid4()}@invalid.pulsai.local",
                    password_hash=None,
                    is_active=False,
                ),
            ]
        )
        db_session.commit()

        response = client.post(
            "/api/v1/admin/announcements/preview",
            json={
                "kind": "service",
                "subject": "Maintenance",
                "body": "Line 1\n\n<script>alert(1)</script>",
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["subject"] == "Maintenance"
        assert data["approximate_recipient_count"] == 2
        assert "<!DOCTYPE html>" in data["html"]
        assert "Line 1" in data["html"]
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in data["html"]
        assert "<script>alert(1)</script>" not in data["html"]

    def test_preview_marketing_kind_uses_marketing_audience_rules(
        self,
        client: TestClient,
        db_session,
        super_admin_headers: dict[str, str],
    ) -> None:
        db_session.add_all(
            [
                User(
                    id=str(uuid4()),
                    email="marketing-on@pulsai.dev",
                    password_hash="h",
                    marketing_consent=True,
                    is_active=True,
                ),
                User(
                    id=str(uuid4()),
                    email="marketing-off@pulsai.dev",
                    password_hash="h",
                    marketing_consent=False,
                    is_active=True,
                ),
                NewsletterSubscriberModel(
                    id=str(uuid4()),
                    email="blocked@pulsai.dev",
                    source="landing",
                    is_lead=False,
                    unsubscribed_at=utc_now(),
                ),
                User(
                    id=str(uuid4()),
                    email="blocked@pulsai.dev",
                    password_hash="h",
                    marketing_consent=True,
                    is_active=True,
                ),
            ]
        )
        db_session.commit()

        response = client.post(
            "/api/v1/admin/announcements/preview",
            json={
                "kind": "marketing",
                "subject": "New feature",
                "body": "Hello marketing users",
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 200, response.text
        assert response.json()["approximate_recipient_count"] == 1

    def test_preview_writes_expected_audit_payload(
        self,
        client: TestClient,
        db_session,
        super_admin_headers: dict[str, str],
    ) -> None:
        db_session.add(
            User(
                id=str(uuid4()),
                email="audit-preview@pulsai.dev",
                password_hash="h",
                is_active=True,
            )
        )
        db_session.commit()

        with patch(
            "src.application.services.audit_service.AuditService.log_admin_action",
            new_callable=AsyncMock,
        ) as mock_audit:
            response = client.post(
                "/api/v1/admin/announcements/preview",
                json={
                    "kind": "service",
                    "subject": "Maintenance",
                    "body": "Preview this announcement",
                },
                headers=super_admin_headers,
            )

        assert response.status_code == 200, response.text
        mock_audit.assert_awaited_once()
        assert mock_audit.await_args.kwargs["action_name"] == "preview_announcement"
        details = mock_audit.await_args.kwargs["details"]
        assert details["campaign_kind"] == "service"
        assert details["subject"] == "Maintenance"
        assert details["approximate_recipient_count"] == 2

    def test_preview_returns_429_when_read_rate_limit_exceeded(
        self,
        client: TestClient,
        super_admin_headers: dict[str, str],
    ) -> None:
        with (
            patch("src.api.rate_limit_dependencies_app.settings.admin_announcement_read_rate_limit_per_minute", 1),
            patch(_LIMITER_CLOCK, return_value=_MID_MINUTE),
        ):
            first = client.post(
                "/api/v1/admin/announcements/preview",
                json={
                    "kind": "service",
                    "subject": "Maintenance",
                    "body": "Rate limit test",
                },
                headers=super_admin_headers,
            )
            second = client.post(
                "/api/v1/admin/announcements/preview",
                json={
                    "kind": "service",
                    "subject": "Maintenance",
                    "body": "Rate limit test",
                },
                headers=super_admin_headers,
            )

        assert first.status_code == 200, first.text
        assert second.status_code == 429, second.text
        assert "Retry-After" in second.headers
        assert int(second.headers["Retry-After"]) >= 1


class TestAdminWelcomeEmailPreview:
    def test_welcome_preview_requires_super_admin(
        self,
        client: TestClient,
        admin_headers: dict[str, str],
    ) -> None:
        response = client.post(
            "/api/v1/admin/email-previews/welcome",
            json={
                "locale": "es",
                "user_name": "Lucia",
            },
            headers=admin_headers,
        )

        assert response.status_code == 403

    def test_welcome_preview_returns_localized_html(
        self,
        client: TestClient,
        super_admin_headers: dict[str, str],
    ) -> None:
        response = client.post(
            "/api/v1/admin/email-previews/welcome",
            json={
                "locale": "es",
                "user_name": "Lucia",
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["subject"] == "Bienvenido a PulsAI"
        assert "<!DOCTYPE html>" in data["html"]
        assert "Hola Lucia," in data["html"]
        assert "Abrir dashboard" in data["html"]

    def test_welcome_preview_writes_expected_audit_payload(
        self,
        client: TestClient,
        super_admin_headers: dict[str, str],
    ) -> None:
        with patch(
            "src.application.services.audit_service.AuditService.log_admin_action",
            new_callable=AsyncMock,
        ) as mock_audit:
            response = client.post(
                "/api/v1/admin/email-previews/welcome",
                json={
                    "locale": "en",
                    "user_name": "Alex",
                },
                headers=super_admin_headers,
            )

        assert response.status_code == 200, response.text
        mock_audit.assert_awaited_once()
        assert mock_audit.await_args.kwargs["action_name"] == "preview_welcome_email"
        details = mock_audit.await_args.kwargs["details"]
        assert details["locale"] == "en"
        assert details["user_name"] == "Alex"
        assert details["subject"] == "Welcome to PulsAI"

    def test_welcome_preview_returns_429_when_read_rate_limit_exceeded(
        self,
        client: TestClient,
        super_admin_headers: dict[str, str],
    ) -> None:
        with (
            patch("src.api.rate_limit_dependencies_app.settings.admin_announcement_read_rate_limit_per_minute", 1),
            patch(_LIMITER_CLOCK, return_value=_MID_MINUTE),
        ):
            first = client.post(
                "/api/v1/admin/email-previews/welcome",
                json={
                    "locale": "en",
                    "user_name": "Rate Limit",
                },
                headers=super_admin_headers,
            )
            second = client.post(
                "/api/v1/admin/email-previews/welcome",
                json={
                    "locale": "en",
                    "user_name": "Rate Limit",
                },
                headers=super_admin_headers,
            )

        assert first.status_code == 200, first.text
        assert second.status_code == 429, second.text
        assert "Retry-After" in second.headers
        assert int(second.headers["Retry-After"]) >= 1


class TestAdminAnnouncementSend:
    def test_send_requires_explicit_campaign_id(
        self,
        client: TestClient,
        super_admin_headers: dict[str, str],
    ) -> None:
        response = client.post(
            "/api/v1/admin/announcements/send",
            json={
                "kind": "service",
                "subject": "Maintenance",
                "body": "Scheduled downtime.",
            },
            headers=super_admin_headers,
        )

        assert response.status_code == 422

    def test_send_enqueues_task_and_returns_campaign_metadata(
        self,
        client: TestClient,
        db_session,
        super_admin_headers: dict[str, str],
    ) -> None:
        user = User(
            id=str(uuid4()),
            email="service-user@pulsai.dev",
            password_hash="h",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()

        campaign_id = str(uuid4())
        celery_result = SimpleNamespace(id="celery-task-123")
        with patch(
            "src.api.admin.announcements_routes._enqueue_admin_announcement",
            return_value=celery_result.id,
        ) as enqueue_mock:
            response = client.post(
                "/api/v1/admin/announcements/send",
                json={
                    "campaign_id": campaign_id,
                    "kind": "service",
                    "subject": "Maintenance",
                    "body": "Scheduled downtime.",
                },
                headers=super_admin_headers,
            )

        assert response.status_code == 202, response.text
        data = response.json()
        assert data["campaign_id"] == campaign_id
        assert data["job_id"] == "celery-task-123"
        assert data["approximate_recipient_count"] == 2
        enqueue_mock.assert_called_once()

    def test_send_is_idempotent_per_campaign_id_for_same_admin(
        self,
        client: TestClient,
        db_session,
        super_admin_headers: dict[str, str],
    ) -> None:
        db_session.add(
            User(
                id=str(uuid4()),
                email="service-user@pulsai.dev",
                password_hash="h",
                is_active=True,
            )
        )
        db_session.commit()

        campaign_id = str(uuid4())
        celery_result = SimpleNamespace(id="celery-task-abc")
        with patch(
            "src.api.admin.announcements_routes._enqueue_admin_announcement",
            return_value=celery_result.id,
        ) as enqueue_mock:
            payload = {
                "campaign_id": campaign_id,
                "kind": "service",
                "subject": "Maintenance",
                "body": "Scheduled downtime.",
            }
            first = client.post(
                "/api/v1/admin/announcements/send",
                json=payload,
                headers=super_admin_headers,
            )
            second = client.post(
                "/api/v1/admin/announcements/send",
                json=payload,
                headers=super_admin_headers,
            )

        assert first.status_code == 202, first.text
        assert second.status_code == 202, second.text
        assert first.json() == second.json()
        assert second.headers.get("X-Idempotent-Replayed") == "true"
        enqueue_mock.assert_called_once()

    def test_send_replays_same_campaign_id_across_super_admins(
        self,
        client: TestClient,
        db_session,
        super_admin_headers: dict[str, str],
        second_super_admin_headers: dict[str, str],
    ) -> None:
        db_session.add(
            User(
                id=str(uuid4()),
                email="service-user@pulsai.dev",
                password_hash="h",
                is_active=True,
            )
        )
        db_session.commit()

        campaign_id = str(uuid4())
        celery_result = SimpleNamespace(id="celery-task-global")
        with patch(
            "src.api.admin.announcements_routes._enqueue_admin_announcement",
            return_value=celery_result.id,
        ) as enqueue_mock:
            payload = {
                "campaign_id": campaign_id,
                "kind": "service",
                "subject": "Maintenance",
                "body": "Scheduled downtime.",
            }
            first = client.post(
                "/api/v1/admin/announcements/send",
                json=payload,
                headers=super_admin_headers,
            )
            second = client.post(
                "/api/v1/admin/announcements/send",
                json=payload,
                headers=second_super_admin_headers,
            )

        assert first.status_code == 202, first.text
        assert second.status_code == 202, second.text
        assert first.json() == second.json()
        enqueue_mock.assert_called_once()

    def test_send_writes_expected_audit_payload_once(
        self,
        client: TestClient,
        db_session,
        super_admin_headers: dict[str, str],
    ) -> None:
        db_session.add(
            User(
                id=str(uuid4()),
                email="audit-send@pulsai.dev",
                password_hash="h",
                is_active=True,
            )
        )
        db_session.commit()

        campaign_id = str(uuid4())
        with (
            patch(
                "src.api.admin.announcements_routes._enqueue_admin_announcement",
                return_value="job-audit-123",
            ),
            patch(
                "src.application.services.audit_service.AuditService.log_admin_action",
                new_callable=AsyncMock,
            ) as mock_audit,
        ):
            first = client.post(
                "/api/v1/admin/announcements/send",
                json={
                    "campaign_id": campaign_id,
                    "kind": "service",
                    "subject": "Critical notice",
                    "body": "Send this announcement",
                },
                headers=super_admin_headers,
            )
            second = client.post(
                "/api/v1/admin/announcements/send",
                json={
                    "campaign_id": campaign_id,
                    "kind": "service",
                    "subject": "Critical notice",
                    "body": "Send this announcement",
                },
                headers=super_admin_headers,
            )

        assert first.status_code == 202, first.text
        assert second.status_code == 202, second.text
        mock_audit.assert_awaited_once()
        assert mock_audit.await_args.kwargs["action_name"] == "send_announcement"
        assert mock_audit.await_args.kwargs["resource_id"] == campaign_id
        details = mock_audit.await_args.kwargs["details"]
        assert details["campaign_id"] == campaign_id
        assert details["campaign_kind"] == "service"
        assert details["subject"] == "Critical notice"
        assert details["approximate_recipient_count"] == 2

    def test_send_returns_429_when_mutation_rate_limit_exceeded(
        self,
        client: TestClient,
        db_session,
        super_admin_headers: dict[str, str],
    ) -> None:
        db_session.add(
            User(
                id=str(uuid4()),
                email="rate-limit-send@pulsai.dev",
                password_hash="h",
                is_active=True,
            )
        )
        db_session.commit()

        with (
            patch(
                "src.api.rate_limit_dependencies_app.settings.admin_announcement_mutation_rate_limit_per_minute",
                1,
            ),
            patch(_LIMITER_CLOCK, return_value=_MID_MINUTE),
            patch(
                "src.api.admin.announcements_routes._enqueue_admin_announcement",
                return_value="job-rate-limit-123",
            ),
        ):
            first = client.post(
                "/api/v1/admin/announcements/send",
                json={
                    "campaign_id": str(uuid4()),
                    "kind": "service",
                    "subject": "Maintenance",
                    "body": "Rate limit send",
                },
                headers=super_admin_headers,
            )
            second = client.post(
                "/api/v1/admin/announcements/send",
                json={
                    "campaign_id": str(uuid4()),
                    "kind": "service",
                    "subject": "Maintenance 2",
                    "body": "Rate limit send",
                },
                headers=super_admin_headers,
            )

        assert first.status_code == 202, first.text
        assert second.status_code == 429, second.text
        assert "Retry-After" in second.headers
        assert int(second.headers["Retry-After"]) >= 1
