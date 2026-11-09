"""
Sync Coinglass API v4 client for research ingestion.

Auth: CG-API-KEY header. Base: https://open-api-v4.coinglass.com

Security: never log the API key.
@see https://docs.coinglass.com/reference/endpoint-overview
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Any

import httpx

from src.infrastructure.derivatives.errors import (
    CoinglassAuthError,
    CoinglassHTTPError,
    CoinglassNotConfiguredError,
    CoinglassPayloadError,
    CoinglassPlanError,
    CoinglassRateLimitError,
)
from src.shared.constants.coinglass import (
    COINGLASS_API_MAX_LIMIT,
    COINGLASS_DEFAULT_BASE_URL,
    COINGLASS_DEFAULT_EXCHANGE,
    COINGLASS_HTTP_MAX_RETRIES,
    COINGLASS_HTTP_RETRY_BASE_S,
    COINGLASS_MIN_REQUEST_INTERVAL_S,
)


def coinglass_symbol_from_ccxt(symbol: str) -> str:
    """Map ccxt perp symbol (BTC/USDT:USDT) to Coinglass pair (BTCUSDT)."""
    base = symbol.split(":", maxsplit=1)[0]
    return base.replace("/", "")


def parse_coinglass_rows(rows: list[dict[str, Any]], *, time_key: str = "time") -> list[dict[str, Any]]:
    """Validate and sort ascending by timestamp ms."""
    out: list[dict[str, Any]] = []
    for row in rows:
        if time_key not in row:
            raise CoinglassPayloadError(f"Coinglass row missing {time_key!r}")
        out.append(row)
    out.sort(key=lambda r: int(r[time_key]))
    return out


def _coinglass_plan_message(msg: str, path: str) -> CoinglassPlanError:
    return CoinglassPlanError(msg, required_plan="Professional", endpoint=path)


def _coinglass_auth_from_http(response: httpx.Response, path: str) -> CoinglassAuthError | CoinglassPlanError:
    msg = f"Coinglass HTTP {response.status_code}"
    try:
        body = response.json()
        if isinstance(body, dict) and body.get("msg"):
            msg = str(body["msg"])
    except ValueError:
        pass
    if response.status_code == HTTPStatus.FORBIDDEN or "plan" in msg.lower():
        return _coinglass_plan_message(msg, path)
    return CoinglassAuthError(msg, status_code=response.status_code)


class CoinglassClient:
    """Fetch multi-year derivatives history (OI, funding, liquidations, L/S ratio)."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = COINGLASS_DEFAULT_BASE_URL,
        timeout_seconds: float = 30.0,
        min_request_interval_seconds: float = COINGLASS_MIN_REQUEST_INTERVAL_S,
        max_retries: int = COINGLASS_HTTP_MAX_RETRIES,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._min_interval = min_request_interval_seconds
        self._max_retries = max(1, max_retries)
        self._last_request_at = 0.0

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        return {"accept": "application/json", "CG-API-KEY": self._api_key}

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_at = time.monotonic()

    def _fetch_envelope(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.is_configured:
            raise CoinglassNotConfiguredError("COINGLASS_API_KEY is not set")

        url = f"{self._base_url}{path}"
        last_err: Exception | None = None
        for attempt in range(self._max_retries):
            self._throttle()
            response = httpx.get(url, headers=self._headers(), params=params, timeout=self._timeout)

            if response.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise _coinglass_auth_from_http(response, path)

            if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
                last_err = CoinglassRateLimitError("Coinglass HTTP 429", status_code=429)
                time.sleep(COINGLASS_HTTP_RETRY_BASE_S * (2**attempt))
                continue

            if response.status_code >= HTTPStatus.BAD_REQUEST:
                raise CoinglassHTTPError(
                    f"Coinglass HTTP {response.status_code}",
                    status_code=response.status_code,
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise CoinglassPayloadError("Coinglass response was not valid JSON") from exc

            if not isinstance(payload, dict):
                raise CoinglassPayloadError("Coinglass response must be a JSON object")

            code = payload.get("code")
            if str(code) != "0":
                msg = str(payload.get("msg", "Coinglass error"))
                if str(code) == "429" or "too many" in msg.lower():
                    last_err = CoinglassRateLimitError(msg, status_code=429)
                    time.sleep(COINGLASS_HTTP_RETRY_BASE_S * (2**attempt))
                    continue
                if "plan" in msg.lower() or "professional" in msg.lower():
                    raise _coinglass_plan_message(msg, path)
                raise CoinglassPayloadError(f"Coinglass code={code}: {msg}")

            return payload

        if last_err is not None:
            raise last_err
        raise CoinglassRateLimitError("Coinglass rate limit exhausted retries", status_code=429)

    def _get(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        data = self._fetch_envelope(path, params).get("data")
        if not isinstance(data, list):
            raise CoinglassPayloadError("Coinglass data must be a list")
        return parse_coinglass_rows([r for r in data if isinstance(r, dict)])

    def _get_object(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET endpoint whose ``data`` field is a JSON object (e.g. heatmap Model3)."""
        data = self._fetch_envelope(path, params).get("data")
        if not isinstance(data, dict):
            raise CoinglassPayloadError("Coinglass data must be a JSON object")
        return data

    def fetch_open_interest_history(
        self,
        *,
        symbol: str,
        exchange: str = COINGLASS_DEFAULT_EXCHANGE,
        interval: str = "1h",
        limit: int = COINGLASS_API_MAX_LIMIT,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "exchange": exchange,
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, COINGLASS_API_MAX_LIMIT),
            "unit": "usd",
        }
        if start_time_ms is not None:
            params["start_time"] = start_time_ms
        if end_time_ms is not None:
            params["end_time"] = end_time_ms
        return self._get("/api/futures/open-interest/history", params)

    def fetch_funding_rate_history(
        self,
        *,
        symbol: str,
        exchange: str = COINGLASS_DEFAULT_EXCHANGE,
        interval: str = "1h",
        limit: int = COINGLASS_API_MAX_LIMIT,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "exchange": exchange,
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, COINGLASS_API_MAX_LIMIT),
        }
        if start_time_ms is not None:
            params["start_time"] = start_time_ms
        if end_time_ms is not None:
            params["end_time"] = end_time_ms
        return self._get("/api/futures/funding-rate/history", params)

    def fetch_liquidation_history(
        self,
        *,
        symbol: str,
        exchange: str = COINGLASS_DEFAULT_EXCHANGE,
        interval: str = "1h",
        limit: int = COINGLASS_API_MAX_LIMIT,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "exchange": exchange,
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, COINGLASS_API_MAX_LIMIT),
        }
        if start_time_ms is not None:
            params["start_time"] = start_time_ms
        if end_time_ms is not None:
            params["end_time"] = end_time_ms
        return self._get("/api/futures/liquidation/history", params)

    def fetch_global_long_short_ratio_history(
        self,
        *,
        symbol: str,
        exchange: str = COINGLASS_DEFAULT_EXCHANGE,
        interval: str = "1h",
        limit: int = COINGLASS_API_MAX_LIMIT,
        start_time_ms: int | None = None,
        end_time_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "exchange": exchange,
            "symbol": symbol,
            "interval": interval,
            "limit": min(limit, COINGLASS_API_MAX_LIMIT),
        }
        if start_time_ms is not None:
            params["start_time"] = start_time_ms
        if end_time_ms is not None:
            params["end_time"] = end_time_ms
        return self._get("/api/futures/global-long-short-account-ratio/history", params)

    def fetch_liquidation_heatmap_model3(
        self,
        *,
        symbol: str,
        exchange: str = COINGLASS_DEFAULT_EXCHANGE,
        range_label: str = "24h",
    ) -> dict[str, Any]:
        """Liquidation heatmap Model3 — requires Coinglass Professional+ plan."""
        params: dict[str, Any] = {
            "exchange": exchange,
            "symbol": symbol,
            "range": range_label,
        }
        return self._get_object("/api/futures/liquidation/heatmap/model3", params)

    def fetch_series_years(
        self,
        fetcher: Any,
        *,
        symbol: str,
        exchange: str,
        interval: str,
        years: int,
    ) -> list[dict[str, Any]]:
        """Paginate backward in 1000-bar chunks until `years` of history or empty."""
        end_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
        start_ms = int((datetime.now(tz=UTC) - timedelta(days=int(365.25 * years))).timestamp() * 1000)
        merged: dict[int, dict[str, Any]] = {}
        cursor_end = end_ms
        for _ in range(200):
            batch = fetcher(
                symbol=symbol,
                exchange=exchange,
                interval=interval,
                limit=COINGLASS_API_MAX_LIMIT,
                end_time_ms=cursor_end,
            )
            if not batch:
                break
            earliest = int(batch[0]["time"])
            for row in batch:
                merged[int(row["time"])] = row
            if earliest <= start_ms or len(batch) < COINGLASS_API_MAX_LIMIT:
                break
            cursor_end = earliest - 1
        return [merged[t] for t in sorted(merged) if t >= start_ms]
