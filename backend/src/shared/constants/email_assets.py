"""SoT for email asset URLs and localhost detection (CODING_STANDARDS §12)."""

from __future__ import annotations

from typing import Final

# Default dev frontend origin — must NOT be used for inline email images in prod.
DEFAULT_LOCAL_FRONTEND_URL: Final[str] = "http://localhost:3000"

# Public origin for logo and other static assets when the configured base is local.
DEFAULT_PUBLIC_ASSET_BASE: Final[str] = "https://pulsai.live"

# Substrings that indicate a non-routable asset base for email clients.
LOCALHOST_ASSET_BASE_MARKERS: Final[tuple[str, ...]] = (
    "localhost",
    "127.0.0.1",
    "[::1]",
    "0.0.0.0",  # noqa: S104 — marker substring, not a bind address
)
