"""Which permission mode a hook fired in, and whether the TODO hooks may speak in it.

Owner, 2026-09-11: "todo list hook MUST pop/run/start ONLY when in auto mode or switch from mode X
to auto mode". Plan mode cannot write code, yet the todo guards blocked three consecutive
submissions there, and the ledger reminder demanded a TodoWrite self-check nobody could act on.

The signal is the payload's `permission_mode`. The CLI builds it into every hook input
(`permission_mode:c(he(t).mode)` in the 2.1.252 binary) and real transcripts record exactly
`auto` (541), `default` (308) and `plan` (6).

THE ONE RULE for a todo hook outside auto mode: it may RECORD what can release or baseline a demand
(a list snapshot, a gate run, a rules read), never what can CREATE one (a resend budget, a ledger
write awaiting an item), and it never SPEAKS. Recording baselines in every mode is what stops the
first auto TodoWrite after a switch from being judged against a list that is minutes stale.

A SEPARATE carve-out governs SUBAGENTS, and it is STRICTER than the mode rule above: a hook firing
inside a subagent call (`fired_inside_subagent`) must neither speak NOR record, in every mode
including auto. Measured 2026-09-13: a subagent's tool calls carry the SAME `session_id` as the
main conversation, so keying state purely by session_id let a subagent's private TodoWrite
scaffolding overwrite the owner-facing `.todo_stable_state.json` and reset
`.todo_pomodoro_state.json` -- the "record baselines outside auto" treatment above is the WRONG
answer here, because recording is exactly what corrupted the state. The discriminator is the
payload's `agent_id` (present only inside a subagent call, per
https://code.claude.com/docs/en/hooks "Common input fields") -- never `agent_type`, which is also
set on a main-thread `--agent` (named-agent) session and would misclassify the owner's own list.

REUSE-AUDIT: considered _hook_state.py (imported below for its state I/O); not extending it because
a permission mode is not a per-session counter, which is all that module models. Considered
apps/api/src/infrastructure/persistence/stripe_webhook_event_model.py (the name collision); not
related — it is a Stripe webhook ORM model sharing only the tokens "hook" and "mode". Searched
first: gortex `permission_mode` and rg over .claude/hooks found no existing reader of the mode.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from _hook_state import load_state, save_state
from _hook_transcript import first_user_text

#: The only mode in which hooks speak.
AUTO_MODE: Final = "auto"

#: Hooks that fire in EVERY mode, because what they prevent cannot be undone by changing mode.
#:
#: Owner, 2026-09-14, asked for auto-only in the SAME message as "a dev paralel is working so
#: watch out, tests and push" -- which names the first two of these by their job. Each entry has
#: a recorded incident in its own docstring:
#:
#:   scoped_stage_guard.py          `git add -A` swept in a 151-line file this session never wrote
#:   no_verify_push_guard.py        a --no-verify push carried 197 foreign commits to master,
#:                                  and a push to master IS a prod deploy
#:   json_write_integrity_guard.py  a torn es.json 404'd every /es/* route for 43 minutes
#:   auth_session_destroy_guard.py  `railway logout` inside a command described as "without
#:                                  changing it" killed the CLI session AND the project link;
#:                                  the repair is a browser OAuth flow only the OWNER can run
#:
#: The fourth entry is here on the set's own criterion rather than by exception: the loss is not
#: data, it is that I cannot undo it. A logout is one word, as easy to type in `default` mode as
#: in `auto`, and afterwards every deploy, log and metric read is dead until a human is at a
#: keyboard. Owner, 2026-09-21: "om my railway logout.. or vercel or claudfalre etc.. HOOK to
#: fire and block you!"
#:
#: Keep this set SMALL and irreversible-only. Process and nag guards do NOT belong here -- they
#: are precisely what the owner silenced. test_hook_mode_gate fails if an entry names a missing
#: file, so the set cannot rot into a list of hooks that no longer exist.
ALWAYS_ON_HOOKS: Final[frozenset[str]] = frozenset(
    {
        "scoped_stage_guard.py",
        "no_verify_push_guard.py",
        "json_write_integrity_guard.py",
        "auth_session_destroy_guard.py",
    }
)

#: The one mode in which nothing can be executed: no write lands, no command runs, no push leaves.
PLAN_MODE: Final = "plan"

#: GATES -- hooks that speak ONLY on a violation, and run in EVERY mode the agent can act in.
#:
#: HOOK-MODE-1 (owner, 2026-09-25: "DEEP think and you do it"). Measured the day before: a session
#: in `acceptEdits` committed and PUSHED nine commits (a push IS a prod deploy) with 98 of 104 hooks
#: silent -- no pulsai.log review before commit, no before/after on both environments, no
#: one-definition or reinvent-the-wheel check on the code it wrote.
#:
#: The 2026-09-14 auto-only rule is about COST, and cost comes only from hooks that speak WITHOUT a
#: violation -- reminders, context injections, ledgers. A hook that speaks only on a violation costs
#: nothing when the work is clean, so silencing it outside auto saved nothing and lost every
#: protection it gives. That is the whole criterion, and it is ENFORCED, not asserted:
#: `test_gate_hooks_speak_only_on_violation.py` drives every registration of every entry with a
#: harmless payload and fails if the hook says anything.
#:
#: What a gate guards, one of three harms that do not depend on the mode:
#:   (a) an action that leaves the machine or kills running work -- commit, push, a live stack;
#:   (b) code landing in the repo that a later session pays for -- a second home, a copied body,
#:       a new suppression, a gate edited without data, a degraded timeframe band;
#:   (c) a claim the owner ACTS on -- a money verdict, a fix declared proven, a number declared
#:       wrong, work declared done or tracked.
#:
#: PLAN mode stays silent for this tier: nothing can be executed there, so a gate could only demand
#: the impossible -- the exact 2026-09-11 token burn the auto-only rule was written for.
#:
#: `architect_no_defer_guard` and `todo_completion_guard` moved here from ALWAYS_ON_HOOKS, where the
#: owner put them on 2026-09-22 ("launching the arms now" and "tracked" written with nothing done,
#: in a non-auto session he was watching). ALWAYS_ON also fired them in PLAN mode, where a plan is
#: nothing but named next steps. And todo_completion_guard never actually ran outside auto at all:
#: its own main() asked `todo_hooks_may_speak` and exited -- the 09-22 decision was inert until now.
GATE_HOOKS: Final[frozenset[str]] = frozenset(
    {
        # (a) actions that leave the machine or kill running work
        "review_before_commit_guard.py",  # reads pulsai.log before every commit
        "precommit_before_publish_guard.py",  # pre-commit ran before anything is published
        "localhost_stack_alive_guard.py",  # a restart kills queued/running cert and re-grade tasks
        "stale_worker_guard.py",  # a worker on boot-time code grades money on code that is gone
        "stale_engine_guard.py",  # a live MEXC engine on boot-time code produces demo evidence about code that is gone
        "undeclared_install_guard.py",  # a by-name pip install made the crash-class gate read 321 for 318's code
        "pgrep_anchor_guard.py",  # an unanchored pgrep wait never ended: a grade chained behind it never started (11-05)
        # (b) code landing in the repo
        "one_definition_guard.py",
        "reinvent_wheel_guard.py",
        "clone_body_guard.py",
        "outside_repo_python_guard.py",  # owner 2026-10-20: a .py outside the repo escapes every gate
        "pandas_last_resort_guard.py",  # owner 2026-10-13: pandas last resort, perf is a must
        "perf_measured_guard.py",  # owner 2026-10-18: a numba kernel / indicator lands only after numpy-numba-polars timings
        "sot_composition_guard.py",
        "keep_in_sync_guard.py",
        "no_new_noqa_guard.py",
        "suppression_guard.py",
        "investigate_before_gate_guard.py",
        "timeframe_band_guard.py",
        "edge_hunt_sot_cert_guard.py",
        "verdict_needs_sot_runner_guard.py",
        # (c) claims the owner acts on
        "grade_tables_shown_guard.py",  # owner 2026-11-02: a landed grade's detail tables reach the reply, by the record's own numbers
        "live_lighter_numbers_guard.py",  # owner 2026-11-04: an account balance comes from live Lighter, read in the same turn
        "fix_needs_before_after_both_envs_guard.py",
        "measure_dont_infer_guard.py",
        "select_window_verdict_guard.py",
        "verdict_window_role_guard.py",
        "kill_needs_ruin_reason_guard.py",
        "owner_first_guard.py",  # owner 2026-10-13: the pinned item first, no chores, no stop while it is open
        "spot_only_verdict_guard.py",
        "boycott_guard.py",  # a cost / caution / few-hours verdict or a new gate drops a script off the owner's grade
        "gate_honesty_guard.py",  # owner 2026-10-18: a gate's finding written around or waved off as 'not my case'
        "naming_guard.py",  # owner 2026-10-18: a new definition named by a vague word or an undefined abbreviation
        "promise_pretool_guard.py",  # "tracked / I'm adding it as an item" with no TodoWrite after it: the next tool waits
        "todo_owner_asked_guard.py",  # owner 2026-10-21: a new todo item only when HIS words ask for it ("STOP ADDING")
        "single_venv_guard.py",  # one interpreter: a second venv was 87,005 indexed files and a 28 GiB gortex heap
        "cert_failure_must_surface_guard.py",
        "verify_judge_guard.py",
        "architect_no_defer_guard.py",
        "todo_completion_guard.py",
        "pass_needs_script_guard.py",  # a both-sides 5m pass may not end a turn without its Pine script
        "pulsai_log_script_guard.py",  # pulsai.log is read through the committed scripts, not an ad-hoc parser
        "subagent_briefing_guard.py",  # a spawn must carry the rules, a fence and (research) the money path
    }
)

#: PLUGIN hooks -- each plugin's OFF switch for this project: plugin name -> (env var, value).
#:
#: PLUGIN-GATE (owner, 2026-10-20). Claude Code registers a plugin's hooks from the plugin's own
#: hooks/hooks.json, so they never pass through _hook_mode_gate.py and fire in every mode, plan included.
#: Measured on ecc 2.2.1: 23 hooks, 5 writing ledgers on a harmless call; with its switch set, 0 reached
#: the model and 0 wrote. The switch is set in .claude/settings.json "env", which keeps the plugin's
#: skills and agents here and its hooks in other projects. test_plugin_hooks_switched_off fails on an
#: enabled plugin that ships hooks with no switch here, and drives every switched hook to prove silence.
PLUGIN_HOOK_SWITCHES: Final[dict[str, tuple[str, str]]] = {"ecc": ("ECC_HOOKS_ENABLED", "false")}


def permission_mode(payload: Any) -> str:
    """The mode this hook fired in, or "" when the payload does not say."""
    if not isinstance(payload, dict):
        return ""
    mode = payload.get("permission_mode")
    return mode if isinstance(mode, str) else ""


def fired_inside_subagent(payload: Any) -> bool:
    """True when this hook fired inside a subagent call, never on the main thread.

    THE DEFECT THIS EXISTS TO KILL (measured 2026-09-13). A subagent's tool calls carry the SAME
    `session_id` as the main conversation, and every todo hook here keys its state purely by
    session_id. So a subagent's own private TodoWrite scaffolding was read and recorded as if it
    were the owner-facing list: `.todo_stable_state.json` held 14 items (the main agent's 6 plus a
    subagent's 8 `BOUNDARY1-*` items); the subagent's accepted write re-stamped every main item
    back to "pending" -- in_progress items included -- and renumbered three of them; the main
    agent's next TodoWrite was then DENIED for "removing" items it never wrote. The same collision
    resets `.todo_pomodoro_state.json` (the owner's pomodoro clock) on every subagent TodoWrite.

    THE SIGNAL. `agent_id` (https://code.claude.com/docs/en/hooks, "Common input fields") is
    "Present only when the hook fires inside a subagent call" -- exactly the discriminator needed.
    `agent_type` is NOT it: that field is also set on a main-thread `--agent` (named-agent)
    session, so keying off it would misclassify the owner's own list as subagent scaffolding and
    go silent on it.
    """
    if not isinstance(payload, dict):
        return False
    agent_id = payload.get("agent_id")
    return isinstance(agent_id, str) and agent_id != ""


#: The prompt the IDE extension opens its summary side session with (CLI 2.1.252, 58 such transcripts since
#: 2026-10-10). A different prompt -- the owner's, or "This session is being continued ..." -- is a working session.
SIDE_SESSION_PROMPT: Final = "Below is a conversation log from a Claude Code coding session."


def harness_side_session(payload: Any) -> bool:
    """True when the hook fired in a side session the IDE opened to summarize a conversation, not in a working one.

    THE DEFECT THIS EXISTS TO KILL (ENGINE-DOWN-2, measured 2026-10-12). The side session runs this repo's hooks, and
    the Stop hooks block its summary with demands the summarizer then acts on. 15 of 58 such sessions ran tools: they
    killed every MEXC demo engine twice (05:31:05, 07:29:36 -- stale_engine_guard told them to "restart" engines they
    never launched), edited PLAN_1M.md, ran `git add -A` + commit, and pushed master, a prod deploy. Nothing in the
    payload tells it apart (same entrypoint, same permission_mode); the transcript's opening prompt does.
    """
    if not isinstance(payload, dict):
        return False
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not path:
        return False
    return first_user_text(path).startswith(SIDE_SESSION_PROMPT)


def hooks_may_speak(payload: Any) -> bool:
    """True in auto mode. A KNOWN other mode silences; an ABSENT mode keeps the original behaviour.

    Absent is not read as "not auto": every real payload carries the field, so the only inputs
    without it are harnesses and older fixtures -- and a guard that goes quiet whenever a field is
    missing is the silent-emptiness defect this repo keeps paying for.

    Owner, 2026-09-14: "NO hooks has to fire if not in auto mode!! SoT, centralized!!" This was
    the TODO hooks' rule since 2026-09-11 and is now the rule for EVERY hook, applied centrally by
    hook_mode_gate.py rather than by 111 hooks each remembering to ask.
    """
    return permission_mode(payload) in ("", AUTO_MODE)


def agent_can_act(payload: Any) -> bool:
    """True in every mode where a write can land or a command can run -- everything but plan.

    The predicate for GATE_HOOKS. An ABSENT mode counts as acting, for the same reason
    `hooks_may_speak` reads absent as auto: a guard that goes quiet when a field is missing is the
    silent-emptiness defect this repo keeps paying for.
    """
    return permission_mode(payload) != PLAN_MODE


#: The original, TODO-scoped name. Kept so the 12 todo hooks that import it keep working, and
#: deliberately an ALIAS rather than a second body: one predicate, one place to change it.
todo_hooks_may_speak = hooks_may_speak


def entered_auto(payload: Any, state_path: Path) -> bool:
    """True the first time a session is seen in auto mode after any other mode (or none).

    Records the mode on every call that carries one, so a switch is caught at whichever event
    comes first after it -- the next prompt, or the next tool call after a mid-turn switch.
    """
    mode = permission_mode(payload)
    if not mode:
        return False
    session = str(payload.get("session_id") or "")
    state = load_state(state_path)
    previous = state.get("mode") if state.get("session_id") == session else ""
    save_state(state_path, {"session_id": session, "mode": mode})
    return mode == AUTO_MODE and previous != AUTO_MODE
