#!/usr/bin/env python3
"""The mode gate is the ONE place that decides whether a hook body runs at all.

REUSE-AUDIT: considered extending test_todo_hooks_auto_mode_only.py (the only existing
mode-aware test); not extending it because that file pins a PER-HOOK property -- "every
*todo*_guard.py asks the mode itself" -- while this pins a CENTRAL one: no hook body runs
outside auto regardless of what the hook knows about modes. Considered _hook_mode.py's own
tests; they cover the predicate, not its application. Searched .claude/hooks for gate/
dispatch/wrapper/runner: no dispatcher exists.

WHAT IS ACTUALLY BEING TESTED. Not "the gate returns True" -- that is the shallow version and it
passes while every hook still fires. These drive the gate as a PROCESS with a real payload on
stdin and assert on the OBSERVABLE effect: did the target's side effect happen, did its stdout
survive byte-identical, did its exit code survive. A hook that is silenced must leave no trace,
and a hook that runs must be indistinguishable from running unwrapped.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent
GATE = HOOKS_DIR / "_hook_mode_gate.py"
SETTINGS = HOOKS_DIR.parent / "settings.json"

#: A target hook that records that it ran, echoes the payload back, and blocks like a real guard.
TARGET_SRC = """\
import json, os, sys
payload = json.load(sys.stdin)
open(os.environ["SENTINEL"], "w").write(payload.get("session_id", ""))
sys.stdout.write(json.dumps({"decision": "block", "reason": "target ran"}))
sys.exit(2)
"""


def _run_gate(
    target: Path, payload: dict[str, object], sentinel: Path
) -> subprocess.CompletedProcess[str]:
    """Drive the gate exactly as the CLI does: payload on stdin, target path as argv[1]."""
    env = {**os.environ, "SENTINEL": str(sentinel)}
    return subprocess.run(
        [sys.executable, str(GATE), str(target)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture()
def target(tmp_path: Path) -> Path:
    path = tmp_path / "sample_guard.py"
    path.write_text(TARGET_SRC)
    return path


@pytest.fixture()
def sentinel(tmp_path: Path) -> Path:
    return tmp_path / "ran.txt"


def _payload(mode: str | None = None, **extra: object) -> dict[str, object]:
    payload: dict[str, object] = {"hook_event_name": "Stop", "session_id": "s-1", **extra}
    if mode is not None:
        payload["permission_mode"] = mode
    return payload


# --------------------------------------------------------------------------- silenced modes


@pytest.mark.parametrize("mode", ["plan", "default", "acceptEdits", "bypassPermissions"])
def test_non_auto_mode_never_runs_the_target(target, sentinel, mode):
    """THE OWNER'S RULE. Any known mode that is not auto leaves the hook body unexecuted."""
    result = _run_gate(target, _payload(mode), sentinel)

    assert not sentinel.exists(), f"{mode}: target ran when it must not have"
    assert result.returncode == 0, f"{mode}: a silenced hook must allow, not block"
    assert result.stdout.strip() == "", f"{mode}: a silenced hook must say nothing"


def test_silenced_hook_emits_no_stderr_either(target, sentinel):
    """Silence means silence -- stderr reaches the transcript the same as stdout."""
    result = _run_gate(target, _payload("plan"), sentinel)

    assert result.stderr.strip() == ""


# --------------------------------------------------------------------------- auto passes through


def test_auto_mode_runs_the_target(target, sentinel):
    result = _run_gate(target, _payload("auto"), sentinel)

    assert sentinel.exists(), "auto mode must run the hook body"
    assert json.loads(result.stdout) == {"decision": "block", "reason": "target ran"}


def test_auto_mode_propagates_the_targets_exit_code(target, sentinel):
    """A guard blocks with exit 2. Swallowing that turns every block into an allow."""
    result = _run_gate(target, _payload("auto"), sentinel)

    assert result.returncode == 2


def test_stdin_is_replayed_to_the_target_intact(target, sentinel):
    """The gate consumes stdin to read the mode; the target must still receive the payload."""
    _run_gate(target, _payload("auto", session_id="abc-123"), sentinel)

    assert sentinel.read_text() == "abc-123"


# --------------------------------------------------------------------------- fail-open cases


def test_absent_mode_runs_the_target(target, sentinel):
    """An ABSENT mode is not 'not auto'.

    Every real payload carries the field, so the only inputs without it are harnesses and older
    fixtures. Reading absent as non-auto would silence the whole hook set on any payload shape
    change -- the silent-emptiness defect this repo keeps paying for.
    """
    result = _run_gate(target, _payload(None), sentinel)

    assert sentinel.exists()
    assert result.returncode == 2


