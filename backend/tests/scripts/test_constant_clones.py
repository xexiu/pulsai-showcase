"""Constant clones: a module-level value that already lives in another module is one clone group, whatever its name.

IMPORTERS/CALLERS: none (a test module). AFFECTED API: src/lib/quality_gates/constant_clones (constant_occurrences)
and its wiring into expression_clones (occurrences / index_for). DATA SCHEMAS: none.

SAME-VALUE (owner, 2026-10-18: "enforce hook and memory ... robust, proactive, always, bullet proof"): a private
`_STOP_REASONS = frozenset({REASON_INITIAL_STOP, REASON_MOVED_STOP})` was written into the thin-stop kernel while
cert/risk_sized_trades.py already held the identical set. No door saw it: concept_definitions judges public NAMES,
expression_clones only expressions of 25+ nodes INSIDE functions, jscpd copied line blocks.

REUSE-AUDIT: tests/scripts/test_expression_clones.py pins the in-function layer; this pins the module-level one.
"""

from __future__ import annotations

from src.lib.quality_gates import expression_clones as clones
from src.lib.quality_gates.constant_clones import constant_occurrences

KERNEL = "apps/api/src/infrastructure/ml/kernel.py"
CERT = "apps/api/src/cert/walk.py"
KERNEL_SRC = "REASON_INITIAL_STOP = 0\nREASON_MOVED_STOP = 1\nSTOP_REASONS = frozenset({REASON_INITIAL_STOP, REASON_MOVED_STOP})\n"


def _keys(source: str, path: str = CERT) -> list[str]:
    return [key for key, *_ in constant_occurrences(source, path)]


def test_todays_case_is_one_group_whatever_the_name_and_privacy() -> None:
    """The kernel defines the reasons; the cert imports them and re-builds the same set under a private name."""
    cert = "from src.infrastructure.ml.kernel import REASON_INITIAL_STOP, REASON_MOVED_STOP\n\n_STOP = frozenset({REASON_INITIAL_STOP, REASON_MOVED_STOP})\n"

    index = clones.index_for({KERNEL: KERNEL_SRC, CERT: cert}, cache_path=None)

    assert frozenset({(KERNEL, "STOP_REASONS"), (CERT, "_STOP")}) in index.groups.values()


def test_a_relative_import_resolves_to_the_same_origin() -> None:
    cert = (
        "from ..infrastructure.ml.kernel import REASON_INITIAL_STOP, REASON_MOVED_STOP\n_STOP = frozenset({REASON_INITIAL_STOP, REASON_MOVED_STOP})\n"
    )

    assert _keys(cert) == _keys(KERNEL_SRC, KERNEL)[-1:]


def test_the_same_text_over_each_modules_own_names_is_not_a_clone() -> None:
    """`RESULTS = SCRATCH / "results"` in two lab modules: each SCRATCH is that module's own directory (measured: x21)."""
    a = "from pathlib import Path\nSCRATCH = Path('/a')\nRESULTS = SCRATCH / 'results'\n"
    b = "from pathlib import Path\nSCRATCH = Path('/b')\nRESULTS = SCRATCH / 'results'\n"

    index = clones.index_for({"apps/api/src/research/a.py": a, "apps/api/src/research/b.py": b}, cache_path=None)

    assert not any(site[1] == "RESULTS" for sites in index.groups.values() for site in sites)


def test_a_literal_value_is_a_clone_only_under_the_same_name() -> None:
    """(0.15, 0.20) as TARGET_VOLS in two modules is a copy; the same numbers under two names may be chance."""
    same = _keys("TARGET_VOLS = (0.15, 0.20)\n") == _keys("_TARGET_VOLS = (0.15, 0.20)\n", KERNEL)
    other = _keys("TARGET_VOLS = (0.15, 0.20)\n") == _keys("SIZE_CLIP = (0.15, 0.20)\n", KERNEL)

    assert same
    assert not other


def test_state_lone_literals_and_self_located_values_are_not_candidates() -> None:
    """Measured noise: a fresh lock / dict / router per module, `-1`, anything read off __file__ / __name__, a TypeVar."""
    source = (
        "import logging, threading\nfrom pathlib import Path\n"
        "_LOCK = threading.Lock()\n_CACHE = {}\n_SEEN = set()\n_SHORT = -1\n_PCT = 100.0\n"
        "logger = logging.getLogger(__name__)\nROOT = Path(__file__).resolve().parents[2]\n__all__ = ['a', 'b']\n"
        "from typing import TypeVar\n_CellT = TypeVar('_CellT', bound=dict)\n"
    )

    assert _keys(source) == []


def test_a_judged_exception_carries_clone_ok() -> None:
    assert _keys("SYMBOLS = ('BTCUSDT', 'ETHUSDT')  # CLONE-OK: the Pine transcription mirrors its source 1:1\n") == []


def test_constants_join_the_function_expressions_in_one_index() -> None:
    """One index, one ratchet, one touch row: the constants ride the expression-clone machinery, not a second one."""
    found = clones.occurrences("X_SYMBOLS = ('BTCUSDT', 'ETHUSDT')\n", "apps/api/src/research/a.py")

    assert [(name, line) for _key, name, line, _parent in found] == [("X_SYMBOLS", 1)]
