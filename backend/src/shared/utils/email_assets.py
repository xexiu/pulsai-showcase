"""Resolve routable email asset origins (no infrastructure imports)."""

from __future__ import annotations

from src.shared.constants.email_assets import (
    DEFAULT_LOCAL_FRONTEND_URL,
    DEFAULT_PUBLIC_ASSET_BASE,
    LOCALHOST_ASSET_BASE_MARKERS,
)


def is_local_email_asset_base(asset_base: str) -> bool:
    """Return True when *asset_base* is empty or points at a dev-only host."""
    normalized = (asset_base or "").strip().rstrip("/").lower()
    if not normalized:
        return True
    if normalized == DEFAULT_LOCAL_FRONTEND_URL.rstrip("/").lower():
        return True
    return any(marker in normalized for marker in LOCALHOST_ASSET_BASE_MARKERS)


def resolve_email_asset_base(asset_base: str) -> str:
    """Return a routable HTTPS origin for inline email assets."""
    if is_local_email_asset_base(asset_base):
        return DEFAULT_PUBLIC_ASSET_BASE
    return asset_base.rstrip("/")
