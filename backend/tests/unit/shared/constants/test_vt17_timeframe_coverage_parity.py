"""Every hunt-band timeframe must be LEAFED or explicitly EXCLUDED. No silent holes.

Owner, 2026-08-14: *"this isnt dynamic?? so next time I add a new X or X,Y Timeframe(s), I need to
manually do hunting again???"*

Yes — and that was the defect. `HUNT_HIGH_TIMEFRAMES` / `HUNT_LOW_TIMEFRAMES` and
`frozen_by_timeframe.json` are two locations that must agree, with nothing enforcing it. It is the
owner's own bug-generator quote in the wild:

    "Give someone state and they'll have a bug one day, but teach them how to represent state in
     two separate locations that have to be kept in sync and they'll have bugs for a lifetime."

MEASURED 2026-08-14: the bands hold 4h/6h/8h/12h/1d + 5m/15m/30m/1h/2h. The leaves map holds
12h/1d/1h/3d/4h/8h. Five band timeframes had no leaf — and they were NOT the same kind of gap:

  * 5m / 15m / 30m — hunted and rejected (commit ab05227ef, "kill 5m/15m/30m"). A DECISION.
  * 2h / 6h        — never hunted at all. They joined the bands after the VT-17 hunt ran, so
                     there is no leaf and no kill record. Nobody chose this.

The distinction existed only in a COMMIT MESSAGE, so no check could tell "tested and rejected"
from "never tested" — which is why 2h/6h sat unexamined and the chart 404'd on them looking
exactly like the deliberate ones.

This test is the mechanism the quote demands: adding a timeframe to a band now FAILS the build
until someone either ships a leaf or records an explicit exclusion with a reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.shared.constants.hunt_timeframes import HUNT_HIGH_TIMEFRAMES, HUNT_LOW_TIMEFRAMES
from src.shared.constants.research_loop_paths import vt_17_momentum_frozen_by_timeframe_path


def _config() -> dict:
    path: Path = vt_17_momentum_frozen_by_timeframe_path()
    assert path.exists(), f"VT-17 frozen leaves config missing: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_config_is_readable_and_has_leaves() -> None:
    """Guard the guard: a parity test that cannot find its counterpart is not a guard at all."""
    config = _config()

    assert isinstance(config.get("leaves"), dict)
    assert config["leaves"], "leaves map is empty — every timeframe would read as an untested hole"


def test_every_band_timeframe_is_leafed_or_explicitly_excluded() -> None:
    """THE MECHANISM. A new band timeframe fails here until it is hunted or explicitly excluded."""
    config = _config()
    leaves = set(config.get("leaves") or {})
    excluded = set(config.get("excluded_timeframes") or {})
    band = set(HUNT_HIGH_TIMEFRAMES) | set(HUNT_LOW_TIMEFRAMES)

    unaccounted = sorted(band - leaves - excluded)

    assert not unaccounted, (
        f"timeframes in the hunt band with no VT-17 leaf and no recorded exclusion: {unaccounted}. "
        "Either run the per-TF lookback hunt and ship a leaf, or add an `excluded_timeframes` "
        "entry naming WHY it is not deployable. Silence cannot distinguish 'never tested' from "
        "'tested and rejected' — which is exactly how 2h/6h went unexamined."
    )


def test_an_exclusion_must_state_a_reason() -> None:
    """An exclusion with no reason is the same silence in a different key."""
    excluded = _config().get("excluded_timeframes") or {}

    for timeframe, entry in excluded.items():
        assert isinstance(entry, dict), f"{timeframe}: exclusion must be an object with a reason"
        reason = str(entry.get("reason") or "").strip()
        assert len(reason) >= 10, f"{timeframe}: exclusion needs a real reason, got {reason!r}"


def test_a_timeframe_is_never_both_leafed_and_excluded() -> None:
    """Contradictory state is worse than missing state: the reader cannot tell which is true."""
    config = _config()
    both = sorted(set(config.get("leaves") or {}) & set(config.get("excluded_timeframes") or {}))

    assert not both, f"timeframes both deployed and excluded: {both}"


@pytest.mark.parametrize("timeframe", sorted(set(HUNT_HIGH_TIMEFRAMES) | set(HUNT_LOW_TIMEFRAMES)))
def test_each_band_timeframe_individually(timeframe: str) -> None:
    """Named per timeframe so a failure says WHICH slot is unaccounted for, not just 'some'."""
    config = _config()

    assert timeframe in (config.get("leaves") or {}) or timeframe in (config.get("excluded_timeframes") or {}), (
        f"{timeframe} is in the hunt band but has neither a VT-17 leaf nor a recorded exclusion"
    )
