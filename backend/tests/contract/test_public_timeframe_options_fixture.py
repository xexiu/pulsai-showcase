"""The timeframe fixture the front end's tests iterate MUST be what the backend serves.

IMPORTERS/CALLERS: none — a test module. It guards ``tests/fixtures/public_timeframe_options.json``,
which the apps/web incremental-fetch tests read.
AFFECTED API: none. DATA SCHEMAS: the fixture's ``options`` is the ``PublicTimeframeOption`` list
``GET /config/public`` serves ({value, ms, label}).

WHY THIS EXISTS. Owner, 2026-09-21: *"the test MUST test ALL timeframes and future added timeframes
-- SoT BE send to FE config timeframes"*. The incremental fetch (``since``) is timeframe-agnostic by
construction, but a test that parametrizes over a HAND-TYPED list proves that only for the list
someone remembered to type. Add ``7h`` to ``TIMEFRAME_REGISTRY`` and such a list keeps passing
while the new timeframe is never exercised -- the same shape as ``2h``/``6h`` being added to the
registry "and to NOTHING else" (``TimeframeBand``'s docstring records the cost).

So the backend tests iterate ``TIMEFRAME_REGISTRY`` directly, and the front end -- which has no
timeframe table of its own and takes ``ms`` from ``/config/public`` at runtime -- iterates this
fixture. This module is what stops that fixture from going stale: it is rebuilt from the SoT and
compared, and a registry change fails HERE, with the command to regenerate, before any front-end
test can quietly test yesterday's list.

The WHOLE registry, not only the default-served subset: ``1m`` is registered but opt-in
(``_DEFAULT_EXCLUDED_TIMEFRAMES``), and enabling it is exactly the "future timeframe" the owner
means. ``default_served`` is recorded alongside so the front end can also assert it covers what
production actually serves today.

REGENERATE (never hand-edit):

    cd apps/api && PULSAI_WRITE_TIMEFRAME_FIXTURE=1 python3 -m pytest tests/contract/test_public_timeframe_options_fixture.py -p no:randomly
"""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path
from typing import Any

from src.shared.constants.timeframes import (
    DEFAULT_SUPPORTED_TIMEFRAME_VALUES,
    TIMEFRAME_REGISTRY,
    build_public_timeframe_options,
)

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "public_timeframe_options.json"

#: Setting this rewrites the fixture from the SoT instead of comparing against it -- the same
#: record-then-compare shape as this repo's other baselines, kept in the one module that owns it.
WRITE_ENV_VAR = "PULSAI_WRITE_TIMEFRAME_FIXTURE"

_FACTS = (
    "IMPORTERS/CALLERS: apps/api/tests/contract/test_public_timeframe_options_fixture.py (drift gate) and the "
    "apps/web incremental-fetch tests, which parametrize over `options`. AFFECTED API: none - a test fixture. "
    "DATA SCHEMAS: `options` is exactly the PublicTimeframeOption list GET /config/public serves "
    "({value, ms, label}), built by build_public_timeframe_options over the WHOLE TIMEFRAME_REGISTRY so a "
    "timeframe that is registered but not served by default (1m) is still tested. Regenerate, never hand-edit: "
    "the drift gate prints the exact command."
)


def expected_document() -> dict[str, Any]:
    """The fixture exactly as the SoT defines it today."""
    return {
        "_facts": _FACTS,
        "source": "src.shared.constants.timeframes.build_public_timeframe_options(TIMEFRAME_REGISTRY)",
        "default_served": list(DEFAULT_SUPPORTED_TIMEFRAME_VALUES),
        "options": [dataclasses.asdict(option) for option in build_public_timeframe_options(TIMEFRAME_REGISTRY)],
    }


def _read_fixture() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(FIXTURE_PATH.read_text())
    return loaded


def test_the_fixture_is_what_config_public_serves_for_the_whole_registry() -> None:
    expected = expected_document()

    if os.environ.get(WRITE_ENV_VAR) == "1":
        FIXTURE_PATH.write_text(json.dumps(expected, indent=2) + "\n")

    assert _read_fixture() == expected, (
        "tests/fixtures/public_timeframe_options.json no longer matches TIMEFRAME_REGISTRY, so the front "
        "end's incremental-fetch tests are iterating a stale timeframe list. Regenerate it:\n\n"
        f"    cd apps/api && {WRITE_ENV_VAR}=1 python3 -m pytest {Path(__file__).relative_to(Path(__file__).parents[2])}\n"
    )


def test_every_registered_timeframe_is_in_the_fixture() -> None:
    """Canary: a fixture that silently lost entries would still 'match' a shrunken expectation."""
    served_values = [option["value"] for option in _read_fixture()["options"]]

    assert served_values, "the fixture holds no timeframes -- every parametrized test built on it is vacuous"
    assert set(served_values) == set(TIMEFRAME_REGISTRY)
    assert len(served_values) == len(set(served_values)), "a timeframe appears twice"


def test_what_production_serves_today_is_a_subset_of_the_fixture() -> None:
    fixture = _read_fixture()
    served_values = {option["value"] for option in fixture["options"]}

    assert fixture["default_served"] == list(DEFAULT_SUPPORTED_TIMEFRAME_VALUES)
    assert set(fixture["default_served"]) <= served_values


def test_every_option_carries_a_positive_bar_length() -> None:
    """The front end derives its bar spacing from ``ms``; a zero or missing one would divide nothing."""
    for option in _read_fixture()["options"]:
        assert isinstance(option["ms"], int)
        assert option["ms"] > 0, option
