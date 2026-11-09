"""The repo's capability map, generated from the files git tracks on every run -- what this repo HAS is read off the
tree, never recalled (owner, 2026-10-26: "also you have pine scripts, resources, indicators, features, strategies,
admin UI endpoints that has books, io, fundings, etc - are you 100% DEE PSearched ... build a tool script to ALWAYS run
it on every session, item, todo list, etc!!").

IMPORTERS/CALLERS: .claude/hooks/repo_inventory_hook.py (every session start: the summary into context and the committed
copy refreshed; every TodoWrite: the entries matching the in-progress items' own words; Stop: a lever / 'the repo has'
reply refused until it ran); .husky/pre-commit (--check, the inventory gate); by hand from apps/api: python -m
src.lib.repo_inventory [--full] [--match WORD ...] [--text "an item's text"] [--write] [--check];
tests/unit/lib/test_repo_inventory.py. AFFECTED API: INVENTORY_FILE, full_lines, inventory_text, write_copy, staged_copy,
stale_message, --write / --check (2026-10-26); the API routes are read from the INDEX, not the worktree. DATA SCHEMAS:
writes INVENTORY_FILE (docs/04-structural/REPO_INVENTORY.txt: a header, then each category (count) and one entry a line);
reads `git ls-files` and the API modules' route decorators.

THE COMMITTED COPY (owner, 2026-10-26: "inventory_full.txt <-- should be commit to git in order to future have it and
enfoirced in hook and memory (done in paralel)"): every session start writes the worktree copy when the tree moved, and the
pre-commit gate refuses a commit whose tracked files moved while its STAGED copy did not -- the map in git is the map of
the commit that carries it. A .txt, so no formatter rewrites what --write wrote.

WHY A GENERATED MAP: twice on 2026-10-26 "what the repo has" was answered from memory -- the owner's own list repeated
back -- while the tree held Hyperliquid whale positions, a stored liquidation-heatmap history, Deribit DVOL, Coinglass
funding / OI, Kalshi FOMC odds, a regime-stratified Kelly, regressor-vol sizers and a meta-label builder that were
never named. A category is a PATH PATTERN over the tracked files, so a file added tomorrow is in tomorrow's map with no
edit here; a category that matches nothing fails its test (a dead category would hide a whole kind of thing).

Standard library only: the hook imports it with the system python3, before any venv.

REUSE-AUDIT: considered .claude/hooks/register_guards.py (lists hook files only), check_edge_hunt_reachable (lab
reachability, not a capability map), the admin indicator_inventory route (indicators only) -- none maps the repo.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[4]
GIT: Final = "/usr/bin/git"  # by absolute path: a bare name runs whatever PATH puts first
#: The committed copy of the full map, repo-relative.
INVENTORY_FILE: Final = "docs/04-structural/REPO_INVENTORY.txt"
_REGENERATE: Final = "cd apps/api && python -m src.lib.repo_inventory --write"
_HEADER: Final = (
    f"REPO INVENTORY -- generated from the files git tracks; never edit by hand. Regenerate: {_REGENERATE}",
    "IMPORTERS/CALLERS: .claude/hooks/repo_inventory_hook.py (refreshes it at every session start); the pre-commit gate",
    "(src/lib/repo_inventory.py --check: a commit whose tracked files moved must carry it); anyone asking what the repo holds.",
    "AFFECTED API: none. DATA SCHEMAS: this file -- each category (its count), then one entry a line.",
    "",
)
EXAMPLES: Final = 14  # names a summary line shows for its category
MATCH_LIMIT: Final = 60  # entries a focused match prints
MIN_WORD: Final = 4  # shorter words match half the tree
#: Words every item and every path share: matching on them would list the whole repo.
COMMON: Final = frozenset(
    {
        "each",
        "with",
        "from",
        "that",
        "this",
        "what",
        "when",
        "have",
        "will",
        "into",
        "only",
        "every",
        "more",
        "than",
        "them",
        "then",
        "they",
        "their",
        "there",
        "owner",
        "item",
        "items",
        "todo",
        "pass",
        "done",
        "after",
        "before",
        "also",
        "must",
        "never",
        "always",
        "same",
        "both",
        "does",
        "over",
        "under",
        "used",
        "uses",
        "using",
        "live",
        "test",
        "tests",
        "file",
        "files",
        "code",
        "real",
        "full",
        "last",
        "days",
        "month",
        "months",
        "window",
        "windows",
        "high",
        "medium",
        "none",
        "true",
        "false",
        "plus",
    }
)
#: Directories that hold records or archived kills, not capabilities.
_NOT_LIVE: Final = r"(?!.*/_archive/)(?!.*/artifacts/)"
#: The lab root as tracked paths spell it -- typed here because the session hook runs this module on the system python
#: (no numpy, so no shared.constants.paths); the architecture test pins it to RESEARCH_ROOT_REL.
LAB_PREFIX: Final = "apps/api/src/research/"
_ROUTE: Final = re.compile(r"@\w+\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_WORD: Final = re.compile(r"[a-z][a-z0-9_]+")
_SHORTEN: Final = ("apps/api/src/", "apps/web/src/", "apps/api/")
#: File names that say nothing on their own -- such an entry is named by its folder.
_GENERIC_STEMS: Final = frozenset({"page", "SKILL", "__init__", "index"})


@dataclass(frozen=True)
class Category:
    """A kind of thing the repo holds, found by a pattern over the tracked paths."""

    name: str
    paths: re.Pattern[str]


def _category(name: str, pattern: str) -> Category:
    return Category(name, re.compile(pattern))


CATEGORIES: Final = (
    _category("Pine scripts", r"\.pine$"),
    _category("indicators (domain home)", r"^apps/api/src/domain/services/indicators/.+\.py$"),
    _category("feature builders (calculate_all)", r"^apps/api/src/domain/services/features/.+\.py$"),
    _category("targets / labels", r"^apps/api/src/domain/services/targets/.+\.py$"),
    _category(
        "position sizing + risk",
        r"^apps/api/src/(?:domain/services/position_sizing/|infrastructure/ml/(?:position_sizers|backtester_position_sizing"
        r"|backtester_drawdown|backtester_funding)|shared/constants/position_sizing|lib/utils/daily_equity_drawdown).*\.py$",
    ),
    _category("regime / volatility models", rf"^apps/api/src/{_NOT_LIVE}.*(?:regime|volatil|garch|hmm|vol_).*\.py$"),
    _category("meta-labeling", rf"^apps/api/src/{_NOT_LIVE}.*meta_label.*\.py$"),
    _category("live engine strategies", rf"^{LAB_PREFIX}engine/strategies/.+\.py$"),
    _category(
        "data providers (exchanges, derivatives, market, sentiment / macro, on-chain)",
        r"^apps/api/src/infrastructure/(?:exchange|derivatives|market_data|sentiment|on_chain|exchange_health)/.+\.py$",
    ),
    _category("stored tables + repositories", r"^apps/api/src/infrastructure/persistence/.+\.py$"),
    _category("ML infrastructure (trainers, model zoo, backtester)", r"^apps/api/src/infrastructure/ml/.+\.py$"),
    _category("API endpoints (method + route)", r"^apps/api/src/api/.+\.py$"),
    _category("admin UI pages", r"^apps/web/src/app/\[locale\]/admin/(?:.+/)?page\.tsx$"),
    _category(
        "market chart overlays (web)",
        r"^apps/web/src/.*(?:order-?book|funding|open-interest|liquidation|heatmap|cvd|volume-profile|whale|depth|taker"
        r"|sentiment|regime|carry).*\.tsx?$",
    ),
    _category("research lab modules", rf"^{LAB_PREFIX}{_NOT_LIVE}.+\.py$"),
    _category("graded records", rf"^{LAB_PREFIX}engine/validation/.+\.txt$"),
    _category("docs and decision records", r"^docs/.+\.md$"),
    _category("skills", r"^\.(?:agents|claude)/skills/[^/]+/SKILL\.md$"),
)
_ENDPOINTS: Final = "API endpoints (method + route)"


def tracked_files(root: Path = ROOT) -> list[str]:
    """Every path git tracks under ``root`` -- what ships, never a scratch file."""
    out = subprocess.run([GIT, "ls-files"], cwd=root, capture_output=True, text=True, check=True).stdout
    return out.splitlines()


def routes_in(source: str) -> list[str]:
    """Every ``METHOD /path`` an API module declares through its router decorators."""
    return [f"{method.upper()} {path}" for method, path in _ROUTE.findall(source)]


def _short(path: str) -> str:
    """A path without its app prefix: still unique, and its folder names stay searchable."""
    for prefix in _SHORTEN:
        if path.startswith(prefix):
            return path.removeprefix(prefix)
    return path


def _index_texts(paths: list[str], root: Path) -> dict[str, str]:
    """Each of ``paths``' text as the INDEX holds it (one ``git cat-file --batch``) -- what a commit carries, never a
    worktree edit left unstaged; a path the index lacks is left out."""
    if not paths:
        return {}
    request = "".join(f":{path}\n" for path in paths).encode()
    out = subprocess.run([GIT, "cat-file", "--batch"], cwd=root, input=request, capture_output=True, check=True).stdout
    texts: dict[str, str] = {}
    at = 0
    for path in paths:
        end = out.index(b"\n", at)
        header = out[at:end].split()
        at = end + 1
        if header[-1] == b"missing":
            continue
        size = int(header[2])
        texts[path] = out[at : at + size].decode("utf-8", errors="replace")
        at += size + 1
    return texts


def _entries(category: Category, paths: list[str], root: Path) -> list[str]:
    """A category's entries: each matching path, and for the API every route a module declares."""
    matched = [p for p in paths if category.paths.search(p)]
    if category.name != _ENDPOINTS:
        return [_short(p) for p in matched]
    sources = _index_texts(matched, root)
    return [f"{_short(path)}: {route}" for path in matched for route in routes_in(sources.get(path, ""))]


