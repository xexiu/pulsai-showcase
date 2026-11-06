"""Running the hook tests must not clobber the LIVE agent evidence ledger.

REUSE-AUDIT: considered `_hook_evidence.STATE` (already honours `HOOK_EVIDENCE_STATE`) and
`test_hook_evidence.py`'s autouse monkeypatch fixture. Neither covers this: the monkeypatch only
protects the in-process module, and several suites here (`test_guards_end_to_end`,
`test_red_team_all_guards`, `test_every_guard_is_wired`) run guards as SUBPROCESSES, which re-import
the module fresh and resolve `STATE` to the real file. So the env var is the only seam that reaches
them, and this is where it gets set — not a second ledger.

MEASURED 2026-08-18. `rules_read` was stamped, `todo_rules_reread_guard` released a 37-item
submission, then a full `pytest .claude/hooks/` run left the ledger holding only
`edit/measurement/ran_command/search/todo` — `rules_read` gone. The next TodoWrite was denied with
"no tool call opened any of these", after the standards HAD been opened minutes earlier.

That makes the test suite a source of false denials, and worse, it silently erases evidence of work
the agent really did. A guard that is reset by running the tests is a guard whose state nobody can
trust.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_hook_evidence_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point every guard — in-process AND subprocess — at a throwaway evidence ledger.

    FUNCTION-scoped on purpose. A session-scoped sandbox protected the live file but let the tests
    pollute EACH OTHER: one test stamping `rules_read` released
    `test_todo_rules_reread_guard::test_it_fires_every_time_without_a_budget`, which exists to prove
    the guard denies every time. Measured: 3 failures with one shared ledger, 0 with one per test.
    Isolation has to be per test, or the suite is just sharing a different global.
    """
    monkeypatch.setenv("HOOK_EVIDENCE_STATE", str(tmp_path / "evidence.json"))
    # `todo_start_standard_guard` keeps its own baseline of the last-seen list, and it is a
    # SECOND live file the suite can clobber. MEASURED 2026-08-31, the day that guard shipped:
    # a full run left the real `.todo_start_state.json` holding `test_hook_conflict_matrix`'s
    # fixture items (RESEARCH-RUN-1, PROD-4, FE-2), so the agent's actual ledger read as
    # entirely unseen and every item in it was judged "NEW" -- the same false-denial the
    # evidence isolation above exists to prevent, one guard later.
    monkeypatch.setenv("TODO_START_STATE", str(tmp_path / "todo-start.json"))
    # `_llm_judge` (opt-in model judge for the prose guards) reads its flag from the environment
    # BEFORE `.env`, so an explicit "0" here keeps every suite on the regexes even when the owner
    # has switched the judge on in `.env` -- otherwise turning the flag on would send the test
    # fixtures to OpenRouter and make the guard suites depend on a remote model's answer.
    monkeypatch.setenv("PULSAI_HOOK_LLM_JUDGE", "0")
    monkeypatch.setenv("PULSAI_HOOK_LLM_JUDGE_LEDGER", str(tmp_path / "llm-judge.jsonl"))
    # `cert_failure_must_surface_guard` keeps a THIRD live file, and one test seeds it by assigning
    # `os.environ["PULSAI_CERT_FAILURE_STATE"]` directly -- never restored. MEASURED 2026-10-01:
    # under pytest-randomly, whenever `test_guard_block_prints_guidance` ran first, its "failure"
    # state leaked into `test_gate_hooks_speak_only_on_violation`'s subprocesses and the cert gate
    # spoke on a harmless Stop (reproduced every time with the order forced). monkeypatch restores
    # the key at teardown even after a direct assignment, so this undoes that leak for every test.
    monkeypatch.setenv("PULSAI_CERT_FAILURE_STATE", str(tmp_path / "cert-failure.json"))
    # Same defect, fourth file: `finding_needs_todo_guard` falls back to the LIVE
    # `.finding_todo_state.json`, and `test_finding_needs_todo_guard` sets FINDING_TODO_STATE at
    # COLLECTION, so a full run shared one file across suites. MEASURED 2026-10-01: a leftover
    # `{"blocked": true}` fails `test_guard_block_prints_guidance[finding_needs_todo_guard.py]`
    # (reproduced by seeding it), and running that case alone wrote `{"blocked": true}` into the
    # live file the real Stop hook reads.
    monkeypatch.setenv("FINDING_TODO_STATE", str(tmp_path / "finding-todo.json"))
    # Fifth and sixth: these two guards had NO override, so their suites and
    # `test_guard_block_prints_guidance` deleted and rewrote the LIVE files (both held test residue
    # at 21:19 on 2026-10-01). Each guard now reads its path from these variables.
    monkeypatch.setenv("ABSENCE_SEARCH_STATE", str(tmp_path / "absence-search.json"))
    monkeypatch.setenv("OWNER_SPEC_SUBSTITUTION_STATE", str(tmp_path / "owner-spec.json"))
    # Seventh and eighth, 2026-10-15: `test_a_legal_submission_survives_every_todo_guard` runs every TodoWrite guard
    # as a subprocess with this environment, and the live `.todo_done_state.json` was found holding its fixture items
    # ("1. AAA [MONEY] ...") -- the close guard's memory of the real ledger wiped by a test run. The contract guard's
    # suite unlinked its live /tmp ledger the same way.
    monkeypatch.setenv("TODO_DONE_STATE", str(tmp_path / "todo-done.json"))
    monkeypatch.setenv("BE_FE_CONTRACT_STATE", str(tmp_path / "be-fe-contract.json"))
