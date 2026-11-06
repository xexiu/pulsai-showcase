"""Standards rules: each counts exactly the shape its rule names, judged per file and ratcheted over the tree.

IMPORTERS/CALLERS: none (a test module). AFFECTED API: src/lib/quality_gates/standards_rules (RULES, tree_totals,
measured_totals, ratchet_standards) and rule_spec's ruff / basedpyright instruments. DATA SCHEMAS: none.

REUSE-AUDIT: considered tests/scripts/test_check_touched_debt.py (it pins the touch rule on real git repos; these pin
each rule's counter and the tree totals).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from src.lib.quality_gates import rule_spec
from src.lib.quality_gates import standards_rules as std

RULE = {r.key: r for r in std.RULES}
_LONG_BODY = "".join(f"    x{i} = {i}\n" for i in range(std.MAX_FUNCTION_LINES + 1))
_BODY_99 = "".join(f"    x{i} = {i}\n" for i in range(std.MAX_FUNCTION_LINES - 1))

#: rule key -> (a text holding exactly one finding, the same idea written the way the rule asks)
CASES: dict[str, tuple[str, str]] = {
    "nested-ternary": (
        "def f(a, b):\n    return 1 if a else 2 if b else 3\n",
        "def f(a, b):\n    if a:\n        return 1\n    return 2 if b else 3\n",
    ),
    "type-suppression": ("x: int = 'a'  # type: ignore[assignment]\n", "x: str = 'a'\n"),
    "numba-loop-reuse": (
        "from numba import njit\n\n\n@njit\ndef f(n):\n    for i in range(n):\n        pass\n    for i in range(n):\n        pass\n",
        "from numba import njit\n\n\n@njit\ndef f(n):\n    for i in range(n):\n        pass\n    for j in range(n):\n        pass\n",
    ),
    # the span counts the def line and not the docstring: 1 + 101 lines is a finding, 1 + 99 is not
    "long-function": (f'def f():\n    """Doc."""\n{_LONG_BODY}', f'def f():\n    """Doc."""\n{_BODY_99}'),
    "global-statement": ("STATE = 0\n\n\ndef f():\n    global STATE\n    STATE = 1\n", "class Box:\n    state = 0\n"),
    "numeric-http-status": (
        "from fastapi import HTTPException\n\n\ndef f():\n    raise HTTPException(404, 'gone')\n",
        "from fastapi import HTTPException, status\n\n\ndef f():\n    raise HTTPException(status.HTTP_404_NOT_FOUND, 'gone')\n",
    ),
    "print-call": ("def f(x):\n    print(x)\n", "import logging\n\n\ndef f(x):\n    logging.getLogger(__name__).info(x)\n"),
    "fat-protocol": (
        "from typing import Protocol\n\n\nclass P(Protocol):\n" + "".join(f"    def m{i}(self) -> None: ...\n" for i in range(8)),
        "from typing import Protocol\n\n\nclass P(Protocol):\n" + "".join(f"    def m{i}(self) -> None: ...\n" for i in range(7)),
    ),
    "mutable-value-object": (
        "from dataclasses import dataclass\n\n\n@dataclass\nclass Price:\n    value: float\n",
        "from dataclasses import dataclass\n\n\n@dataclass(frozen=True)\nclass Price:\n    value: float\n",
    ),
    "lab-complexity": (
        "def f(x: int) -> int:\n    y = 0\n" + "".join(f"    if x == {i}:\n        y += {i}\n" for i in range(14)) + "    return y\n",
        "def f(x: int) -> int:\n    return x + 1\n",
    ),
    "lab-silent-failure": (
        "def f() -> int:\n    try:\n        return int('1')\n    except Exception:\n        return 0\n",
        "def f() -> int:\n    try:\n        return int('1')\n    except ValueError:\n        return 0\n",
    ),
    "lab-silent-return": (
        "def pick(x: int) -> int | None:\n    if x > 1:\n        return None\n    if x < 0:\n        return None\n    return x\n",
        "def pick(x: int) -> int:\n    if x > 1 or x < 0:\n        raise ValueError(x)\n    return x\n",
    ),
    "lab-magic-number": ("def f(x: int) -> bool:\n    return x > 17\n", "LIMIT = 17\n\n\ndef f(x: int) -> bool:\n    return x > LIMIT\n"),
    "lab-bug-class": (
        "def f(x: str) -> object:\n    return eval(x)\n",
        "import ast\n\n\ndef f(x: str) -> object:\n    return ast.literal_eval(x)\n",
    ),
    "missing-docstring": ("def build() -> int:\n    return 1\n", 'def build() -> int:\n    """One."""\n    return 1\n'),
    "deep-nesting": (
        "def f(a: list[list[list[list[list[list[int]]]]]]) -> int:\n    n = 0\n    for b in a:\n        for c in b:\n            for d in c:\n                for e in d:\n                    for g in e:\n                        for h in g:\n                            n += h\n    return n\n",
        "def f(a: list[int]) -> int:\n    n = 0\n    for b in a:\n        n += b\n    return n\n",
    ),
    "io-property": (
        "class C:\n    @property\n    def rows(self):\n        return self.session.execute('x')\n",
        "class C:\n    def rows(self):\n        return self.session.execute('x')\n",
    ),
    # E402 is waived for the lab in pyproject: the row still counts it, so a touched lab file pays it down
    "lab-ruff": ("X = 1\nimport os\n\nY = os.sep\n", "import os\n\nX = 1\nY = os.sep\n"),
    # PERF-RATCHET (2026-10-14): a list built by a loop (PERF401) -> the comprehension
    "perf-loops": (
        "def f(xs: list[int]) -> list[int]:\n    out = []\n    for x in xs:\n        out.append(x * 2)\n    return out\n",
        "def f(xs: list[int]) -> list[int]:\n    return [x * 2 for x in xs]\n",
    ),
    "pandas-vet": (
        "import pandas as pd\n\n\ndef f(df: pd.DataFrame) -> object:\n    return df.values\n",
        "import pandas as pd\n\n\ndef f(df: pd.DataFrame) -> object:\n    return df.to_numpy()\n",
    ),
    # the classic per-bar scalar read -> one vectorised comparison
    "pandas-loop": (
        "def first(c, st, n):\n    for i in range(n):\n        if c.iloc[i] < st.iloc[i]:\n            return i\n    return -1\n",
        "import numpy as np\n\n\ndef first(c, st):\n    hits = np.flatnonzero(c.to_numpy() < st.to_numpy())\n    return int(hits[0]) if len(hits) else -1\n",
    ),
    "pandas-undeclared": ("import pandas as pd\n\nX = pd.Series([1, 2])\n", "import numpy as np\n\nX = np.array([1, 2])\n"),
    # ANN-GATE (owner, 2026-10-18): a parameter without its type -> the signature says what it takes
    "missing-annotation": (
        "def scale(x, factor: float) -> float:\n    return x * factor\n",
        "def scale(x: float, factor: float) -> float:\n    return x * factor\n",
    ),
    # a bare `list` is list[Unknown] -> the element type written down
    "unknown-type": ("def size(rows: list) -> int:\n    return len(rows)\n", "def size(rows: list[int]) -> int:\n    return len(rows)\n"),
}


def test_every_rule_has_a_case() -> None:
    assert set(CASES) == set(RULE)


#: Where a rule's case is judged: the first of these it applies to (ruff reads its config by path).
_PATHS = ("apps/api/src/application/services/c.py", "apps/api/src/research/edge_hunt/c.py", "apps/api/src/domain/value_objects/c.py")


@pytest.mark.parametrize("key", sorted(CASES))
def test_a_rule_counts_its_shape_and_not_the_asked_for_spelling(key: str) -> None:
    finding, fixed = CASES[key]
    rule = RULE[key]
    path = next(p for p in _PATHS if rule.applies(p))
    assert rule.count_file(path, finding) >= 1
    assert rule.count_file(path, fixed) == 0


def test_a_text_that_does_not_parse_counts_nothing_rather_than_crashing() -> None:
    assert all(rule.count("def (:\n") == 0 for rule in std.RULES)


def test_scopes_judge_the_files_the_rule_is_about() -> None:
    assert RULE["print-call"].applies("apps/api/src/application/x.py")
    assert not RULE["print-call"].applies("apps/api/src/scripts/x.py")  # CLIs print by design
    assert not RULE["print-call"].applies("apps/api/src/research/x.py")
    assert RULE["mutable-value-object"].applies("apps/api/src/domain/value_objects/price.py")
    assert RULE["nested-ternary"].applies("apps/api/src/research/x.py")
    assert not RULE["nested-ternary"].applies("apps/web/x.py")


def test_a_ruff_tree_total_counts_the_tracked_files_in_scope_and_nothing_else(tmp_path: Path) -> None:
    """Files are handed to ruff one by one: overlapping directory roots made ruff 0.15.6 drop a file's findings in
    about half the runs. An untracked file, or one outside the rule's scope, is never counted."""
    lab = tmp_path / "apps" / "api" / "src" / "research"
    lab.mkdir(parents=True)
    for name in ("a.py", "scratch.py"):
        (lab / name).write_text("def f(x: str) -> object:\n    return eval(x)\n")
    (tmp_path / "apps" / "api" / "src" / "product.py").write_text("def f(x: str) -> object:\n    return eval(x)\n")
    tracked = {"apps/api/src/research/a.py", "apps/api/src/product.py"}
    assert std.ruff_tree_total(RULE["lab-bug-class"], tmp_path, tracked) == 1
    assert std.ruff_tree_total(RULE["lab-bug-class"], tmp_path, set()) == 0


