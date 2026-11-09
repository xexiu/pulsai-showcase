"""
Application Configuration

Loads settings from environment variables with Pydantic.

Field index (sections) — implementation split across ``settings_sections/``:
  1. Core Application          → settings_core.py
  2. Database & Redis          → settings_core.py
  3. Security & Authentication → settings_security.py
  4. Email (Resend)            → settings_integrations.py
  5. CORS & Trusted Hosts      → settings_security.py
  6. Cookie Authentication     → settings_security.py
  7. OAuth (Google)            → settings_security.py
  8. Billing (Stripe)            → settings_integrations.py
  9. AI Providers              → settings_integrations.py
 10. Telegram                  → settings_integrations.py
 11. Exchange API Keys         → settings_integrations.py
 12. Trading Defaults          → settings_trading.py
 13. Signal Configuration      → settings_trading.py
 14. Chart API                  → settings_trading.py
  15-26. Ops / limits / workers → settings_ops*.py (composite SettingsOpsMixin)
 27. Model health monitoring  → settings.py directly (HEALTHROLLBACK-1b; ticket scoped this
     flag to this file rather than settings_integrations.py, unlike every other `*_enabled` flag
     listed above)
"""

from functools import lru_cache
from typing import Self, cast

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.infrastructure.config.settings_sections.settings_core import LOCAL_DEV_DATABASE_URL, SettingsCoreMixin
from src.infrastructure.config.settings_sections.settings_integrations import SettingsIntegrationsMixin
from src.infrastructure.config.settings_sections.settings_ops import SettingsOpsMixin
from src.infrastructure.config.settings_sections.settings_ops_features import (
    DEVELOPMENT_BACKTEST_RESPONSE_CACHE_HISTORICAL_TTL_SECONDS,
)
from src.infrastructure.config.settings_sections.settings_ops_rate_limits import (
    DEVELOPMENT_BACKTEST_RUN_RATE_LIMIT_ADMIN_PER_MINUTE,
    DEVELOPMENT_BACKTEST_RUN_RATE_LIMIT_SUPER_ADMIN_PER_MINUTE,
)
from src.infrastructure.config.settings_sections.settings_security import (
    DEFAULT_DEVELOPMENT_ACCESS_TOKEN_EXPIRE_MINUTES,
    DEFAULT_NON_DEV_ACCESS_TOKEN_EXPIRE_MINUTES,
    INSECURE_DEFAULT_SECRET_KEY,
    MAX_NON_DEV_ACCESS_TOKEN_EXPIRE_MINUTES,
    SettingsSecurityMixin,
)
from src.infrastructure.config.settings_sections.settings_trading import SettingsTradingMixin
from src.shared.utils.email_assets import is_local_email_asset_base

# Re-export module-level constants (backwards compatibility)
__all__ = [
    "DEFAULT_DEVELOPMENT_ACCESS_TOKEN_EXPIRE_MINUTES",
    "DEFAULT_NON_DEV_ACCESS_TOKEN_EXPIRE_MINUTES",
    "INSECURE_DEFAULT_SECRET_KEY",
    "MAX_NON_DEV_ACCESS_TOKEN_EXPIRE_MINUTES",
    "Settings",
    "get_settings",
    "settings",
]


