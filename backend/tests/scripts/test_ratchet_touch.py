"""ratchet_touch: the ONE touch-to-lower rule every per-file ratchet enforces at commit.

IMPORTERS/CALLERS: pytest only. AFFECTED API: none. DATA SCHEMAS: none.

The owner's rule (2026-09-24): "everytime someone touches a file, its his resp to fix/refactor and
lower the ratchet until we reach 0 -- same for OTHERS ratchets". Written once here so a second
ratchet cannot re-implement it slightly differently: the duplicate-lines gate measures duplicated
lines, the file-size gate measures effective lines over the cap, both feed the same judgement.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from src.lib.quality_gates.ratchet_touch import (
    changed_paths,
    index_blob,
    is_mechanical_move,
    main,
    moved_from,
    ref_blob,
    rewrite_for_move,
    rewrite_moved_paths,
    touch_violations,
    touched_only,
)

_GIT = shutil.which("git") or "/usr/bin/git"


class TestTheRule:
    @pytest.mark.parametrize(
        ("before", "now", "is_new", "violates"),
        [
            (None, 0, True, False),
            (None, 3, True, True),
            (10, 9, False, False),
            (10, 10, False, True),
            (10, 11, False, True),
            (0, 0, False, False),
            (0, 1, False, True),
        ],
    )
    def test_touched_files_pay_down_new_files_start_clean(self, before: int | None, now: int, is_new: bool, violates: bool) -> None:
        before_counts = {} if before is None else {"f.py": before}

        found = touch_violations(["f.py"], now={"f.py": now}, before=before_counts, new_files={"f.py"} if is_new else set(), unit="widgets")

        assert bool(found) is violates

    @pytest.mark.parametrize(("before", "now", "violates"), [(2, 1, True), (2, 0, False), (0, 0, False)])
    def test_clear_on_touch_demands_zero_not_merely_less(self, before: int, now: int, violates: bool) -> None:
        found = touch_violations(["f.py"], now={"f.py": now}, before={"f.py": before}, new_files=set(), unit="noqa", clear_on_touch=True)

        assert bool(found) is violates

    def test_the_message_carries_the_metric_unit(self) -> None:
        found = touch_violations(["f.py"], now={"f.py": 7}, before={"f.py": 7}, new_files=set(), unit="excess lines")

        assert len(found) == 1
        assert "excess lines" in found[0]


def _run(repo: Path, *args: str) -> None:
    subprocess.run([_GIT, *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text("committed\n")
    _run(root, "init", "-q")
    _run(root, "add", "pkg")
    _run(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "seed")
    return root


class TestReadingFromGitNotTheWorkingTree:
    def test_index_blob_is_the_staged_content(self, repo: Path) -> None:
        (repo / "pkg" / "a.py").write_text("staged\n")
        _run(repo, "add", "pkg")
        (repo / "pkg" / "a.py").write_text("unstaged\n")

        assert index_blob(repo, "pkg/a.py") == "staged\n"

    def test_ref_blob_reads_a_commit_and_is_none_for_a_new_path(self, repo: Path) -> None:
        assert ref_blob(repo, "HEAD", "pkg/a.py") == "committed\n"
        assert ref_blob(repo, "HEAD", "pkg/new.py") is None

    def test_changed_paths_lists_only_the_staged_changes(self, repo: Path) -> None:
        (repo / "pkg" / "b.py").write_text("new\n")
        _run(repo, "add", "pkg/b.py")
        (repo / "pkg" / "a.py").write_text("edited but not staged\n")

        assert changed_paths(repo, "--cached") == ["pkg/b.py"]


_LAB_MODULE = "from scripts.research.lab import x\nROOT = 'apps/api/scripts/research/artifacts'\nX = 1  # noqa: E402\n"


def _commit_all(repo: Path) -> None:
    _run(repo, "add", "-A")
    _run(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "c")


class TestAFormatterPassIsNotATouch:
    """2026-10-03: pre-push refused 20 files the move rewrote because ruff format now writes Python 3.14's
    unparenthesised ``except A, B:``. Formatting them made every one a "touch", and the debt gates then demanded
    silent-return, trade-floor and duplicate-line paydowns in 20 production files for 44 formatter lines -- two
    gates that cannot both be satisfied. ruff format preserves the AST, so equal formatted output means no
    debt can have changed."""

    _BEFORE = b"def f():\n    try:\n        pass\n    except (OSError, ValueError):\n        return None\n"
    _AFTER = b"def f():\n    try:\n        pass\n    except OSError, ValueError:\n        return None\n"

    def test_a_format_only_change_is_mechanical(self) -> None:
        assert is_mechanical_move(self._BEFORE, self._AFTER, "apps/api/src/x.py", "apps/api/src/x.py")

    def test_a_real_code_change_is_still_a_touch(self) -> None:
        changed = self._AFTER.replace(b"return None", b"return 0")
        assert not is_mechanical_move(self._BEFORE, changed, "apps/api/src/x.py", "apps/api/src/x.py")

    def test_a_move_plus_its_reformat_is_mechanical(self) -> None:
        before = b"from scripts.research import m\n" + self._BEFORE
        after = b"from src.research import m\n" + self._AFTER
        assert is_mechanical_move(before, after, "apps/api/scripts/research/x.py", "apps/api/src/research/x.py")

    def test_it_works_under_an_interpreter_without_ruff(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The husky hook runs bare `python3`, which resolved to a Homebrew 3.14 with no ruff module: every
        format-only file failed closed and the commit was refused. The formatter is found as a binary."""
        monkeypatch.setattr("sys.executable", "/nonexistent/python3")
        assert is_mechanical_move(self._BEFORE, self._AFTER, "apps/api/src/x.py", "apps/api/src/x.py")

    def test_only_python_is_normalised(self) -> None:
        assert not is_mechanical_move(b"a  b\n", b"a b\n", "docs/x.md", "docs/x.md")


