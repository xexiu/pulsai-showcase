"""P8-M-7 (M-5 remediation): Settings SoT for API runtime bind / session / CORS dev regex.

Pre-P8 these values were hardcoded in ``src.main``:
- ``session_cookie="pulsai_session"``
- ``max_age=600`` (10 minutes)
- dev LAN origin regex literal ``r"http://192\\.168\\.\\d+\\.\\d+:3000"``
- ``host="0.0.0.0"`` + ``port=8000`` in ``uvicorn.run``

Moving them to :class:`Settings` lets ops tune per-environment (docker vs
kubernetes vs localhost) without touching code, and the defaults stay
identical to the prior literals — this is a backwards-compatible lift.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def settings_factory():  # type: ignore[no-untyped-def]
    """Build a fresh :class:`Settings` instance (bypasses the module-level cache)."""
    from src.infrastructure.config.settings import Settings

    return Settings


class TestOauthSessionSettings:
    def test_oauth_session_cookie_name_defaults_to_pulsai_session(self, settings_factory) -> None:  # type: ignore[no-untyped-def]
        s = settings_factory()
        assert s.oauth_session_cookie_name == "pulsai_session"

    def test_oauth_session_max_age_seconds_defaults_to_600(self, settings_factory) -> None:  # type: ignore[no-untyped-def]
        s = settings_factory()
        assert s.oauth_session_max_age_seconds == 600

    def test_oauth_session_max_age_must_be_positive(self, settings_factory, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from pydantic import ValidationError

        monkeypatch.setenv("OAUTH_SESSION_MAX_AGE_SECONDS", "0")
        with pytest.raises(ValidationError):
            settings_factory()

    def test_oauth_session_max_age_can_be_overridden(self, settings_factory, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setenv("OAUTH_SESSION_MAX_AGE_SECONDS", "1200")
        s = settings_factory()
        assert s.oauth_session_max_age_seconds == 1200


class TestCorsDevLanOriginRegex:
    def test_default_matches_localhost_lan_ipv4(self, settings_factory) -> None:  # type: ignore[no-untyped-def]
        import re

        s = settings_factory()
        pattern = re.compile(s.cors_dev_lan_origin_regex)
        assert pattern.fullmatch("http://192.168.1.42:3000") is not None
        assert pattern.fullmatch("http://192.168.11.29:3000") is not None

    def test_default_matches_loopback_ipv4(self, settings_factory) -> None:  # type: ignore[no-untyped-def]
        """127.0.0.1:3000 is a dev origin too, and leaving it out is a measured time sink.

        Measured 2026-09-06: the app answers at BOTH http://localhost:3000 and
        http://127.0.0.1:3000, but only the first was an allowed origin, so the second failed
        with a bare ``net::ERR_FAILED`` and no ``Access-Control-Allow-Origin`` header — a
        symptom that reads as "the API is down" rather than "the origin was rejected".

        Loopback is strictly narrower than the 192.168.0.0/16 range already allowed here, and
        this regex applies ONLY when environment == "development" (``registry.py`` passes None
        otherwise). Starlette matches it with ``fullmatch``, so the alternation cannot be
        widened by a crafted origin such as ``http://evil.example/?http://127.0.0.1:3000``.
        """
        import re

        s = settings_factory()
        pattern = re.compile(s.cors_dev_lan_origin_regex)
        assert pattern.fullmatch("http://127.0.0.1:3000") is not None

    def test_default_rejects_public_hosts(self, settings_factory) -> None:  # type: ignore[no-untyped-def]
        import re

        s = settings_factory()
        pattern = re.compile(s.cors_dev_lan_origin_regex)
        assert pattern.fullmatch("http://evil.example.com:3000") is None
        assert pattern.fullmatch("http://10.0.0.1:3000") is None

    def test_override_via_env(self, settings_factory, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        custom = r"http://10\.0\.\d+\.\d+:3000"
        monkeypatch.setenv("CORS_DEV_LAN_ORIGIN_REGEX", custom)
        s = settings_factory()
        assert s.cors_dev_lan_origin_regex == custom


class TestApiBindSettings:
    def test_api_bind_host_defaults_to_all_interfaces(self, settings_factory) -> None:  # type: ignore[no-untyped-def]
        s = settings_factory()
        assert s.api_bind_host == "0.0.0.0"  # noqa: S104 — SoT default lives here

    def test_api_port_defaults_to_8000(self, settings_factory) -> None:  # type: ignore[no-untyped-def]
        s = settings_factory()
        assert s.api_port == 8000

    def test_api_port_in_valid_tcp_range(self, settings_factory, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from pydantic import ValidationError

        monkeypatch.setenv("API_PORT", "70000")
        with pytest.raises(ValidationError):
            settings_factory()

    def test_api_port_zero_rejected(self, settings_factory, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        from pydantic import ValidationError

        monkeypatch.setenv("API_PORT", "0")
        with pytest.raises(ValidationError):
            settings_factory()