def test_a_head_file_moved_off_disk_is_skipped_not_handed_to_the_instrument(tmp_path: Path) -> None:
    """8f: a staged git mv left HEAD's path missing on disk and crashed basedpyright for the whole ratchet. The tree
    totals measure what is on disk; the moved file counts under its new path once committed."""
    lab = tmp_path / "apps" / "api" / "src" / "research"
    lab.mkdir(parents=True)
    (lab / "a.py").write_text("def f(x: str) -> object:\n    return eval(x)\n")
    tracked = {"apps/api/src/research/a.py", "apps/api/src/research/moved_away.py"}
    assert std.ruff_tree_total(RULE["lab-bug-class"], tmp_path, tracked) == 1


@pytest.fixture
def failing_ruff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A ruff that exits 2, the way a crashed or misconfigured one does."""
    binary = tmp_path / "ruff"
    binary.write_text("#!/bin/sh\necho 'ruff: boom' >&2\nexit 2\n")
    binary.chmod(0o755)
    monkeypatch.setattr(rule_spec, "ruff_binary", lambda: str(binary))
    return binary


def test_a_ruff_that_cannot_run_is_never_read_as_a_clean_file(failing_ruff: Path) -> None:
    rule = RULE["lab-bug-class"]
    with pytest.raises(std.InstrumentUnavailableError, match="ruff failed"):
        rule.count_file("apps/api/src/research/a.py", "x = 1\n")
    with pytest.raises(std.InstrumentUnavailableError, match="ruff failed over the tree"):
        std.ruff_tree_total(rule, std._REPO, {"apps/api/src/research/kline_columns.py"})


def test_no_ruff_anywhere_is_instrument_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rule_spec, "API_ROOT", tmp_path)
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(std.InstrumentUnavailableError, match="ruff not found"):
        rule_spec.ruff_binary()


# The tree measurement itself is a GATE STEP, not a unit test (SLOW-TESTS, 2026-10-18: 118 s in every edit loop):
# verify.sh 2f-std and the CI step 'Standards tree ratchet' run the CLI, which exits 1 on a rise, an unrecorded fall,
# or a dead rule (0 against a non-zero baseline). The ratchet's logic is tested below on faked totals.


def test_verify_and_ci_run_the_tree_ratchet() -> None:
    """The tree measurement moved out of pytest; this keeps the two gate steps that run it from disappearing."""
    verify = (std._REPO / "apps" / "api" / "scripts" / "verify.sh").read_text(encoding="utf-8")
    ci = (std._REPO / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "python3 -m src.lib.quality_gates.standards_rules" in verify
    assert "python -m src.lib.quality_gates.standards_rules" in ci


@pytest.mark.parametrize(("delta", "code", "verb"), [(0, 0, ""), (1, 1, "ROSE"), (-1, 1, "fell")])
def test_the_ratchet_refuses_a_rise_and_an_unrecorded_fall(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], delta: int, code: int, verb: str
) -> None:
    measured = {r.key: r.baseline for r in std.RULES} | {"missing-annotation": RULE["missing-annotation"].baseline + delta}
    monkeypatch.setattr(std, "measured_totals", lambda _repo: measured)
    assert std.ratchet_standards(std._REPO) == code
    assert verb in capsys.readouterr().out


def test_the_tree_lists_the_tests_no_ast_rule_reads() -> None:
    """sources_at_ref reads src + scripts; the ruff rows judge tests too, so their tree total lists the tracked tests."""
    tests = std.tracked_tests(std._REPO)
    assert len(tests) > 1000
    assert all(p.startswith(std.TESTS_PREFIX) and p.endswith(".py") for p in tests)


def test_the_lab_waiver_hides_a_finding_from_lint_but_never_from_its_ratchet() -> None:
    """RUFF-RESEARCH (owner, 2026-10-13): the lab is linted; its existing debt is waived per code in pyproject. A
    waived code must vanish from a plain run (CI stays green) and still count for the row that ratchets it."""
    lab, text = "apps/api/src/research/edge_hunt/c.py", "def f(x: int) -> bool:\n    return x > 17\n"
    assert std.ruff_findings(("PLR2004",), lab, text) == 0  # the waiver, as `ruff check .` reads it
    assert std.ruff_findings(("PLR2004",), lab, text, waived=True) == 1  # the ratchet's count
    assert std.ruff_findings(("PLR2004",), "apps/api/src/application/c.py", text) == 1  # product: never waived


def test_the_waiver_is_read_from_pyproject_and_conventions_are_not_debt() -> None:
    codes = rule_spec.lab_waiver_codes()
    assert {"E402", "PLR2004", "ANN001"} <= set(codes)
    assert not {"N803", "N806", "N811", "N812"} & set(codes)  # naming conventions, kept on purpose
    owned = {c for r in std.RULES if r.key != "lab-ruff" and r.applies("apps/api/src/research/x.py") for c in r.ruff_codes}
    assert not owned & set(RULE["lab-ruff"].ruff_codes)  # each waived finding is counted by one row only
    assert not {"ANN001", "ANN201", "ANN202"} & set(RULE["lab-ruff"].ruff_codes)  # missing-annotation owns them
    assert RULE["lab-ruff"].applies("apps/api/tests/unit/research/test_x.py")


def test_a_lab_test_answers_to_the_lab_waiver_not_to_every_test_convention() -> None:
    """The lab rows lift the LAB waiver only. A lab test keeps the tests' conventions (an unused fixture argument is
    pytest wiring, ARG001); the same finding in lab code is waived debt the row counts."""
    text = "def check(fixture_a: int) -> None:\n    assert True\n"
    assert RULE["lab-ruff"].count_file("apps/api/tests/unit/research/test_x.py", text) == 0
    assert RULE["lab-ruff"].count_file("apps/api/src/research/x.py", text) == 1


_SIGNATURE_JUDGED = (
    "apps/api/src/application/x.py",
    "apps/api/src/scripts/x.py",
    "apps/api/src/research/x.py",
    "apps/api/scripts/x.py",
    "apps/api/tests/unit/test_x.py",
    "apps/api/tests/unit/research/test_x.py",
)


def test_annotations_are_counted_everywhere_through_every_exemption() -> None:
    """ANN-GATE (owner, 2026-10-18: "enforce annotations everywhere"): product, CLIs, the lab, ops scripts and tests.
    The tests' blanket ANN exemption, the CLIs' ANN001 and the lab waiver hide the finding from `ruff check .`; the row
    counts it through all of them (and past noqa)."""
    rule, text = RULE["missing-annotation"], "def helper(x):  # noqa: ANN001\n    return x\n"
    assert all(rule.applies(p) for p in _SIGNATURE_JUDGED)
    assert not rule.applies("apps/web/x.py")
    assert not rule.applies("apps/api/alembic/versions/x.py")
    assert std.ruff_findings(rule.ruff_codes, "apps/api/tests/unit/test_x.py", text) == 0  # as `ruff check .` reads it
    assert all(rule.count_file(p, text) == 2 for p in _SIGNATURE_JUDGED)  # ANN001 + ANN201
    assert "ANN401" not in rule.ruff_codes  # an explicit Any is written down: explicit_any owns it


def test_unknown_types_are_judged_in_product_code_only() -> None:
    rule = RULE["unknown-type"]
    assert rule.applies("apps/api/src/application/x.py")
    assert not rule.applies("apps/api/src/research/x.py")
    assert not rule.applies("apps/api/tests/unit/test_x.py")


def test_the_unknown_type_count_resolves_imports_like_the_real_tree() -> None:
    """The text is checked in a symlinked copy of apps/api: a relative import of a sibling resolves as it does on disk.
    Were it unresolved, ROOT would be of unknown type and counted."""
    rule = RULE["unknown-type"]
    assert rule.count_file("apps/api/src/lib/quality_gates/probe.py", "from .rule_spec import API_ROOT\n\nROOT = API_ROOT\n") == 0
    assert rule.count_file("apps/api/src/new_pkg/deep/probe.py", "def size(rows: list) -> int:\n    return len(rows)\n") >= 1


def test_the_root_pyright_config_keeps_the_unknown_rules_off() -> None:
    """The row runs basedpyright with a config of its own: switching the rules on in the root config would paint every
    existing finding red in the IDE and in the pre-push basedpyright gate."""
    root = json.loads(rule_spec.PYRIGHT_CONFIG.read_text(encoding="utf-8"))
    assert RULE["unknown-type"].pyright_rules
    assert not set(RULE["unknown-type"].pyright_rules) & set(root)


@pytest.fixture
def failing_basedpyright(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A basedpyright that exits 3 with no JSON, the way a bad config does."""
    binary = tmp_path / "basedpyright"
    binary.write_text("#!/bin/sh\necho 'config error' >&2\nexit 3\n")
    binary.chmod(0o755)
    monkeypatch.setattr(rule_spec, "pyright_binary", lambda: str(binary))
    return binary


