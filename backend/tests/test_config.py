"""
Configuration Tests

Tests for application settings and configuration.
"""

import pytest

from src.domain.enums import Exchange
from src.infrastructure.config.settings import INSECURE_DEFAULT_SECRET_KEY, Settings, get_settings, settings
from src.infrastructure.config.settings_sections.settings_core import LOCAL_DEV_DATABASE_URL
from src.shared.constants.timeframes import TIMEFRAME_REGISTRY

# Non-dev Settings() must pass a public FRONTEND_URL (production validator).
_TEST_PUBLIC_FRONTEND_URL = "https://pulsai.live"


@pytest.fixture(autouse=True)
def _deployed_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-dev Settings() refuse the local-dev database URL, as a real deploy that sets DATABASE_URL never hits; the
    tests about that default pass or clear it themselves."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://pulsai:deployed@db.internal:5432/pulsai")


def test_settings_singleton() -> None:
    """Test that get_settings returns cached instance."""
    settings1 = get_settings()
    settings2 = get_settings()

    assert settings1 is settings2


def test_settings_default_values() -> None:
    """Test that settings have correct default values."""
    assert settings.app_name == "PulsAI API"
    assert settings.app_version == "0.1.0"
    assert settings.app_release.startswith(settings.app_version)
    assert settings.environment in ["development", "staging", "production"]


def test_settings_app_release_includes_short_build_sha_when_present() -> None:
    """Release string should include a short commit suffix for deploy provenance."""
    test_settings = Settings(app_version="0.1.0", app_build_sha="0123456789abcdef")
    assert test_settings.app_release == "0.1.0+01234567"


def test_settings_cors_origins() -> None:
    """Test that CORS origins is parsed correctly."""
    # cors_origins is stored as comma-separated string
    assert isinstance(settings.cors_origins, str)
    # cors_origins_list parses it to a list
    assert isinstance(settings.cors_origins_list, list)
    assert len(settings.cors_origins_list) > 0
    assert all(origin.startswith("http") for origin in settings.cors_origins_list)


def test_settings_cors_origins_includes_frontend_url() -> None:
    """Frontend URL must be present in allowed CORS origins.

    WHY:
    - In production, if CORS_ORIGINS is accidentally unset, the frontend should still
      work as long as FRONTEND_URL is configured.
    - This prevents the browser from failing with missing Access-Control-Allow-Origin.
    """
    test_settings = Settings(
        environment="production",
        cors_origins="http://localhost:3000",
        frontend_url="https://pulsai.live",
        secret_key="prod-secure-secret-for-test-only",
        access_token_expire_minutes=60,
    )

    assert "https://pulsai.live" in test_settings.cors_origins_list


def test_settings_is_production_property() -> None:
    """Test is_production property."""
    test_settings = Settings(
        environment="production",
        secret_key="prod-secure-secret-for-test-only",
        frontend_url=_TEST_PUBLIC_FRONTEND_URL,
        access_token_expire_minutes=60,
    )
    assert test_settings.is_production is True

    test_settings = Settings(environment="development")
    assert test_settings.is_production is False


def test_settings_is_staging_property() -> None:
    """is_staging is True only for environment='staging'."""
    assert (
        Settings(
            environment="staging",
            secret_key="staging-secret-for-test-only-32-chars",
            frontend_url=_TEST_PUBLIC_FRONTEND_URL,
        ).is_staging
        is True
    )
    assert (
        Settings(
            environment="production",
            secret_key="prod-secure-secret-for-test-only",
            frontend_url=_TEST_PUBLIC_FRONTEND_URL,
        ).is_staging
        is False
    )
    assert Settings(environment="development").is_staging is False


def test_settings_is_debug_or_staging_property() -> None:
    """is_debug_or_staging is True when debug=True OR environment='staging' — gate for support-only details."""
    # Pure staging: True via environment
    assert (
        Settings(
            environment="staging",
            secret_key="staging-secret-for-test-only-32-chars",
            frontend_url=_TEST_PUBLIC_FRONTEND_URL,
        ).is_debug_or_staging
        is True
    )

    # Production with debug=False: False
    prod = Settings(
        environment="production",
        secret_key="prod-secure-secret-for-test-only",
        frontend_url=_TEST_PUBLIC_FRONTEND_URL,
        debug=False,
    )
    assert prod.is_debug_or_staging is False

    # Production with debug=True (e.g. troubleshooting flag): True via debug
    prod_debug = Settings(
        environment="production",
        secret_key="prod-secure-secret-for-test-only",
        frontend_url=_TEST_PUBLIC_FRONTEND_URL,
        debug=True,
    )
    assert prod_debug.is_debug_or_staging is True

    # Development defaults: True (debug=True is the development default)
    assert Settings(environment="development").is_debug_or_staging is True


def test_settings_token_expiration() -> None:
    """Test token expiration defaults."""
    assert settings.access_token_expire_minutes > 0
    assert settings.refresh_token_expire_days > 0


def test_settings_rejects_default_secret_in_production() -> None:
    """Production must fail fast if SECRET_KEY is still the insecure default."""
    with pytest.raises(ValueError, match="non-default value"):
        Settings(environment="production", secret_key=INSECURE_DEFAULT_SECRET_KEY)


