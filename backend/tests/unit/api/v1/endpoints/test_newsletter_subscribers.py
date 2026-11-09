"""
Unit tests for Newsletter Subscribers endpoint.

BEHAVIOR (not implementation):
- POST with new email returns 201 and success message.
- POST with duplicate email returns 409 and body contains email for FE message.
- POST with invalid email returns 422.
- POST with blocked domain (example.com) returns 422.

@see src/api/v1/endpoints/newsletter_subscribers.py
"""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import status

from src.infrastructure.persistence.newsletter_subscriber_model import NewsletterSubscriberModel
from src.infrastructure.persistence.user_model import User
from src.infrastructure.security.newsletter_unsubscribe_token import (
    create_newsletter_unsubscribe_token,
)
from src.infrastructure.security.user_marketing_unsubscribe_token import (
    create_user_marketing_unsubscribe_token,
)

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestSubscribeNewsletter:
    """Behavior tests for POST /api/v1/newsletter_subscribers."""

    def test_subscribe_new_email_returns_201_and_message(self, client: TestClient) -> None:
        """
        Given a valid new email,
        When POST /api/v1/newsletter_subscribers is called,
        Then returns 201 and a success message.
        """
        response = client.post(
            "/api/v1/newsletter_subscribers",
            json={"email": "new@pulsai.dev", "source": "landing"},
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "message" in data
        assert len(data["message"]) > 0

    def test_subscribe_duplicate_email_returns_409_with_email_in_body(self, client: TestClient) -> None:
        """
        Given an email already subscribed,
        When POST /api/v1/newsletter_subscribers is called with same email,
        Then returns 409 and body contains error code NEWSLETTER_EMAIL_EXISTS and details.email
        so FE can show "The email X is on our system already. Please try another."
        """
        email = "duplicate@pulsai.dev"
        client.post(
            "/api/v1/newsletter_subscribers",
            json={"email": email, "source": "landing"},
        )
        response = client.post(
            "/api/v1/newsletter_subscribers",
            json={"email": email, "source": "landing"},
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "NEWSLETTER_EMAIL_EXISTS"
        assert data["error"].get("details", {}).get("email") == email

    def test_subscribe_duplicate_email_normalized_returns_409(self, client: TestClient) -> None:
        """
        Duplicate is detected by normalized email (lowercase).
        When same email is submitted with different casing, returns 409.
        """
        client.post(
            "/api/v1/newsletter_subscribers",
            json={"email": "User@Pulsai.Dev", "source": "landing"},
        )
        response = client.post(
            "/api/v1/newsletter_subscribers",
            json={"email": "user@pulsai.dev", "source": "landing"},
        )
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["error"]["code"] == "NEWSLETTER_EMAIL_EXISTS"

    def test_subscribe_invalid_email_returns_422(self, client: TestClient) -> None:
        """
        Given invalid email format,
        When POST /api/v1/newsletter_subscribers is called,
        Then returns 422 (validation error).
        """
        response = client.post(
            "/api/v1/newsletter_subscribers",
            json={"email": "not-an-email", "source": "landing"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_subscribe_blocked_domain_returns_422(self, client: TestClient) -> None:
        """
        Given a blocked test domain (example.com),
        When POST /newsletter_subscribers is called,
        Then returns 422 (early rejection before DB write or Resend call).
        """
        response = client.post(
            "/api/v1/newsletter_subscribers",
            json={"email": "bot@example.com", "source": "landing"},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_subscribe_defaults_source_to_landing(self, client: TestClient) -> None:
        """
        When source is omitted, request still succeeds (default "landing").
        """
        response = client.post(
            "/api/v1/newsletter_subscribers",
            json={"email": "default_source@pulsai.dev"},
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_subscribe_with_blog_source_stored_and_counted_in_stats(self, client: TestClient) -> None:
        """
        Blog page uses source "blog" for attribution. Must persist (not fall back to landing).
        """
        email = "blog_attribution@pulsai.dev"
        response = client.post(
            "/api/v1/newsletter_subscribers",
            json={"email": email, "source": "blog"},
        )
        assert response.status_code == status.HTTP_201_CREATED

        stats = client.get("/api/v1/newsletter_subscribers/stats").json()
        assert stats["by_source"].get("blog", 0) >= 1

    def test_subscribe_lead_calls_entitlement_hook(
        self,
        client: TestClient,
    ) -> None:
        """
        First LEAD_CAP subscribers are leads; automation must run for entitlement + audit.
        """
        with (
            patch(
                "src.api.v1.endpoints.newsletter_subscribers.process_newsletter_lead_entitlement",
                new_callable=AsyncMock,
            ) as mock_ent,
            patch(
                "src.infrastructure.persistence.newsletter_subscriber_repository.NewsletterSubscriberRepository.count_leads",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            response = client.post(
                "/api/v1/newsletter_subscribers",
                json={"email": f"lead_{uuid4()}@pulsai.dev", "source": "landing"},
            )

        assert response.status_code == status.HTTP_201_CREATED
        mock_ent.assert_called_once()


class TestUnsubscribeNewsletter:
    """POST /newsletter_subscribers/unsubscribe — idempotent opt-out."""

    def test_unsubscribe_invalid_token_still_204(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/newsletter_subscribers/unsubscribe",
            json={"token": "invalidtok" * 2},
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_unsubscribe_newsletter_token_marks_subscriber_unsubscribed(
        self,
        client: TestClient,
        db_session,
    ) -> None:
        subscriber = NewsletterSubscriberModel(
            id=str(uuid4()),
            email="subscriber-unsub@pulsai.dev",
            source="landing",
            is_lead=False,
        )
        db_session.add(subscriber)
        db_session.commit()

        response = client.post(
            "/api/v1/newsletter_subscribers/unsubscribe",
            json={"token": create_newsletter_unsubscribe_token(subscriber.id)},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        db_session.refresh(subscriber)
        assert subscriber.unsubscribed_at is not None

    def test_unsubscribe_user_token_marks_marketing_consent_false(
        self,
        client: TestClient,
        db_session,
    ) -> None:
        user = User(
            id=str(uuid4()),
            email="marketing-user@pulsai.dev",
            password_hash="h",
            marketing_consent=True,
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/api/v1/newsletter_subscribers/unsubscribe",
            json={"token": create_user_marketing_unsubscribe_token(user.id)},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        db_session.refresh(user)
        assert user.marketing_consent is False
        assert user.marketing_consent_at is not None


class TestGetNewsletterStats:
    """Behavior tests for GET /api/v1/newsletter_subscribers/stats."""

    def test_get_stats_returns_lead_cap_and_counts(self, client: TestClient) -> None:
        """
        GET /stats returns lead_count, lead_cap, seats_left, normal_subscriber_count, by_source.
        """
        response = client.get("/api/v1/newsletter_subscribers/stats")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "lead_count" in data
        assert "lead_cap" in data
        assert data["lead_cap"] == 1000
        assert "seats_left" in data
        assert "normal_subscriber_count" in data
        assert "by_source" in data
        assert isinstance(data["by_source"], dict)

    def test_get_stats_seats_left_decreases_as_leads_subscribe(self, client: TestClient) -> None:
        """
        After subscribing, lead_count increases and seats_left decreases (until cap).
        """
        r0 = client.get("/api/v1/newsletter_subscribers/stats").json()
        initial_lead_count = r0["lead_count"]
        initial_seats_left = r0["seats_left"]

        client.post(
            "/api/v1/newsletter_subscribers",
            json={"email": "stats_lead@pulsai.dev", "source": "landing"},
        )
        r1 = client.get("/api/v1/newsletter_subscribers/stats").json()
        assert r1["lead_count"] == initial_lead_count + 1
        assert r1["seats_left"] == initial_seats_left - 1
        assert r1["by_source"].get("landing", 0) >= 1
