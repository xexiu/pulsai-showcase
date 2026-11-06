"""OHLCV Polars-frame normalization helpers (SoT).

WHY: OHLCV frames carry the ``timestamp`` column either as epoch-milliseconds
(integer dtypes — raw exchange candles, the WS stream tail, the Redis cache) or already
as a Polars ``Datetime``. Any code that runs a temporal/``.dt`` operation (feature
calculation, charting) MUST normalize to ``Datetime`` first, or Polars raises
``InvalidOperationError: 'hour' operation not supported for dtype 'i64'``.

This was previously inlined at 4 call sites (the OHLCV service tier-access reader,
the historical fetcher, the Redis cache reader, and the stream-supervisor chart
precompute writer). The writer diverged once and silently broke supervisor
precompute — so the cast now lives in ONE place.
"""

from __future__ import annotations

from typing import Literal

import polars as pl

#: Canonical OHLCV timestamp column (SoT: src/shared/constants/ohlcv_columns.py).
OHLCV_TIMESTAMP_COLUMN = "timestamp"

#: Epoch unit the platform persists OHLCV timestamps in (exchange candles are ms).
#: Typed as a Literal so it satisfies polars ``from_epoch``'s ``time_unit`` overload.
_EPOCH_TIME_UNIT: Literal["ms"] = "ms"


def ensure_timestamp_datetime(df: pl.DataFrame, *, column: str = OHLCV_TIMESTAMP_COLUMN) -> pl.DataFrame:
    """Idempotently normalize an epoch-ms integer timestamp column to ``Datetime``.

    Uses ``dtype.is_integer()`` (not ``== Int64``) so ``UInt64`` / ``Int32`` tails
    from Polars inference or exchange round-trips still decode — a strict ``Int64``
    check allowed ``UInt64`` epoch-ms through and broke ``.dt.*`` temporal
    features with ``InvalidOperationError`` (weekday/hour on i64).

    No-op when the column is absent or already ``Datetime`` / non-integer.

    Args:
        df: OHLCV Polars frame that may carry ``column`` as epoch-ms integers or Datetime.
        column: Timestamp column name (defaults to the canonical ``timestamp``).

    Returns:
        The frame with ``column`` guaranteed to be a Polars ``Datetime`` when present.
    """
    if column not in df.columns:
        return df
    dtype = df[column].dtype
    if dtype.is_integer():
        return df.with_columns(pl.from_epoch(column, time_unit=_EPOCH_TIME_UNIT).alias(column))
    return df
