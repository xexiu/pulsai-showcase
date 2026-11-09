"""Smoke tests: SettingsIntegrationsMixin Binance section (Slice 1a).

Pins the contract of the ``binance_api_base_url`` knob added for the Cloudflare
Worker REST proxy: empty by default (feature OFF, direct ``api.binance.com``),
loadable from env var ``BINANCE_API_BASE_URL``, type ``str``. See
``apps/api/src/infrastructure/exchange/binance_rest_url_override.py`` for the
consumer.
"""

from __future__ import annotations

import pytest  # noqa: TC002

from src.infrastructure.config.settings import Settings


def test_binance_api_base_url_defaults_to_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature OFF by default. Local dev + un-migrated services keep their
    direct ``api.binance.com`` traffic. Only services with an explicit env var
    route through the Cloudflare Worker proxy.

    The env var is CLEARED first. A test that asserts a DEFAULT while `Settings()` still reads
    the ambient environment is asserting the developer's shell, not the default: measured
    2026-08-19 on a machine that exports the production `BINANCE_API_BASE_URL`, this failed with
    the Cloudflare worker URL. Same shape as the `TRUSTED_HOSTS` leak that made 118 API tests
    vacuous — there the ambient value made tests pass for the wrong reason; here it makes them
    fail for the wrong reason, and both hide what the code actually does.
    """
    monkeypatch.delenv("BINANCE_API_BASE_URL", raising=False)

    s = Settings(environment="development")

    assert s.binance_api_base_url == ""


def test_binance_api_base_url_loaded_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operators set ``BINANCE_API_BASE_URL`` on the Railway service to opt in.
    Pydantic-settings auto-loads it from the env (mixin pattern)."""
    monkeypatch.setenv("BINANCE_API_BASE_URL", "https://binance-proxy.example.workers.dev")

    s = Settings(environment="development")

    assert s.binance_api_base_url == "https://binance-proxy.example.workers.dev"


def test_binance_api_base_url_is_string_type() -> None:
    """Type contract: string, not URL object. The consuming helper does its
    own validation (rstrip-slash, prefix-match against the default host)."""
    s = Settings(environment="development", binance_api_base_url="https://x.example/")

    assert isinstance(s.binance_api_base_url, str)


# ─────────────────────────────────────────────────────────────────────────────
# Slice 1b — binance_ws_base_url
# ─────────────────────────────────────────────────────────────────────────────


def test_binance_ws_base_url_defaults_to_empty_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feature OFF by default — direct ``wss://stream.binance.com:9443``.

    Env cleared for the same reason as the REST default above: otherwise this asserts whatever
    the developer's shell exports.
    """
    monkeypatch.delenv("BINANCE_WS_BASE_URL", raising=False)

    s = Settings(environment="development")

    assert s.binance_ws_base_url == ""


def test_binance_ws_base_url_loaded_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Operators set ``BINANCE_WS_BASE_URL`` to opt in. Same Worker hostname
    as REST but ``wss://`` scheme."""
    monkeypatch.setenv("BINANCE_WS_BASE_URL", "wss://binance-proxy.example.workers.dev")

    s = Settings(environment="development")

    assert s.binance_ws_base_url == "wss://binance-proxy.example.workers.dev"