def test_a_basedpyright_that_cannot_run_is_never_read_as_a_clean_file(failing_basedpyright: Path) -> None:
    rule = RULE["unknown-type"]
    with pytest.raises(std.InstrumentUnavailableError, match="basedpyright failed"):
        rule.count_file("apps/api/src/application/x.py", "x = 1\n")
    with pytest.raises(std.InstrumentUnavailableError, match="basedpyright failed"):
        std.pyright_tree_total(rule, std._REPO, {"apps/api/src/main.py"})


def test_no_basedpyright_anywhere_is_instrument_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rule_spec, "API_ROOT", tmp_path)
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(std.InstrumentUnavailableError, match="basedpyright not found"):
        rule_spec.pyright_binary()


def test_a_cli_module_prints_by_design() -> None:
    """A module with a __main__ entry point is a CLI (the quality-gate tools): stdout is its interface."""
    cli = 'def main() -> None:\n    print("report")\n\n\nif __name__ == "__main__":\n    main()\n'
    assert RULE["print-call"].count(cli) == 0


def test_a_comment_quoting_a_directive_is_not_a_suppression() -> None:
    """mypy and pyright honour a directive only where a comment segment starts; prose in backticks is not one."""
    assert RULE["type-suppression"].count("# the old line carried `# pyright: ignore[x]` with its reason\nx = 1\n") == 0
    assert RULE["type-suppression"].count("x = f()  # noqa: E501  # type: ignore[no-untyped-call]\n") == 1


