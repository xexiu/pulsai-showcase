"""GET /config/public exposes registry-backed timeframe metadata."""

from typing import TYPE_CHECKING

from src.shared.constants.timeframes import TIMEFRAME_LABELS, TIMEFRAME_REGISTRY

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def test_config_public_includes_timeframe_options(client: TestClient) -> None:
    response = client.get("/api/v1/config/public")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "timeframe_options" in data
    options = data["timeframe_options"]
    assert isinstance(options, list)
    assert len(options) == len(data["timeframes"])
    for opt in options:
        assert opt["value"] in TIMEFRAME_REGISTRY
        assert opt["ms"] == TIMEFRAME_REGISTRY[opt["value"]].milliseconds
        assert opt["label"] == TIMEFRAME_LABELS[opt["value"]]
    values = [o["value"] for o in options]
    assert values == data["timeframes"]
