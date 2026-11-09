from src.infrastructure.config.settings import settings
from src.shared.constants.celery import (
    ARENA_REFRESH_MAX_RETRIES,
    ARENA_REFRESH_SOFT_TIME_LIMIT_SECONDS,
    ARENA_REFRESH_TIME_LIMIT_SECONDS,
    CELERY_BEAT_MAX_LOOP_INTERVAL_SECONDS,
    CELERY_DEFAULT_RATE_LIMIT,
    CELERY_ENABLE_UTC,
    CELERY_REDBEAT_LOCK_TIMEOUT_SECONDS,
    CELERY_RESULT_EXPIRES_SECONDS,
    CELERY_SIGNAL_MODEL_PREWARM_MAX_SECONDS,
    CELERY_SOLO_RSS_WATCHDOG_MAX_KIB,
    CELERY_TASK_ACKS_LATE,
    CELERY_TASK_REJECT_ON_WORKER_LOST,
    CELERY_TIMEZONE,
    CELERY_WORKER_MAX_MEMORY_PER_CHILD_KIB,
    CELERY_WORKER_MAX_TASKS_PER_CHILD,
    CELERY_WORKER_PREFETCH_MULTIPLIER,
    CELERY_WORKER_PROC_ALIVE_TIMEOUT_SECONDS,
    CELERY_WORKER_PROCESS_INIT_MAX_SECONDS,
    GENERATE_SIGNALS_SOFT_TIME_LIMIT_SECONDS,
    GENERATE_SIGNALS_TIME_LIMIT_SECONDS,
    MODEL_CLEANUP_MAX_RETRIES,
    MODEL_CLEANUP_SOFT_TIME_LIMIT_SECONDS,
    MODEL_CLEANUP_TIME_LIMIT_SECONDS,
    OHLCV_BACKFILL_MAX_RETRIES,
    OHLCV_BACKFILL_SOFT_TIME_LIMIT_SECONDS,
    OHLCV_BACKFILL_TIME_LIMIT_SECONDS,
    OHLCV_SYNC_MAX_RETRIES,
    OHLCV_SYNC_RETRY_DELAY_SECONDS,
    OHLCV_SYNC_SOFT_TIME_LIMIT_SECONDS,
    OHLCV_SYNC_TIME_LIMIT_SECONDS,
    TRAINING_EXECUTE_JOB_EXPIRES,
    TRAINING_LOCK_TIMEOUT_SECONDS,
    TRAINING_SOFT_TIME_LIMIT,
    TRAINING_TASK_DISPATCH_EXPIRES,
    TRAINING_TIME_LIMIT,
)


def test_training_celery_runtime_uses_settings_backed_defaults() -> None:
    """Training worker timing must have one settings-backed owner."""
    assert settings.celery_training_time_limit == TRAINING_TIME_LIMIT
    assert settings.celery_training_soft_limit == TRAINING_SOFT_TIME_LIMIT
    assert settings.celery_training_dispatch_expires == TRAINING_TASK_DISPATCH_EXPIRES
    assert TRAINING_EXECUTE_JOB_EXPIRES == TRAINING_TIME_LIMIT
    assert TRAINING_LOCK_TIMEOUT_SECONDS == TRAINING_TIME_LIMIT


def test_training_celery_runtime_preserves_safe_timeout_ordering() -> None:
    """Soft and expiry windows must remain coherent for training flows."""
    assert TRAINING_SOFT_TIME_LIMIT < TRAINING_TIME_LIMIT
    assert TRAINING_TASK_DISPATCH_EXPIRES <= TRAINING_EXECUTE_JOB_EXPIRES


def test_celery_worker_process_init_max_seconds_matches_celery_docs() -> None:
    """Celery 5.6: worker_process_init handlers must not block more than ~4s."""
    assert CELERY_WORKER_PROCESS_INIT_MAX_SECONDS == 4.0


def test_celery_signal_model_prewarm_budget_is_post_ohlcv_slice() -> None:
    """Model loads get a dedicated window after Numba/OHLCVModel (not from process t0)."""
    assert CELERY_SIGNAL_MODEL_PREWARM_MAX_SECONDS == 8.0


def test_celery_worker_proc_alive_timeout_covers_heavy_pool_child_init() -> None:
    """Prefork UP handshake must outlast Numba + OHLCVModel + model prewarm (often >> 4s)."""
    assert CELERY_WORKER_PROC_ALIVE_TIMEOUT_SECONDS >= CELERY_WORKER_PROCESS_INIT_MAX_SECONDS
    assert CELERY_WORKER_PROC_ALIVE_TIMEOUT_SECONDS >= CELERY_SIGNAL_MODEL_PREWARM_MAX_SECONDS
    assert CELERY_WORKER_PROC_ALIVE_TIMEOUT_SECONDS >= 30.0


