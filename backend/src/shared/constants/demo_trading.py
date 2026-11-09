"""Demo trading SoT: order lifecycle states and append-only event types."""

from __future__ import annotations

from typing import Final

from src.shared.constants.http_idempotency import HTTP_IDEMPOTENCY_KEY_MAX_LEN

# Order lifecycle (demo_orders.status) — explicit strings for API/DB contract stability.
DEMO_ORDER_STATUS_PENDING = "pending"
DEMO_ORDER_STATUS_FILLED = "filled"
DEMO_ORDER_STATUS_CANCELLED = "cancelled"

# Append-only demo_trading_events.event_type (demo surface only; first rollout).
DEMO_EVENT_TRADE_EXECUTED = "trade_executed"

# Idempotency-Key header: max length we persist — re-export from the HTTP SoT so paper/demo/HTTP
# stay in lockstep (single source: ``http_idempotency.HTTP_IDEMPOTENCY_KEY_MAX_LEN``).
DEMO_IDEMPOTENCY_KEY_MAX_LEN: Final[int] = HTTP_IDEMPOTENCY_KEY_MAX_LEN
