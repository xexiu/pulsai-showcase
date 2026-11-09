"""Auth cookie helpers — session vs persistent refresh policy."""

from unittest.mock import MagicMock

from src.application.auth.cookies import set_auth_cookies, set_csrf_cookie
from src.application.auth.jwt import JWTService
from src.infrastructure.config.settings import settings


def test_refresh_cookie_path_matches_browser_proxy_and_direct_api() -> None:
    """Refresh must be sent on Next.js `/api/auth/refresh` (rewrites to `/api/v1/auth/refresh`).

    A cookie with path `/api/v1/auth/refresh` is NOT included on `/api/auth/refresh`, so refresh
    breaks after access JWT expiry (~30m) when using the same-origin proxy.
    """
    response = MagicMock()
    set_auth_cookies(response, "access-jwt", "refresh-jwt", persist_refresh=True)

    refresh_call = next(c for c in response.set_cookie.call_args_list if c.kwargs.get("key") == settings.auth_cookie_refresh_name)
    assert refresh_call.kwargs.get("path") == "/api"


def test_set_auth_cookies_session_mode_uses_none_max_age_on_refresh_cookie() -> None:
    response = MagicMock()
    set_auth_cookies(response, "access-jwt", "refresh-jwt", persist_refresh=False)

    refresh_call = next(c for c in response.set_cookie.call_args_list if c.kwargs.get("key") == settings.auth_cookie_refresh_name)
    assert refresh_call.kwargs.get("max_age") is None

    access_call = next(c for c in response.set_cookie.call_args_list if c.kwargs.get("key") == settings.auth_cookie_access_name)
    assert access_call.kwargs.get("max_age") == settings.access_token_expire_minutes * 60


def test_set_csrf_cookie_session_mode_uses_none_max_age() -> None:
    response = MagicMock()
    set_csrf_cookie(response, "csrf-val", persist=False)

    assert response.set_cookie.call_count == 1
    assert response.set_cookie.call_args.kwargs.get("max_age") is None


def test_refresh_jwt_persist_claim_round_trips() -> None:
    svc = JWTService(
        secret_key="unit-test-jwt-secret-key-32bytes-min",
        access_token_expire_minutes=15,
        refresh_token_expire_days=7,
    )
    token = svc.create_refresh_token("user-1", persist_refresh=False)
    payload = svc.verify_token(token, expected_type="refresh")

    assert payload is not None
    assert payload.persist_refresh is False

    token_default = svc.create_refresh_token("user-2")
    payload_default = svc.verify_token(token_default, expected_type="refresh")

    assert payload_default is not None
    assert payload_default.persist_refresh is True
