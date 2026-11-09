"""Architectural fitness function: gate the FILESYSTEM half of the research-lab boundary.

Companion to ``test_no_new_scripts_research_import_in_src.py`` (the IMPORT axis, pinned at 0 —
FULLY CLOSED). That test cannot see this axis: a raw string naming a ``src/research/...`` path
is not an ``import`` statement, so it sails straight through. Measured 2026-09-13 by AST-walking
every string constant in ``src``: **88 occurrences across 45 files**, 23 of them in the designated
SoT module (``shared/constants/research_loop_paths.py``) and the other **58 across 39 files**
scattered through application services, ports, domain services, infrastructure and workers — each
one a hand-typed guess at where the offline research lab keeps a file, with nothing checking that
the guess agrees with any other guess, or with what the Dockerfile actually ships.

That ungated axis broke production: commit 73bb08427. ``CAPITAL_CERT_INVENTORY_REL`` in
``research_loop_paths.py`` named the ``edge_lab/inventory_cryptobacktest`` directory the capital-cert
reads, and no Dockerfile ``COPY`` shipped it — prod graded books against a corpus it could not see
while localhost read the full set. The only "enforcement" was a hand-maintained Dockerfile ``COPY``
allowlist that has to agree, by eye, with 88 literals written in a different language.

**THE MIGRATION LANDED (2026-09-13), so this is now a FLOOR, not a ratchet.** Plan row R-2:
``RESEARCH_ROOT_REL`` / ``ARTIFACT_ROOT_REL`` in ``shared/constants/paths.py`` are the one
spelling, and every path constant composes from them (equivalence proved byte-identical for
every derived constant before the change landed). The count went 58 -> 39 -> 0: 58 was the
grandfathered debt, 39 was what remained once every RUNTIME literal moved behind the constant,
and all 39 were DOCSTRING prose, which the scanner no longer counts because a docstring opens
no file. R-1 (caches -> ``var/research/``) is now a one-constant change.

What this test buys from here: a NEW hand-typed lab path anywhere in ``src`` outside that one
SoT module is the C-7 defect returning, and it goes red immediately — see ``docs/02-technical/
RESEARCH_LAB_BOUNDARY_ARCHITECT_DECISION.md``.

Adding a NEW file with a lab-path literal → do NOT; import the constant from
``shared.constants.research_loop_paths`` (which composes from ``shared.constants.paths``), or add
a constant there composed from ``ARTIFACT_ROOT_REL`` — never retype the root.

REUSE-AUDIT: considered ``tests/unit/shared/constants/test_research_loop_paths_api_root.py`` (unit
tests the ``API_ROOT``-relative resolution *behaviour* of one function in ``research_loop_paths.py``,
not a repo-wide literal scan) and ``tests/unit/infrastructure/test_research_loop_container_paths.py``
(pins Docker-container path resolution for that same module) — neither walks ``src`` for stray
literals, so neither can be extended into this fitness function; both stay as-is, testing what they
already test. Considered ``src/research/research_repo_paths.py`` — the *lab-side* mirror of
repo-root resolution (out of scope: ``src`` cannot and must not import it). Not extending any of
them: this is a new architectural class of check (a repo-wide AST literal scan, exactly the shape of
the sibling ``test_no_new_scripts_research_import_in_src.py``), not a fork of a path-resolution unit
test.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path
from typing import Final

from tests.helpers.api_paths import API_ROOT, production_src_py

_SRC_ROOT: Final[Path] = API_ROOT / "src"

#: The substring that marks a string literal as NAMING a path into the offline research lab.
#: Deliberately the slash form: ``src.research`` (dotted) is an IMPORT, already closed at 0 by
#: test_no_new_scripts_research_import_in_src.py — a disjoint axis, not this one.
_LAB_PATH_MARKER: Final[str] = "src/research"

# Modules explicitly permitted to hold a src/research path literal, WITH THE REASON — so this
# list documents itself instead of rotting into an unexplained escape hatch. Each is either the
# designated path SoT the migration resolves through, or a module whose only occurrence is a
# docstring/"@see" reference to the research script it documents, never a resolved runtime path.
_ALLOWED_SOT_MODULES: Final[dict[Path, str]] = {
    Path("shared/constants/paths.py"): (
        "THE one spelling of the lab root. RESEARCH_ROOT_REL / ARTIFACT_ROOT_REL live here and "
        "every other constant composes from them, so moving the root (plan R-1, caches -> "
        "var/research/) is a one-line change here instead of a find-and-replace over ~23 "
        "hand-typed strings. The sibling path modules that used to be listed here -- "
        "research_loop_paths.py, insights_tier_paths.py and four modules whose only mention was "
        "a docstring -- no longer need an exemption: the first two now COMPOSE from this root, "
        "and prose is not counted at all."
    ),
    Path("lib/quality_gates/ratchet_touch.py"): (
        "MOVE HISTORY, not a runtime path: its rewrite rules and _MOVED_PREFIXES name where files LIVED "
        "at past commits (scripts/research -> src/research, src/research/cert -> src/cert) so a moved file "
        "is paired with its delete. Deriving them from today's RESEARCH_ROOT_REL would silently rewrite "
        "that history the day the root moves again (moved here from scripts/ by SCRIPTS-BOUNDARY, 10-04)."
    ),
    Path("lib/quality_gates/concept_definitions.py"): (
        "GATE TOOLING runs under the bare interpreter the git hooks use (no numpy), and importing "
        "shared.constants.paths executes src/shared/__init__.py, which imports numpy -- measured 2026-10-04: "
        "the pre-commit died with ModuleNotFoundError. The literal stays; "
        "test_gate_tooling_lab_paths_match_the_root_constant pins it to RESEARCH_ROOT_REL."
    ),
    Path("lib/quality_gates/verify_gate_helpers.py"): (
        "Same as concept_definitions: gate tooling the bare-interpreter hooks import; pinned to "
        "RESEARCH_ROOT_REL by test_gate_tooling_lab_paths_match_the_root_constant."
    ),
    Path("lib/repo_inventory.py"): (
        "The repo map .claude/hooks/repo_inventory_hook.py runs at session start on the system python3 (no numpy, so "
        "no shared.constants.paths): its one lab spelling, LAB_PREFIX, is pinned to RESEARCH_ROOT_REL by "
        "test_gate_tooling_lab_paths_match_the_root_constant."
    ),
}
_ALLOWED_SOT_MODULE_PATHS: Final[frozenset[Path]] = frozenset(_ALLOWED_SOT_MODULES)

# The exact, deliberate set of `src` files (relative to apps/api/src/) that name a src/research
# path OUTSIDE the allowed SoT modules today. Grandfathered debt — NOT a free pass for new files.
# Migrate to a port/constant incrementally; remove the entry here when a file's last literal is gone.
#: EMPTY, and that is the point. Measured 2026-09-13 after the migration: 0 runtime literals
#: outside the SoT module. The 39 occurrences the old scanner still saw were every one of them
#: a docstring naming the script a module documents -- prose, not a filesystem dependency.
_KNOWN_DEBT_FILES: Final[frozenset[Path]] = frozenset()

#: Total src/research literal OCCURRENCES (not files) across `_KNOWN_DEBT_FILES` today.
#: Pinned at ZERO. Never rise: a new hand-typed lab path in `src` is the C-7 defect returning.
#: MEASURED 2026-09-13, the whole arc in one line: 58 (the grandfathered debt this ratchet was
#: born holding) -> 39 after every RUNTIME literal moved behind `RESEARCH_ROOT_REL` -> 0 once
#: the scanner stopped counting docstring prose. Runtime literals outside the SoT module: 0.
_GRANDFATHERED_LITERAL_DEBT_COUNT: Final[int] = 0


def _iter_python_files(root: Path) -> Iterator[Path]:
    """Production src only: the lab itself lives at src/research since 2026-10-03."""
    yield from production_src_py(root)


def _docstring_constant_ids(tree: ast.AST) -> set[int]:
    """``id()`` of every constant that is a module / class / function DOCSTRING.

    Identity, not value: two identical strings elsewhere in the file must still be counted.
    """
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        first = node.body[0] if node.body else None
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            ids.add(id(first.value))
    return ids


def _lab_path_literal_count(path: Path) -> int:
    """How many RUNTIME string constants in ``path`` name a src/research path.

    Docstrings are excluded: a docstring naming a research script is documentation that opens
    no file, so it cannot cause the C-7 failure this gate exists to stop (code resolving a
    hand-typed path the image does not ship). Counting prose would also pressure an author to
    reword accurate documentation to satisfy a number.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = _docstring_constant_ids(tree)
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _LAB_PATH_MARKER in node.value and id(node) not in docstrings
    )


