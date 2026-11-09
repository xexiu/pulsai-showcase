"""Smoke tests: settings ops mixin defaults surface on Settings (per-mixin contract)."""

from __future__ import annotations

import pytest  # noqa: TC002

from src.infrastructure.config.settings import Settings
from src.infrastructure.config.settings_sections.settings_ops_platform import SettingsOpsPlatformMixin
from src.infrastructure.config.settings_sections.settings_ops_vendors import SettingsOpsVendorsMixin
from src.infrastructure.config.settings_sections.settings_ops_workers import SettingsOpsWorkersMixin


def test_settings_ops_rate_limits_mixin_defaults() -> None:
    """Rate-limit knobs from SettingsOpsRateLimitsMixin."""
    s = Settings(environment="development")
    assert s.rate_limit_backend == "memory"
    assert s.signals_generate_rate_limit_per_minute == 10
    assert s.market_ohlcv_rate_limit_per_minute == 60
    assert s.signal_read_delay_free_seconds == 900


def test_settings_ops_features_mixin_defaults() -> None:
    """Feature flags from SettingsOpsFeaturesMixin."""
    s = Settings(environment="development")
    assert s.feature_backtest is True
    assert s.feature_live_trading is False
    assert s.backtest_use_calculate_selected is False
    assert s.inference_compare_api_enabled is True
    assert s.max_backtest_days == 365


def test_development_backtest_historical_cache_ttl_is_four_hours(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dev sweeps cache huge payloads; 4h TTL limits Redis bloat without env override."""
    monkeypatch.delenv("BACKTEST_RESPONSE_CACHE_HISTORICAL_TTL_SECONDS", raising=False)
    s = Settings(environment="development")
    assert s.backtest_response_cache_historical_ttl_seconds == 14_400


def test_production_backtest_historical_cache_ttl_stays_twenty_four_hours(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BACKTEST_RESPONSE_CACHE_HISTORICAL_TTL_SECONDS", raising=False)
    s = Settings(
        environment="production",
        secret_key="test-production-secret-key-with-sufficient-length",
        frontend_url="https://pulsai.live",
    )
    assert s.backtest_response_cache_historical_ttl_seconds == 86_400


def test_development_backtest_historical_cache_ttl_respects_explicit_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BACKTEST_RESPONSE_CACHE_HISTORICAL_TTL_SECONDS", "7200")
    s = Settings(environment="development")
    assert s.backtest_response_cache_historical_ttl_seconds == 7200


def test_settings_ops_workers_mixin_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Celery worker knobs from SettingsOpsWorkersMixin.

    Post-Epic-B: ``paper_trading_lifecycle_*`` + ``paper_trading_retention_*`` settings
    were deleted alongside the Celery tasks that consumed them.
    """
    monkeypatch.delenv("PULSAI_CLEAR_OHLCV_STREAM_REDIS_ON_SUPERVISOR_START", raising=False)
    s = Settings(environment="development")
    assert s.celery_task_max_retries == 3
    assert s.celery_generate_signals_soft_limit == 300
    assert s.boot_ohlcv_stream_supervisors is True
    assert s.clear_ohlcv_stream_redis_on_supervisor_start is True


def test_clear_ohlcv_stream_redis_on_supervisor_start_off_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PULSAI_CLEAR_OHLCV_STREAM_REDIS_ON_SUPERVISOR_START", raising=False)
    s = Settings(
        environment="production",
        secret_key="test-production-secret-key-with-sufficient-length",
        frontend_url="https://pulsai.live",
    )
    assert s.clear_ohlcv_stream_redis_on_supervisor_start is False


def test_settings_ops_platform_mixin_defaults() -> None:
    """Platform / observability knobs from SettingsOpsPlatformMixin (env-stable fields)."""
    s = Settings(environment="development")
    assert s.ip_block_enabled is True
    assert s.vip_code_expiration_hours == 168
    assert s.pagination_default_limit == 50
    assert s.ohlcv_max_limit == 1000
    assert s.admin_health_queue_wait_warn_seconds == 0.5


def test_settings_ops_vendors_mixin_defaults() -> None:
    """Vendor / websocket knobs from SettingsOpsVendorsMixin (env-stable fields)."""
    s = Settings(environment="development")
    assert s.exchange_api_timeout == 30
    assert s.websocket_max_connections_per_ip == 30
    assert s.glassnode_base_url == "https://api.glassnode.com"
    assert s.websocket_reconnect_max_delay == 60.0
    assert s.fundamental_onchain_spike_rate_limit_per_minute == 30


def test_settings_ops_mixins_expose_class_level_defaults() -> None:
    """Mixin classes keep SoT defaults on class attributes (before Settings env overlay)."""
    assert SettingsOpsPlatformMixin.pulsai_log_last_bar_features is False
    assert SettingsOpsPlatformMixin.model_candidate_upload_enabled is False
    assert SettingsOpsWorkersMixin.celery_task_max_retries == 3
    assert SettingsOpsVendorsMixin.headline_sentiment_use_finbert is True
    assert SettingsOpsVendorsMixin.on_chain_use_stub is False