def test_unparseable_payload_runs_the_target(tmp_path, sentinel):
    """Fails OPEN. A gate that eats hooks on malformed input disables the whole guard set.

    WHAT REFUTED THE FIRST VERSION of this test, which was MY error and not the gate's: it reused
    the shared `target` fixture, whose body is `json.load(sys.stdin)`. Fed "not json at all" that
    target raises JSONDecodeError and never reaches its sentinel write -- so the assertion was
    unsatisfiable for EVERY possible gate behaviour, and its failure said nothing about the gate.
    A test that cannot pass when the code is correct is testing the fixture, not the code.

    The target here therefore does not parse stdin, which isolates the one property under test:
    did the gate hand control to the hook despite being unable to read the mode?
    """
    tolerant = tmp_path / "tolerant_guard.py"
    tolerant.write_text('import os, sys\nsys.stdin.read()\nopen(os.environ["SENTINEL"], "w").write("ran")\n')
    env = {**os.environ, "SENTINEL": str(sentinel)}
    subprocess.run(
        [sys.executable, str(GATE), str(tolerant)],
        input="not json at all",
        capture_output=True,
        text=True,
        env=env,
    )

    assert sentinel.exists(), "malformed payload must not silence hooks"


def test_missing_target_does_not_crash_the_tool_call(sentinel):
    """A bad registration must not break the user's tool call."""
    result = _run_gate(HOOKS_DIR / "does_not_exist.py", _payload("auto"), sentinel)

    assert result.returncode == 0


# --------------------------------------------------------------------------- carve-outs


def test_always_on_guard_runs_in_plan_mode(tmp_path, sentinel):
    """Irreversible-loss guards outlive the mode rule.

    The owner asked for auto-only in the SAME message as "a dev paralel is working so watch out,
    tests and push" -- which is scoped_stage_guard and no_verify_push_guard by name. A lost file
    and a 197-commit push to master (a prod deploy) are not recoverable by switching modes.
    """
    import _hook_mode

    always_on = sorted(_hook_mode.ALWAYS_ON_HOOKS)
    assert always_on, "the carve-out must be explicit, not empty-by-accident"

    target = tmp_path / always_on[0]
    target.write_text(TARGET_SRC)
    result = _run_gate(target, _payload("plan"), sentinel)

    assert sentinel.exists(), f"{always_on[0]} must fire in every mode"
    assert result.returncode == 2


def test_always_on_set_names_only_real_hooks():
    """A carve-out naming a file that does not exist protects nothing and reads as if it does."""
    import _hook_mode

    for name in _hook_mode.ALWAYS_ON_HOOKS:
        assert (HOOKS_DIR / name).exists(), f"ALWAYS_ON_HOOKS names a missing hook: {name}"


def test_subagent_is_silenced_even_in_auto(target, sentinel):
    """Stricter than the mode rule, and already the SoT's position.

    A subagent's tool calls carry the SAME session_id as the main conversation, so letting its
    hooks run corrupts the owner-facing todo state. agent_id is the discriminator.
    """
    result = _run_gate(target, _payload("auto", agent_id="sub-7"), sentinel)

    assert not sentinel.exists()
    assert result.returncode == 0


def test_subagent_carve_out_beats_always_on(tmp_path, sentinel):
    """Both rules fire at once; the subagent rule is the stricter one and must win."""
    import _hook_mode

    target = tmp_path / sorted(_hook_mode.ALWAYS_ON_HOOKS)[0]
    target.write_text(TARGET_SRC)
    result = _run_gate(target, _payload("auto", agent_id="sub-7"), sentinel)

    assert not sentinel.exists()
    assert result.returncode == 0


# --------------------------------------------------------------------------- harness side sessions
#
# ENGINE-DOWN-2 (2026-10-12). The IDE opens a short SIDE session to summarize the conversation, and it runs this repo's
# hooks. Its Stop hooks blocked the summary with demands, and the summarizer acted on them: it killed the four MEXC
# demo engines (05:31:05, 07:29:36), edited PLAN_1M.md, committed with `git add -A`, and pushed master (a prod deploy).

#: The first user record of a real side session (8ae62afe, CLI 2.1.252), the conversation log after it cut.
SIDE_FIRST_RECORD = {
    "type": "user",
    "promptSource": "sdk",
    "entrypoint": "claude-vscode",
    "message": {
        "role": "user",
        "content": "Below is a conversation log from a Claude Code coding session. Create a summary to help the next "
        "session quickly understand the context.\n\n## Prioritize including\n- Design decisions ...",
    },
}