def inventory(root: Path = ROOT) -> dict[str, list[str]]:
    """Category name -> its entries, in CATEGORIES order, read off the tracked tree now."""
    paths = tracked_files(root)
    return {category.name: _entries(category, paths, root) for category in CATEGORIES}


def search_words(text: str) -> list[str]:
    """The words of ``text`` worth matching on: at least MIN_WORD letters, none of the COMMON ones, in order, once."""
    words = [w for w in _WORD.findall(text.lower()) if len(w) >= MIN_WORD and w not in COMMON]
    return list(dict.fromkeys(words))


def matching(tree: dict[str, list[str]], words: list[str], limit: int = MATCH_LIMIT) -> list[tuple[str, str]]:
    """(category, entry) of every entry holding any of ``words``, the entries holding the most words first."""
    lowered = [w.lower() for w in words]
    scored = [
        (sum(w in entry.lower() for w in lowered), order, name, entry) for order, (name, entries) in enumerate(tree.items()) for entry in entries
    ]
    hits = sorted((s for s in scored if s[0] > 0), key=lambda s: (-s[0], s[1]))
    return [(name, entry) for _hits, _order, name, entry in hits[:limit]]


def _name_of(entry: str) -> str:
    """An entry's short name: a route as it is, a path by its file stem (by its folder when the stem is generic)."""
    path, sep, route = entry.partition(": ")
    if sep:
        return route
    file = Path(path)
    return file.parent.name if file.stem in _GENERIC_STEMS else file.stem


