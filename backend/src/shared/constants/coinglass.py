"""Coinglass API v4 constants (research + infrastructure)."""

from __future__ import annotations

# Coinglass exchange label (not ccxt enum) — SoT for client defaults and panel ingest.
COINGLASS_DEFAULT_EXCHANGE: str = "Binance"

COINGLASS_CROSS_VENUE_EXCHANGES: tuple[str, ...] = ("Binance", "Bybit", "OKX")

# API client defaults — align with COINGLASS_BASE_URL in apps/api/.env.example and settings.
COINGLASS_DEFAULT_BASE_URL: str = "https://open-api-v4.coinglass.com"

# History pagination: Coinglass v4 max rows per request.
COINGLASS_API_MAX_LIMIT: int = 1000

# Rows with time < this value are treated as seconds and scaled to ms.
COINGLASS_TIME_MS_THRESHOLD: int = 1_000_000_000_000

# Client-side throttle between requests (paid tier still rate-limits).
COINGLASS_MIN_REQUEST_INTERVAL_S: float = 1.2

# HTTP retry policy for 429 / embedded rate-limit codes.
COINGLASS_HTTP_MAX_RETRIES: int = 6
COINGLASS_HTTP_RETRY_BASE_S: float = 2.0
