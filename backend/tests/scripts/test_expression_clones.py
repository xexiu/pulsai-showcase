"""Expression clones: the same normalised expression in two functions anywhere in src/ and scripts/ is one finding.

IMPORTERS/CALLERS: none (a test module). AFFECTED API: src/lib/quality_gates/expression_clones (occurrences,
clone_index, index_for, CloneIndex, ratchet_expression_clones). DATA SCHEMAS: the cache file (content hash -> occurrences).

REUSE-AUDIT: considered tests/scripts/test_concept_definitions.py (names and registered shapes, not arbitrary
expressions) -- this pins the general layer DRY-GENERIC-SRC adds.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.lib.quality_gates import expression_clones as clones
from src.lib.quality_gates.concept_definitions import sources_on_disk

if TYPE_CHECKING:
    import pytest

#: 25+ AST nodes: the annualised Sharpe the lab re-derived in 68 functions.
SHARPE = "float(r.mean() / r.std() * np.sqrt(bpy)) if len(r) > 30 else 0.0"


def _module(fn: str, expr: str, *, var: str = "r") -> str:
    return f"import numpy as np\n\n\ndef {fn}({var}, bpy):\n    return {expr.replace('r.', f'{var}.').replace('len(r)', f'len({var})')}\n"


def _index(files: dict[str, str]) -> clones.CloneIndex:
    return clones.index_for(files, cache_path=None)


def test_one_expression_in_two_functions_of_two_files_is_one_group() -> None:
    """Renaming the variable does not hide the copy: names are placeholders."""
    index = _index({"apps/api/src/research/a.py": _module("score_a", SHARPE), "apps/api/scripts/b.py": _module("score_b", SHARPE, var="ret")})
    assert list(index.groups.values()) == [frozenset({("apps/api/src/research/a.py", "score_a"), ("apps/api/scripts/b.py", "score_b")})]


def test_a_different_constant_or_attribute_is_a_different_concept() -> None:
    other = SHARPE.replace("> 30", "> 20").replace("np.sqrt", "np.log")
    assert _index({"apps/api/src/a.py": _module("f", SHARPE), "apps/api/src/b.py": _module("g", other)}).groups == {}


def test_a_small_expression_is_not_a_concept() -> None:
    small = "r.mean() / r.std()"
    assert _index({"apps/api/src/a.py": _module("f", small), "apps/api/src/b.py": _module("g", small)}).groups == {}


def test_annotations_messages_and_f_strings_are_not_candidates() -> None:
    """The measured noise: a long type annotation, a print / log line, an f-string message."""
    body = (
        "import logging\nlog = logging.getLogger(__name__)\n\n\n"
        "def {fn}(x: dict[str, dict[str, dict[str, dict[str, int]]]]) -> dict[str, dict[str, dict[str, int]]]:\n"
        "    print(x['a'], x['b'], x['c'], x['d'], x['e'], x['f'], sep=', ', flush=True)\n"
        "    log.info('%s %s %s %s', x['a'], x['b'], x['c'], x['d'], x['e'], x['f'])\n"
        "    return {{}}\n"
    )
    files = {"apps/api/src/a.py": body.format(fn="f"), "apps/api/src/b.py": body.format(fn="g")}
    assert _index(files).groups == {}


def test_only_the_maximal_clone_is_reported() -> None:
    """The Sharpe expression holds a 20+ node part; a part held by exactly the same functions is not a second group."""
    index = _index({"apps/api/src/a.py": _module("f", SHARPE), "apps/api/src/b.py": _module("g", SHARPE)})
    assert len(index.groups) == 1


def test_a_judged_exception_says_clone_ok_on_its_line() -> None:
    marked = _module("g", SHARPE).replace("else 0.0\n", "else 0.0  # CLONE-OK: Pine transcription, mirrors its source\n")
    assert _index({"apps/api/src/a.py": _module("f", SHARPE), "apps/api/src/b.py": marked}).groups == {}


def test_out_of_scope_files_are_not_read() -> None:
    files = {"apps/api/src/a.py": _module("f", SHARPE), "apps/web/b.py": _module("g", SHARPE)}
    assert _index(files).groups == {}


def test_the_report_names_a_src_shared_home_or_asks_for_one() -> None:
    homed = _index({"apps/api/src/shared/math/sharpe.py": _module("annualised_sharpe", SHARPE), "apps/api/src/b.py": _module("g", SHARPE)})
    assert "HOME apps/api/src/shared/math/sharpe.py::annualised_sharpe" in homed.report()[0]
    homeless = _index({"apps/api/src/a.py": _module("f", SHARPE), "apps/api/src/b.py": _module("g", SHARPE)})
    assert "give it one in src/shared" in homeless.report()[0]


def test_a_files_debt_is_its_clone_memberships() -> None:
    index = _index(
        {"apps/api/src/a.py": _module("f", SHARPE) + _module("h", SHARPE).split("\n\n\n", 1)[1], "apps/api/src/b.py": _module("g", SHARPE)}
    )
    assert (index.sites_in("apps/api/src/a.py"), index.sites_in("apps/api/src/b.py"), index.sites_in("apps/api/src/c.py")) == (2, 1, 0)


def test_the_cache_skips_texts_it_has_seen_and_survives_a_bad_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = tmp_path / "clones.json"
    files = {"apps/api/src/a.py": _module("f", SHARPE), "apps/api/src/b.py": _module("g", SHARPE)}
    first = clones.index_for(files, cache_path=cache)
    calls: list[str] = []
    real = clones.occurrences

    def spy(text: str) -> list[clones.Occurrence]:
        calls.append(text)
        return real(text)

    monkeypatch.setattr(clones, "occurrences", spy)
    assert clones.index_for(files, cache_path=cache).groups == first.groups
    assert calls == []
    cache.write_text(cache.read_text().replace('"files": {', '"files": {"bad": [["", "f", "x", ""]], ', 1))
    assert clones.index_for(files, cache_path=cache).groups == first.groups  # a malformed row is dropped, never grouped


def test_the_real_tree_is_read_and_holds_the_measured_clone() -> None:
    """Canary: a scope or parse mistake reads as a clean tree. The lab's Sharpe copy must be found, many times over."""
    index = clones.index_for(sources_on_disk(clones._REPO), clones.cache_for(clones._REPO))
    assert len(index.groups) > 500
    assert max(len(sites) for sites in index.groups.values()) >= 20


