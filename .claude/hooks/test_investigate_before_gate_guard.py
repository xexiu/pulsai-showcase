"""The gate-edit guard must block blind gate edits and stay out of the way otherwise."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import sys
import time
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parent / "investigate_before_gate_guard.py"
_spec = importlib.util.spec_from_file_location("igg", _HOOK)
assert _spec and _spec.loader
igg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(igg)


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(igg, "STATE", tmp_path / "state.json")


class TestFrontendGatesAreGuardedToo:
    """A gate is not a Python idea, and this guard used to believe it was.

    `is_gate_edit` opened with `if not path.endswith(".py"): return False`, so every decision
    rule in `apps/web` -- tier thresholds, visibility policy, eligibility checks -- could be
    moved with no empirical check whatsoever. Owner, 2026-08-09: "ALL hooks must be 100%
    dynamic, not only for your USE cases, but should match ALL BE AND FE CODEBASE."

    Two bugs sat on top of each other: even past the suffix test, `_GATE_CONTENT` matched
    Python's capitalised `return False` and TypeScript writes `return false`. Fixing only the
    suffix would have looked like a fix and caught nothing.
    """

    @pytest.mark.parametrize(
        "path,text",
        [
            ("apps/web/src/config/chart-tier-policy.ts", "export const TIER_THRESHOLD = 0.8;"),
            ("apps/web/src/components/PromoteGate.tsx", "if (x === 1) return false;"),
            ("apps/web/src/hooks/use-eligibility-gate.ts", "return score >= MIN_SCORE;"),
            ("apps/web/src/config/verdict-policy.js", "if (a !== b) return true;"),
        ],
    )
    def test_frontend_decision_rules_are_detected(self, path: str, text: str) -> None:
        assert igg.is_gate_edit(path, text) is True

    def test_lowercase_return_false_counts(self) -> None:
        """The second bug, pinned on its own: TS booleans are lowercase."""
        assert igg.is_gate_edit("apps/web/src/gate-policy.ts", "return false;") is True

    @pytest.mark.parametrize(
        "path,text",
        [
            ("apps/web/src/components/Button.tsx", "return false;"),  # no gate word in path
            ("docs/promote-threshold.md", "score >= 0.8"),  # not source
            ("apps/web/src/config/gate-policy.ts", "// just a comment"),  # no boundary moved
        ],
    )
    def test_still_stays_out_of_the_way(self, path: str, text: str) -> None:
        assert igg.is_gate_edit(path, text) is False

    @pytest.mark.parametrize(
        "command",
        ["jq '.capital_modes' cert.json", "pnpm test -- tier", "npx tsx scan.ts", "node -e 'x'"],
    )
    def test_frontend_data_checks_count_as_verification(self, command: str) -> None:
        """Otherwise a well-researched FE gate edit gets denied for doing the legwork in jq."""
        assert igg.is_verification(command) is True

    def test_idle_commands_still_do_not_count(self) -> None:
        for command in ("ls -la", "git status", "cd apps/web"):
            assert igg.is_verification(command) is False


@pytest.mark.parametrize(
    "path,text",
    [
        ("src/domain/services/edge_lifecycle/capital_cert_promote.py", "    return False"),
        ("src/domain/x/promote_policy.py", "MIN_SHARPE = 1.2"),
        ("scripts/headline_survivors.py", "if dd <= -0.95:"),
    ],
)
def test_gate_edits_are_recognised(path: str, text: str) -> None:
    assert igg.is_gate_edit(path, text)


@pytest.mark.parametrize(
    "path,text",
    [
        ("src/api/routes/health.py", "return False"),  # not a gate-ish path
        ("src/domain/promote_policy.py", "logger.info('promoted')"),  # no boundary moved
        ("docs/CERT_INVENTORY.md", "return False"),  # not python
    ],
)
def test_non_gate_edits_pass_through(path: str, text: str) -> None:
    assert not igg.is_gate_edit(path, text)


@pytest.mark.parametrize(
    "cmd",
    [
        "python -c \"import json; json.load(open('cert.json'))\"",
        "cat src/research/artifacts/edge_lab/x.json",
        "psql -c 'SELECT count(*) FROM backtest_runs'",
        "pytest tests/unit/domain -q",
    ],
)
def test_real_data_commands_count_as_verification(cmd: str) -> None:
    assert igg.is_verification(cmd)


@pytest.mark.parametrize("cmd", ["ls -la", "git status", "echo hi", "mkdir -p out"])
def test_bookkeeping_commands_are_not_verification(cmd: str) -> None:
    assert not igg.is_verification(cmd)


def _run(payload: dict[str, object], state: Path | None = None) -> str:
    """Spawn the hook with ISOLATED state.

    The subprocess re-imports the module, so monkeypatching `igg.STATE` in-process does not reach
    it — without an env override the test reads the developer's real state file and passes or fails
    depending on what commands happened to run earlier that session.
    """
    env = {**os.environ, "INVESTIGATE_GUARD_STATE": str(state or (Path(tempfile.mkdtemp()) / "s.json"))}
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return proc.stdout


def _edit_payload() -> dict[str, object]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "src/domain/services/edge_lifecycle/capital_cert_promote.py",
            "new_string": "    if window_is_in_sample is True:\n        return False",
        },
    }


def test_blind_gate_edit_is_denied() -> None:
    """THE REGRESSION: editing a promotion gate with no empirical check behind it."""
    out = _run(_edit_payload())
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_gate_edit_allowed_after_a_recent_verification(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"last_verified_at": time.time()}))
    proc = subprocess.run(
        [sys.executable, "-c", f"import runpy,sys;sys.argv=['h'];"
         f"import importlib.util;s=importlib.util.spec_from_file_location('h',r'{_HOOK}');"
         f"m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
         f"m.STATE=__import__('pathlib').Path(r'{state}');raise SystemExit(m.main())"],
        input=json.dumps(_edit_payload()),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.stdout.strip() == "", "a verified investigation must let the edit through"


def test_stale_verification_does_not_license_an_edit(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"last_verified_at": time.time() - igg.WINDOW_SECONDS - 60}))
    proc = subprocess.run(
        [sys.executable, "-c", f"import importlib.util;s=importlib.util.spec_from_file_location('h',r'{_HOOK}');"
         f"m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
         f"m.STATE=__import__('pathlib').Path(r'{state}');raise SystemExit(m.main())"],
        input=json.dumps(_edit_payload()),
        capture_output=True,
        text=True,
        check=False,
    )
    assert "deny" in proc.stdout


class TestRedecidingARuleNeedsARefutation:
    """The eight-day failure: the same rule decided again, and again, and again.

    Owner, 2026-08-14: *"tomorrow you will say use this logic and that logic and output will be
    different than yesterday and you will change your mind"*.

    The two existing checks ask whether DATA was read and whether a NUMBER was justified. Neither
    notices a rule being decided a THIRD time. Measured on the session that produced this: the
    SELECT rule was rewritten three times in one turn and every rewrite passed, because each had
    corpus reads in its window and reused an existing constant.

    Those three were RIGHT to make -- each cited the measurement that killed its predecessor --
    so the guard asks for exactly that and nothing more. Blocking iteration would have blocked
    the work that fixed the defect.
    """

    PATH = "src/domain/services/edge_lifecycle/capital_cert_promote.py"

    def _state(self, *, age_seconds: float = 0.0) -> dict:
        return {"gate_edits": {self.PATH: time.time() - age_seconds}}

    def test_a_first_edit_is_never_a_redecision(self) -> None:
        assert not igg.redecides_without_refutation(
            self.PATH, "    return False", {}, now=time.time()
        )

    def test_a_second_edit_with_no_refutation_is_blocked(self) -> None:
        assert igg.redecides_without_refutation(
            self.PATH, "    return True  # better this way", self._state(), now=time.time()
        )

    def test_a_second_edit_that_names_what_refuted_the_last_one_passes(self) -> None:
        """The whole point: science passes, preference does not."""
        text = (
            "    # MEASURED on 6 tapes: ranking by mar picks spot_10k/2pct, $10,030 on $10,000.\n"
            "    return False"
        )

        assert not igg.redecides_without_refutation(self.PATH, text, self._state(), now=time.time())

    def test_a_stale_previous_edit_does_not_count_as_churn(self) -> None:
        """Revisiting a rule days later is normal work, not drift."""
        old = self._state(age_seconds=igg.WINDOW_SECONDS + 60)

        assert not igg.redecides_without_refutation(self.PATH, "    return True", old, now=time.time())

    def test_a_non_gate_edit_is_untouched(self) -> None:
        assert not igg.redecides_without_refutation(
            "src/api/routes/health.py", "    return False", self._state(), now=time.time()
        )


def test_malformed_input_fails_open() -> None:
    proc = subprocess.run(
        [sys.executable, str(_HOOK)], input="not json", capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
