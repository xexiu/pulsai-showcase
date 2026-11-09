"""Unit tests for shared ``now_ms`` helper.

Promotes the previously-duplicated ``int(time.time() * 1000)`` pattern into a
single SoT in ``src.shared.utils.datetime_utils`` so that integration tests can
monkeypatch one entry point (mirrors ``utc_now``'s contract).
"""

from __future__ import annotations

import time

from src.shared.utils import datetime_utils


def test_now_ms_returns_epoch_milliseconds_int() -> None:
    """Return value is an int close to ``time.time() * 1000`` at call time."""
    before = int(time.time() * 1000)
    result = datetime_utils.now_ms()
    after = int(time.time() * 1000)

    assert isinstance(result, int)
    assert before <= result <= after


def test_now_ms_is_monkeypatchable_single_entry_point(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Tests must be able to freeze ``now_ms`` via ``monkeypatch`` of the SoT."""
    monkeypatch.setattr(datetime_utils, "now_ms", lambda: 1_700_000_000_000)

    assert datetime_utils.now_ms() == 1_700_000_000_000
