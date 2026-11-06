"""
Rollback and anomaly latency policy constants (C.4/C.7 SoT).

Single source of truth for P99 latency thresholds used by:
- RollbackService (auto-rollback when latency exceeds threshold)
- AnomalyDetectionService (warning/critical latency drift)
- Performance/latency API (threshold_exceeded)

Per-model: get_rollback_latency_threshold_ms(symbol, timeframe) returns default
for now; can be extended to read from config/DB per model later.
"""

# Default P99 latency thresholds (ms)
# WHY 100ms rollback: Sustained high latency indicates model or infra degradation.
# WHY 50ms warning: Trading target is <50ms; above is worth alerting.
LATENCY_P99_ROLLBACK_MS = 100
"""P99 latency threshold for auto-rollback (sustained = model/infra issue)."""

LATENCY_P99_WARNING_MS = 50
"""P99 latency threshold for warning (above trading target)."""

LATENCY_P99_CRITICAL_MS = 100
"""P99 latency threshold for critical anomaly (same as rollback)."""


def get_rollback_latency_threshold_ms(symbol: str, timeframe: str) -> int:
    """
    Per-model rollback latency threshold (C.4).

    Returns threshold in ms. Default is global constant; later can read from
    config/DB per (symbol, timeframe) for stricter/looser models.
    """
    # SoT: single default; per-model overrides can be added via config
    _ = (symbol, timeframe)
    return LATENCY_P99_ROLLBACK_MS


def get_anomaly_latency_warning_ms(symbol: str, timeframe: str) -> int:
    """Per-model anomaly warning threshold (C.4)."""
    _ = (symbol, timeframe)
    return LATENCY_P99_WARNING_MS


def get_anomaly_latency_critical_ms(symbol: str, timeframe: str) -> int:
    """Per-model anomaly critical threshold (C.4)."""
    _ = (symbol, timeframe)
    return LATENCY_P99_CRITICAL_MS
