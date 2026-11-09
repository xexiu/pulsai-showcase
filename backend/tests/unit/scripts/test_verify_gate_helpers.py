"""Behavior contracts for verify.sh gate helpers (touch-gate + research bug count).

PRO tests: lock the regressions we already paid for in production:
- path filter must include untracked ``apps/api/src/**/*.py`` without relying on ``**`` globs
- basedpyright JSON summary must parse without fragile nested greps as the SoT
- research concise lines with ANSI color must still count (false-zero bug)
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

# REUSE-AUDIT: web verify-script + hook guards are different surfaces; this module is SoT.
from src.lib.quality_gates.verify_gate_helpers import (
    BASEDPYRIGHT_ERROR_BASELINE,
    NOQA_BASELINE,
    count_noqa_comments,
    count_research_bug_findings,
    main,
    normalize_typecheck_relpaths,
    parse_basedpyright_counts,
    production_src_targets,
    silent_return_functions,
)
from src.shared.constants.research_loop_paths import repo_root


def test_normalize_keeps_unique_sorted_src_py_relpaths() -> None:
    raw = [
        "apps/api/src/workers/tasks/generate_signals.py",
        "apps/api/scripts/verify.sh",
        "apps/api/src/workers/tasks/generate_signals.py",
        "apps/api/src/domain/services/edge_lifecycle/capital_cert_promote.py",
        "apps/web/src/foo.ts",
        "apps/api/src/README.md",
    ]

    got = normalize_typecheck_relpaths(raw)

    assert got == [
        "src/domain/services/edge_lifecycle/capital_cert_promote.py",
        "src/workers/tasks/generate_signals.py",
    ]


def test_normalize_includes_untracked_src_paths_without_globstar() -> None:
    """``git ls-files --others apps/api/src/`` returns plain paths; filter must accept them."""
    raw = ["apps/api/src/_touch_gate_probe.py"]

    assert normalize_typecheck_relpaths(raw) == ["src/_touch_gate_probe.py"]


def test_normalize_admits_research_scripts_to_the_typecheck_gate() -> None:
    """A changed research script must reach basedpyright — owner: "add it also".

    This filter returned ``src/`` only, so ``src/research`` was invisible to the verify 2i
    touch-gate no matter what ``pyrightconfig.json`` said. That is half of why an undefined name
    (``MIN_ABS_T_FOR_SIGNAL`` in ``llm_market_decision.py``) lived in a committed file long enough
    to crash the 8h, 6h and 1d runs immediately before each printed its verdict.
    """
    raw = [
        "apps/api/src/research/edge_hunt/llm_market_decision.py",
        "apps/api/src/workers/tasks/generate_signals.py",
    ]

    assert normalize_typecheck_relpaths(raw) == [
        "src/research/edge_hunt/llm_market_decision.py",
        "src/workers/tasks/generate_signals.py",
    ]


def test_normalize_still_rejects_scripts_outside_research() -> None:
    """Widening is two named trees, not "scripts/". A one-off script is not gated by this."""
    raw = ["apps/api/scripts/ship_model_to_r2.py", "apps/api/src/research/edge_hunt/x.py"]

    assert normalize_typecheck_relpaths(raw) == ["src/research/edge_hunt/x.py"]


def test_parse_basedpyright_counts_reads_summary() -> None:
    payload = '{"summary":{"errorCount":3,"warningCount":1,"informationCount":0}}'

    errors, warnings = parse_basedpyright_counts(payload)

    assert errors == 3
    assert warnings == 1


def test_parse_basedpyright_counts_unparseable_returns_none() -> None:
    errors, warnings = parse_basedpyright_counts("not-json{{{")

    assert errors is None
    assert warnings is None


def test_count_research_bugs_ignores_ansi_and_non_matching_lines() -> None:
    concise = (
        "\x1b[1msrc/research/ampe_inspired_scout_wf_oos.py\x1b[0m:217:19: F541 f-string\n"
        "tests/unit/research/test_foo.py:1:1: F401 unused import\n"
        "somewhere/else.py:1:1: F401 should not count\n"
        "src/application/services/x.py:1:1: F401 production src is not the lab\n"
        "\n"
    )

    assert count_research_bug_findings(concise) == 2


def test_production_src_is_every_src_entry_but_the_research_lab() -> None:
    """The full mypy/basedpyright gates scan production src/; the lab (moved into src/research on 2026-10-03)
    keeps its own ratchets. pyright's exclude also silences EXPLICITLY passed files (measured: 0 analyzed),
    so the lab cannot be excluded in pyrightconfig -- the full run names production src instead."""
    targets = production_src_targets()

    assert "src/research" not in targets
    assert {"src/application", "src/domain", "src/cert"} <= set(targets)
    assert all(t.startswith("src/") and "__pycache__" not in t for t in targets)


class TestBasedpyrightBaselineHasOneSource:
    """The ratchet number must live in ONE place, and CI must parse with the tested SoT.

    Landed 2026-08-24: the CI mirror hardcoded its own ``'72'`` while its comment named
    ``verify.sh`` as the SoT, and re-implemented the JSON summary parse with ``grep``.
    Both ratchets are two-sided (they fail when the count FALLS, to force locking the gain
    in), so a drifted copy does not fail once -- it fails EVERY later PR until a human
    notices the second file. verify.sh's own "lock the gain" message never mentions
    ci.yml, so drift is the expected outcome of paying type debt, not a rare accident.
    """

    def test_baseline_cli_prints_the_single_source_value(self, capsys: pytest.CaptureFixture[str]) -> None:
        """``verify_gate_helpers.py baseline`` is the one place bash reads the number from."""
        assert main(["baseline"]) == 0
        assert capsys.readouterr().out.strip() == str(BASEDPYRIGHT_ERROR_BASELINE)

    def test_ci_workflow_does_not_hardcode_a_second_baseline(self) -> None:
        """A mirror needs a mechanism: ci.yml must derive the number, never restate it."""
        ci = (repo_root() / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        hardcoded = re.search(r"BASEDPYRIGHT_ERROR_BASELINE:\s*'?\d+'?", ci)
        assert hardcoded is None, (
            f"ci.yml hardcodes the baseline ({hardcoded.group(0) if hardcoded else ''}); "
            "derive it from src/lib/quality_gates/verify_gate_helpers.py so paying type debt cannot "
            "leave CI failing on every subsequent PR."
        )

    def test_ci_workflow_parses_the_summary_with_the_tested_helper(self) -> None:
        """CI must reuse ``parse-bp`` -- grep-JSON is the bug class this module replaced."""
        ci = (repo_root() / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        assert "src.lib.quality_gates.verify_gate_helpers parse-bp" in ci
        assert '"errorCount"' not in ci, (
            "ci.yml greps the basedpyright JSON summary; parse_basedpyright_counts exists "
            "precisely because inline bash grepping silently under-counted."
        )

    def test_verify_sh_derives_the_baseline_from_the_helper(self) -> None:
        """verify.sh reads the same SoT, so the two gates cannot disagree."""
        sh = (repo_root() / "apps/api/scripts/verify.sh").read_text(encoding="utf-8")
        assert "src.lib.quality_gates.verify_gate_helpers baseline" in sh
        assert re.search(r"BASEDPYRIGHT_ERROR_BASELINE:-\d+", sh) is None, "verify.sh still falls back to a hardcoded baseline literal."


def test_verify_sh_research_rise_remediation_matches_the_gate() -> None:
    """The ROSE echo is what the next agent runs. A shortened cousin under-counts.

    MEASURED 2026-08-25: the printed ``Run:`` omitted ``tests/unit/research``,
    ``--ignore-noqa``, and ``--color never``. Following it reported ~298 vs the
    gate's 577, which is how a session asked the owner to choose bisect vs
    re-baseline of a number it never measured. Rise → fix the new findings.
    The owner is not the decision procedure.
    """
    sh = (repo_root() / "apps/api/scripts/verify.sh").read_text(encoding="utf-8")
    rose_at = sh.index("research bug-class findings ROSE")
    rose_block = sh[rose_at : rose_at + 900]
    assert "tests/unit/research" in rose_block, rose_block
    assert "--ignore-noqa" in rose_block, rose_block
    assert "--color never" in rose_block, rose_block
    assert "count-research" in rose_block, rose_block
    lowered = rose_block.lower()
    assert "re-baseline" not in lowered
    assert "need your call" not in lowered
    assert "bisect" not in lowered


def test_research_bug_baseline_is_paid_to_zero() -> None:
    """Owner 2026-08-25: stop ratcheting 539; pay the corpus. Measured 0 after the paydown."""
    sh = (repo_root() / "apps/api/scripts/verify.sh").read_text(encoding="utf-8")
    match = re.search(r"RESEARCH_BUG_BASELINE:-(\d+)", sh)
    assert match is not None, "verify.sh lost the research bug-class baseline"
    assert int(match.group(1)) == 0, f"baseline is {match.group(1)}; lock RESEARCH_BUG_BASELINE to the measured 0"


class TestNoqaTouchGate:
    """Owner, 2026-09-17: a touched file MUST leave with its `noqa` fixed, and the lower baseline is
    locked, so the count walks down to 0 one touch at a time.

    The whole-tree ratchet alone only forbids GROWTH. The half that makes the debt shrink is the
    `noqa` row of scripts/check_touched_debt.py (tests/scripts/test_check_touched_debt.py drives it on
    real git repos); what stays here is the COUNTER both halves share, and its wiring.
    """

    def test_the_counter_reads_comments_not_strings(self) -> None:
        """Falsifier: a docstring ABOUT noqa is not a suppression."""
        source = '"""explains # noqa usage"""\nx = "# noqa"\nimport os  # noqa: F401\n'
        assert count_noqa_comments(source) == 1

    def test_a_comment_that_only_mentions_noqa_is_not_a_suppression(self) -> None:
        """Measured 2026-10-03: 2 prose comments in src (and 8 in this gate's own module) were counted as
        suppressions, so editing the gate's docs 'owed' paying down debt that did not exist."""
        prose = "# the `noqa` row of check_touched_debt\n#: ``noqa: ARG001`` markers record it\nx = 1\n"
        assert count_noqa_comments(prose) == 0

    def test_file_level_and_trailing_directives_both_count(self) -> None:
        source = "# ruff: noqa: E501\nimport os  # type: ignore[x]  # noqa: F401\ny = 2  #noqa\n"
        assert count_noqa_comments(source) == 3

    def test_the_precommit_gate_types_staged_src_files_too(self) -> None:
        """Staged src/ files used to meet ruff only; basedpyright reached them in CI, too late."""
        text = (repo_root() / "apps/api/scripts/lint_staged_python.sh").read_text(encoding="utf-8")
        helper = text[text.index("typecheck() {") : text.index("\n}\n", text.index("typecheck() {"))]
        assert '-m scripts.run_mypy "$@"' in helper  # both checkers run inside the one helper, side by side
        assert '-m scripts.basedpyright_gate "$@"' in helper
        assert 'typecheck "" "${src_files[@]}"' in text

    def test_the_ratchet_reads_the_baseline_instead_of_restating_it(self) -> None:
        """Two copies of a two-sided baseline fail every later commit once one is lowered."""
        ratchet = repo_root() / "apps/api/tests/unit/architecture/test_noqa_ratchet.py"
        tree = ast.parse(ratchet.read_text(encoding="utf-8"))
        restated = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and any(
                isinstance(target, ast.Name) and target.id == "NOQA_BASELINE"
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            )
        ]
        assert restated == [], f"test_noqa_ratchet.py assigns its own NOQA_BASELINE at {restated}"
        assert NOQA_BASELINE >= 0


def test_a_module_logger_of_any_name_counts_as_emitting() -> None:
    """SILENT-LOG (2026-10-16): mexc_demo binds its logger as LOG; a function logging through it was read as silent.
    The detector reads the names the module itself binds to logging.getLogger -- a name it does not bind still is not one."""
    src = "\n".join([
        "import logging",
        "LOG = logging.getLogger(__name__)",
        "def logs(x):",
        "    if x is None:",
        "        return None",
        "    if x < 0:",
        "        LOG.info('negative %s', x)",
        "        return None",
        "    return x",
        "def silent(x):",                     # canary: the same shape with no logger is still counted
        "    if x is None:",
        "        return None",
        "    if x < 0:",
        "        LOG_LIKE.info('not a logger')",
        "        return None",
        "    return x",
    ])  # fmt: skip
    assert silent_return_functions(ast.parse(src)) == ["silent"]
