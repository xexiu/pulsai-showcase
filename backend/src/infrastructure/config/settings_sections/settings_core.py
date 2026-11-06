"""Settings mixin — Core Application + Database (sections 1-2)."""

from typing import Literal

from pydantic import AliasChoices, Field


class SettingsCoreMixin:
    # ═══════════════════════════════════════════════════════════════════════════

    app_name: str = "PulsAI API"
    app_version: str = "0.1.0"
    # Build/commit provenance (auto-populated on Railway/GitHub when available).
    app_build_sha: str = Field(
        default="",
        validation_alias=AliasChoices(
            "app_build_sha",
            "APP_BUILD_SHA",
            "RAILWAY_GIT_COMMIT_SHA",
            "VERCEL_GIT_COMMIT_SHA",
            "GITHUB_SHA",
            "SOURCE_VERSION",
        ),
    )
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    # When True, POST /signals/generate accepts test_action/test_confidence outside development.
    # Default False: staging/production reject synthetic signals unless TESTING=true (pytest).
    allow_public_test_signals: bool = False

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════

    database_url: str = "postgresql+asyncpg://pulsai:pulsai_dev@localhost:5432/pulsai"
    redis_url: str = "redis://localhost:6379"

    # ═══════════════════════════════════════════════════════════════════════════
