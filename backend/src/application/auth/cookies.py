"""
Cookie helpers for web authentication.

WHY centralize:
- Keep cookie flags consistent across login/refresh/logout/OAuth.
- Avoid subtle security drift from duplicated set_cookie calls.
"""

import logging
from typing import TYPE_CHECKING

from src.infrastructure.config.settings import settings

if TYPE_CHECKING:
    from fastapi import Response

logger = logging.getLogger(__name__)


def _cookie_domain() -> str | None:
    """Return cookie domain, or None for a host-only cookie.

    OUTSIDE PRODUCTION/STAGING THE CONFIGURED DOMAIN IS IGNORED, and that is structural rather than
    a policy about tidy config. A cookie ``Domain`` is only meaningful on a registrable domain; local
    dev serves on ``localhost`` / ``127.0.0.1``, where no ``Domain`` value can ever match. The only
    correct answer locally is host-only, whatever the setting says.

    MEASURED 2026-08-20: ``AUTH_COOKIE_DOMAIN=".pulsai.live"`` reached a local ``.env`` (pulled from
    Railway) and every localhost login issued cookies scoped to the PRODUCTION domain. Browsers
    silently DISCARD such a cookie, so nothing was stored, ``/auth/refresh`` answered "Missing
    refresh token", and the app bounced back to login in every browser including incognito.
    Re-entering the password could not help. The login response BODY still carried valid tokens,
    which is why the token path looked healthy while the cookie path the browser uses was dead.

    Adding the key to the env puller's ``ENV_IDENTITY_KEYS`` stops THAT key arriving bare from THAT
    script. It does nothing about a hand-edited ``.env``, a stale shell export, a container default,
    or the next environment-specific key nobody has classified yet. Refusing the value here makes the
    whole class inert at the point of failure, however it got there.
    """
    domain = settings.auth_cookie_domain.strip()
    if not domain:
        return None
    if not (settings.is_production or settings.is_staging):
        logger.warning(
            "Ignoring auth_cookie_domain %r outside production/staging - a Domain attribute cannot "
            "match a localhost origin, and honouring it would silently discard every auth cookie.",
            domain,
        )
        return None
    return domain


def _cookie_secure() -> bool:
    """Use secure cookies in non-development environments."""
    return settings.is_production or settings.is_staging


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    *,
    persist_refresh: bool = True,
) -> None:
    """Set access and refresh cookies with secure defaults.

    When ``persist_refresh`` is False (user unchecked "remember me"), the refresh cookie is a
    browser session cookie (no Max-Age) so it is cleared when the browser session ends. Access
    token TTL is unchanged (short-lived JWT).
    """
    domain = _cookie_domain()
    secure = _cookie_secure()
    refresh_max_age = settings.refresh_token_expire_days * 24 * 60 * 60 if persist_refresh else None

    response.set_cookie(
        key=settings.auth_cookie_access_name,
        value=access_token,
        httponly=True,
        secure=secure,
        samesite=settings.auth_cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
        domain=domain,
    )
    # Path `/api` (not `/api/v1/auth/refresh`): browsers match the *request* path. Next.js serves
    # refresh at `/api/auth/refresh` while the backend route is `/api/v1/auth/refresh`; a narrow
    # path would omit the refresh cookie on proxied refresh calls.
    response.set_cookie(
        key=settings.auth_cookie_refresh_name,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite=settings.auth_cookie_samesite,
        max_age=refresh_max_age,
        path="/api",
        domain=domain,
    )


def set_csrf_cookie(
    response: Response,
    csrf_token: str,
    *,
    persist: bool = True,
) -> None:
    """Set readable CSRF cookie for double-submit validation."""
    domain = _cookie_domain()
    secure = _cookie_secure()
    csrf_max_age = settings.refresh_token_expire_days * 24 * 60 * 60 if persist else None
    response.set_cookie(
        key=settings.auth_cookie_csrf_name,
        value=csrf_token,
        httponly=False,
        secure=secure,
        samesite=settings.auth_cookie_samesite,
        max_age=csrf_max_age,
        path="/",
        domain=domain,
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear all auth-related cookies."""
    domain = _cookie_domain()
    response.delete_cookie(
        key=settings.auth_cookie_access_name,
        path="/",
        domain=domain,
    )
    response.delete_cookie(
        key=settings.auth_cookie_refresh_name,
        path="/api",
        domain=domain,
    )
    response.delete_cookie(
        key=settings.auth_cookie_csrf_name,
        path="/",
        domain=domain,
    )