def summary_lines(tree: dict[str, list[str]]) -> list[str]:
    """One line per category: its count and its first EXAMPLES names."""
    total = sum(len(entries) for entries in tree.values())
    lines = [f"REPO INVENTORY (git ls-files, now): {total} entries in {len(tree)} categories -- search them before any lever"]
    for name, entries in tree.items():
        names = ", ".join(_name_of(e) for e in entries[:EXAMPLES]) + (", ..." if len(entries) > EXAMPLES else "")
        lines.append(f"  {name} ({len(entries)}): {names}")
    return lines


def match_lines(tree: dict[str, list[str]], words: list[str]) -> list[str]:
    """The entries matching ``words``, grouped under their category."""
    hits = matching(tree, words)
    lines = [f"REPO INVENTORY matching {', '.join(words) or '(no words)'}: {len(hits)} entries"]
    shown: str | None = None
    for name, entry in hits:
        if name != shown:
            lines.append(f"  {name}")
            shown = name
        lines.append(f"    {entry}")
    return lines


def full_lines(tree: dict[str, list[str]]) -> list[str]:
    """Every entry of every category: the category with its count, then one entry a line."""
    lines: list[str] = []
    for name, entries in tree.items():
        lines += [f"{name} ({len(entries)})", *(f"  {entry}" for entry in entries)]
    return lines


def inventory_text(tree: dict[str, list[str]]) -> str:
    """The committed copy's whole text: its header, then full_lines."""
    return "\n".join([*_HEADER, *full_lines(tree)]) + "\n"


def write_copy(path: Path, tree: dict[str, list[str]]) -> bool:
    """Write ``tree``'s inventory_text to ``path``; True when the text there changed."""
    text = inventory_text(tree)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def staged_copy(root: Path = ROOT) -> str | None:
    """INVENTORY_FILE as the index holds it -- what the next commit carries; None when the index holds none."""
    return _index_texts([INVENTORY_FILE], root).get(INVENTORY_FILE)


def stale_message(root: Path = ROOT) -> str | None:
    """None when the staged copy is the map of the staged tree; else what is wrong and the fix."""
    staged = staged_copy(root)
    if staged == inventory_text(inventory(root)):
        return None
    state = "is not in the index" if staged is None else "is stale for this commit -- the tracked files moved"
    carry = f"then carry {INVENTORY_FILE} in this commit (git add it, or name it among the commit's paths)"
    return f"repo inventory: {INVENTORY_FILE} {state}. Fix: {_REGENERATE}, {carry}."


def main(argv: list[str] | None = None) -> int:
    """Print the summary, every entry (--full) or the entries matching words (--match / --text); write the committed copy
    (--write); or exit 1 when the staged copy is not the staged tree's map (--check, the pre-commit gate)."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--full", action="store_true", help="every entry of every category")
    parser.add_argument("--match", nargs="*", default=[], help="words to match the entries on")
    parser.add_argument("--text", default="", help="free text (an item, a question): its words are matched")
    parser.add_argument("--write", action="store_true", help=f"write the committed copy, {INVENTORY_FILE}")
    parser.add_argument("--check", action="store_true", help="exit 1 when the staged copy is not the staged tree's map")
    args = parser.parse_args(argv)
    if args.check:
        problem = stale_message()
        if problem:
            print(problem)
            return 1
        return 0
    tree = inventory()
    if args.write:
        changed = write_copy(ROOT / INVENTORY_FILE, tree)
        print(f"{INVENTORY_FILE}: {'written' if changed else 'already current'} ({sum(len(e) for e in tree.values())} entries)")
        return 0
    matched: list[str] = args.match
    text: str = args.text
    words = [*matched, *search_words(text)]
    if words:
        print("\n".join(match_lines(tree, words)))
    elif args.full:
        print("\n".join(full_lines(tree)))
    else:
        print("\n".join(summary_lines(tree)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
