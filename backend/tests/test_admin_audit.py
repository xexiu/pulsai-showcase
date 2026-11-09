"""
Tests for Admin Audit Log Endpoints (Sprint 1.9)

TDD: These tests are written FIRST before implementation.

Tests cover:
- GET /api/v1/admin/audit - List audit logs with pagination and filters

BEHAVIOR being tested:
- Only admins can access audit logs
- Pagination works correctly
- Filters: user_id, event_type, risk_level, date range
- Results ordered by time descending (newest first)
"""

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from src.infrastructure.persistence.audit_log_model import AuditAction, AuditLog, EventType, RiskLevel
from src.infrastructure.persistence.user_model import User

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_admin_user() -> User:
    """Create a mock admin user."""
    return User(
        id="admin-uuid-123",
        email="admin@pulsai.dev",
        password_hash="hashed",
        name="Admin User",
        role="admin",
        is_active=True,
        is_verified=True,
    )


@pytest.fixture
def mock_audit_logs() -> list[AuditLog]:
    """Create mock audit log entries for testing."""
    now = datetime.now(UTC)
    logs = []

    # Create diverse audit log entries
    events = [
        (EventType.USER_LOGIN, RiskLevel.LOW, "user-1"),
        (EventType.FAILED_LOGIN, RiskLevel.MEDIUM, "user-2"),
        (EventType.MOCK_MODE_TOGGLE, RiskLevel.MEDIUM, "admin-uuid-123"),
        (EventType.MODEL_PROMOTE, RiskLevel.HIGH, "admin-uuid-123"),
        (EventType.SECURITY_ALERT, RiskLevel.CRITICAL, None),
        (EventType.USER_BAN, RiskLevel.HIGH, "admin-uuid-123"),
    ]

    for i, (event_type, risk_level, user_id) in enumerate(events):
        log = AuditLog(
            id=i + 1,
            time=now - timedelta(hours=i),
            event_type=event_type,
            action=AuditAction.CREATE,
            status="success",
            risk_level=risk_level,
            user_id=user_id,
            ip_address="192.168.1.1",
        )
        logs.append(log)

    return logs


# =============================================================================
# GET /admin/audit Tests
# =============================================================================


