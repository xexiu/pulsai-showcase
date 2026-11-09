"""tests.helpers.api_paths — one apps/api root for the test tree."""

from __future__ import annotations

from src.shared.constants.paths import API_ROOT_PATH
from src.shared.constants.research_loop_paths import api_package_root, repo_root
from tests.helpers.api_paths import API_ROOT, REPO_ROOT, TESTS_ROOT


def test_api_root_is_paths_sot() -> None:
    assert API_ROOT_PATH == API_ROOT
    assert api_package_root() == API_ROOT
    assert (API_ROOT / "src").is_dir()
    assert (API_ROOT / "src" / "research").is_dir()


def test_tests_root_and_repo_root_are_sot() -> None:
    assert TESTS_ROOT == API_ROOT / "tests"
    assert TESTS_ROOT.is_dir()
    assert repo_root() == REPO_ROOT
    assert (REPO_ROOT / ".git").exists() or (REPO_ROOT / "apps" / "api").is_dir()


def test_api_root_matches_helpers_package_anchor() -> None:
    """Single parents count lives beside this helper file — not in every test."""
    helpers_anchor = API_ROOT / "tests"
    assert helpers_anchor == TESTS_ROOT


def test_ensure_api_root_on_sys_path_is_idempotent(monkeypatch: object) -> None:
    import sys

    from tests.helpers import api_paths as ap

    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != str(API_ROOT)])
    first = ap.ensure_api_root_on_sys_path()
    second = ap.ensure_api_root_on_sys_path()
    assert first == API_ROOT
    assert second == API_ROOT
    assert sys.path.count(str(API_ROOT)) == 1
