"""epoch_ms: the same epoch milliseconds for every input kind, and a datetime input is read, never re-parsed.

IMPORTERS / CALLERS: pytest. AFFECTED API: src/shared/utils/datetime_utils.epoch_ms. DATA SCHEMAS: none.

RECORD-1S (2026-10-16): the live map spent 4.1 of its ~5 ms per call in `pd.to_datetime(index, utc=True)` on an index
that was already a UTC DatetimeIndex -- 100x the 0.04 ms the epoch read itself takes, on every call of 31 sites.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.shared.utils.datetime_utils import epoch_ms


def _reference(values: pd.Index | pd.Series) -> np.ndarray:
    """The conversion as it always was: parse to UTC, then declare the ms unit."""
    return np.asarray(pd.DatetimeIndex(pd.to_datetime(values, utc=True)).as_unit("ms").astype("int64"), dtype=np.int64)


_STAMPS = pd.date_range("2024-03-30 22:00:00.123456", periods=240, freq="37min")  # crosses a DST change in Madrid
CASES = {
    "aware-utc-us": _STAMPS.tz_localize("UTC").as_unit("us"),
    "aware-madrid-ns": _STAMPS.tz_localize("UTC").tz_convert("Europe/Madrid").as_unit("ns"),
    "naive-ns": _STAMPS.as_unit("ns"),
    "naive-s": _STAMPS.as_unit("s"),
    "series-aware": pd.Series(_STAMPS.tz_localize("UTC")),
    "series-naive": pd.Series(_STAMPS),
    "with-nat": pd.DatetimeIndex([_STAMPS[0], pd.NaT, _STAMPS[5]]).tz_localize("UTC"),
    "iso-strings": pd.Index([s.isoformat() for s in _STAMPS[:20]]),
}


@pytest.mark.parametrize("name", list(CASES))
def test_every_input_kind_gives_the_same_epoch_ms_as_always(name: str) -> None:
    values = CASES[name]
    got = epoch_ms(values)
    assert got.dtype == np.int64
    np.testing.assert_array_equal(got, _reference(values))


def test_a_datetime_input_is_read_without_being_parsed_again(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_parse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a DatetimeIndex was sent through pd.to_datetime")

    monkeypatch.setattr(pd, "to_datetime", no_parse)
    for name in ("aware-utc-us", "aware-madrid-ns", "naive-ns", "series-aware", "series-naive", "with-nat"):
        assert len(epoch_ms(CASES[name])) == len(CASES[name])