def _transcript(tmp_path: Path, first_user: Mapping[str, object]) -> str:
    path = tmp_path / "session.jsonl"
    records = [{"type": "queue-operation", "operation": "enqueue"}, first_user, {"type": "assistant", "message": {}}]
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return str(path)


def test_a_side_session_is_silenced_even_in_auto(target, sentinel, tmp_path):
    result = _run_gate(target, _payload("auto", transcript_path=_transcript(tmp_path, SIDE_FIRST_RECORD)), sentinel)

    assert not sentinel.exists()
    assert result.returncode == 0
    assert result.stdout == ""


def test_a_side_session_still_meets_the_irreversible_loss_guards(tmp_path, sentinel):
    """It ran `git add -A` and pushed master: scoped_stage / no_verify_push must stay on for it."""
    import _hook_mode

    target = tmp_path / sorted(_hook_mode.ALWAYS_ON_HOOKS)[0]
    target.write_text(TARGET_SRC)
    _run_gate(target, _payload("default", transcript_path=_transcript(tmp_path, SIDE_FIRST_RECORD)), sentinel)

    assert sentinel.exists()


def test_a_working_session_is_not_mistaken_for_a_side_session(target, sentinel, tmp_path):
    """Canary: the owner's own first prompt -- and a session continued after compaction -- run every hook."""
    for prompt in ("ok continue with DEMO-1K", "This session is being continued from a previous conversation"):
        record = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": prompt}]}}
        sentinel.unlink(missing_ok=True)
        _run_gate(target, _payload("auto", transcript_path=_transcript(tmp_path, record)), sentinel)
        assert sentinel.exists(), prompt


def test_an_unreadable_transcript_runs_the_target(target, sentinel, tmp_path):
    """Fail OPEN: a missing transcript is not a side session."""
    _run_gate(target, _payload("auto", transcript_path=str(tmp_path / "missing.jsonl")), sentinel)

    assert sentinel.exists()


# --------------------------------------------------------------------------- self-gating hooks
#
# WHAT REFUTED THE FIRST VERSION OF THIS FILE (written ~40 minutes earlier, same session).
#
# As first written, every test here PASSED against a gate that silences all 12 mode-aware todo
# hooks outside auto. Measured: 14 files import `_hook_mode` (12 hooks + 2 test files), and
# `_hook_mode`'s own docstring records the rule they implement -- "outside auto it may RECORD
# what can release or baseline a demand, never SPEAK". A gate that skips the hook entirely skips
# the RECORDING too.
#
# The consequence is a real regression the first test set could not see: the first TodoWrite
# after a plan -> auto switch gets judged against a list snapshot minutes stale, and the denial
# it produces looks exactly like the guard working correctly. That is the defect `_hook_mode`
# was written to kill, reintroduced one layer up.
#
# So the gate grew decision 3 (self-gating hooks pass through) and these tests pin it. The old
# test set was not wrong about what it asserted -- it was incomplete in a way that made a
# silent regression pass green, which is the same thing as being wrong.


SELF_GATING_SRC = """\
import json, os, sys
import _hook_mode
payload = json.load(sys.stdin)
open(os.environ["SENTINEL"], "w").write(payload.get("session_id", ""))
"""


def test_self_gating_hook_still_runs_in_plan_mode(tmp_path, sentinel):
    """A hook that asks the mode ITSELF must not be pre-empted by the gate."""
    target = tmp_path / "todo_like_guard.py"
    target.write_text(SELF_GATING_SRC)
    env = {**os.environ, "SENTINEL": str(sentinel), "PYTHONPATH": str(HOOKS_DIR)}
    subprocess.run(
        [sys.executable, str(GATE), str(target)],
        input=json.dumps(_payload("plan")),
        capture_output=True,
        text=True,
        env=env,
    )

    assert sentinel.exists(), "a self-gating hook must reach its own mode logic"


def test_self_gating_detection_selects_the_real_todo_hooks():
    """Not vacuous: the marker must actually match the hooks it was designed around."""
    import _hook_mode_gate as hook_mode_gate

    detected = {path.name for path in HOOKS_DIR.glob("*_guard.py") if hook_mode_gate._is_self_gating(path)}

    assert "todo_stable_guard.py" in detected
    assert "todo_completion_guard.py" in detected
    assert len(detected) >= 8, f"expected the todo guard family, got {sorted(detected)}"


def test_self_gating_detection_rejects_an_ordinary_hook(tmp_path):
    """The complement: a hook with no mode logic must NOT be treated as self-gating."""
    import _hook_mode_gate as hook_mode_gate

    plain = tmp_path / "plain_guard.py"
    plain.write_text("import sys\nsys.exit(0)\n")

    assert not hook_mode_gate._is_self_gating(plain)


