"""apps/api root for tests — SoT is ``paths.API_ROOT_PATH`` (no private parents[N]).

REUSE-AUDIT: production uses ``src.shared.constants.paths.API_ROOT_PATH`` and
``research_loop_paths.api_package_root``. Tests must not invent a third parents[N]
ladder; this helper is the one bootstrap for the test tree.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.shared.constants.paths import API_ROOT_PATH, RESEARCH_ROOT_REL
from src.shared.constants.research_loop_paths import repo_root

#: Alias so call sites can keep a short name without recomputing parents[N].
API_ROOT: Path = API_ROOT_PATH
#: ``apps/api/tests`` — fixtures / contract goldens live here.
TESTS_ROOT: Path = API_ROOT / "tests"
#: Monorepo root (``.claude/hooks``, ``apps/web``) — SoT ``research_loop_paths.repo_root``.
REPO_ROOT: Path = repo_root()
#: The research LAB. It moved from scripts/research into src/research on 2026-10-03 and keeps its own gate
#: policy; a production-src architecture test walks ``production_src_py()``, never ``src.rglob``.
RESEARCH_LAB: Path = API_ROOT / RESEARCH_ROOT_REL

__all__ = [
    "API_ROOT",
    "REPO_ROOT",
    "RESEARCH_LAB",
    "TESTS_ROOT",
    "ensure_api_root_on_sys_path",
    "is_research_lab",
    "production_src_py",
]


def is_research_lab(path: Path) -> bool:
    """True for a path inside the research lab (src/research)."""
    return path.resolve().is_relative_to(RESEARCH_LAB)


def production_src_py(root: Path | None = None) -> list[Path]:
    """Sorted .py files under ``root`` (default apps/api/src), minus the research lab and caches."""
    base = root or API_ROOT / "src"
    return sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts and not is_research_lab(p))


def ensure_api_root_on_sys_path() -> Path:
    """Insert ``apps/api`` on ``sys.path`` once (script-style test imports)."""
    root = str(API_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return API_ROOT