class TestAMoveIsNotATouch:
    """Owner, 2026-10-03: "move all ... we must only have src/research". A file that only changes ADDRESS
    keeps its debt; charging it as touched would refuse the move for debt it did not add."""

    @pytest.fixture
    def lab(self, repo: Path) -> Path:
        (repo / "apps/api/scripts/research").mkdir(parents=True)
        (repo / "apps/api/scripts/research/m.py").write_text(_LAB_MODULE)
        (repo / "apps/api/tests").mkdir(parents=True)
        (repo / "apps/api/tests/test_m.py").write_text("from scripts.research import m\n")
        _commit_all(repo)
        (repo / "apps/api/src/research").mkdir(parents=True)
        return repo

    def test_the_push_range_uses_the_same_rule(self, lab: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        """Pre-push type-checked all 1,711 .py files of the move's push range (4,377 basedpyright errors) because
        it read the raw `git diff`; the commit gates had judged only real touches. One rule for both."""
        base = subprocess.run([_GIT, "rev-parse", "HEAD"], cwd=lab, capture_output=True, text=True, check=True).stdout.strip()
        _run(lab, "mv", "apps/api/scripts/research/m.py", "apps/api/src/research/m.py")
        (lab / "apps/api/tests/test_m.py").write_text("from src.research import m\nx = 1\n")
        _commit_all(lab)
        monkeypatch.chdir(lab)

        assert main(["--touched-in", base, "HEAD"]) == 0
        assert capsys.readouterr().out.split() == ["apps/api/tests/test_m.py"]

    def test_a_byte_identical_git_mv_is_not_touched(self, lab: Path) -> None:
        _run(lab, "mv", "apps/api/scripts/research/m.py", "apps/api/src/research/m.py")

        assert changed_paths(lab, "--cached") == []

    def test_a_move_that_only_rewrites_the_research_path_is_not_touched(self, lab: Path) -> None:
        _run(lab, "mv", "apps/api/scripts/research/m.py", "apps/api/src/research/m.py")
        moved = _LAB_MODULE.replace("scripts.research", "src.research").replace("scripts/research", "src/research")
        (lab / "apps/api/src/research/m.py").write_text(moved)
        (lab / "apps/api/tests/test_m.py").write_text("from src.research import m\n")
        _run(lab, "add", "-A")

        assert changed_paths(lab, "--cached") == []

    def test_a_move_that_also_changes_code_is_touched_under_its_new_path(self, lab: Path) -> None:
        _run(lab, "mv", "apps/api/scripts/research/m.py", "apps/api/src/research/m.py")
        (lab / "apps/api/src/research/m.py").write_text(_LAB_MODULE + "Y = 2\n")
        _run(lab, "add", "-A")

        assert changed_paths(lab, "--cached") == ["apps/api/src/research/m.py"]

    def test_the_old_path_is_read_as_the_before_side(self, lab: Path) -> None:
        _run(lab, "mv", "apps/api/scripts/research/m.py", "apps/api/src/research/m.py")

        assert moved_from(lab, "--cached") == {"apps/api/src/research/m.py": "apps/api/scripts/research/m.py"}

    def test_lint_staged_is_handed_only_the_real_touches(self, lab: Path) -> None:
        _run(lab, "mv", "apps/api/scripts/research/m.py", "apps/api/src/research/m.py")
        (lab / "apps/api/src/research/edited.py").write_text("X = 1\n")
        _run(lab, "add", "-A")
        staged = [str(lab / "apps/api/src/research/m.py"), str(lab / "apps/api/src/research/edited.py")]

        assert touched_only(staged, lab) == [str(lab / "apps/api/src/research/edited.py")]

    def test_a_file_outside_the_staged_diff_is_still_linted(self, lab: Path) -> None:
        """Regression 2026-10-03: the first filter kept only staged paths, so test_lint_staged_python's
        unstaged fixture files were dropped and five type-error checks passed vacuously."""
        loose = lab / "apps/api/src/loose.py"
        loose.parent.mkdir(parents=True, exist_ok=True)
        loose.write_text("X: int = 'no'\n")

        assert touched_only([str(loose)], lab) == [str(loose)]

    def test_a_file_outside_the_repository_is_still_linted(self, lab: Path, tmp_path: Path) -> None:
        """Regression 2026-10-04: an absolute path outside the repo raised ValueError (relative_to), and
        lint_staged_python.sh read that crash as an empty file list -- exit 0 on a real type error. A file
        the index cannot hold cannot be a positively identified move, so it is kept."""
        outside = tmp_path / "elsewhere" / "apps/api/src/research/probe.py"
        outside.parent.mkdir(parents=True)
        outside.write_text("X: int = 'no'\n")

        assert touched_only([str(outside)], lab) == [str(outside)]

    def test_a_research_test_moved_with_its_tree_is_not_touched(self, lab: Path) -> None:
        old = "apps/api/tests/unit/scripts/research/test_x.py"
        body = "from scripts.research import m\nHOME = 'apps/api/tests/unit/scripts/research'\n"
        (lab / old).parent.mkdir(parents=True)
        (lab / old).write_text(body)
        _commit_all(lab)
        (lab / "apps/api/tests/unit/research").mkdir(parents=True)
        _run(lab, "mv", old, "apps/api/tests/unit/research/test_x.py")
        moved = "from src.research import m\nHOME = 'apps/api/tests/unit/research'\n"
        (lab / "apps/api/tests/unit/research/test_x.py").write_text(moved)
        _run(lab, "add", "-A")

        assert changed_paths(lab, "--cached") == []

    @pytest.mark.parametrize(
        ("before", "after"),
        [
            ("bash scripts/research_mypy_crash_class.sh", "bash scripts/research_mypy_crash_class.sh"),
            ("apps/api/scripts/researchXXX", "apps/api/scripts/researchXXX"),
            ("apps/api/tests/scripts/research/edge_hunt", "apps/api/tests/unit/research/edge_hunt"),
            ("from scripts.research.edge_hunt import k", "from src.research.edge_hunt import k"),
            ("cd apps/api && ls scripts/research/", "cd apps/api && ls src/research/"),
            ('_API / "scripts" / "research" / "artifacts"', '_API / "src" / "research" / "artifacts"'),
            ('Path("tests") / "scripts" / "research",', 'Path("tests") / "unit" / "research",'),
            ('Path("tests") / "unit" / "scripts" / "research",', 'Path("tests") / "unit" / "research",'),
            ('_API / "scripts" / "research_tools"', '_API / "scripts" / "research_tools"'),
            # The production entries leave src/research so it is the lab and nothing else (one directory, one policy).
            ("from src.research.cert.grid_cells import x", "from src.cert.grid_cells import x"),
            ("python -m src.research.cert BTC", "python -m src.cert BTC"),
            ('API_ROOT / "src" / "research" / "cert" / "x.py"', 'API_ROOT / "src" / "cert" / "x.py"'),
            ("from src.research.tv_rule_boswaves import r", "from src.domain.services.features.tv_rule_boswaves import r"),
            ("tests/unit/research/cert/test_x.py", "tests/unit/cert/test_x.py"),
            ("tests/unit/research/test_tv_rule_lux_structure.py", "tests/unit/domain/services/features/test_tv_rule_lux_structure.py"),
            ("from scripts.research.cert_gate_overlay_cells import c", "from src.research.cert_gate_overlay_cells import c"),
        ],
    )
    def test_the_rewrite_moves_only_the_research_tree(self, before: str, after: str) -> None:
        assert rewrite_moved_paths(before) == after

    def test_a_working_tree_move_is_judged_from_disk(self, lab: Path) -> None:
        """--changed-vs-head (verify's touch list) diffs the WORKING TREE, whose new blobs need not exist in the
        object store; reading one crashed with IndexError before 2026-10-03."""
        _run(lab, "mv", "apps/api/scripts/research/m.py", "apps/api/src/research/m.py")
        moved = _LAB_MODULE.replace("scripts.research", "src.research").replace("scripts/research", "src/research")
        (lab / "apps/api/src/research/m.py").write_text(moved)
        (lab / "apps/api/src/research/new.py").write_text("X = 1\n")
        _run(lab, "add", "apps/api/src/research/new.py")
        (lab / "apps/api/src/research/new.py").write_text("X = 2\n")

        assert changed_paths(lab, "HEAD") == ["apps/api/src/research/new.py"]

    @pytest.mark.parametrize(
        ("old", "new", "before", "after"),
        [
            # one level shallower: an ancestor index above the removed directory drops by one
            (
                "apps/api/tests/unit/scripts/research/pine/t.py",
                "apps/api/tests/unit/research/pine/t.py",
                "API = Path(__file__).resolve().parents[5]\nHERE = Path(__file__).parents[1]\n",
                "API = Path(__file__).resolve().parents[4]\nHERE = Path(__file__).parents[1]\n",
            ),
            (
                "apps/api/src/research/cert/m.py",
                "apps/api/src/cert/m.py",
                "R = Path(__file__).resolve().parents[3]\n",
                "R = Path(__file__).resolve().parents[2]\n",
            ),
            # depth preserved: nothing changes
            (
                "apps/api/scripts/research/a.py",
                "apps/api/src/research/a.py",
                "R = Path(__file__).resolve().parents[2]\n",
                "R = Path(__file__).resolve().parents[2]\n",
            ),
        ],
    )
    def test_a_move_that_changes_depth_re_points_its_own_ancestors(self, old: str, new: str, before: str, after: str) -> None:
        """Regression 2026-10-03: 244 files moved one level shallower; 69 tests (and the cert engine's
        model_spec) climbed parents[N] to the API root and would have landed one directory too high."""
        assert rewrite_for_move(before, old, new) == after

    def test_a_shallower_move_that_re_points_its_ancestor_is_still_mechanical(self, lab: Path) -> None:
        old = "apps/api/tests/unit/scripts/research/test_d.py"
        (lab / old).parent.mkdir(parents=True)
        (lab / old).write_text("API = Path(__file__).resolve().parents[4]\n")
        _commit_all(lab)
        (lab / "apps/api/tests/unit/research").mkdir(parents=True)
        _run(lab, "mv", old, "apps/api/tests/unit/research/test_d.py")
        (lab / "apps/api/tests/unit/research/test_d.py").write_text("API = Path(__file__).resolve().parents[3]\n")
        _run(lab, "add", "-A")

        assert changed_paths(lab, "--cached") == []

        (lab / "apps/api/tests/unit/research/test_d.py").write_text("API = Path(__file__).resolve().parents[2]\n")
        _run(lab, "add", "-A")
        assert changed_paths(lab, "--cached") == ["apps/api/tests/unit/research/test_d.py"]

    def test_since_a_ref_judges_the_same_way(self, lab: Path) -> None:
        base = subprocess.run([_GIT, "rev-parse", "HEAD"], cwd=lab, check=True, capture_output=True, text=True).stdout.strip()
        _run(lab, "mv", "apps/api/scripts/research/m.py", "apps/api/src/research/m.py")
        _commit_all(lab)

        assert changed_paths(lab, base, "HEAD") == []


_REPO = Path(__file__).resolve().parents[4]
#: Every per-file ratchet that enforces the touch-to-lower rule at commit. Grows as each ratchet
#: in the RATCHET-TOUCH-1 audit is moved onto the shared rule.
_TOUCH_GATES = ("check_duplicate_lines.py", "check_file_size_baseline.py", "check_touched_debt.py")


@pytest.mark.parametrize("gate", _TOUCH_GATES)
def test_ratchets_touch_to_lower(gate: str) -> None:
    """Each gate runs at commit AND judges through the one shared rule, never its own copy."""
    hook = (_REPO / ".husky" / "pre-commit").read_text(encoding="utf-8")
    source = (_REPO / "apps" / "api" / "scripts" / gate).read_text(encoding="utf-8")

    assert f"apps/api/scripts/{gate} --staged" in hook, f"{gate} is not run by .husky/pre-commit"
    assert "from src.lib.quality_gates.ratchet_touch import" in source, f"{gate} does not use the shared rule"
    assert "def touch_violations(" not in source, f"{gate} carries its own copy of the rule"
