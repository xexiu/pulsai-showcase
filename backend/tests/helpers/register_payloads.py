"""
Test-only helpers: POST /auth/register JSON bodies.

WHY: RegisterRequest requires terms_consent + data_processing_consent (GDPR).
Tests that omit them get 422 → no user → KeyError on login["data"].
SoT for integration tests that need a registered user.
"""

from __future__ import annotations

from typing import Any


def register_json(email: str, password: str, **extra: Any) -> dict[str, Any]:
    """
    Minimal valid register body for TestClient.post("/api/v1/auth/register", json=...).

    Pass name=..., invitation_code=..., etc. as keyword args when needed.
    """
    body: dict[str, Any] = {
        "email": email,
        "password": password,
        "terms_consent": True,
        "data_processing_consent": True,
    }
    body.update(extra)
    return body
