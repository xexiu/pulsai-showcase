"""Email asset-base resolution — broken-logo regression guard."""

from __future__ import annotations

from src.shared.constants.email_assets import DEFAULT_PUBLIC_ASSET_BASE
from src.shared.utils.email_assets import (
    is_local_email_asset_base,
    resolve_email_asset_base,
)


def test_localhost_frontend_url_is_detected_as_local() -> None:
    assert is_local_email_asset_base("http://localhost:3000") is True
    assert is_local_email_asset_base("http://127.0.0.1:3000") is True


def test_production_frontend_url_is_not_local() -> None:
    assert is_local_email_asset_base("https://pulsai.live") is False


def test_resolve_email_asset_base_falls_back_for_localhost() -> None:
    assert resolve_email_asset_base("http://localhost:3000") == DEFAULT_PUBLIC_ASSET_BASE


def test_resolve_email_asset_base_preserves_public_origin() -> None:
    assert resolve_email_asset_base("https://pulsai.live") == "https://pulsai.live"


def test_empty_asset_base_falls_back_to_public_origin() -> None:
    assert resolve_email_asset_base("") == DEFAULT_PUBLIC_ASSET_BASE