def test_the_tree_ratchet_is_current() -> None:
    """The recorded baseline equals the measured count (a fall must be locked, a rise refused)."""
    assert clones.ratchet_expression_clones(clones._REPO) == 0, f"re-measure: BASELINE_CLONE_GROUPS is {clones.BASELINE_CLONE_GROUPS}"


# SAME-VALUE (2026-10-18): a small helper copied under a new name -- no single expression of it reaches MIN_NODES, so
# only its WHOLE body can be compared. Locals and parameters are placeholders; a global name resolves to its origin.
_CHECK = "def {name}(entry_price, leverage):\n    if entry_price <= 0 or leverage < 1:\n        msg = 'bad inputs'\n        raise ValueError(msg)\n"


def test_a_small_helper_copied_under_another_name_is_one_group() -> None:
    files = {
        "apps/api/src/shared/math/a.py": _CHECK.format(name="_check_inputs"),
        "apps/api/src/cert/b.py": _CHECK.format(name="_validate").replace("entry_price", "px"),
    }

    groups = list(_index(files).groups.values())

    assert frozenset({("apps/api/src/shared/math/a.py", "_check_inputs"), ("apps/api/src/cert/b.py", "_validate")}) in groups


def test_the_same_body_over_each_modules_own_constant_is_not_a_clone() -> None:
    """`return shared(w, COST)` where every module's COST is its own: the measured _net_from_w x42 lookalike."""
    body = "from src.shared.costs import shared\nCOST = {cost}\n\n\ndef _net(w, r):\n    out = shared(w, r, COST)\n    return out * 2.0 + 1.0\n"
    files = {"apps/api/src/research/a.py": body.format(cost=1.0), "apps/api/src/research/b.py": body.format(cost=2.0)}

    assert not any(site[1] == "_net" for sites in _index(files).groups.values() for site in sites)


def test_a_body_below_the_floor_is_not_a_candidate() -> None:
    tiny = "def {name}(self):\n    return self._x\n"
    files = {"apps/api/src/a.py": tiny.format(name="x"), "apps/api/src/b.py": tiny.format(name="y")}

    assert _index(files).groups == {}
