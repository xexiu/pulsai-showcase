"""Settings mixin — Security, CORS, Cookie auth, OAuth (sections 3, 5-7)."""

from typing import Final, Literal

from pydantic import Field, computed_field

INSECURE_DEFAULT_SECRET_KEY = "change-me-in-production-use-openssl-rand-hex-32"
MAX_NON_DEV_ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60
DEFAULT_NON_DEV_ACCESS_TOKEN_EXPIRE_MINUTES = 60
DEFAULT_DEVELOPMENT_ACCESS_TOKEN_EXPIRE_MINUTES = 43200

#: Hosts the hosting platform uses to call the app ITSELF, admitted whatever TRUSTED_HOSTS says.
#:
#: Railway gates a deploy on the service's healthcheck path and sends that request with this
#: Host header (docs.railway.com/deployments/healthchecks). Measured 2026-09-14: with no
#: healthcheck, prod /health answered 502 for 44s across one deploy; with a healthcheck that
#: TrustedHostMiddleware rejected -- prod's TRUSTED_HOSTS named no such host, probed at 400 --
#: every deploy would FAIL and prod would freeze on the old image with nothing reporting why.
#: So it is part of the allowlist by construction rather than something each env edit must
#: remember. A Railway-owned name cannot be used to inject a Host header for our own domains.
PLATFORM_HEALTHCHECK_HOSTS: Final[tuple[str, ...]] = ("healthcheck.railway.app",)


