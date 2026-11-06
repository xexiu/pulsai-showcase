"""HTTP optimistic concurrency helpers (ETag/If-Match)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import HTTPException, status


def build_strong_etag(payload: dict[str, Any]) -> str:
    """Build a deterministic strong ETag from a JSON-serializable payload."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f'"{digest}"'


_PROXY_CONTENT_CODING_SUFFIXES = ("-gzip", "-br", "-deflate")
_WEAK_ETAG_PREFIX = "W/"
_MIN_QUOTED_ETAG_LEN = 2  # an opening and a closing double-quote


def _normalize_etag_for_compare(tag: str) -> str:
    """Reduce an ETag to its opaque core for proxy-tolerant If-Match comparison.

    Compressing edges (Cloudflare, nginx) rewrite a strong validator in transit — weakening it to
    ``W/"x"`` and/or appending a content-coding suffix (``"x-gzip"``). The browser echoes that
    transformed value back as ``If-Match``, so a byte-exact compare against the server's freshly
    built strong ETag can *never* match and every conditional write 412s. Normalising both sides to
    the opaque core (strip the weak prefix, the surrounding quotes, and a trailing coding suffix)
    restores the intended compare while still distinguishing genuinely different resources.
    """
    text = tag.strip()
    if text[: len(_WEAK_ETAG_PREFIX)].upper() == _WEAK_ETAG_PREFIX:
        text = text[len(_WEAK_ETAG_PREFIX) :].strip()
    if len(text) >= _MIN_QUOTED_ETAG_LEN and text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    for suffix in _PROXY_CONTENT_CODING_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    return text


def if_match_matches_current(*, if_match: str | None, current_etag: str) -> bool:
    """Return True when If-Match is absent or matches the current ETag.

    Tolerant of edge ETag rewriting (weak ``W/`` prefix, ``-gzip``/``-br`` content-coding suffix)
    so a Cloudflare/nginx-transformed validator still matches — see
    :func:`_normalize_etag_for_compare`. A genuinely different validator still fails.
    """
    if if_match is None:
        return True
    return _normalize_etag_for_compare(if_match) == _normalize_etag_for_compare(current_etag)


def assert_if_match_or_412(
    *,
    if_match: str | None,
    current_etag: str,
    resource_label: str,
) -> None:
    """Raise 412 when If-Match is present and does not match the current ETag."""
    if if_match_matches_current(if_match=if_match, current_etag=current_etag):
        return
    raise HTTPException(
        status_code=status.HTTP_412_PRECONDITION_FAILED,
        detail=f"Precondition failed: stale {resource_label}. Refresh and retry.",
    )