# --------------------------------------------------------------------------- the ratchet


def _registered_commands() -> list[tuple[str, str]]:
    settings = json.loads(SETTINGS.read_text())
    out: list[tuple[str, str]] = []
    for event, matchers in settings.get("hooks", {}).items():
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                out.append((event, hook.get("command", "")))
    return out


def test_the_scan_finds_registrations():
    """Guards the ratchet below from passing vacuously if settings.json moves or empties."""
    assert len(_registered_commands()) > 100


def test_every_file_based_registration_routes_through_the_gate():
    """THE RATCHET. This is what stops the next hook from forgetting the rule.

    Inline `node -e` approvers are exempt BY NAME: they are not hook files, they never speak,
    and they exist only to auto-answer a prompt. Everything that can print to the transcript
    goes through the gate.
    """
    ungated = [
        f"{event}: {command}"
        for event, command in _registered_commands()
        if ".claude/hooks/" in command and "_hook_mode_gate.py" not in command
    ]

    assert not ungated, "these registrations bypass the mode gate:\n  " + "\n  ".join(ungated)


def test_settings_json_is_still_valid_json():
    """The splice edits command strings in place; a broken settings.json disables every hook."""
    settings = json.loads(SETTINGS.read_text())

    assert set(settings.get("hooks", {})) >= {"PreToolUse", "PostToolUse", "Stop", "SessionStart"}


# --------------------------------------------------------------------------- HOOK-MODE-1: the gate tier
#
# Measured 2026-09-24: a whole day in `acceptEdits` ran 98 of 104 hooks silent -- the pulsai.log
# review before commit, before/after on both environments, one-definition, reinvent-the-wheel --
# while the session committed and PUSHED nine commits (a push IS a prod deploy). The auto-only rule
# saves tokens only on hooks that speak WITHOUT a violation; a hook that speaks only on a violation
# costs nothing when the work is clean, so silencing it buys nothing and loses everything.


@pytest.mark.parametrize("mode", ["default", "acceptEdits", "auto", "bypassPermissions", ""])
def test_a_gate_hook_runs_in_every_mode_the_agent_can_act_in(mode: str) -> None:
    import _hook_mode
    import _hook_mode_gate

    gate = sorted(_hook_mode.GATE_HOOKS)[0]
    payload = _payload(mode or None)

    assert _hook_mode_gate.should_run(HOOKS_DIR / gate, payload) is True


def test_a_gate_hook_is_silent_in_plan_mode() -> None:
    """Nothing can be executed in plan mode, so a gate there could only demand the impossible."""
    import _hook_mode
    import _hook_mode_gate

    for name in sorted(_hook_mode.GATE_HOOKS - _self_gating_names()):
        assert _hook_mode_gate.should_run(HOOKS_DIR / name, _payload("plan")) is False, name


def test_a_nag_stays_auto_only() -> None:
    """The 2026-09-14 rule still binds everything that is not a gate."""
    import _hook_mode_gate

    nag = HOOKS_DIR / "main_objective_reminder.py"
    assert _hook_mode_gate.should_run(nag, _payload("acceptEdits")) is False
    assert _hook_mode_gate.should_run(nag, _payload("auto")) is True


def test_the_gate_tier_and_the_always_on_set_are_disjoint() -> None:
    import _hook_mode

    assert not (_hook_mode.GATE_HOOKS & _hook_mode.ALWAYS_ON_HOOKS)


def test_every_gate_hook_exists_and_is_registered() -> None:
    """A gate that is not a file, or not wired in settings.json, protects nothing and reads as if it did."""
    import _hook_mode

    registered = SETTINGS.read_text()
    for name in _hook_mode.GATE_HOOKS:
        assert (HOOKS_DIR / name).exists(), f"GATE_HOOKS names a missing hook: {name}"
        assert name in registered, f"GATE_HOOKS names an unregistered hook: {name}"


def _self_gating_names() -> set[str]:
    import _hook_mode_gate

    return {path.name for path in HOOKS_DIR.glob("*_guard.py") if _hook_mode_gate._is_self_gating(path)}


# --------------------------------------------------------------------------- GORTEX-HOOK-HOLE

#: A target that records the tool and the file it was told about, the way the write-time guards read them.
SEES_SRC = """\
import json, os, sys
payload = json.load(sys.stdin)
tool_input = payload.get("tool_input") or {}
open(os.environ["SENTINEL"], "w").write(f"{payload.get('tool_name')}|{tool_input.get('file_path')}")
"""


