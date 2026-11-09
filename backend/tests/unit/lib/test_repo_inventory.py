"""repo_inventory: the repo's capability map, generated from the files git tracks.

IMPORTERS/CALLERS: pytest. AFFECTED API: pins repo_inventory (CATEGORIES, inventory, routes_in, matching, summary_lines,
inventory_text, write_copy, staged_copy, stale_message). DATA SCHEMAS: none -- the real tracked tree, a hand-built route
sample, and scratch git repositories under tmp_path for the committed copy's gate.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from src.lib import repo_inventory as inv

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(scope="module")
def tree() -> dict[str, list[str]]:
    return inv.inventory()


def test_every_category_finds_something_on_the_real_tree(tree: dict[str, list[str]]) -> None:
    """A category that matches nothing is a dead category: the map would silently stop showing a whole kind of thing."""
    empty = [name for name in (c.name for c in inv.CATEGORIES) if not tree.get(name)]
    assert empty == []


def test_the_map_holds_what_the_owner_named(tree: dict[str, list[str]]) -> None:
    """Owner, 2026-10-26: 'pine scripts, resources, indicators, features, strategies, admin UI endpoints that has books,
    io, fundings' -- each kind is in the map, read off the tree."""
    every = " ".join(" ".join(entries) for entries in tree.values())
    for named in ("pine", "funding", "liquidation", "whale", "deribit", "kelly", "meta_label", "admin/"):
        assert named in every


def test_routes_are_read_off_the_decorators() -> None:
    source = '@router.get("/funding/{symbol}")\nasync def a(): ...\n@router.post(\n    "/books/run",\n)\ndef b(): ...\n'
    assert inv.routes_in(source) == ["GET /funding/{symbol}", "POST /books/run"]


def test_a_match_ranks_entries_by_the_words_they_hold(tree: dict[str, list[str]]) -> None:
    hits = inv.matching(tree, ["drawdown", "volatility", "regime"])
    assert hits
    assert all(any(w in entry.lower() for w in ("drawdown", "volatil", "regime")) for _cat, entry in hits)


def test_short_and_common_words_never_match_everything() -> None:
    assert inv.search_words("the SOL and BTC for each day of the loss") == ["loss"]


def test_the_summary_names_every_category_with_its_count(tree: dict[str, list[str]]) -> None:
    text = "\n".join(inv.summary_lines(tree))
    for category in inv.CATEGORIES:
        assert f"{category.name} ({len(tree[category.name])})" in text


def test_the_committed_text_is_the_header_then_every_entry(tree: dict[str, list[str]]) -> None:
    text = inv.inventory_text(tree)
    assert text.startswith("REPO INVENTORY -- generated from the files git tracks")
    assert text == inv.inventory_text(tree)  # the same tree, the same bytes: a copy can be held to it exactly
    for category in inv.CATEGORIES:
        assert f"\n{category.name} ({len(tree[category.name])})\n" in text


def _git(root: Path, *args: str) -> None:
    subprocess.run([inv.GIT, *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A scratch git repository holding one staged Pine script."""
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.pine").write_text("//@version=6\n")
    _git(tmp_path, "add", "a.pine")
    return tmp_path


def test_the_gate_wants_the_copy_staged_and_current(repo: Path) -> None:
    copy = repo / inv.INVENTORY_FILE
    assert "is not in the index" in (inv.stale_message(repo) or "")
    assert inv.write_copy(copy, inv.inventory(repo))
    assert inv.stale_message(repo) is not None  # written but not staged: the commit would not carry it
    _git(repo, "add", inv.INVENTORY_FILE)
    assert inv.stale_message(repo) is None
    (repo / "b.pine").write_text("//@version=6\n")
    _git(repo, "add", "b.pine")
    assert "stale for this commit" in (inv.stale_message(repo) or "")  # a new file and the old copy: refused
    assert inv.write_copy(copy, inv.inventory(repo))
    _git(repo, "add", inv.INVENTORY_FILE)
    assert inv.stale_message(repo) is None


def test_writing_an_unchanged_copy_reports_no_change(repo: Path) -> None:
    copy = repo / inv.INVENTORY_FILE
    assert inv.write_copy(copy, inv.inventory(repo))
    assert not inv.write_copy(copy, inv.inventory(repo))


def test_routes_are_read_from_the_index_not_an_unstaged_edit(repo: Path) -> None:
    module = repo / "apps/api/src/api/books.py"
    module.parent.mkdir(parents=True)
    module.write_text('@router.get("/books")\ndef a(): ...\n')
    _git(repo, "add", "apps/api/src/api/books.py")
    module.write_text('@router.get("/elsewhere")\ndef a(): ...\n')  # left unstaged: no commit carries it
    assert inv.inventory(repo)["API endpoints (method + route)"] == ["api/books.py: GET /books"]