def _debt_counts_outside_allowed_modules() -> dict[Path, int]:
    """``{relative_path: literal_count}`` for every src file OUTSIDE the allowed SoT modules."""
    counts: dict[Path, int] = {}
    for py_file in _iter_python_files(_SRC_ROOT):
        rel = py_file.relative_to(_SRC_ROOT)
        if rel in _ALLOWED_SOT_MODULE_PATHS:
            continue
        count = _lab_path_literal_count(py_file)
        if count:
            counts[rel] = count
    return counts


def test_no_new_research_path_literal_outside_the_allowed_sot_modules() -> None:
    """A file that never named a lab path before must not start now outside the SoT modules."""
    outside = _debt_counts_outside_allowed_modules()
    new_files = sorted(str(p) for p in (set(outside) - _KNOWN_DEBT_FILES))
    assert new_files == [], (
        "New src/research path literal(s) planted OUTSIDE the allowed SoT modules "
        "(RESEARCH_LAB_BOUNDARY_ARCHITECT_DECISION.md, 73bb08427 broke prod on exactly this axis): "
        "resolve the path through shared.constants.research_loop_paths (or a sibling module listed "
        "in _ALLOWED_SOT_MODULES) instead of typing it again. New files:\n  - " + "\n  - ".join(new_files)
    )


