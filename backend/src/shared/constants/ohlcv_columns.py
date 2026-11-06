"""Canonical OHLCV DataFrame column contract — shared SoT.

WHY THIS MODULE EXISTS
----------------------
Until 2026-06-01, the OHLCV column set was duplicated/implied across at
least five sites — each layer carried its own private notion of the
schema, and the four producer tiers (namespaced Redis from the
supervisor, legacy Redis cache, Postgres repository, exchange fetcher)
diverged on whether ``is_closed`` was present or absent. That asymmetry
caused ``polars.exceptions.ComputeError: schema lengths differ`` at the
chart-display merge (verified in prod log 2026-06-01 06:30:04 on
``/api/v1/market/chart-indicators``).

This module promotes the canonical chart-display OHLCV column set to a
single source of truth so:

1. ``merge_chart_display_frames`` can project heterogeneous tier outputs
   to a uniform schema before ``pl.concat``, eliminating the bug class.
2. Future readers and serialisers can import the SoT instead of inlining
   a 6-tuple of strings (today's duplications live in
   ``ohlcv_cache.py``, ``ohlcv_repository.py``, ``ohlcv_fetcher_historical.py``,
   ``market_chart_serialization.py`` — they should adopt this SoT in a
   follow-up hygiene slice; out of scope here per surgical-changes rule).

WHY THIS IS A TUPLE, NOT A LIST
-------------------------------
The OHLCV chart-display contract is immutable across module loads — a
chart endpoint that started serving 6-col frames must not start serving
7-col frames mid-process because a list was mutated by reference. A
tuple makes accidental mutation a TypeError instead of a silent
data-shape change.

WHY ``is_closed`` IS NOT HERE
-----------------------------
``is_closed`` is a domain field of :class:`OHLCVBar` (see
``src/domain/ohlcv/closed_bar.py``) and is required by the live-signal
inference path. The supervisor writes it intentionally; the cache
preserves it on round-trip. **But the chart-display pipeline doesn't
read it** — chart consumers slice by timestamp, not by the closure
flag. Keeping ``is_closed`` out of the chart-display column set
prevents the supervisor's metadata from leaking into the FE chart
response AND eliminates the schema asymmetry at the merge.

Producers that need ``is_closed`` (the live-signal path) consume it via
the typed ``OHLCVBar`` API, not via the polars DataFrames in
``OHLCVService``. The two contracts are deliberately separate.
"""

from __future__ import annotations

from typing import Final

# Canonical chart-display column set. Order matters: matches the wire
# format used by ``GET /api/v1/market/chart-indicators`` and the JSON
# serialisation at ``market_chart_serialization.py``. Producers MUST
# return frames containing AT LEAST these columns (extras allowed at
# producer boundaries, but consumers should project to this set before
# any cross-tier merge or wire emission).
OHLCV_CHART_DISPLAY_COLUMNS: Final[tuple[str, ...]] = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
)

# Sibling SoT — the OHLC core (no volume). Used by callers that only
# need to assert the price-bar shape is well-formed and don't care about
# volume presence (e.g. the post-preprocess feature-consistency probe in
# ``api/routes/admin/feature_consistency_post_preprocess.py``, which
# samples first/last candles regardless of whether ``volume`` was
# stripped earlier in the pipeline). Derived from the parent SoT via
# slice so a column-set change in one place propagates automatically —
# the two tuples can never drift out of sync.
OHLC_CORE_COLUMNS: Final[tuple[str, ...]] = OHLCV_CHART_DISPLAY_COLUMNS[:-1]

# Sibling SoT -- the value columns of a frame whose INDEX carries the time (the pandas 1m frames).
# Derived by slice, like OHLC_CORE_COLUMNS, so it can never drift from the display columns.
OHLCV_VALUE_COLUMNS: Final[tuple[str, ...]] = OHLCV_CHART_DISPLAY_COLUMNS[1:]

# Sibling SoT -- the bar columns a feature overlay reads (high / low / close / volume, no open): the fifo_* and titan_*
# research overlays refuse a frame missing one. Two modules restated it until 8f (2026-10-20).
HLCV_COLUMNS: Final[tuple[str, ...]] = OHLCV_CHART_DISPLAY_COLUMNS[2:]


__all__ = ["HLCV_COLUMNS", "OHLCV_CHART_DISPLAY_COLUMNS", "OHLCV_VALUE_COLUMNS", "OHLC_CORE_COLUMNS"]
