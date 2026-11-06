"""
Shared constants for PulsAI backend (C.7 SoT).

Centralized configuration values to eliminate magic numbers and DRY violations.
Import from this package: from src.shared.constants import DEFAULT_MODELS_PATH, ...
"""

# Define these first so they exist before any import chain (e.g. celery -> settings -> ml)
# that imports from this package. Avoids circular import.
EPSILON_FOR_DIVISION = 1e-20
# RELATIVE: a std <= this * max(|mean|, 1) is float noise from a constant series. Read it only through
# src/shared/math/zero_dispersion.py; the value is chosen by the measurement in its test.
NEAR_ZERO_STD_THRESHOLD = 1e-12
# Model key parsing: "symbol_timeframe" = 2 parts
EXPECTED_KEY_PARTS = 2

# Light submodules first (no celery deps) so they exist during celery import chain.
from src.shared.constants.backtest import (
    DEFAULT_BACKTEST_ATR_MULTIPLIER,
    DEFAULT_BACKTEST_ATR_PERIOD,
    DEFAULT_BACKTEST_INITIAL_CAPITAL,
    DEFAULT_BACKTEST_MAX_OPEN_POSITIONS,
    DEFAULT_BACKTEST_MAX_SL_PCT,
    DEFAULT_BACKTEST_MIN_NET_PCT,
    DEFAULT_BACKTEST_RISK_REWARD_RATIO,
    DEFAULT_BACKTEST_USE_TAKER_FEES,
    DEFAULT_VALIDATION_BACKTEST_MAX_OPEN_POSITIONS,
)
from src.shared.constants.carry import (
    CARRY_ADVERSE_LOOKBACK_DAYS,
    CARRY_DEFAULT_MMR,
    CARRY_MAX_LEVERAGE,
    CARRY_QTY_EPS,
    CARRY_ROUNDTRIP_FEE_PCT,
    CARRY_TAKER_FEE_PCT,
    CARRY_VENUES,
    DEFAULT_CARRY_DAYS,
    DEFAULT_CARRY_VENUES_CSV,
    HOURS_PER_YEAR,
    MAX_CARRY_DAYS,
    MIN_CARRY_DAYS,
    CarryPositionStatus,
    CarryTickStatus,
)
from src.shared.constants.celery import (
    TRAINING_EXECUTE_JOB_EXPIRES,
    TRAINING_LOCK_TIMEOUT_SECONDS,
    TRAINING_SOFT_TIME_LIMIT,
    TRAINING_TASK_DISPATCH_EXPIRES,
    TRAINING_TIME_LIMIT,
)
from src.shared.constants.confidence import (
    DEFAULT_MIN_SIGNAL_CONFIDENCE_PERCENT,
    DEFAULT_MIN_SIGNAL_CONFIDENCE_THRESHOLD,
    ML_CONFIDENCE_PERCENT_DISPLAY_DECIMALS,
    confidence_pct_to_threshold,
)
from src.shared.constants.features import (
    DEFAULT_MAX_FEATURES,
    DEFAULT_MIN_FEATURES_AFTER_SELECTION,
    FEATURE_CORRELATION_THRESHOLD,
    HIGH_VELOCITY_DELTA_THRESHOLD,
    MAX_FEATURES_LIMIT,
    MIN_CANDLES_FOR_BACKTEST,
    MIN_CANDLES_FOR_INDICATORS,
)
from src.shared.constants.fees import (
    BINANCE_MAKER_FEE,
    BINANCE_TAKER_FEE,
    BITGET_MAKER_FEE,
    BITGET_TAKER_FEE,
    DEFAULT_FEE_RATE,
    DEFAULT_ROUNDTRIP_COST,
    DEFAULT_SLIPPAGE,
    DEFAULT_TURNOVER_COST_PER_SIDE,
)
from src.shared.constants.health import (
    DB_PROBE_SQL,
    STATUS_DEGRADED,
    STATUS_HEALTHY,
    STATUS_NOT_CONFIGURED,
    STATUS_NOT_READY,
    STATUS_READY,
    STATUS_UNHEALTHY,
)
from src.shared.constants.live_signal_latency import (
    LIVE_SIGNAL_INNER_LATENCY_WARN_ENSEMBLE_MS,
    LIVE_SIGNAL_INNER_LATENCY_WARN_SINGLE_MODEL_MS,
    live_signal_inner_latency_warn_ms,
)
from src.shared.constants.locales import SUPPORTED_USER_LOCALES
from src.shared.constants.newsletter import (
    ALLOWED_SOURCES,
    LEAD_CAP,
)
from src.shared.constants.notification import (
    NOTIFICATION_INNER_KEY_FAILED,
    NOTIFICATION_INNER_KEY_RATE_LIMITED,
    NOTIFICATION_INNER_KEY_SENT,
    NOTIFICATION_KEY_EMAIL_FAILED,
    NOTIFICATION_KEY_EMAIL_RATE_LIMITED,
    NOTIFICATION_KEY_EMAIL_SENT,
    NOTIFICATION_KEY_TELEGRAM_FAILED,
    NOTIFICATION_KEY_TELEGRAM_SENT,
    notification_result_skeleton,
)
from src.shared.constants.paths import DEFAULT_MODELS_PATH
from src.shared.constants.predictions import (
    PREDICTION_CLASS_BUY,
    PREDICTION_CLASS_HOLD,
    PREDICTION_CLASS_SELL,
)
from src.shared.constants.rollback_policy import (
    LATENCY_P99_CRITICAL_MS,
    LATENCY_P99_ROLLBACK_MS,
    LATENCY_P99_WARNING_MS,
    get_anomaly_latency_critical_ms,
    get_anomaly_latency_warning_ms,
    get_rollback_latency_threshold_ms,
)
from src.shared.constants.runtime import (
    REDBEAT_KEY_PREFIX,
    RETRY_LOCK_KEY_PREFIX,
    RETRY_LOCK_SCAN_PATTERN,
    RETRY_LOCK_TTL_SECONDS,
    SCHEDULE_CONFIG_REDIS_KEY,
    SIGNAL_PUBSUB_CHANNEL,
    TRAINING_LOCK_KEY_PREFIX,
    TRAINING_LOCK_SCAN_PATTERN,
    build_retry_lock_key,
    build_training_lock_key,
)
from src.shared.constants.telegram import (
    TELEGRAM_API_BASE_URL,
    TELEGRAM_API_SEND_MESSAGE_PATH,
    TELEGRAM_EXPLAIN_RATE_LIMIT_PER_MINUTE,
    TELEGRAM_EXPLAIN_TIMEOUT_SECONDS,
    TELEGRAM_GENERAL_RATE_LIMIT_PER_MINUTE,
    TELEGRAM_PARSE_MODE_MARKDOWN,
    TELEGRAM_POLLING_RESTART_DELAY_SEC,
    TELEGRAM_POLLING_RESTART_LIMIT,
    TELEGRAM_POLLING_STARTUP_BASE_DELAY_SEC,
    TELEGRAM_POLLING_STARTUP_MAX_RETRIES,
    TELEGRAM_SEND_MESSAGE_TIMEOUT_SEC,
)
from src.shared.constants.themes import (
    DEFAULT_PUBLIC_UI_THEME,
    DEFAULT_USER_THEME,
    SUPPORTED_USER_THEMES,
    UserTheme,
)
from src.shared.constants.timeframes import (
    ALIGNMENT_TIMEFRAMES_ORDER,
    DEFAULT_SUPPORTED_TIMEFRAME_VALUES,
    DEFAULT_TIMEFRAME,
    DEFAULT_TIMEFRAME_DELTA,
    DEFAULT_TIMEFRAME_MS,
    SUPPORTED_TIMEFRAME_VALUES,
    TIMEFRAME_DELTA,
    TIMEFRAME_MS,
    TIMEFRAME_REGISTRY,
    VALID_TIMEFRAMES_SIGNAL_AND_TRAINING,
    TimeframeDefinition,
    get_supported_timeframes,
)
from src.shared.constants.trading import (
    DEFAULT_EXCHANGE,
    DEFAULT_SYMBOL,
    DEFAULT_SYMBOLS,
    SUPPORTED_EXCHANGE_VALUES,
    VOLUME_SPIKE_THRESHOLD,
    get_supported_exchanges,
)

