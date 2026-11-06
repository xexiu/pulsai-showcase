"""
Health and readiness probe constants.

Single source of truth for status strings and DB probe so health.py, admin health,
and worker health checks do not drift. No magic strings in endpoints.

@see docs/04-structural/CODING_STANDARDS.md — no hardcoded literals
"""

# Readiness / liveness status (K8s, load balancers)
STATUS_READY = "ready"
STATUS_NOT_READY = "not_ready"

# Service health status (admin dashboard, ServiceStatus)
STATUS_HEALTHY = "healthy"
STATUS_UNHEALTHY = "unhealthy"
STATUS_DEGRADED = "degraded"
STATUS_NOT_CONFIGURED = "not_configured"

# Database connectivity probe — one place so all probes use same query
# WHY SELECT 1: Minimal round-trip; validates connection and basic execution
DB_PROBE_SQL = "SELECT 1"

# Admin health summary: inference latency lookback (aggregate + per-production-TF table).
# WHY 24h: production TFs span 5m-1w; a 1h window hides 4h/1d/1w cadence and misleads ops.
HEALTH_SUMMARY_LATENCY_PERIOD_HOURS = 24