class Settings(
    SettingsCoreMixin,
    SettingsSecurityMixin,
    SettingsIntegrationsMixin,
    SettingsTradingMixin,
    SettingsOpsMixin,
    BaseSettings,
):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # Model health monitoring (HEALTHROLLBACK-1b)
    # ═══════════════════════════════════════════════════════════════════════════
    # Drift detection (execute_health_checks_sync, beat-scheduled every 5 min on the
    # "monitoring" queue) always runs and reports, regardless of this flag. Auto-rollback of a
    # PRODUCTION model is a separate, owner-gated action: it stays OFF until explicitly enabled,
    # because unpublishing a user-visible production model is the owner's call, not an automatic
    # one. See src/workers/tasks/training_tasks_health.py::_process_health_result.
    model_health_auto_rollback_enabled: bool = False

    # ═══════════════════════════════════════════════════════════════════════════
    # Derived Properties (cross-section)
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

        # WHY: In production we expect the API to be called from the configured
        # frontend domain. If CORS_ORIGINS is accidentally unset on the platform,
        # the browser will fail with "No Access-Control-Allow-Origin".
        # So we always union in FRONTEND_URL as a safe, intended origin.
        frontend_origin = self.frontend_url.strip().rstrip("/")
        if frontend_origin and frontend_origin not in origins:
            origins.append(frontend_origin)

        # De-dup while preserving order (defensive; keeps deterministic test output).
        seen: set[str] = set()
        deduped: list[str] = []
        for origin in origins:
            if origin not in seen:
                seen.add(origin)
                deduped.append(origin)

        return deduped

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self.environment == "staging"

    @property
    def is_debug_or_staging(self) -> bool:
        """
        True when verbose support-only details are allowed.

        SoT for "we may expose internal IDs / extra logging to humans here":
        - Production: only when ``debug=True`` is explicitly set (troubleshooting flag).
        - Staging: always on (support reproduces customer issues there).
        - Development: always on (developers debugging local work).

        Equivalently: ``True`` for any non-production environment, OR when ``debug``
        is explicitly set in production. ``debug`` does NOT auto-default to True
        in development (it stays False unless overridden), so this property must
        treat the development environment as an explicit allow.

        Consumers (Telegram /explain confirmation lines, server-side full-UUID logs,
        etc.) read this property instead of re-implementing the predicate so the
        environment matrix lives in one place.

        NOTE: name predates the development branch of the logic; a more accurate
        rename (e.g. ``shows_support_details`` or ``allows_verbose_internals``) is
        a separate follow-up to avoid churn in all callers.
        """
        return self.debug or not self.is_production

    @property
    def has_binance_keys(self) -> bool:
        """Check if Binance API keys are configured."""
        return bool(self.binance_api_key and self.binance_secret_key)

    @property
    def has_bitget_keys(self) -> bool:
        """Check if Bitget API keys are configured."""
        return bool(self.bitget_api_key and self.bitget_secret_key)

    @property
    def app_release(self) -> str:
        """Version string with optional short build SHA (e.g. 0.1.0+1a2b3c4d)."""
        sha = (self.app_build_sha or "").strip()
        if not sha:
            return self.app_version
        return f"{self.app_version}+{sha[:8]}"

    # ═══════════════════════════════════════════════════════════════════════════
    # Cross-section validators
    # ═══════════════════════════════════════════════════════════════════════════

    @model_validator(mode="before")
    @classmethod
    def _set_env_aware_access_token_default(cls, data: object) -> object:
        """Use long TTL default only in development when value is not explicitly set."""
        if not isinstance(data, dict):
            return data
        values = cast("dict[str, object]", data)  # the raw input mapping: keys are field names

        if values.get("access_token_expire_minutes") not in (None, ""):
            return values

        environment = str(values.get("environment", "development")).lower()
        if environment == "development":
            merged_data = dict(values)
            merged_data["access_token_expire_minutes"] = DEFAULT_DEVELOPMENT_ACCESS_TOKEN_EXPIRE_MINUTES
            return merged_data

        return values

    @model_validator(mode="after")
    def _default_clear_ohlcv_stream_redis_on_supervisor_start_in_dev(self) -> Self:
        """Enable supervisor Redis clear on cold start in development unless env overrides."""
        if "clear_ohlcv_stream_redis_on_supervisor_start" in self.model_fields_set:
            return self
        if self.environment == "development":
            object.__setattr__(self, "clear_ohlcv_stream_redis_on_supervisor_start", True)
        return self

    @model_validator(mode="after")
    def _redbeat_lock_covers_beat_tick_interval(self) -> Self:
        """Ensure Redis lock TTL outlasts capped sleep between RedBeat tick()/extend() cycles."""
        min_lock_seconds = self.celery_beat_max_loop_interval * 3
        if self.celery_redbeat_lock_timeout < min_lock_seconds:
            msg = (
                "celery_redbeat_lock_timeout must be >= 3 * celery_beat_max_loop_interval "
                f"({min_lock_seconds}s); got lock={self.celery_redbeat_lock_timeout}s, "
                f"beat_max_loop={self.celery_beat_max_loop_interval}s"
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _elevate_development_backtest_research_rate_limits(self) -> Self:
        """Local dev only: OOS Hub sweeps fire far more POST /backtest/run than prod UI."""
        if self.environment != "development":
            return self
        object.__setattr__(
            self,
            "backtest_run_rate_limit_admin_per_minute",
            max(
                self.backtest_run_rate_limit_admin_per_minute,
                DEVELOPMENT_BACKTEST_RUN_RATE_LIMIT_ADMIN_PER_MINUTE,
            ),
        )
        object.__setattr__(
            self,
            "backtest_run_rate_limit_super_admin_per_minute",
            max(
                self.backtest_run_rate_limit_super_admin_per_minute,
                DEVELOPMENT_BACKTEST_RUN_RATE_LIMIT_SUPER_ADMIN_PER_MINUTE,
            ),
        )
        return self

    @model_validator(mode="after")
    def _cap_development_backtest_historical_cache_ttl(self) -> Self:
        """Local dev only: shorter historical cache TTL so OOS sweeps do not bloat Redis."""
        if self.environment != "development":
            return self
        if "backtest_response_cache_historical_ttl_seconds" in self.model_fields_set:
            return self
        object.__setattr__(
            self,
            "backtest_response_cache_historical_ttl_seconds",
            DEVELOPMENT_BACKTEST_RESPONSE_CACHE_HISTORICAL_TTL_SECONDS,
        )
        return self

    @model_validator(mode="after")
    def _enforce_no_local_defaults_in_non_dev(self) -> Self:
        """Reject the committed local-dev defaults outside development: the insecure JWT secret, and the local database
        URL (a deploy that forgot DATABASE_URL must fail at boot, not run on committed credentials)."""
        if self.environment not in {"production", "staging"}:
            return self
        if self.secret_key == INSECURE_DEFAULT_SECRET_KEY:
            raise ValueError("secret_key must be set to a non-default value in staging/production")
        if self.database_url == LOCAL_DEV_DATABASE_URL:
            raise ValueError("database_url must be set (DATABASE_URL) in staging/production, not the local-dev default")
        return self

    @model_validator(mode="after")
    def _enforce_access_token_ttl_in_non_dev(self) -> Self:
        """Reject long-lived access tokens outside development."""
        if self.environment in {"production", "staging"} and self.access_token_expire_minutes > MAX_NON_DEV_ACCESS_TOKEN_EXPIRE_MINUTES:
            raise ValueError("access_token_expire_minutes must be <= 1440 in staging/production")
        return self

    @model_validator(mode="after")
    def _enforce_public_frontend_url_in_non_dev(self) -> Self:
        """Reject default localhost FRONTEND_URL outside development (broken email logos/links)."""
        if self.environment in {"production", "staging"} and is_local_email_asset_base(self.frontend_url):
            raise ValueError(
                "frontend_url must be a public HTTPS origin in staging/production (set FRONTEND_URL=https://pulsai.live or your deployed domain)"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