@pytest.mark.parametrize(
    ("key", "path", "text"),
    [
        ("long-function", "apps/api/src/application/x.py", f"def big() -> None:\n{_LONG_BODY}"),
        ("nested-ternary", "apps/api/src/application/x.py", "y = 1 if a else 2 if b else 3\nz = 4 if c else 5 if d else 6\n"),
        ("type-suppression", "apps/api/src/application/x.py", "x = f()  # type: ignore[call]\n"),
        ("lab-magic-number", "apps/api/src/research/x.py", "def f(v: int) -> bool:\n    return v > 7 and v < 99\n"),
        ("pandas-undeclared", "apps/api/src/research/x.py", "import pandas as pd\n\nq = pd.Series([1])\nr = pd.Series([2])\n"),
    ],
)
def test_each_finding_is_located_exactly_as_often_as_it_is_counted(key: str, path: str, text: str) -> None:
    """LOCATE (owner, 2026-10-19): a row said only 'N at HEAD, now N'. It now says where -- read from the same sites
    or diagnostics it counts, so a list can never be longer or shorter than its count."""
    rule = RULE[key]
    found = rule.locate(path, text)

    assert len(found) == rule.count_file(path, text) >= 1
    assert all(line.startswith("L") and line[1].isdigit() for line in found)


def test_the_list_cli_prints_each_rows_findings_with_their_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lab = tmp_path / "apps" / "api" / "src" / "research" / "probe.py"
    lab.parent.mkdir(parents=True)
    lab.write_text("def f(v: int) -> bool:\n    return v > 7\n", encoding="utf-8")
    monkeypatch.setattr(std, "API_ROOT", tmp_path / "apps" / "api")

    assert std.main(["--list", "src/research/probe.py"]) == 0
    printed = capsys.readouterr().out
    assert "lab-magic-number: 1" in printed
    assert "L2 PLR2004" in printed