class SettingsSecurityMixin:
    # ═══════════════════════════════════════════════════════════════════════════

    secret_key: str = INSECURE_DEFAULT_SECRET_KEY
    # Fernet key (url-safe base64, 32 bytes) for encrypting user exchange API credentials at rest.
    # Empty in development: derived from secret_key (see exchange_key_encryption module).
    # REQUIRED in production — set EXCHANGE_KEY_ENCRYPTION_SECRET in env.
    exchange_key_encryption_secret: str = ""
    # Max JSON/body size for HTTP requests (bytes). Applied via MaxBodySizeMiddleware (Content-Length).
    max_request_body_bytes: int = 10 * 1024 * 1024  # 10 MiB
    # Secure-by-default in staging/production; development override applied via validator below.
    access_token_expire_minutes: int = DEFAULT_NON_DEV_ACCESS_TOKEN_EXPIRE_MINUTES
    refresh_token_expire_days: int = 30  # 30 days
    password_reset_token_expire_minutes: int = 30  # OWASP recommends 15-60 mins
    password_reset_rate_limit: int = 3  # Max reset requests per hour per email

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════

    # CORS (comma-separated string from .env, parsed via property)
    # LAN (192.168.x.x:3000) allowed in dev via regex in main.py; add to CORS_ORIGINS if needed
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001,http://localhost:8000"

    # Explicit CORS methods/headers (no "*" — reduces browser attack surface)
    cors_allow_methods: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    # Idempotency-Key: FE trading mutations (e.g. POST /api/v1/trading/orders) — required for browser preflight.
    cors_allow_headers: str = "Authorization,Content-Type,Accept,X-Request-ID,X-CSRF-Token,Idempotency-Key"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_allow_methods_list(self) -> list[str]:
        """Parse CORS allow_methods from comma-separated string."""
        return [m.strip() for m in self.cors_allow_methods.split(",") if m.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_allow_headers_list(self) -> list[str]:
        """Parse CORS allow_headers from comma-separated string."""
        return [h.strip() for h in self.cors_allow_headers.split(",") if h.strip()]

    # Trusted Host header (Host header injection / cache poisoning). Comma-separated.
    # Include testserver for pytest TestClient; production: api.example.com,example.com
    trusted_hosts: str = "localhost,127.0.0.1,testserver"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def trusted_hosts_list(self) -> list[str]:
        """Configured trusted hosts plus the platform healthcheck hosts, deduplicated, order kept."""
        configured = [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]
        return list(dict.fromkeys([*configured, *PLATFORM_HEALTHCHECK_HOSTS]))

    # Dev-only: CORS regex allowing LAN browsers (e.g. 192.168.x.x:3000) into the API
    # without forcing every developer to hand-edit CORS_ORIGINS. Applied ONLY when
    # environment == "development" (see src.main.create_app).
    # SoT: overrideable via CORS_DEV_LAN_ORIGIN_REGEX (e.g. 10.0.x network) without code change.
    #: Dev-only extra origins. Loopback is included because the app answers at BOTH
    #: http://localhost:3000 and http://127.0.0.1:3000, and allowing only the first makes the
    #: second fail with a bare net::ERR_FAILED and no Access-Control-Allow-Origin -- a symptom
    #: that reads as "the API is down" rather than "the origin was rejected" (measured
    #: 2026-09-06). Loopback is strictly narrower than the 192.168.0.0/16 range already here,
    #: and registry.py passes this regex to CORSMiddleware ONLY when environment is
    #: "development". Starlette applies it with fullmatch, so the alternation cannot be widened
    #: by a crafted origin.
    cors_dev_lan_origin_regex: str = r"http://(192\.168\.\d+\.\d+|127\.0\.0\.1):3000"

    # API bind host / port used by ``uvicorn.run`` when executing ``python -m src.main``.
    # Production deployments (Dockerfile / ASGI server configs) typically override these
    # via API_BIND_HOST / API_PORT env vars; defaults match the historical hardcoded values.
    api_bind_host: str = "0.0.0.0"  # noqa: S104 — SoT default; real bind decided at deploy time
    api_port: int = Field(default=8000, ge=1, le=65535)

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════

    auth_cookie_access_name: str = "pulsai_at"
    auth_cookie_refresh_name: str = "pulsai_rt"
    auth_cookie_csrf_name: str = "pulsai_csrf"
    auth_cookie_domain: str = ""
    auth_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    auth_csrf_header_name: str = "X-CSRF-Token"

    # OAuth state cookie (Starlette SessionMiddleware): short-lived, only needed
    # during the Google OAuth redirect/callback roundtrip. Separate from the main
    # auth cookies above so rotating it does not invalidate user sessions.
    oauth_session_cookie_name: str = "pulsai_session"
    oauth_session_max_age_seconds: int = Field(default=600, ge=1)
    # OAuth SessionMiddleware SameSite policy. Kept as a setting so the cross-site
    # redirect trade-off ("lax" allows Google's top-level redirect to carry the
    # cookie) is explicit and overrideable for stricter deployments.
    oauth_session_same_site: Literal["lax", "strict", "none"] = "lax"

    # OpenAPI docs mount paths. Hidden in production via ``create_app`` by comparing
    # ``environment`` to ``"production"``. Overrideable for staging debugging or to
    # relocate the docs behind an admin prefix.
    openapi_docs_url: str = "/docs"
    openapi_redoc_url: str = "/redoc"

    # ═══════════════════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════════════════
    # Get credentials from: https://console.cloud.google.com/apis/credentials
    # 1. Create OAuth 2.0 Client ID (Web application type)
    # 2. Authorized redirect URIs must match exactly (Google sends the auth code here):
    #    {api_public_url}/api/v1/auth/google/callback  # noqa: ERA001

    # WHY: Session cookie for OAuth state is set on the API host; redirect must hit the API.
    api_public_url: str = "http://localhost:8000"
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def google_oauth_redirect_uri(self) -> str:
        """Google OAuth redirect URI (must match Google Cloud Console + authorize_redirect)."""
        base = self.api_public_url.rstrip("/")
        return f"{base}/api/v1/auth/google/callback"

    @property
    def has_google_oauth(self) -> bool:
        """Check if Google OAuth is configured."""
        return bool(self.google_oauth_client_id and self.google_oauth_client_secret)

    # ═══════════════════════════════════════════════════════════════════════════
