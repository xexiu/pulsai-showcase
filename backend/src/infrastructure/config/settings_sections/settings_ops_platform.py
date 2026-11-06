"""IP/VIP, model uploads, observability, pagination (settings §19-22)."""

from pydantic import AliasChoices, Field


class SettingsOpsPlatformMixin:
    ip_block_enabled: bool = True
    ip_block_permanent_ips: str = ""
    abuse_log_max_entries: int = 5000
    abuse_alert_threshold_per_minute: int = 30
    ip_auto_block_strikes_threshold: int = 20
    ip_auto_block_strikes_window_minutes: int = 15
    ip_auto_block_duration_minutes: int = 60

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════

    vip_code_expiration_hours: int = 168  # 7 days default, configurable per campaign
    vip_admin_resend_rate_limit_per_hour: int = 3  # Max resends per admin per hour
    vip_admin_resend_rate_limit_window_minutes: int = 60
    vip_email_max_total_invites: int = 5  # Max total codes (used + unused) per email
    vip_validate_rate_limit_per_minute: int = 20  # Public validate endpoint: per-IP limit
    vip_validate_not_found_alert_threshold_per_minute: int = 8  # Repeated invalid-code probes trigger security alert log
    vip_usage_rate_limit_per_minute: int = 30  # Auth usage endpoint: per-user+ip limit

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════

    model_candidate_upload_max_files: int = 200
    model_candidate_upload_max_total_mb: int = 250
    # Master switch for POST .../upload-candidate (UI hidden by default; use ship_model_to_r2 CLI).
    model_candidate_upload_enabled: bool = False
    model_candidate_upload_rate_limit_per_minute: int = 5
    # Soft cap surfaced in admin upload modal (bytes). Default 10 GiB.
    model_storage_quota_bytes: int = 10 * 1024 * 1024 * 1024
    # Legacy env name; upload route always requires SuperAdminUser — prefer MODEL_CANDIDATE_UPLOAD_ENABLED.
    model_candidate_upload_super_admin_only: bool = False
    model_candidate_keep_latest_per_model: int = 20
    model_candidate_retention_days: int = 45
    # Global cap on non-deleted trained model versions (sum across all symbol/timeframe).
    # WHY: Bounded storage and predictable admin UX; super admin can raise via env / future UI.
    # Set to 0 to disable the cap (emergency only — prefer raising the limit or purging old models).
    max_stored_model_versions: int = 1000
    # `model_prewarm_auto_reconcile_stale_refs` / `model_prewarm_stale_ref_dry_run` were REMOVED on
    # 2026-09-16 together with the boot-time registry reconcile they configured. That reconcile let
    # a cache warmer delete production references when a load failed — it once blanked a dev
    # registry because the BINARIES were absent locally — so it shipped permanently dry-run, and no
    # Railway service or env file ever set either flag. What it actually produced was a
    # `would_reconcile` count beside a warning that already named every failed reference. Missing
    # artifacts are still reported, read-only, by `ModelStorage.get_stale_production_references` on
    # the admin health check.

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════

    sentry_dsn: str = ""  # Optional: https://xxx@sentry.io/xxx
    # Admin GET /admin/logs: directory for pulsai.log (empty = default apps/api/logs)
    application_logs_directory: str = ""
    # Admin /admin/health compact live-signal observability thresholds (single SoT).
    admin_health_queue_wait_warn_seconds: float = 0.5
    admin_health_queue_wait_critical_seconds: float = 2.0
    admin_health_persist_commit_warn_seconds: float = 0.1
    admin_health_persist_commit_critical_seconds: float = 0.25
    admin_health_persist_error_rate_warn: float = 0.02
    admin_health_persist_error_rate_critical: float = 0.05
    admin_health_exchange_tier_ratio_warn: float = 0.2
    admin_health_exchange_tier_ratio_critical: float = 0.4

    pulsai_log_last_bar_features: bool = False
    pulsai_log_backtest_last_bar_features: bool = False
    # Max lines read across pulsai.log + rotated files per request (tail each file).
    admin_system_logs_max_lines_scan: int = 50_000

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════

    pagination_default_limit: int = 50
    pagination_max_limit: int = 500
    ohlcv_default_limit: int = 500
    ohlcv_max_limit: int = 1000
    # OHLCV upsert chunk target (rows/statement). Capped by asyncpg max params at runtime.
    ohlcv_upsert_chunk_rows_target: int = Field(
        default=2000,
        ge=1,
        validation_alias=AliasChoices("PULSAI_OHLCV_UPSERT_CHUNK_ROWS_TARGET"),
        description=(
            "Target rows per OHLCV INSERT ... ON CONFLICT statement; runtime clamps "
            "to asyncpg bind-parameter safety ceiling (env PULSAI_OHLCV_UPSERT_CHUNK_ROWS_TARGET)"
        ),
    )