def test_settings_rejects_default_secret_in_staging() -> None:
    """Staging must follow production-grade secret hygiene."""
    with pytest.raises(ValueError, match="non-default value"):
        Settings(environment="staging", secret_key=INSECURE_DEFAULT_SECRET_KEY)


def test_settings_allows_default_secret_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local development keeps ergonomic defaults.

    SECRET_KEY is cleared explicitly: this asserts the DEFAULT, and a developer who has run the
    local stack has a real SECRET_KEY exported into their shell, which `Settings()` reads. Without
    the delenv the test passes in CI (no `.env`) and fails on every machine that runs the app —
    a red suite nobody trusts, for a value that is not the thing under test.
    """
    monkeypatch.delenv("SECRET_KEY", raising=False)

    test_settings = Settings(environment="development")

    assert test_settings.secret_key == INSECURE_DEFAULT_SECRET_KEY


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_settings_rejects_the_committed_local_database_url_outside_development(environment: str) -> None:
    """A deploy that forgot DATABASE_URL must fail at boot, not run on the committed local-dev credentials (the same
    rule the secret key already follows; SonarQube secrets:S6698 flagged the default, 2026-11-06)."""
    with pytest.raises(ValueError, match="database_url"):
        Settings(
            environment=environment,
            secret_key="x" * 64,
            frontend_url=_TEST_PUBLIC_FRONTEND_URL,
            database_url=LOCAL_DEV_DATABASE_URL,
        )


def test_settings_keeps_the_local_database_url_in_development(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert Settings(environment="development").database_url == LOCAL_DEV_DATABASE_URL


def test_settings_rejects_localhost_frontend_url_in_production() -> None:
    """Production must not boot with default FRONTEND_URL (broken email asset links)."""
    with pytest.raises(ValueError, match="frontend_url"):
        Settings(
            environment="production",
            secret_key="prod-secure-secret-for-test-only",
            frontend_url="http://localhost:3000",
        )


def test_settings_rejects_very_long_access_token_ttl_in_production() -> None:
    """Production must reject overly long access token TTL values."""
    with pytest.raises(ValueError, match="access_token_expire_minutes"):
        Settings(
            environment="production",
            secret_key="prod-secure-secret-for-test-only",
            access_token_expire_minutes=43200,
        )


def test_settings_allows_long_access_token_ttl_in_development() -> None:
    """Development keeps flexibility for local testing convenience."""
    test_settings = Settings(
        environment="development",
        access_token_expire_minutes=43200,
    )
    assert test_settings.access_token_expire_minutes == 43200


def test_settings_defaults_access_token_ttl_safely_in_production() -> None:
    """Production should boot safely when ACCESS_TOKEN_EXPIRE_MINUTES is unset."""
    test_settings = Settings(
        environment="production",
        secret_key="prod-secure-secret-for-test-only",
        frontend_url=_TEST_PUBLIC_FRONTEND_URL,
    )
    assert test_settings.access_token_expire_minutes <= 1440


def test_settings_keeps_long_access_token_default_in_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Development default remains long-lived when not overridden by env / .env."""
    monkeypatch.delenv("ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)
    test_settings = Settings(environment="development", _env_file=None)
    assert test_settings.access_token_expire_minutes == 43200


def test_settings_max_request_body_bytes() -> None:
    """Test max request body default (DoS guard)."""
    assert settings.max_request_body_bytes >= 1024 * 1024


def test_settings_reads_celery_worker_max_memory_per_child_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Celery worker recycle limit should be env-configurable for deployment tuning."""
    monkeypatch.setenv("CELERY_WORKER_MAX_MEMORY_PER_CHILD_KIB", "786432")
    test_settings = Settings(_env_file=None)
    assert test_settings.celery_worker_max_memory_per_child_kib == 786432


def test_settings_reads_solo_rss_watchdog_cap_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Solo-pool RSS watchdog cap must be env-tunable per service (monitoring vs ohlcv_stream)."""
    monkeypatch.setenv("CELERY_SOLO_RSS_WATCHDOG_MAX_KIB", "614400")  # 600 MiB
    test_settings = Settings(_env_file=None)
    assert test_settings.celery_solo_rss_watchdog_max_kib == 614400


def test_settings_reads_headline_sentiment_refresh_minutes_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Headline sentiment cadence must be env-tunable (restore faster refresh if Phase-2 needs it)."""
    monkeypatch.setenv("CELERY_HEADLINE_SENTIMENT_REFRESH_MINUTES", "10")
    test_settings = Settings(_env_file=None)
    assert test_settings.celery_headline_sentiment_refresh_minutes == 10


def test_settings_telegram_notify_timeframes_list_parsed_from_string() -> None:
    """SoT: telegram_notify_timeframes_list parses comma-separated string; empty = []."""
    test_settings = Settings(telegram_notify_timeframes="1h")
    assert test_settings.telegram_notify_timeframes_list == ["1h"]

    test_settings = Settings(telegram_notify_timeframes="30m, 1h")
    assert test_settings.telegram_notify_timeframes_list == ["30m", "1h"]

    test_settings = Settings(telegram_notify_timeframes="")
    assert test_settings.telegram_notify_timeframes_list == []


def test_settings_telegram_notify_timeframes_default_is_the_whole_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Owner 2026-08-25: the default TG allowlist is every trainable timeframe, LTF and HTF.

    Was `["4h", "8h", "12h", "1d"]`, hand-typed here AND in the constant AND in a third test,
    all three disagreeing by the time anyone looked. The default is derived from the registry
    now, so this asserts the derivation rather than re-typing the members a fourth time.

    Narrowing where a chart-PATTERN fire counts as evidence is a different question, and it
    lives behind `BULKOWSKI_PATTERN_NOTIFY_TIMEFRAMES` instead of riding on this list.

    HERMETIC, for the same reason `test_settings_allows_default_secret_in_development` is: this
    asserts the DEFAULT, and a bare `Settings()` reads `.env` and the shell. Both carry a real
    deployment value here — `.env:252` and prod both set `TELEGRAM_NOTIFY_TIMEFRAMES=4h,8h,12h,1d`
    — so the unpinned version asserted the OVERRIDE and went red on every machine that has run the
    stack, while passing in CI where no `.env` exists. That is the "red suite nobody trusts"
    failure the sibling test above already documents.
    """
    from src.shared.constants.hunt_timeframes import TELEGRAM_NOTIFY_DEFAULT_TIMEFRAMES

    monkeypatch.delenv("TELEGRAM_NOTIFY_TIMEFRAMES", raising=False)
    default_settings = Settings(_env_file=None)

    assert default_settings.telegram_notify_timeframes_list == list(TELEGRAM_NOTIFY_DEFAULT_TIMEFRAMES)
    assert "5m" in default_settings.telegram_notify_timeframes_list
    assert "6h" in default_settings.telegram_notify_timeframes_list, (
        "6h is an HTF band member (2026-08-12) and a trainable timeframe; a default that omits it "
        "is the degraded 4h/8h/12h/1d spelling full-htf-grid-always.md exists to forbid"
    )
    assert "1d" in default_settings.telegram_notify_timeframes_list


def test_settings_supported_timeframes_are_registry_filtered() -> None:
    """Configured supported timeframes should be a deduplicated subset of the backend registry."""
    test_settings = Settings(supported_timeframes="4h,1h,4h,15m")
    assert test_settings.supported_timeframes_list == ["4h", "1h", "15m"]


def test_settings_supported_timeframes_reject_unknown_values() -> None:
    """Unknown supported_timeframes values should fail fast instead of silently drifting.

    The example was "6h" until 6h became a real HTF band member (2026-08-12) — the sixth stale
    fixture in this repo that used a plausible timeframe as its example of an impossible one, and
    so went red on a correct change. The literal is now asserted to be outside the registry.
    """
    unknown = "not-a-timeframe"
    assert unknown not in TIMEFRAME_REGISTRY

    test_settings = Settings(supported_timeframes=f"1h,{unknown}")

    with pytest.raises(ValueError, match="Unsupported timeframes"):
        _ = test_settings.supported_timeframes_list


def test_settings_supported_exchanges_are_enum_filtered() -> None:
    """Configured supported exchanges should be a deduplicated subset of the backend exchange enum."""
    test_settings = Settings(supported_exchanges="bitget,binance,bitget")

    assert test_settings.supported_exchanges_list == [
        Exchange.BITGET.value,
        Exchange.BINANCE.value,
    ]


def test_settings_supported_exchanges_reject_unknown_values() -> None:
    """Unknown supported_exchanges values should fail fast instead of advertising unsupported runtime paths."""
    test_settings = Settings(supported_exchanges="binance,gateio")

    with pytest.raises(ValueError, match="Unsupported exchanges"):
        _ = test_settings.supported_exchanges_list


def test_settings_free_tier_allowed_symbols_parsed_from_string() -> None:
    """Free-tier symbol allowlist should parse from comma-separated env value."""
    test_settings = Settings(
        supported_symbols="BTC/USDT,ETH/USDT,SOL/USDT",
        free_tier_allowed_symbols="BTC/USDT,ETH/USDT",
    )
    assert test_settings.free_tier_allowed_symbols_list == ["BTC/USDT", "ETH/USDT"]


def test_settings_free_tier_allowed_symbols_reject_unknown_values() -> None:
    """Unknown free-tier symbols should fail fast to avoid FE/BE policy drift."""
    test_settings = Settings(
        supported_symbols="BTC/USDT,ETH/USDT",
        free_tier_allowed_symbols="BTC/USDT,SOL/USDT",
    )

    with pytest.raises(ValueError, match="Unsupported free-tier symbols"):
        _ = test_settings.free_tier_allowed_symbols_list


def test_settings_does_not_expose_unused_local_notification_sandbox_allowlist() -> None:
    """Dead local-only allowlist must not remain in the public Settings surface."""
    test_settings = Settings(_env_file=None)

    assert "local_notification_sandbox_allowlist" not in Settings.model_fields
    assert not hasattr(test_settings, "local_notification_sandbox_allowlist")