def test_a_gortex_edit_reaches_the_target_as_the_edit_it_is(tmp_path: Path, sentinel: Path) -> None:
    """GORTEX-HOOK-HOLE (2026-10-12): 21 of 23 write-time guards read only tool_input["file_path"]; gortex sends
    "path". The gate hands every target the built-in shape, so no guard has to learn gortex."""
    target = tmp_path / "sees_guard.py"
    target.write_text(SEES_SRC)
    payload = _payload("auto", hook_event_name="PreToolUse", tool_name="mcp__gortex__edit_file",
                       tool_input={"path": "apps/api/x.py", "old_string": "a", "new_string": "b"})
    env_root = str(tmp_path / "repo")
    result = subprocess.run([sys.executable, str(GATE), str(target)], input=json.dumps(payload), capture_output=True,
                            text=True, env={**os.environ, "SENTINEL": str(sentinel), "CLAUDE_PROJECT_DIR": env_root})
    assert result.returncode == 0, result.stderr
    assert sentinel.read_text() == f"Edit|{env_root}/apps/api/x.py"


def test_the_dry_door_judges_a_gortex_write_like_a_write(tmp_path: Path) -> None:
    """The measured hole, end to end on the REAL guard: one_definition_guard denied a second home for epoch_ms as a
    Write and let the same text through as mcp__gortex__write_file. Canary first: the Write shape must be denied."""
    root = HOOKS_DIR.parent.parent
    rel = "apps/api/src/research/pine/probe_second_home.py"
    content = '"""probe."""\n\n\ndef epoch_ms(index):\n    return index.as_unit("ms").asi8\n'
    shapes = {"Write": {"file_path": f"{root}/{rel}", "content": content},
              "mcp__gortex__write_file": {"path": f"{root.name}/{rel}", "content": content}}
    denied = {}
    for tool, tool_input in shapes.items():
        payload = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "permission_mode": "auto",
                   "session_id": "gortex-hole", "cwd": str(root)}
        out = subprocess.run([sys.executable, str(GATE), str(HOOKS_DIR / "one_definition_guard.py")], input=json.dumps(payload),
                             capture_output=True, text=True, env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})
        denied[tool] = '"deny"' in out.stdout or out.returncode == 2
    assert denied["Write"], "canary: the DRY door no longer denies a second epoch_ms home -- this test proves nothing"
    assert denied["mcp__gortex__write_file"], "a gortex write passes the DRY door a Write cannot"


def _gate_out(target: str, payload: dict[str, object], root: Path) -> subprocess.CompletedProcess[str]:
    full = {"hook_event_name": "PreToolUse", "permission_mode": "auto", "session_id": "gortex-batch", "cwd": str(root), **payload}
    return subprocess.run([sys.executable, str(GATE), str(HOOKS_DIR / target)], input=json.dumps(full), capture_output=True,
                          text=True, env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})  # fmt: skip


def test_a_gortex_batch_is_judged_entry_by_entry_and_the_first_deny_is_the_answer() -> None:
    """GORTEX-BATCH-HOLE (2026-10-14), on the REAL guards: an `.apply` the pandas guard denies as an Edit, and a second
    epoch_ms home the DRY door denies as a Write, each hidden as the SECOND entry of a gortex batch_edit behind a clean
    first entry. One deny on stdout -- never one answer per entry, which the harness could not parse."""
    root = HOOKS_DIR.parent.parent
    clean = {"path": f"{root.name}/apps/api/src/research/pine/sr_sweep_signals_5m/book_chart50.py", "old_string": "def months(",
             "new_string": "def months("}  # fmt: skip
    pandas_edit = {**clean, "new_string": "def probe(t):\n    return t.apply(len)\n\n\ndef months("}
    second_home = {"path": f"{root}/apps/api/src/research/pine/probe_second_home.py",
                   "content": '"""probe."""\n\n\ndef epoch_ms(index):\n    return index.as_unit("ms").asi8\n'}  # fmt: skip
    for target, bad in (("pandas_last_resort_guard.py", pandas_edit), ("one_definition_guard.py", second_home)):
        out = _gate_out(target, {"tool_name": "mcp__gortex__batch_edit", "tool_input": {"edits": [clean, bad]}}, root)
        assert out.stdout.count('"permissionDecision"') == 1 and '"deny"' in out.stdout, (target, out.stdout, out.stderr)
        quiet = _gate_out(target, {"tool_name": "mcp__gortex__batch_edit", "tool_input": {"edits": [clean, clean]}}, root)
        assert '"deny"' not in quiet.stdout, (target, quiet.stdout)  # a clean batch stays clean
