"""The evidence ledger is what makes a guard un-rephrasable, so it gets its own tests.

A guard released by a PHRASE is satisfied by typing the phrase — proven on 2026-08-07 when the
owner probed `measure_dont_infer_guard` with a lazy line and it passed. `_hook_evidence` is the
fix, written once: PostToolUse stamps what actually happened, and the Stop check asks about
BEHAVIOUR, which no wording can fake.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_HOOKS = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_hook_evidence", _HOOKS / "_hook_evidence.py")
assert _spec and _spec.loader
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)


def _record_many(args: tuple[str, str, str]) -> None:
    """Module-level so `multiprocessing.Pool` can pickle it. Re-imports the module per process,
    exactly as a real hook subprocess does — the in-process monkeypatch never reaches those."""
    import importlib.util as _il
    import os as _os

    state_path, tool, target = args
    _os.environ["HOOK_EVIDENCE_STATE"] = state_path
    spec = _il.spec_from_file_location("_hook_evidence_worker", _HOOKS / "_hook_evidence.py")
    assert spec and spec.loader
    module = _il.module_from_spec(spec)
    spec.loader.exec_module(module)
    for _ in range(40):
        module.record({"tool_name": tool, "tool_input": {"file_path": target, "command": target}})


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ev, "STATE", tmp_path / "evidence.json")
    ev.clear()


@pytest.mark.parametrize(
    "tool,command,expected",
    [
        ("Bash", "grep -rn foo src/", "search"),
        ("Bash", "rg --line-buffered ERROR", "search"),
        ("Bash", "python scripts/verify_published_backtest_drawdown.py", "measurement"),
        ("Bash", "python -m pytest tests/ -q", "measurement"),
        ("Bash", "./scripts/run-with-nohup.sh x -- python thing.py", "ran_command"),
        ("Edit", "", "edit"),
        ("Write", "", "edit"),
    ],
)
def test_classify_recognises_each_evidence_kind(tool: str, command: str, expected: str) -> None:
    assert expected in ev.classify(tool, command)


def test_record_then_had_reports_the_action() -> None:
    ev.record({"tool_name": "Bash", "tool_input": {"command": "grep -rn thing src/"}}, now=1000.0)

    assert ev.had("search", now=1000.0)
    assert not ev.had("measurement", now=1000.0)


def test_evidence_expires_outside_the_window() -> None:
    """Stale evidence must not clear a fresh claim — otherwise one grep licenses the session."""
    ev.record({"tool_name": "Bash", "tool_input": {"command": "grep -rn x src/"}}, now=1000.0)

    assert ev.had("search", now=1000.0 + ev.WINDOW_SECONDS - 1)
    assert not ev.had("search", now=1000.0 + ev.WINDOW_SECONDS + 1)


def test_unknown_commands_record_nothing() -> None:
    assert ev.record({"tool_name": "Bash", "tool_input": {"command": "echo hi"}}, now=5.0) == set()
    assert not ev.had("search", now=5.0)


def test_missing_evidence_reads_false_not_raise() -> None:
    """Fails to 'no evidence', which only makes a guard STRICTER — never wedged."""
    assert not ev.had("search")
    assert not ev.had("nonexistent-kind")


def test_unreadable_state_fails_closed_to_no_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = tmp_path / "corrupt.json"
    bad.write_text("{ not json")
    monkeypatch.setattr(ev, "STATE", bad)

    assert not ev.had("search")


def test_edit_tools_count_even_with_no_command_text() -> None:
    """Edit/Write carry a file_path, not a command; they must still register as an edit."""
    ev.record({"tool_name": "Write", "tool_input": {"file_path": "/tmp/x.py"}}, now=10.0)

    assert ev.had("edit", now=10.0)


class TestTodoContentIsRecordedNotJustTheFact:
    """A guard must be able to ask WHICH gap was tracked, not merely that SOME todo was written."""

    def test_todo_content_is_stored_for_matching(self) -> None:
        ev.record(
            {
                "tool_name": "TodoWrite",
                "tool_input": {
                    "todos": [
                        {"content": "1w. WIPE-THRESHOLD-GAP: best_clean_cell never applies 95%"},
                        {"content": "6a. FE-2 tooltip"},
                    ]
                },
            }
        )

        text = ev.recorded_text("todo")

        assert "best_clean_cell" in text
        assert "FE-2" in text

    def test_recorded_text_is_empty_when_nothing_was_tracked(self) -> None:
        assert ev.recorded_text("todo") == ""


class TestTheLedgerPathIsResolvedWhenUSED:
    """`HOOK_EVIDENCE_STATE` must win at CALL time, or the suite wipes the live ledger.

    MEASURED 2026-08-31. Mid-session the real ledger collapsed to a single key:

        {"search": <7s ago>}          -- rules_read, edit, measurement, ran_command all gone

    `conftest.py` sets HOOK_EVIDENCE_STATE per test precisely to stop this, and its docstring
    describes the exact incident. But `STATE` was assigned at MODULE level, so it froze at
    IMPORT -- which happens at collection, before any fixture runs. Every guard imported
    in-process during the suite therefore wrote to the REAL file, and a test that recorded a
    small dict overwrote the agent's actual evidence.

    The consequence is not cosmetic: `rules_read` kept vanishing, so `todo_rules_reread_guard`
    denied real submissions minutes after the standards had genuinely been opened. The env-var
    seam existed and simply never reached the code it was written for.
    """

    def test_the_env_var_is_honoured_after_import(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        elsewhere = tmp_path / "redirected.json"
        monkeypatch.setenv("HOOK_EVIDENCE_STATE", str(elsewhere))

        ev.record({"tool_name": "Bash", "tool_input": {"command": "grep -rn foo src/"}})

        assert elsewhere.exists(), "record() still wrote to the import-time path"

    def test_reads_follow_the_same_redirect(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOOK_EVIDENCE_STATE", str(tmp_path / "a.json"))
        ev.record({"tool_name": "Bash", "tool_input": {"command": "grep -rn foo src/"}})
        assert ev.had("search") is True

        monkeypatch.setenv("HOOK_EVIDENCE_STATE", str(tmp_path / "b.json"))

        assert ev.had("search") is False, "had() read the previous ledger after the redirect"


class TestConcurrentWritersDoNotEraseEachOther:
    """Several PostToolUse guards call `record()` for the SAME tool call, at the same time.

    MEASURED 2026-08-18 — the bug behind every spurious "no tool call opened any of these": four
    processes recording concurrently ended with `LOST: ['edit', 'search']`. `record()` did
    read-modify-write with no atomicity and no lock, so the last writer's `_load()` snapshot
    overwrote every key another process had added in between. A truncated file mid-write reads as
    `{}` and wipes the ledger outright.

    The symptom looked like a delivery problem — evidence stamped, then simply gone by the next
    hook — and I first blamed the harness for not delivering PostToolUse on MCP tools. It delivers
    fine; a gortex read stamps `rules_read` instantly. The loss was here.
    """

    def test_parallel_records_keep_every_kind(self, tmp_path: Path) -> None:
        import multiprocessing as mp

        state = tmp_path / "evidence.json"
        jobs = [
            (str(state), "Read", "docs/04-structural/DDD_PATTERNS.md"),
            (str(state), "Write", "/tmp/a.py"),
            (str(state), "Bash", "python -m pytest tests/"),
            (str(state), "Read", "docs/02-technical/ARCHITECTURE.md"),
        ]
        with mp.Pool(4) as pool:
            pool.map(_record_many, jobs)

        final = json.loads(state.read_text(encoding="utf-8"))

        # The kinds these four inputs actually stamp: a rules path -> rules_read, a Write -> edit,
        # and `python -m pytest` -> measurement + ran_command. (An earlier draft also asserted
        # `search`, which none of these inputs produce — a wrong expectation, not a lost key.)
        for kind in ("rules_read", "edit", "measurement", "ran_command"):
            assert kind in final, f"{kind} was erased by a concurrent writer: {sorted(final)}"

    def test_a_truncated_ledger_does_not_erase_the_rest(self, tmp_path: Path) -> None:
        """A half-written file must not read as `{}` and take every other kind down with it."""
        state = tmp_path / "evidence.json"
        monkey = ev.STATE
        try:
            ev.STATE = state
            ev.record({"tool_name": "Read", "tool_input": {"file_path": "DDD_PATTERNS.md"}})
            state.write_text('{"rules_read": 1755500000.0, "edi', encoding="utf-8")

            ev.record({"tool_name": "Write", "tool_input": {"file_path": "/tmp/x.py"}})

            recovered = json.loads(state.read_text(encoding="utf-8"))
            assert "edit" in recovered
        finally:
            ev.STATE = monkey


class TestTheConsolidatedGortexSurfaceCountsAsSearch:
    """The MANDATED lookup tools must produce `search` evidence; the FORBIDDEN one already does.

    MEASURED 2026-08-31, while designing a guard that would require a Phase 0 reuse search:

        classify("mcp__gortex__search", ...)      -> set()
        classify("Bash", "grep -rn foo src/")     -> {"search"}

    CLAUDE.md mandates gortex, and a PreToolUse hook DENIES grep against indexed source. So the
    only tool that could stamp `search` was the one the agent is blocked from using, and any
    guard keyed to `search` would be unsatisfiable by an agent obeying the rules -- the
    jointly-unsatisfiable failure `guards-can-be-jointly-unsatisfiable` already records.

    The cause is drift, not oversight: the pattern lists gortex's OLD split tool names
    (search_text, search_symbols, find_usages, get_symbol_source, read_file) and the surface has
    since consolidated to `mcp__gortex__{search,read,explore,relations,trace}`. Same shape as
    `TestGortexPathsAreEvidenceToo` below -- mandated tooling invisible to the ledger -- one kind
    over.
    """

    @pytest.mark.parametrize(
        "tool",
        [
            "mcp__gortex__search",
            "mcp__gortex__read",
            "mcp__gortex__explore",
            "mcp__gortex__relations",
            "mcp__gortex__trace",
        ],
    )
    def test_each_consolidated_lookup_tool_records_search(self, tool: str) -> None:
        assert "search" in ev.classify(tool, "pulsai/apps/web")

    def test_the_old_split_names_still_count(self) -> None:
        """The rename is additive; an older client still sends these."""
        assert "search" in ev.classify("mcp__gortex__search_text", "deflated_sharpe")

    def test_a_gortex_mutation_is_not_search_evidence(self) -> None:
        """Looking something up is the evidence; changing it is not."""
        assert "search" not in ev.classify("mcp__gortex__edit", "pulsai/apps/web/foo.ts")


class TestTheConsolidatedGortexToolsNestTheirPath:
    """`target.file` is where the current gortex tools put the path, and record() never looked.

    MEASURED 2026-08-31, while being denied by `todo_rules_reread_guard` after opening the
    standards four times with `mcp__gortex__read`:

        the live ledger held {"search": <37s ago>, "edit": ...} and NO `rules_read`
        classify("mcp__gortex__read", "pulsai/.cursor/rules/coding-standards-mandatory.mdc")
            -> {"rules_read", "search"}

    So the pattern was right and the PATH never reached it. `record()` falls back to
    `file_path` or `path`; the consolidated tools send neither -- they nest it as
    `target.file`. The guard was therefore unsatisfiable by the mandated tooling, while
    `Read` is denied on indexed source: the jointly-unsatisfiable trap, one field deeper than
    `TestGortexPathsAreEvidenceToo` below.

    It hid because the `search` kind matches the TOOL NAME, so recording looked healthy.
    """

    def test_a_nested_target_file_records_rules_read(self) -> None:
        payload = {
            "tool_name": "mcp__gortex__read",
            "tool_input": {
                "operation": "file",
                "target": {"file": "pulsai/.cursor/rules/coding-standards-mandatory.mdc"},
            },
        }

        assert "rules_read" in ev.record(payload)

    def test_a_nested_target_file_of_an_unrelated_file_is_not_rules_evidence(self) -> None:
        payload = {
            "tool_name": "mcp__gortex__read",
            "tool_input": {"target": {"file": "pulsai/apps/web/src/utils/indicators/rsi.ts"}},
        }

        assert "rules_read" not in ev.record(payload)

    def test_a_symbol_target_does_not_crash_the_recorder(self) -> None:
        """`target` may carry `symbol`/`symbols` instead of `file`; neither is a path."""
        payload = {
            "tool_name": "mcp__gortex__read",
            "tool_input": {"target": {"symbols": ["a::b", "c::d"]}},
        }

        assert "rules_read" not in ev.record(payload)


class TestGortexPathsAreEvidenceToo:
    """CLAUDE.md MANDATES gortex over `Read`, and gortex sends `path`, never `file_path`.

    MEASURED 2026-08-18: the standards were opened with `mcp__gortex__read_file` and
    `todo_rules_reread_guard` still denied every submission with "no tool call opened any of
    these". `record()` fell back to `file_path` ONLY — a key gortex does not send — so the path
    text never reached `PATTERNS["rules_read"]` and the mandated tooling could not satisfy a guard
    keyed to paths.

    This is the same dead-guard class `test_every_guard_is_wired.test_a_read_matcher_also_sees_gortex`
    already pins, caught one layer lower: that fix widened the guard's MATCHER to gortex, so the
    recorder now RUNS on a gortex read — but the payload FIELD it reads was never widened with it,
    so it runs and records nothing. A matcher that fires into a field that is always empty is
    indistinguishable from a guard that was never wired at all.
    """

    def test_gortex_read_of_a_standard_records_rules_read(self) -> None:
        ev.record(
            {
                "tool_name": "mcp__gortex__read_file",
                "tool_input": {"path": "pulsai/docs/04-structural/DDD_PATTERNS.md"},
            },
            now=100.0,
        )

        assert ev.had("rules_read", now=100.0)

    def test_native_read_of_a_standard_still_records_rules_read(self) -> None:
        """The `file_path` route must keep working — this widens the field set, never swaps it."""
        ev.record(
            {
                "tool_name": "Read",
                "tool_input": {"file_path": "/repo/docs/02-technical/ARCHITECTURE.md"},
            },
            now=100.0,
        )

        assert ev.had("rules_read", now=100.0)

    def test_a_gortex_read_of_an_unrelated_file_is_not_rules_evidence(self) -> None:
        """Widening the field must not turn every gortex read into a rules read."""
        ev.record(
            {"tool_name": "mcp__gortex__read_file", "tool_input": {"path": "apps/api/src/main.py"}},
            now=100.0,
        )

        assert not ev.had("rules_read", now=100.0)
