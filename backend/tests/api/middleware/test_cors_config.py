"""
CORS: explicit allow_methods and allow_headers (no wildcards).

Behavior: preflight OPTIONS returns Access-Control-Allow-Methods/Headers from settings.
"""

from __future__ import annotations

from starlette.testclient import TestClient  # noqa: TC002 - runtime test client

from src.infrastructure.config import settings


class TestCorsExplicitConfiguration:
    """Preflight reflects configured method and header allowlists."""

    def test_preflight_lists_explicit_methods(self, client: TestClient) -> None:
        response = client.options(
            "/health",
            headers={
                "Origin": settings.cors_origins_list[0],
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status_code == 200
        allow_methods = response.headers.get("access-control-allow-methods", "")
        assert "*" not in allow_methods
        for method in settings.cors_allow_methods_list:
            assert method in allow_methods

    def test_preflight_lists_explicit_headers(self, client: TestClient) -> None:
        response = client.options(
            "/health",
            headers={
                "Origin": settings.cors_origins_list[0],
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

        assert response.status_code == 200
        allow_headers = response.headers.get("access-control-allow-headers", "")
        assert "*" not in allow_headers.lower()
        assert "authorization" in allow_headers.lower()

    def test_preflight_allows_trading_mutation_headers(self, client: TestClient) -> None:
        """Browser preflight for cookie-auth trading POST must allow Idempotency-Key + CSRF."""
        response = client.options(
            "/health",
            headers={
                "Origin": settings.cors_origins_list[0],
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,idempotency-key,x-csrf-token",
            },
        )

        assert response.status_code == 200
