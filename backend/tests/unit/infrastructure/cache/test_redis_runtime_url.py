"""Behavior tests for pytest-xdist Redis DB isolation."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.infrastructure.cache.redis_connections import resolve_redis_url


class TestResolveRedisUrl:
    def test_returns_settings_url_outside_tests(self) -> None:
        with (
            patch.dict(os.environ, {"TESTING": "false"}, clear=False),
            patch(
                "src.infrastructure.cache.redis_connections.settings.redis_url",
                "redis://localhost:6379/0",
            ),
        ):
            assert resolve_redis_url() == "redis://localhost:6379/0"

    def test_serial_test_run_uses_default_redis_db(self) -> None:
        env = {"TESTING": "true"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("PYTEST_XDIST_WORKER", None)
            with patch(
                "src.infrastructure.cache.redis_connections.settings.redis_url",
                "redis://localhost:6379",
            ):
                assert resolve_redis_url() == "redis://localhost:6379"

    @pytest.mark.parametrize(
        ("worker", "expected_path"),
        [
            ("gw0", "/1"),
            ("gw9", "/10"),
        ],
    )
    def test_xdist_worker_uses_dedicated_redis_db(self, worker: str, expected_path: str) -> None:
        with (
            patch.dict(os.environ, {"TESTING": "true", "PYTEST_XDIST_WORKER": worker}, clear=False),
            patch(
                "src.infrastructure.cache.redis_connections.settings.redis_url",
                "redis://localhost:6379/0",
            ),
        ):
            assert resolve_redis_url() == f"redis://localhost:6379{expected_path}"
