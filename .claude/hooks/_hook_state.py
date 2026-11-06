"""Shared state loading for guards that bound how many times they may block.

THE DEFECT THIS EXISTS TO KILL (measured 2026-08-16, across all 69 guards).

A guard bounds its blocks so it can never wedge a session — `_MAX_BLOCKS = 2` or `3`. That counter
lived in a gitignored state file that only ever incremented and was never cleaned. So once a guard
hit its bound it returned "don't block" **forever**: new session, IDE restart, resuming hours after
a usage limit — same file, still dead.

Three guards were found already dead on the dev machine:

    verify_judge_guard          blocks 2 / max 2   DEAD
    capital_provenance_guard    blocks 3 / max 3   DEAD since 2026-08-13
    instruction_compliance      blocks 3 / max 3   DEAD

`verify_judge_guard` is the one that blocks quoting a doc instead of verifying it. It was dead all
day on 2026-08-16 while exactly that failure happened repeatedly and silently.

Owner: *"what if a close ide? what If I change and create new session? what if you reach limit, wait
X hours and start again? ... are you MONKEY CODING and DOING blindly the code without THINKING and
EVALUATING???"*

THE FIX. The bound is loop-safety WITHIN one session's stop-loop, so it must be scoped to that
session. A new `session_id` resets the counters; the same one keeps the bound intact. With no
session id available the state is returned untouched — fail SAFE, never silently re-arm mid-loop.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Final

#: Counters that are only meaningful within one session's stop-loop and must reset with it.
#: `blocks` is the near-universal name; a guard with extra per-session tallies lists them itself.
SESSION_SCOPED_KEYS: tuple[str, ...] = ("blocks",)

#: A resumed session older than this has lost its context anyway, so a per-session state file
#: past this age is pure clutter -- pruning it keeps the sibling glob from growing unbounded
#: across however many sessions have ever touched this repo.
SESSION_STATE_MAX_AGE_DAYS: Final = 7


def _prune_stale_siblings(base: Path) -> None:
    """Remove `<stem>.*<suffix>` siblings of `base` older than `SESSION_STATE_MAX_AGE_DAYS`.

    Bounded to the ONE glob this function targets and never raises -- a state-path helper must
    not be the reason a hook wedges, and it must never touch a file outside its own naming
    convention.
    """
    try:
        cutoff = time.time() - SESSION_STATE_MAX_AGE_DAYS * 86400
        for sibling in base.parent.glob(f"{base.stem}.*{base.suffix}"):
            try:
                if sibling.is_file() and sibling.stat().st_mtime < cutoff:
                    sibling.unlink()
            except OSError:
                continue
    except Exception:
        pass


def session_state_path(base: Path, session_id: str) -> Path:
    """A state file PRIVATE to `session_id`, sibling to `base` -- or `base` itself when
    `session_id` is empty (fail-safe: today's single-file behaviour, never worse).

    THE COLLISION THIS EXISTS TO KILL (measured 2026-09-13). Every todo hook's state file was ONE
    path shared repo-wide, stamped with a single `session_id`. Two PEER Claude Code sessions in
    the same repo -- ordinary multi-session use, not a bug in either session -- write to the SAME
    file: whichever session's hook fires last wins, and `scoped_to_session` treats every OTHER
    session as "new" and resets its counters. Measured: a peer session's SessionStart reset the
    lead session's running pomodoro clock (open_count 6 -> 0, deadline restarted); the identical
    shape lets a peer's TodoWrite reset `.todo_stable_state.json`, after which the next write from
    the original session is judged against nothing (fail-open). `agent_id` does not fix this --
    different PEER SESSIONS have different session_ids, not agent_ids.

    THE FIX: one file PER SESSION. `session_id` is hashed (never embedded raw) so the filename is
    filesystem-safe regardless of what the id contains, truncated to 12 hex chars -- enough that
    an accidental collision between two real session ids is astronomically unlikely while keeping
    the sibling glob short and readable.

    Also prunes state files this same naming convention orphaned from sessions long past (see
    `_prune_stale_siblings`), so the count of these files does not grow forever.
    """
    if not session_id:
        return base
    digest = hashlib.sha1(session_id.encode("utf-8", "replace")).hexdigest()[:12]
    _prune_stale_siblings(base)
    return base.with_name(f"{base.stem}.{digest}{base.suffix}")


def scoped_to_session(
    state: dict[str, Any],
    session_id: str,
    *,
    reset_keys: tuple[str, ...] = SESSION_SCOPED_KEYS,
) -> dict[str, Any]:
    """Return `state` for this session, zeroing the bounded counters when the session changed.

    Non-counter state (cached evidence, timestamps, audited-commit lists) is PRESERVED across the
    reset: it describes the repository, not the conversation, and re-deriving it would be waste.
    """
    if not session_id:
        return state
    if state.get("session_id") == session_id:
        return state
    fresh = dict(state)
    fresh["session_id"] = session_id
    fresh["session_started_at"] = time.time()
    for key in reset_keys:
        fresh[key] = 0
    return fresh


def load_state(
    path: Path,
    session_id: str = "",
    *,
    reset_keys: tuple[str, ...] = SESSION_SCOPED_KEYS,
) -> dict[str, Any]:
    """Read a guard's JSON state file and scope it to the session. Never raises."""
    try:
        raw = json.loads(path.read_text())
    except Exception:
        raw = {}
    return scoped_to_session(raw if isinstance(raw, dict) else {}, session_id, reset_keys=reset_keys)


def finding_fingerprint(text: str) -> str:
    """Stable identity for one finding, so REPETITION can be told from PROGRESS.

    Whitespace-normalised: a reflowed paragraph is the same deferral, and treating it as new
    would hand the agent a way to reset the counter by rewording nothing.
    """
    return hashlib.sha1(" ".join(text.split()).encode("utf-8", "replace")).hexdigest()


def wedged_on_no_progress(
    path: Path,
    session_id: str,
    fingerprint: str,
    *,
    max_stuck: int,
) -> bool:
    """True when the IDENTICAL finding has survived `max_stuck` consecutive stops.

    THE ALTERNATIVE THIS REPLACES, and why it is not a matter of taste. A Stop guard needs some
    loop safety, and the cheap one is `if payload.get("stop_hook_active"): return`. That makes the
    guard ONE-SHOT: after any nudge in a stop cluster every later stop passes untouched -- including
    a finding nobody has ever been shown. Measured 2026-09-06 on `architect_no_defer_guard`, which
    blocks its trigger sentence when driven directly and stayed silent when that sentence shipped.

    `todo_completion_guard` reached the same conclusion on 2026-08-05 and wrote its own version of
    this; extracted here so the third guard that needs it does not write a fourth.

    A fingerprint is strictly better because it separates the two cases the flag conflates: an
    agent that is WORKING (text changes -> counter resets -> unlimited pressure) from one that is
    WEDGED (identical text -> counter climbs -> release). Callers must report a release as a wedge,
    never as agreement -- the finding still stands.
    """
    state = load_state(path, session_id)
    previous = state.get("fingerprint")
    blocks = int(state.get("blocks", 0)) + 1 if previous == fingerprint else 1
    save_state(
        path,
        {**state, "session_id": session_id, "fingerprint": fingerprint, "blocks": blocks},
    )
    return blocks > max_stuck


def save_state(path: Path, state: dict[str, Any]) -> None:
    """Persist a guard's state. Never raises — a guard must not die on a read-only filesystem."""
    try:
        path.write_text(json.dumps(state))
    except Exception:
        pass