def test_known_debt_files_not_stale() -> None:
    """A debt file with zero literals left has been migrated — lower the pin in the same PR."""
    outside = _debt_counts_outside_allowed_modules()
    migrated = sorted(str(p) for p in (_KNOWN_DEBT_FILES - set(outside)))
    assert migrated == [], (
        "Stale entry in _KNOWN_DEBT_FILES (no src/research literal found any more — likely "
        "migrated to a port/constant). Remove it here AND lower "
        "_GRANDFATHERED_LITERAL_DEBT_COUNT in the same PR so the pin tracks the real debt:\n  - " + "\n  - ".join(migrated)
    )


def test_research_path_literal_debt_count_is_pinned() -> None:
    """The debt size may only shrink (migration), never silently grow or silently shrink."""
    outside = _debt_counts_outside_allowed_modules()
    actual_count = sum(outside.values())
    assert actual_count == _GRANDFATHERED_LITERAL_DEBT_COUNT, (
        f"src/research literal debt outside the allowed SoT modules changed: measured "
        f"{actual_count}, pinned {_GRANDFATHERED_LITERAL_DEBT_COUNT}. If it ROSE, a new literal "
        "was hand-typed into an already-grandfathered file — migrate it, don't grow the count. If "
        "it FELL, a migration landed — lower this pin (see test_known_debt_files_not_stale)."
    )


def test_scan_is_not_vacuous() -> None:
    """A scan that silently walks zero files or finds zero literals reports green for the wrong
    reason — see .claude/rules/queries-must-clean-up-when-the-user-leaves.md's precedent for why a
    gate matching nothing is worse than no gate. Canary against a broken root / marker, not tied to
    the shrinking debt count above (which is allowed, and expected, to reach zero over time).
    """
    all_files = list(_iter_python_files(_SRC_ROOT))
    assert len(all_files) > 100, (
        f"Only {len(all_files)} .py files found under {_SRC_ROOT} — the scan root is almost "
        "certainly misconfigured; a real apps/api/src tree has thousands."
    )
    total_literals = sum(_lab_path_literal_count(f) for f in all_files)
    assert total_literals > 0, (
        f"'{_LAB_PATH_MARKER}' matched zero string literals anywhere in src — the marker or the "
        "AST walk is broken, not the lab boundary suddenly clean (see test_no_new_scripts_research_"
        "import_in_src.py for the disjoint, already-closed import axis)."
    )


