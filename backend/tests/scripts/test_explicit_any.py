"""Explicit-Any ratchet: what counts as a reference to typing.Any, what a split may carry, and the tree total.

IMPORTERS/CALLERS: pytest only. AFFECTED API: none. DATA SCHEMAS: none -- every case is an in-memory source
text, except the tree tests, which read this checkout's HEAD the way verify.sh does.

THE QUESTION (owner, 2026-10-05): "I'm seeing ALL over the codebase Any -> dict[str, Any] or Any plain...
should we enforce this typing?" Each counter test pins one form a reference can take -- including the ones
ruff ANN401 never reads (an alias, a cast, a TypeVar bound, a quoted annotation) -- or one string that only
looks like one. The move tests replay the shapes of the real splits 8f3fe59df (exceptions, 35 Any moved) and
043c51d4e (train_model, 5 moved with their methods and 1 added on the new mixin).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from src.lib.quality_gates.concept_definitions import sources_at_ref
from src.lib.quality_gates.explicit_any import (
    CANARY_COUNT,
    CANARY_SOURCE,
    MIN_TREE_FILES,
    MovedAny,
    any_by_definition,
    any_canary_is_alive,
    any_lines,
    any_references,
    any_tree_verdict,
    only_removed_code,
    ratchet_any_tree,
)

_IMPORT = "from typing import Any\n\n"
_REPO = Path(__file__).resolve().parents[4]
_GIT = shutil.which("git") or "/usr/bin/git"


class TestEveryFormOfAReferenceCounts:
    @pytest.mark.parametrize(
        ("label", "source", "expected"),
        [
            ("argument and return annotations", _IMPORT + "def f(x: Any) -> Any:\n    return x\n", 2),
            ("the dict[str, Any] payload", _IMPORT + "def f(row: dict[str, Any]) -> None:\n    return None\n", 1),
            ("a variable annotation", _IMPORT + "cache: dict[str, Any] = {}\n", 1),
            ("an alias ANN401 never reads", _IMPORT + "JSON = dict[str, Any]\n", 1),
            ("a cast", _IMPORT + "from typing import cast\n\ny = cast(Any, 1)\n", 1),
            ("a quoted cast", "from typing import cast\n\ny = cast('dict[str, Any]', {})\n", 1),
            ("a quoted annotation", "def f(x: 'Any') -> None:\n    return None\n", 1),
            ("a quote inside an annotation", "def f(x: list['Any']) -> None:\n    return None\n", 1),
            ("a quote inside a quote", "def f(x: \"list['Any']\") -> None:\n    return None\n", 1),
            ("typing.Any", "import typing\n\n\ndef f(x: typing.Any) -> None:\n    return None\n", 1),
            ("a module alias", "import typing as t\n\n\ndef f(x: t.Any) -> None:\n    return None\n", 1),
            ("an import alias", "from typing import Any as Anything\n\n\ndef f(x: Anything) -> None:\n    return None\n", 1),
            ("a TypeVar bound", _IMPORT + "from typing import TypeVar\n\nT = TypeVar('T', bound=Any)\n", 1),
            ("a quoted TypeVar bound", "from typing import TypeVar\n\nT = TypeVar('T', bound='Any')\n", 1),
            ("a quoted TypeAlias", "from typing import TypeAlias\n\nRow: TypeAlias = 'dict[str, Any]'\n", 1),
            ("a PEP 695 alias", _IMPORT + "type Row = dict[str, Any]\n", 1),
        ],
    )
    def test_the_form_is_counted(self, label: str, source: str, expected: int) -> None:
        assert any_references(source) == expected, label

    @pytest.mark.parametrize(
        ("label", "source"),
        [
            ("an import alone", "from typing import Any\nimport typing\n"),
            ("a string that is a value", 'MODES = {"Any": 1}\nprint("Any")\n'),
            ("a docstring", 'def f() -> None:\n    """Accepts Any payload."""\n'),
            ("a Literal value", "from typing import Literal\n\n\ndef f(mode: Literal['Any']) -> None:\n    return None\n"),
            ("Annotated metadata", "from typing import Annotated\n\n\ndef f(x: Annotated[int, 'Any']) -> None:\n    return None\n"),
            ("a name that only contains it", "Anything = 1\nCompany = Anything\n"),
            ("an unparseable text", "def f(x: Any) -> \n"),
        ],
    )
    def test_the_form_is_not_counted(self, label: str, source: str) -> None:
        assert any_references(source) == 0, label

    def test_each_reference_carries_its_line(self) -> None:
        assert any_lines(_IMPORT + "A = dict[str, Any]\nB = 1\nC = list[Any]\n") == [3, 5]

    def test_the_canary_counts_every_form_it_holds(self) -> None:
        assert any_canary_is_alive()
        assert any_references(CANARY_SOURCE) == CANARY_COUNT


_SPLIT_SOURCE = (
    _IMPORT + "def keep(x: int) -> int:\n    return x\n\n\n"
    "def _clean(row: dict[str, Any]) -> dict[str, Any]:\n    return row\n\n\n"
    "class Pipeline:\n    def __init__(self, p: Any) -> None:\n        self.p = p\n\n"
    "    def _stage(self, m: Any) -> Any:\n        return m\n"
)


class TestDefinitionsAreTheUnitAMoveCarries:
    def test_the_counts_per_definition_sum_to_the_file(self) -> None:
        guarded = "from typing import TYPE_CHECKING, Any\n\nif TYPE_CHECKING:\n    Row = dict[str, Any]\n" + _SPLIT_SOURCE[len(_IMPORT) :]
        for source in (CANARY_SOURCE, _SPLIT_SOURCE, guarded):
            assert sum(any_by_definition(source).values()) == any_references(source)

    def test_a_method_is_its_own_definition_and_a_dunder_stays_with_its_class(self) -> None:
        found = any_by_definition(_SPLIT_SOURCE)

        assert found["clean"] == 2  # leading underscore dropped: made public by a split, still the same code
        assert found["stage"] == 2
        assert found["Pipeline.__init__"] == 1
        assert found["keep"] == 0  # a zero-count definition is still a name a split can carry


class TestASplitMovesDebtItDoesNotAddIt:
    def test_a_definition_that_left_its_file_carries_its_any_into_a_new_one(self) -> None:
        moved = MovedAny([(_SPLIT_SOURCE, "def keep(x: int) -> int:\n    return x\n")])

        assert moved.added(_IMPORT + "def clean(row: dict[str, Any]) -> dict[str, Any]:\n    return row\n") == 0

    def test_a_definition_retyped_in_place_departed_nothing(self) -> None:
        """A paydown is not credit: otherwise every forced touch-to-lower payment is reinvested in a new file."""
        retyped = _SPLIT_SOURCE.replace("dict[str, Any]", "dict[str, int]")
        moved = MovedAny([(_SPLIT_SOURCE, retyped)])

        assert moved.added(_IMPORT + "def clean(row: dict[str, Any]) -> None:\n    return None\n") == 1

    def test_one_departed_definition_is_claimed_once(self) -> None:
        moved = MovedAny([(_SPLIT_SOURCE, None)])
        copy = _IMPORT + "def clean(row: dict[str, Any]) -> dict[str, Any]:\n    return row\n"

        assert moved.added(copy) == 0
        assert moved.added(copy) == 2

    def test_methods_moved_into_a_mixin_carry_theirs_and_a_new_attribute_is_charged(self) -> None:
        """043c51d4e's shape: stage methods moved into TrainingStagesMixin, which also declared its host's attribute."""
        host = _SPLIT_SOURCE.replace("    def _stage(self, m: Any) -> Any:\n        return m\n", "    pass\n")
        mixin = _IMPORT + "class StagesMixin:\n    p: Any\n\n    def _stage(self, m: Any) -> Any:\n        return m\n"

        assert MovedAny([(_SPLIT_SOURCE, host)]).added(mixin) == 1

    def test_a_deleted_file_carries_every_definition_it_held(self) -> None:
        moved = MovedAny([(_SPLIT_SOURCE, None)])

        assert moved.added(_SPLIT_SOURCE) == 0

    def test_module_level_code_no_name_owns_is_never_credit(self) -> None:
        moved = MovedAny([(_IMPORT + "print(dict[str, Any])\n", "")])

        assert moved.added(_IMPORT + "print(dict[str, Any])\n") == 1


class TestARemovalOnlyChangeCannotAddAny:
    _BEFORE = '"""Module."""\n\nimport os\n\n' + _SPLIT_SOURCE

    def test_removing_definitions_and_readdressing_imports_and_docs_is_removal_only(self) -> None:
        after = '"""Module -- split, see the new file."""\n\nimport re\n\n' + _SPLIT_SOURCE.replace(
            "def _clean(row: dict[str, Any]) -> dict[str, Any]:\n    return row\n\n\n", ""
        )

        assert only_removed_code(self._BEFORE, after)
        assert MovedAny.owes_on_touch(self._BEFORE, after) is False

    def test_a_comment_only_change_is_removal_only(self) -> None:
        assert only_removed_code(self._BEFORE, self._BEFORE.replace("def keep", "# kept\ndef keep"))

    def test_editing_a_kept_definition_is_a_real_touch(self) -> None:
        edited = self._BEFORE.replace("return x\n", "return x + 1\n", 1)

        assert not only_removed_code(self._BEFORE, edited)
        assert MovedAny.owes_on_touch(self._BEFORE, edited) is True

    def test_adding_a_definition_is_a_real_touch(self) -> None:
        assert not only_removed_code(self._BEFORE, self._BEFORE + "\n\ndef extra() -> None:\n    return None\n")

    def test_an_unparseable_side_is_a_real_touch(self) -> None:
        assert not only_removed_code(self._BEFORE, "def broken(:\n")


class TestTheTreeRatchet:
    @pytest.mark.parametrize(("baseline", "code"), [(3, 0), (2, 1), (4, 1)])
    def test_the_total_may_neither_rise_nor_fall_unrecorded(self, baseline: int, code: int) -> None:
        assert any_tree_verdict({"a.py": 2, "b.py": 1, "c.py": 0}, baseline)[0] == code

    def test_a_rise_names_the_heaviest_files(self) -> None:
        _code, lines = any_tree_verdict({"heavy.py": 9, "light.py": 1}, 5)

        assert any("heavy.py" in line for line in lines)

    def test_a_fall_names_the_number_to_lock(self) -> None:
        _code, lines = any_tree_verdict({"a.py": 2}, 5)

        assert any("lower BASELINE_ANY_REFERENCES to 2" in line for line in lines)

    def test_a_scope_that_reads_almost_nothing_is_not_a_clean_tree(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _git(tmp_path, "init", "-q")
        (tmp_path / "apps/api/src").mkdir(parents=True)
        (tmp_path / "apps/api/src/only.py").write_text("X = 1\n", encoding="utf-8")
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "c")

        assert ratchet_any_tree(tmp_path, baseline=0) == 1
        assert "nothing was measured" in capsys.readouterr().out


def _git(repo: Path, *args: str) -> None:
    subprocess.run([_GIT, *args], cwd=repo, check=True, capture_output=True)


class TestTheRatchetMeasuresTheRealTree:
    """Two canaries: a scan that reads nothing, or a counter that matches nothing, reports green forever."""

    def test_the_scan_reads_the_tree_and_finds_any_in_a_file_known_to_use_it(self) -> None:
        sources = sources_at_ref(_REPO, "HEAD")
        # Known by TEXT, independently of the AST counter under test.
        known = next(path for path, text in sorted(sources.items()) if "def " in text and "dict[str, Any]" in text)

        assert len(sources) > MIN_TREE_FILES
        assert any_references(sources[known]) > 0

    def test_verify_runs_the_tree_ratchet(self) -> None:
        verify = (_REPO / "apps" / "api" / "scripts" / "verify.sh").read_text(encoding="utf-8")

        assert "src.lib.quality_gates.explicit_any --tree" in verify
