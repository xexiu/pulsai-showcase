from src.shared.constants.runtime import (
    MODEL_CACHE_INVALIDATE_CHANNEL,
    REDBEAT_KEY_PREFIX,
    REDIS_PUBSUB_RECONNECT_DELAY_SECONDS,
    RETRY_LOCK_KEY_PREFIX,
    RETRY_LOCK_TTL_SECONDS,
    SCHEDULE_CONFIG_REDIS_KEY,
    SIGNAL_PUBSUB_CHANNEL,
    TRAINING_LOCK_KEY_PREFIX,
    build_retry_lock_key,
    build_training_lock_key,
)


def test_runtime_redis_namespaces_are_centralized() -> None:
    """Cross-process Redis keys should share one explicit contract."""
    assert SCHEDULE_CONFIG_REDIS_KEY == "pulsai:scheduled_tasks:enabled"
    assert SIGNAL_PUBSUB_CHANNEL == "pulsai:signals"
    assert MODEL_CACHE_INVALIDATE_CHANNEL == "pulsai:model_cache_invalidate"
    assert TRAINING_LOCK_KEY_PREFIX == "pulsai:training:lock:"
    assert REDBEAT_KEY_PREFIX == "pulsai:beat:"
    assert REDIS_PUBSUB_RECONNECT_DELAY_SECONDS == 5


def test_runtime_key_builders_preserve_existing_wire_format() -> None:
    """Centralization must not silently rename existing runtime keys."""
    assert build_training_lock_key("btc_usdt_1h:xgboost_3class") == ("pulsai:training:lock:btc_usdt_1h:xgboost_3class")
    assert RETRY_LOCK_KEY_PREFIX == "retry_lock:"
    assert build_retry_lock_key("job-123") == "retry_lock:job-123"
    assert RETRY_LOCK_TTL_SECONDS == 5