class TestListAuditLogs:
    """Tests for GET /api/v1/admin/audit endpoint."""

    def test_list_audit_requires_admin_auth(
        self,
        client: TestClient,
    ) -> None:
        """Non-admins should not be able to list audit logs."""
        response = client.get("/api/v1/admin/audit")
        assert response.status_code == 401

    def test_list_audit_forbidden_for_regular_user(
        self,
        client: TestClient,
        access_token: str,
    ) -> None:
        """Regular users cannot list audit logs."""
        response = client.get(
            "/api/v1/admin/audit",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.skip(reason="Endpoint not implemented yet - TDD")
    def test_list_audit_returns_paginated_response(
        self,
        client: TestClient,
        mock_admin_user: User,
        mock_audit_logs: list[AuditLog],
    ) -> None:
        """Admin should get paginated list of audit logs."""
        with (
            patch(
                "src.application.auth.dependencies.get_current_user",
                return_value=mock_admin_user,
                autospec=True,
            ),
            patch(
                "src.infrastructure.persistence.audit_repository.AuditRepository.list_logs",
                new_callable=AsyncMock,
                return_value=(mock_audit_logs, 6),
            ),
        ):
            response = client.get(
                "/api/v1/admin/audit?page=1&per_page=10",
                headers={"Authorization": "Bearer admin-token"},
            )

            assert response.status_code == 200
            data = response.json()

            # Check pagination metadata
            assert data["total"] == 6
            assert data["page"] == 1
            assert data["per_page"] == 10
            assert len(data["logs"]) == 6

    @pytest.mark.skip(reason="Endpoint not implemented yet - TDD")
    def test_list_audit_filter_by_event_type(
        self,
        client: TestClient,
        mock_admin_user: User,
    ) -> None:
        """Filter by event type should work."""
        with patch(
            "src.application.auth.dependencies.get_current_user",
            return_value=mock_admin_user,
            autospec=True,
        ):
            response = client.get(
                "/api/v1/admin/audit?event_type=user_login",
                headers={"Authorization": "Bearer admin-token"},
            )

            assert response.status_code == 200

    @pytest.mark.skip(reason="Endpoint not implemented yet - TDD")
    def test_list_audit_filter_by_risk_level(
        self,
        client: TestClient,
        mock_admin_user: User,
    ) -> None:
        """Filter by risk level should work."""
        with patch(
            "src.application.auth.dependencies.get_current_user",
            return_value=mock_admin_user,
            autospec=True,
        ):
            response = client.get(
                "/api/v1/admin/audit?risk_level=critical",
                headers={"Authorization": "Bearer admin-token"},
            )

            assert response.status_code == 200

    @pytest.mark.skip(reason="Endpoint not implemented yet - TDD")
    def test_list_audit_filter_by_user_id(
        self,
        client: TestClient,
        mock_admin_user: User,
    ) -> None:
        """Filter by user ID should work."""
        with patch(
            "src.application.auth.dependencies.get_current_user",
            return_value=mock_admin_user,
            autospec=True,
        ):
            response = client.get(
                "/api/v1/admin/audit?user_id=admin-uuid-123",
                headers={"Authorization": "Bearer admin-token"},
            )

            assert response.status_code == 200

    @pytest.mark.skip(reason="Endpoint not implemented yet - TDD")
    def test_list_audit_filter_by_date_range(
        self,
        client: TestClient,
        mock_admin_user: User,
    ) -> None:
        """Filter by date range should work."""
        with patch(
            "src.application.auth.dependencies.get_current_user",
            return_value=mock_admin_user,
            autospec=True,
        ):
            response = client.get(
                "/api/v1/admin/audit?since=2026-01-01T00:00:00Z&until=2026-01-31T23:59:59Z",
                headers={"Authorization": "Bearer admin-token"},
            )

            assert response.status_code == 200

    @pytest.mark.skip(reason="Endpoint not implemented yet - TDD")
    def test_list_audit_ordered_by_time_desc(
        self,
        client: TestClient,
        mock_admin_user: User,
        mock_audit_logs: list[AuditLog],
    ) -> None:
        """
        Audit logs should be ordered by time descending (newest first).

        WHY: Most relevant events are recent; admins need to see them first.
        """
        with (
            patch(
                "src.application.auth.dependencies.get_current_user",
                return_value=mock_admin_user,
                autospec=True,
            ),
            patch(
                "src.infrastructure.persistence.audit_repository.AuditRepository.list_logs",
                new_callable=AsyncMock,
                return_value=(mock_audit_logs, len(mock_audit_logs)),
            ),
        ):
            response = client.get(
                "/api/v1/admin/audit",
                headers={"Authorization": "Bearer admin-token"},
            )

            assert response.status_code == 200
            data = response.json()

            # First log should be newest
            logs = data["logs"]
            if len(logs) > 1:
                for i in range(len(logs) - 1):
                    assert logs[i]["time"] >= logs[i + 1]["time"]


# =============================================================================
# Repository Tests
# =============================================================================


class TestAuditRepository:
    """Tests for AuditRepository."""

    @pytest.mark.skip(reason="Repository not implemented yet - TDD")
    @pytest.mark.asyncio
    async def test_list_logs_with_pagination(self) -> None:
        """Repository should support pagination."""
        # Will test actual DB queries

    @pytest.mark.skip(reason="Repository not implemented yet - TDD")
    @pytest.mark.asyncio
    async def test_list_logs_filters_by_event_type(self) -> None:
        """Repository should filter by event type."""

    @pytest.mark.skip(reason="Repository not implemented yet - TDD")
    @pytest.mark.asyncio
    async def test_list_logs_filters_by_risk_level(self) -> None:
        """Repository should filter by risk level."""

    @pytest.mark.skip(reason="Repository not implemented yet - TDD")
    @pytest.mark.asyncio
    async def test_list_logs_filters_by_date_range(self) -> None:
        """Repository should filter by date range."""
