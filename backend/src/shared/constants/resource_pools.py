"""
Default connection pool sizes and lifecycle settings (CODING_STANDARDS §12).

WHY centralized:
- Tuning in one place; avoids magic numbers scattered across database/redis clients.
"""

DEFAULT_ASYNC_DB_POOL_SIZE = 5

#: How long a connection may sit IDLE INSIDE A TRANSACTION before Postgres kills it (ms).
#:
#: Sized against the failure it exists to bound. MEASURED 2026-08-27: one connection sat
#: `idle in transaction` on an OHLCV INSERT for 86 SECONDS, holding 1 of the 5 pool slots, while
#: an indexed `SELECT users.id` was logged at 42s and `/market/xs-trend-symbol-signal` at 91.6s
#: — all of it queueing for a free connection, since nothing was lock-blocked.
#:
#: 30s is far longer than any legitimate gap between statements in one transaction (the app's own
#: work is sub-second), and far shorter than the 86s leak. It bounds IDLE time only, so a slow
#: bulk insert that is actively working is never interrupted.
IDLE_IN_TRANSACTION_TIMEOUT_MS = 30_000
DEFAULT_ASYNC_DB_MAX_OVERFLOW = 10
DEFAULT_REDIS_MAX_CONNECTIONS = 50

# Sync engine (Celery workers) — tighter than async because each prefork
# child has its OWN pool, so total conns multiply by child count. With 4
# Celery service types each running 1-2 children, a tight per-child cap
# keeps the total under Postgres `max_connections` (see Finding H3 in
# docs/04-structural/PLAN_db_performance_followups.md).
DEFAULT_SYNC_DB_POOL_SIZE = 3
DEFAULT_SYNC_DB_MAX_OVERFLOW = 2

DEFAULT_POOL_RECYCLE_SECONDS = 1800
"""Recycle DB connections after 30 min to prevent stale/idle-timeout drops."""