# Numerical precision thresholds (values set at top of file to avoid circular import)
# WHY 1e-20: Values below this are considered effectively zero (numerical precision)
# Used for division safety, standard deviation checks, etc.

# Feature/indicator division safety (DRY: one place for ATR, channel width, etc.)
# WHY 1e-12: Avoid div-by-zero in indicators; small enough to not affect ratios
FEATURE_NEAR_ZERO = 1e-12
# Safe divisor when denominator can be zero (e.g. volume, price range)
FEATURE_SAFE_DIV = 1e-10

# MAD (Median Absolute Deviation) scale factor.
# WHY 1.4826: For N(0,1), median(|X|) = 0.6745, so 1/0.6745 ≈ 1.4826.
# Makes MAD*1.4826 consistent with std for normally distributed data while
# remaining robust to outliers (up to 50% data contamination).
# Used by: feature_volatility (features), feature_normalization (ML preprocessing),
# mean_reversion_target (target labeling).
MAD_SCALE_FACTOR = 1.4826

__all__ = [
    "ALIGNMENT_TIMEFRAMES_ORDER",
    "ALLOWED_SOURCES",
    "BINANCE_MAKER_FEE",
    "BINANCE_TAKER_FEE",
    "BITGET_MAKER_FEE",
    "BITGET_TAKER_FEE",
    "CARRY_ADVERSE_LOOKBACK_DAYS",
    "CARRY_DEFAULT_MMR",
    "CARRY_MAX_LEVERAGE",
    "CARRY_QTY_EPS",
    "CARRY_ROUNDTRIP_FEE_PCT",
    "CARRY_TAKER_FEE_PCT",
    "CARRY_VENUES",
    "DB_PROBE_SQL",
    "DEFAULT_BACKTEST_ATR_MULTIPLIER",
    "DEFAULT_BACKTEST_ATR_PERIOD",
    "DEFAULT_BACKTEST_INITIAL_CAPITAL",
    "DEFAULT_BACKTEST_MAX_OPEN_POSITIONS",
    "DEFAULT_BACKTEST_MAX_SL_PCT",
    "DEFAULT_BACKTEST_MIN_NET_PCT",
    "DEFAULT_BACKTEST_RISK_REWARD_RATIO",
    "DEFAULT_BACKTEST_USE_TAKER_FEES",
    "DEFAULT_CARRY_DAYS",
    "DEFAULT_CARRY_VENUES_CSV",
    "DEFAULT_EXCHANGE",
    "DEFAULT_FEE_RATE",
    "DEFAULT_MAX_FEATURES",
    "DEFAULT_MIN_FEATURES_AFTER_SELECTION",
    "DEFAULT_MIN_SIGNAL_CONFIDENCE_PERCENT",
    "DEFAULT_MIN_SIGNAL_CONFIDENCE_THRESHOLD",
    "DEFAULT_MODELS_PATH",
    "DEFAULT_PUBLIC_UI_THEME",
    "DEFAULT_ROUNDTRIP_COST",
    "DEFAULT_SLIPPAGE",
    "DEFAULT_SUPPORTED_TIMEFRAME_VALUES",
    "DEFAULT_SYMBOL",
    "DEFAULT_SYMBOLS",
    "DEFAULT_TIMEFRAME",
    "DEFAULT_TIMEFRAME_DELTA",
    "DEFAULT_TIMEFRAME_MS",
    "DEFAULT_TURNOVER_COST_PER_SIDE",
    "DEFAULT_USER_THEME",
    "DEFAULT_VALIDATION_BACKTEST_MAX_OPEN_POSITIONS",
    "EPSILON_FOR_DIVISION",
    "EXPECTED_KEY_PARTS",
    "FEATURE_CORRELATION_THRESHOLD",
    "FEATURE_NEAR_ZERO",
    "FEATURE_SAFE_DIV",
    "HIGH_VELOCITY_DELTA_THRESHOLD",
    "HOURS_PER_YEAR",
    "LATENCY_P99_CRITICAL_MS",
    "LATENCY_P99_ROLLBACK_MS",
    "LATENCY_P99_WARNING_MS",
    "LEAD_CAP",
    "LIVE_SIGNAL_INNER_LATENCY_WARN_ENSEMBLE_MS",
    "LIVE_SIGNAL_INNER_LATENCY_WARN_SINGLE_MODEL_MS",
    "MAD_SCALE_FACTOR",
    "MAX_CARRY_DAYS",
    "MAX_FEATURES_LIMIT",
    "MIN_CANDLES_FOR_BACKTEST",
    "MIN_CANDLES_FOR_INDICATORS",
    "MIN_CARRY_DAYS",
    "ML_CONFIDENCE_PERCENT_DISPLAY_DECIMALS",
    "NEAR_ZERO_STD_THRESHOLD",
    "NOTIFICATION_INNER_KEY_FAILED",
    "NOTIFICATION_INNER_KEY_RATE_LIMITED",
    "NOTIFICATION_INNER_KEY_SENT",
    "NOTIFICATION_KEY_EMAIL_FAILED",
    "NOTIFICATION_KEY_EMAIL_RATE_LIMITED",
    "NOTIFICATION_KEY_EMAIL_SENT",
    "NOTIFICATION_KEY_TELEGRAM_FAILED",
    "NOTIFICATION_KEY_TELEGRAM_SENT",
    "PREDICTION_CLASS_BUY",
    "PREDICTION_CLASS_HOLD",
    "PREDICTION_CLASS_SELL",
    "REDBEAT_KEY_PREFIX",
    "RETRY_LOCK_KEY_PREFIX",
    "RETRY_LOCK_SCAN_PATTERN",
    "RETRY_LOCK_TTL_SECONDS",
    "SCHEDULE_CONFIG_REDIS_KEY",
    "SIGNAL_PUBSUB_CHANNEL",
    "STATUS_DEGRADED",
    "STATUS_HEALTHY",
    "STATUS_NOT_CONFIGURED",
    "STATUS_NOT_READY",
    "STATUS_READY",
    "STATUS_UNHEALTHY",
    "SUPPORTED_EXCHANGE_VALUES",
    "SUPPORTED_TIMEFRAME_VALUES",
    "SUPPORTED_USER_LOCALES",
    "SUPPORTED_USER_THEMES",
    "TELEGRAM_API_BASE_URL",
    "TELEGRAM_API_SEND_MESSAGE_PATH",
    "TELEGRAM_EXPLAIN_RATE_LIMIT_PER_MINUTE",
    "TELEGRAM_EXPLAIN_TIMEOUT_SECONDS",
    "TELEGRAM_GENERAL_RATE_LIMIT_PER_MINUTE",
    "TELEGRAM_PARSE_MODE_MARKDOWN",
    "TELEGRAM_POLLING_RESTART_DELAY_SEC",
    "TELEGRAM_POLLING_RESTART_LIMIT",
    "TELEGRAM_POLLING_STARTUP_BASE_DELAY_SEC",
    "TELEGRAM_POLLING_STARTUP_MAX_RETRIES",
    "TELEGRAM_SEND_MESSAGE_TIMEOUT_SEC",
    "TIMEFRAME_DELTA",
    "TIMEFRAME_MS",
    "TIMEFRAME_REGISTRY",
    "TRAINING_EXECUTE_JOB_EXPIRES",
    "TRAINING_LOCK_KEY_PREFIX",
    "TRAINING_LOCK_SCAN_PATTERN",
    "TRAINING_LOCK_TIMEOUT_SECONDS",
    "TRAINING_SOFT_TIME_LIMIT",
    "TRAINING_TASK_DISPATCH_EXPIRES",
    "TRAINING_TIME_LIMIT",
    "VALID_TIMEFRAMES_SIGNAL_AND_TRAINING",
    "VOLUME_SPIKE_THRESHOLD",
    "CarryPositionStatus",
    "CarryTickStatus",
    "TimeframeDefinition",
    "UserTheme",
    "build_retry_lock_key",
    "build_training_lock_key",
    "confidence_pct_to_threshold",
    "get_anomaly_latency_critical_ms",
    "get_anomaly_latency_warning_ms",
    "get_rollback_latency_threshold_ms",
    "get_supported_exchanges",
    "get_supported_timeframes",
    "live_signal_inner_latency_warn_ms",
    "notification_result_skeleton",
]