def test_shared_celery_worker_defaults_are_centralized() -> None:
    """Celery app defaults should come from one shared constant surface."""
    assert CELERY_TIMEZONE == "UTC"
    assert CELERY_ENABLE_UTC is True
    assert CELERY_RESULT_EXPIRES_SECONDS == 86400
    assert CELERY_WORKER_PREFETCH_MULTIPLIER == 1
    assert CELERY_WORKER_MAX_MEMORY_PER_CHILD_KIB >= 0  # 0 = disabled, >0 = KiB limit
    assert CELERY_DEFAULT_RATE_LIMIT == "10/m"
    assert CELERY_TASK_ACKS_LATE is True
    assert CELERY_TASK_REJECT_ON_WORKER_LOST is True
    assert settings.celery_worker_max_memory_per_child_kib == CELERY_WORKER_MAX_MEMORY_PER_CHILD_KIB
    assert settings.celery_worker_max_tasks_per_child == CELERY_WORKER_MAX_TASKS_PER_CHILD
    assert CELERY_WORKER_MAX_TASKS_PER_CHILD >= 50
    assert settings.celery_redbeat_lock_timeout == CELERY_REDBEAT_LOCK_TIMEOUT_SECONDS
    assert settings.celery_beat_max_loop_interval == CELERY_BEAT_MAX_LOOP_INTERVAL_SECONDS


def test_solo_rss_watchdog_cap_is_centralized_and_sane() -> None:
    """Solo-pool RSS watchdog cap must come from settings (one owner) and be a usable bound.

    BEHAVIOR: ``--pool=solo`` workers (monitoring, ohlcv_stream) cannot use
    ``worker_max_memory_per_child`` (prefork-only). This cap is the solo equivalent:
    0 = disabled, >0 = recycle the worker (warm shutdown) above N KiB.
    """
    assert settings.celery_solo_rss_watchdog_max_kib == CELERY_SOLO_RSS_WATCHDOG_MAX_KIB
    assert CELERY_SOLO_RSS_WATCHDOG_MAX_KIB >= 0
    if CELERY_SOLO_RSS_WATCHDOG_MAX_KIB > 0:
        # If enabled, leave headroom for one heavy task (FinBERT/model load) before recycling.
        assert CELERY_SOLO_RSS_WATCHDOG_MAX_KIB >= 512_000  # >= 512 MiB


def test_non_training_task_runtime_contracts_are_centralized() -> None:
    """Arena, OHLCVModel, and cleanup task decorators should share named runtime policy."""
    assert settings.celery_task_max_retries == OHLCV_SYNC_MAX_RETRIES
    assert settings.celery_task_retry_delay == OHLCV_SYNC_RETRY_DELAY_SECONDS
    assert settings.celery_ohlcv_sync_time_limit == OHLCV_SYNC_TIME_LIMIT_SECONDS
    assert settings.celery_ohlcv_sync_soft_limit == OHLCV_SYNC_SOFT_TIME_LIMIT_SECONDS
    assert OHLCV_SYNC_SOFT_TIME_LIMIT_SECONDS < OHLCV_SYNC_TIME_LIMIT_SECONDS
    assert OHLCV_BACKFILL_MAX_RETRIES == 1
    assert OHLCV_BACKFILL_SOFT_TIME_LIMIT_SECONDS < OHLCV_BACKFILL_TIME_LIMIT_SECONDS
    assert ARENA_REFRESH_MAX_RETRIES == 1
    assert ARENA_REFRESH_SOFT_TIME_LIMIT_SECONDS < ARENA_REFRESH_TIME_LIMIT_SECONDS
    assert MODEL_CLEANUP_MAX_RETRIES == 0
    assert MODEL_CLEANUP_SOFT_TIME_LIMIT_SECONDS < MODEL_CLEANUP_TIME_LIMIT_SECONDS
    assert settings.celery_generate_signals_time_limit == GENERATE_SIGNALS_TIME_LIMIT_SECONDS
    assert settings.celery_generate_signals_soft_limit == GENERATE_SIGNALS_SOFT_TIME_LIMIT_SECONDS
    assert GENERATE_SIGNALS_SOFT_TIME_LIMIT_SECONDS < GENERATE_SIGNALS_TIME_LIMIT_SECONDS
