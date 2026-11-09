"""Coinglass v4 client behavior (httpx mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.derivatives.coinglass_client import (
    CoinglassClient,
    coinglass_symbol_from_ccxt,
    parse_coinglass_rows,
)
from src.infrastructure.derivatives.errors import (
    CoinglassAuthError,
    CoinglassNotConfiguredError,
    CoinglassPayloadError,
    CoinglassRateLimitError,
)
from src.shared.constants.coinglass import COINGLASS_DEFAULT_EXCHANGE


def _mock_response(*, status_code: int, body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=body)
    return resp


def test_coinglass_symbol_from_ccxt_maps_perp() -> None:
    assert coinglass_symbol_from_ccxt("BTC/USDT:USDT") == "BTCUSDT"
    assert coinglass_symbol_from_ccxt("ETH/USDT:USDT") == "ETHUSDT"


def test_parse_coinglass_rows_requires_time() -> None:
    with pytest.raises(CoinglassPayloadError):
        parse_coinglass_rows([{"open": "1"}], time_key="time")


def test_parse_coinglass_rows_sorts_ascending() -> None:
    rows = parse_coinglass_rows(
        [{"time": 2000, "close": "2"}, {"time": 1000, "close": "1"}],
        time_key="time",
    )
    assert [r["time"] for r in rows] == [1000, 2000]


def test_not_configured_raises() -> None:
    client = CoinglassClient(api_key="")
    with pytest.raises(CoinglassNotConfiguredError):
        client.fetch_open_interest_history(symbol="BTCUSDT", exchange=COINGLASS_DEFAULT_EXCHANGE, interval="1h")


def test_fetch_open_interest_success() -> None:
    body = {
        "code": "0",
        "msg": "success",
        "data": [{"time": 1000, "open": "1", "high": "2", "low": "0.5", "close": "1.5"}],
    }
    with patch(
        "src.infrastructure.derivatives.coinglass_client.httpx.get",
        return_value=_mock_response(status_code=200, body=body),
    ) as mock_get:
        client = CoinglassClient(api_key="tok")
        rows = client.fetch_open_interest_history(symbol="BTCUSDT", exchange=COINGLASS_DEFAULT_EXCHANGE, interval="1h", limit=10)

    assert len(rows) == 1
    assert rows[0]["close"] == "1.5"
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs["headers"]["CG-API-KEY"] == "tok"


def test_embedded_429_retries_then_succeeds() -> None:
    ok = {
        "code": "0",
        "msg": "success",
        "data": [{"time": 1000, "open": "1", "high": "2", "low": "0.5", "close": "1.5"}],
    }
    rate = {"code": "429", "msg": "Too Many Requests", "data": []}
    with patch(
        "src.infrastructure.derivatives.coinglass_client.httpx.get",
        side_effect=[
            _mock_response(status_code=200, body=rate),
            _mock_response(status_code=200, body=ok),
        ],
    ) as mock_get:
        client = CoinglassClient(api_key="tok", min_request_interval_seconds=0.0, max_retries=3)
        rows = client.fetch_open_interest_history(symbol="BTCUSDT", exchange=COINGLASS_DEFAULT_EXCHANGE, interval="1h", limit=10)
    assert len(rows) == 1
    assert mock_get.call_count == 2


def test_embedded_nonzero_code_raises_payload() -> None:
    body = {"code": "400", "msg": "bad", "data": []}
    with patch(
        "src.infrastructure.derivatives.coinglass_client.httpx.get",
        return_value=_mock_response(status_code=200, body=body),
    ):
        client = CoinglassClient(api_key="tok")
        with pytest.raises(CoinglassPayloadError):
            client.fetch_open_interest_history(symbol="BTCUSDT", exchange=COINGLASS_DEFAULT_EXCHANGE, interval="1h")


def test_http_401_raises_auth() -> None:
    with patch(
        "src.infrastructure.derivatives.coinglass_client.httpx.get",
        return_value=_mock_response(status_code=401, body={}),
    ):
        client = CoinglassClient(api_key="tok")
        with pytest.raises(CoinglassAuthError):
            client.fetch_open_interest_history(symbol="BTCUSDT", exchange=COINGLASS_DEFAULT_EXCHANGE, interval="1h")


def test_http_429_retries_then_raises() -> None:
    with patch(
        "src.infrastructure.derivatives.coinglass_client.httpx.get",
        return_value=_mock_response(status_code=429, body={}),
    ) as mock_get:
        client = CoinglassClient(api_key="tok", min_request_interval_seconds=0.0, max_retries=2)
        with pytest.raises(CoinglassRateLimitError):
            client.fetch_open_interest_history(symbol="BTCUSDT", exchange=COINGLASS_DEFAULT_EXCHANGE, interval="1h")
    assert mock_get.call_count == 2


def test_invalid_json_raises_payload() -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.json = MagicMock(side_effect=ValueError("not json"))
    with patch("src.infrastructure.derivatives.coinglass_client.httpx.get", return_value=resp):
        client = CoinglassClient(api_key="tok")
        with pytest.raises(CoinglassPayloadError, match="not valid JSON"):
            client.fetch_open_interest_history(symbol="BTCUSDT", exchange=COINGLASS_DEFAULT_EXCHANGE, interval="1h")


def test_non_list_data_raises_payload() -> None:
    body = {"code": "0", "msg": "success", "data": {"bad": True}}
    with patch(
        "src.infrastructure.derivatives.coinglass_client.httpx.get",
        return_value=_mock_response(status_code=200, body=body),
    ):
        client = CoinglassClient(api_key="tok")
        with pytest.raises(CoinglassPayloadError, match="must be a list"):
            client.fetch_open_interest_history(symbol="BTCUSDT", exchange=COINGLASS_DEFAULT_EXCHANGE, interval="1h")


def test_fetch_funding_rate_history_delegates_to_get() -> None:
    body = {"code": "0", "msg": "success", "data": [{"time": 1000, "close": "0.01"}]}
    with patch(
        "src.infrastructure.derivatives.coinglass_client.httpx.get",
        return_value=_mock_response(status_code=200, body=body),
    ) as mock_get:
        client = CoinglassClient(api_key="tok")
        rows = client.fetch_funding_rate_history(symbol="BTCUSDT", exchange=COINGLASS_DEFAULT_EXCHANGE, interval="4h", limit=5)
    assert len(rows) == 1
    assert "/funding-rate/" in mock_get.call_args.args[0]


def test_fetch_liquidation_history_success() -> None:
    body = {"code": "0", "msg": "success", "data": [{"time": 1000, "longLiquidationUsd": "1"}]}
    with patch(
        "src.infrastructure.derivatives.coinglass_client.httpx.get",
        return_value=_mock_response(status_code=200, body=body),
    ) as mock_get:
        client = CoinglassClient(api_key="tok")
        rows = client.fetch_liquidation_history(symbol="BTCUSDT", exchange=COINGLASS_DEFAULT_EXCHANGE, interval="1h")
    assert len(rows) == 1
    assert "/liquidation/" in mock_get.call_args.args[0]


def test_fetch_global_long_short_ratio_success() -> None:
    body = {"code": "0", "msg": "success", "data": [{"time": 1000, "longShortRatio": "1.2"}]}
    with patch(
        "src.infrastructure.derivatives.coinglass_client.httpx.get",
        return_value=_mock_response(status_code=200, body=body),
    ) as mock_get:
        client = CoinglassClient(api_key="tok")
        rows = client.fetch_global_long_short_ratio_history(symbol="BTCUSDT", exchange=COINGLASS_DEFAULT_EXCHANGE, interval="1h")
    assert len(rows) == 1
    assert "long-short" in mock_get.call_args.args[0]


def test_fetch_liquidation_heatmap_model3_success() -> None:
    body = {
        "code": "0",
        "msg": "success",
        "data": {
            "y_axis": [100.0],
            "liquidation_leverage_data": [[0, 0, 1.0]],
            "price_candlesticks": [],
        },
    }
    with patch(
        "src.infrastructure.derivatives.coinglass_client.httpx.get",
        return_value=_mock_response(status_code=200, body=body),
    ) as mock_get:
        client = CoinglassClient(api_key="tok")
        payload = client.fetch_liquidation_heatmap_model3(
            symbol="BTCUSDT",
            exchange=COINGLASS_DEFAULT_EXCHANGE,
            range_label="24h",
        )
    assert payload["y_axis"] == [100.0]
    assert "heatmap/model3" in mock_get.call_args.args[0]


def test_fetch_liquidation_heatmap_model3_plan_error() -> None:
    from src.infrastructure.derivatives.errors import CoinglassPlanError

    body = {"code": "400", "msg": "Professional plan required"}
    with patch(
        "src.infrastructure.derivatives.coinglass_client.httpx.get",
        return_value=_mock_response(status_code=200, body=body),
    ):
        client = CoinglassClient(api_key="tok")
        with pytest.raises(CoinglassPlanError):
            client.fetch_liquidation_heatmap_model3(symbol="BTCUSDT")


def test_is_configured_false_for_blank_key() -> None:
    client = CoinglassClient(api_key="   ")
    assert client.is_configured is False