class TestTheScannerCountsRuntimeLiteralsNotProse:
    """A docstring that NAMES a research script is documentation; it reads no file.

    THE DISTINCTION THIS PINS, measured 2026-09-13. After the runtime migration (every real path
    resolving through ``RESEARCH_ROOT_REL`` in ``shared/constants/paths.py``) the scan still
    counted **39** occurrences across 27 files — and every one of them is PROSE: a module or
    function docstring naming the research script a module documents. Runtime literals: **0**.

    Counting prose makes the ratchet measure the wrong thing. The failure this gate exists to stop
    is C-7: code resolving a hand-typed path the image does not ship (commit 73bb08427). A
    docstring cannot do that — it is never opened, never joined to a root, never shipped-or-not.
    Worse, counting it creates pressure to reword accurate documentation to satisfy a number,
    which is how a gate starts producing damage instead of catching it.

    So the scanner judges by ROLE, the same principle as ``.claude/rules/full-htf-grid-always.md``
    exempting records and fixtures: a runtime literal is debt, a docstring mention is not. The
    lab CODE is not moving either (plan R-3 deleted), so those docstrings stay accurate.
    """

    def _module(self, tmp_path: Path, body: str) -> Path:
        path = tmp_path / "sample.py"
        path.write_text(body, encoding="utf-8")
        return path

    def test_a_module_docstring_naming_the_lab_is_not_debt(self, tmp_path: Path) -> None:
        path = self._module(tmp_path, '"""Mirrors src/research/edge_hunt/foo.py."""\n\nX = 1\n')

        assert _lab_path_literal_count(path) == 0

    def test_a_function_docstring_naming_the_lab_is_not_debt(self, tmp_path: Path) -> None:
        path = self._module(
            tmp_path,
            'def f() -> None:\n    """@see src/research/edge_hunt/bar.py."""\n    return None\n',
        )

        assert _lab_path_literal_count(path) == 0

    def test_a_runtime_assignment_is_still_debt(self, tmp_path: Path) -> None:
        """The discriminating case: without it the two above would pass on a scanner counting nothing."""
        path = self._module(tmp_path, 'REL = "src/research/artifacts/x.json"\n')

        assert _lab_path_literal_count(path) == 1

    def test_a_runtime_literal_inside_a_call_is_still_debt(self, tmp_path: Path) -> None:
        path = self._module(tmp_path, 'def f():\n    return open("src/research/artifacts/x.json")\n')

        assert _lab_path_literal_count(path) == 1

    def test_a_docstring_and_a_runtime_literal_in_one_file_counts_only_the_literal(self, tmp_path: Path) -> None:
        path = self._module(
            tmp_path,
            '"""Documents src/research/edge_hunt/foo.py."""\n\nREL = "src/research/artifacts/x.json"\n',
        )

        assert _lab_path_literal_count(path) == 1


def test_gate_tooling_lab_paths_match_the_root_constant() -> None:
    """The allow-listed gate modules spell the lab root themselves (they cannot import src.shared); this keeps
    each spelling equal to RESEARCH_ROOT_REL, so moving the root fails here instead of silently splitting."""
    from src.lib import repo_inventory
    from src.lib.quality_gates import concept_definitions, verify_gate_helpers
    from src.shared.constants.paths import RESEARCH_ROOT_REL

    lab_prefix = f"apps/api/{RESEARCH_ROOT_REL}/"
    assert lab_prefix == concept_definitions.GENERIC_NAME_LAB
    assert lab_prefix == repo_inventory.LAB_PREFIX
    assert lab_prefix in verify_gate_helpers._TYPECHECKED_PREFIXES
    assert verify_gate_helpers._RESEARCH_FINDING_RE.match(f"{RESEARCH_ROOT_REL}/x.py")
