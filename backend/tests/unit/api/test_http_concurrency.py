"""Unit tests for ETag / If-Match helpers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.api.http_concurrency import (
    assert_if_match_or_412,
    build_strong_etag,
    if_match_matches_current,
)


def test_build_strong_etag_is_deterministic() -> None:
    payload = {"a": 1, "b": [2, 3]}
    assert build_strong_etag(payload) == build_strong_etag({"b": [2, 3], "a": 1})


def test_if_match_matches_when_absent() -> None:
    assert if_match_matches_current(if_match=None, current_etag='"abc"') is True


def test_if_match_matches_when_equal() -> None:
    etag = build_strong_etag({"x": 1})
    assert if_match_matches_current(if_match=etag, current_etag=etag) is True


def test_if_match_fails_when_stale() -> None:
    etag = build_strong_etag({"x": 1})
    assert if_match_matches_current(if_match='"stale"', current_etag=etag) is False


def test_if_match_matches_weak_prefix_from_proxy() -> None:
    # Cloudflare weakens a strong validator in transit; the client echoes ``W/"…"`` back.
    etag = build_strong_etag({"x": 1})
    assert if_match_matches_current(if_match=f"W/{etag}", current_etag=etag) is True
    assert if_match_matches_current(if_match=f"w/{etag}", current_etag=etag) is True


def test_if_match_matches_gzip_suffix_from_proxy() -> None:
    # nginx appends a content-coding suffix inside the tag for compressed responses.
    digest = build_strong_etag({"x": 1}).strip('"')
    assert if_match_matches_current(if_match=f'"{digest}-gzip"', current_etag=f'"{digest}"') is True


def test_if_match_matches_weak_and_gzip_combined() -> None:
    digest = build_strong_etag({"x": 1}).strip('"')
    assert if_match_matches_current(if_match=f'W/"{digest}-gzip"', current_etag=f'"{digest}"') is True


def test_if_match_still_fails_for_genuinely_different_etag_even_when_weak() -> None:
    etag = build_strong_etag({"x": 1})
    assert if_match_matches_current(if_match='W/"different-gzip"', current_etag=etag) is False


def test_assert_if_match_or_412_accepts_proxy_weakened_etag() -> None:
    etag = build_strong_etag({"x": 1})
    # Must NOT raise: the validator only differs by the proxy's weak prefix.
    assert_if_match_or_412(if_match=f"W/{etag}", current_etag=etag, resource_label="config")


def test_assert_if_match_or_412_raises_on_stale() -> None:
    etag = build_strong_etag({"x": 1})
    with pytest.raises(HTTPException) as exc_info:
        assert_if_match_or_412(if_match='"stale"', current_etag=etag, resource_label="config")
    assert exc_info.value.status_code == 412


def test_assert_if_match_or_412_noop_when_absent() -> None:
    assert_if_match_or_412(if_match=None, current_etag='"x"', resource_label="config")
