#!/usr/bin/env python3
"""Block reinventing the wheel — dynamic DRY / reuse-first guard.

THE FAILURE (owner, 2026-08-07 and prior): agent writes parallel harnesses
(``run_strategy_ml_feat_combo_cert.py``, per-leaf ``cert_*_full_findbest`` clones,
proxy train→x_exit_grid for a different feature pack) WITHOUT first searching for
existing SoT / helpers. Soft ``reuse-check.sh`` only *warned* — agent ignored it.

This guard is **dynamic**, not CERT-only:

  1. NEW-file Write with strong **name collision** vs tracked files (token score)
  2. NEW-file Write whose body **forks a configured SoT module** (JSON registry —
     add entries; do not hardcode one leaf forever)
  3. DENY unless the agent either:
       * left a ``REUSE-AUDIT:`` in the new file citing why existing paths do not
         suffice, OR
       * ran a codebase investigate command in the last N minutes (rg/gortex/…)

Enforcement: PreToolUse(Write) deny + PostToolUse(Bash|…) investigate stamp.
Fails OPEN on internal errors.
"""

from __future__ import annotations

#: Derived from the registration this guard already carries in settings.json, so
#: `register_guards --apply` can restore it if that file is ever regenerated.
HOOK_EVENT = ("PostToolUse", "PreToolUse")

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from _hook_deny import print_tool_denial

HOOK_DIR = Path(__file__).resolve().parent
STATE =Path(os.environ.get("REINVENT_WHEEL_STATE", HOOK_DIR / ".reinvent_wheel_state.json"))
SOT_CONFIG = Path(os.environ.get("REINVENT_WHEEL_SOT", HOOK_DIR / "reinvent_wheel_sot.json"))

_GENERIC = frozenset(
    {
        "test",
        "tests",
        "spec",
        "specs",
        "index",
        "init",
        "main",
        "app",
        "apps",
        "util",
        "utils",
        "helper",
        "helpers",
        "type",
        "types",
        "config",
        "conf",
        "base",
        "common",
        "core",
        "mod",
        "module",
        "models",
        "model",
        "schema",
        "schemas",
        "const",
        "constant",
        "constants",
        "service",
        "services",
        "new",
        "old",
        "tmp",
        "temp",
        "draft",
        "data",
        "file",
        "run",
        "script",
        "scripts",
    }
)

_REUSE_AUDIT = re.compile(r"REUSE-AUDIT:\s*\S.{15,}", re.IGNORECASE | re.DOTALL)
_INVESTIGATE_CMD = re.compile(
    r"("
    r"\brg\b|\bgrep\b|\bag\b|\bripgrep\b"
    r"|gortex|smart_context|search_symbols|find_files|get_callers|get_call_chain"
    r"|find_usages|ctx_grep|search_text|search_ast"
    r"|reuse-check|ARCHITECT_CHECKLIST|MODULE_MAP"
    r"|git\s+ls-files|git\s+grep"
    r")",
    re.IGNORECASE,
)

# Basename smells that almost always mean a parallel harness fork.
_FORK_NAME = re.compile(
    r"(combo_cert|full_findbest|_findbest|_capital_x_exit|_cert_clone|x_exit_clone)",
    re.IGNORECASE,
)


def _load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict[str, Any]) -> None:
    try:
        STATE.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


def _load_sot() -> dict[str, Any]:
    try:
        raw = json.loads(SOT_CONFIG.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {
            "name_collision_min_score": 2,
            "investigate_window_seconds": 1800,
            "extend_not_clone": [],
        }


def significant_tokens(stem: str) -> list[str]:
    """Lowercase alnum tokens ≥4 chars, dropping boilerplate words."""
    parts = re.split(r"[^a-z0-9]+", stem.lower())
    out: list[str] = []
    for p in parts:
        if len(p) < 4 or p in _GENERIC:
            continue
        out.append(p)
    return out


def list_tracked_files(repo_root: str) -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", repo_root, "ls-files"],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if proc.returncode != 0:
            return []
        return [ln for ln in proc.stdout.splitlines() if ln.strip()]
    except Exception:
        return []


def find_similar_tracked(new_path: str, tracked: list[str]) -> list[tuple[int, str]]:
    """Score tracked basenames by shared significant tokens with the new file stem."""
    base = os.path.basename(new_path)
    stem = base.rsplit(".", 1)[0]
    tokens = significant_tokens(stem)
    if not tokens:
        return []
    scored: list[tuple[int, str]] = []
    for rel in tracked:
        other = os.path.basename(rel)
        other_stem = other.rsplit(".", 1)[0]
        if other_stem == stem:
            continue
        other_l = other_stem.lower()
        score = sum(1 for t in tokens if t in other_l)
        if score > 0:
            scored.append((score, rel))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return scored[:12]


def has_reuse_audit(content: str) -> bool:
    """True when the new file documents a reuse investigation."""
    if not _REUSE_AUDIT.search(content or ""):
        return False
    # Must cite at least one code path-ish token so the audit is not a no-op sentence.
    return bool(re.search(r"[\w./-]+\.(py|ts|tsx|js|md)", content, re.IGNORECASE))


#: Modules a REUSE-AUDIT names. Only code files — a cited `.md` is context, not something the
#: file could have imported, so citing docs never incurs the import demand.
_AUDIT_CITED_MODULE = re.compile(r"[\w./-]+\.(?:py|ts|tsx|js)", re.IGNORECASE)


def reuse_audit_is_proved(content: str) -> bool:
    """True when the REUSE-AUDIT is backed by an actual import of a module it names.

    THE HOLE THIS CLOSES, and it is mine. On 2026-08-30 I wrote two scripts that forked the cert
    SoT, headed each with a fluent ``REUSE-AUDIT: considered <SoT>.py …``, and this guard passed
    both — because the old check was ``REUSE-AUDIT:`` plus any token shaped like a path. Both are
    things you TYPE. The owner had to notice and tell me to delete them.

    Owner, same day: "so tired of hearing from you … same or similar mistakes but hidden under
    other words/similar words or sentences."

    ``import <the module you said you considered>`` cannot be produced by rewording. So: if the
    audit names code modules, at least one of them must actually be imported. If it names only
    docs, or names nothing importable, the audit stands on its prose as before — the demand is
    made only where it is checkable.
    """
    text = content or ""
    if not has_reuse_audit(text):
        return False

    cited = {
        os.path.basename(m.group(0)).rsplit(".", 1)[0]
        for m in _AUDIT_CITED_MODULE.finditer(text)
    }
    cited.discard("")
    if not cited:
        return True  # nothing importable was named; prose audit, unchanged behaviour

    for stem in cited:
        # `import x`, `from x import y`, `from a.b.x import y`, `import a.b.x as z`
        if re.search(rf"^\s*(?:from|import)\s+[\w.]*\b{re.escape(stem)}\b", text, re.M):
            return True
    return False


def reuse_audit_addresses(content: str, strong: list[tuple[int, str]]) -> bool:
    """True when the audit names at least one of the colliding files the guard actually found.

    `reuse_audit_is_proved` asks whether an audit's OWN citations are backed by an import. This
    asks the prior question: does the audit answer the candidate that was PUT IN FRONT OF IT?

    MEASURED 2026-09-01 -- `test_xs_books_declare_their_kind.py` duplicated the assertion in
    `test_xs_books_are_not_declared_single_asset.py`, which the collision check had already
    surfaced as its top hit. The new file's audit discussed the `@hypothesis` decorator and the
    harness classifier instead, and passed. Nothing forced it to mention the sibling.

    Matched on the STEM the guard found, so it cannot be satisfied by rewording: to pass you have
    to write the name of the file you are about to duplicate, and once written, the answer is
    either a real reason or an obvious hole in review.
    """
    text = (content or "").lower()
    for _score, rel in strong:
        stem = os.path.basename(rel).rsplit(".", 1)[0].lower()
        if stem and stem in text:
            return True
    return False


def is_investigate_command(command: str) -> bool:
    return bool(_INVESTIGATE_CMD.search(command or ""))


def recent_investigate(window_seconds: int) -> bool:
    last = float(_load_state().get("last_investigate_at") or 0.0)
    return last > 0 and (time.time() - last) <= float(window_seconds)


def is_sot_fork_body(basename: str, content: str, sot: dict[str, Any]) -> str | None:
    """Return matching SoT rule id when body+name smell like a forbidden clone."""
    text = content or ""
    if len(text) < 200 and not _FORK_NAME.search(basename):
        return None
    name_l = basename.lower()
    for rule in sot.get("extend_not_clone") or []:
        if not isinstance(rule, dict):
            continue
        markers = [str(m) for m in (rule.get("module_markers") or [])]
        body_any = [str(b) for b in (rule.get("body_any") or [])]
        name_any = [str(n).lower() for n in (rule.get("name_any") or [])]
        hit_module = any(m in text for m in markers)
        hit_body = sum(1 for b in body_any if b in text) >= 2
        hit_name = any(n in name_l for n in name_any) or bool(_FORK_NAME.search(basename))
        # Importing a SoT module into a new findbest/combo_cert-named file is enough.
        if hit_module and hit_name:
            return str(rule.get("id") or "sot_fork")
        # Copy-paste of the grid body under a fork-ish name (no import string) — still a clone.
        if hit_body and hit_name:
            return str(rule.get("id") or "sot_fork")
    return None


#: Surfaces that HAVE an SoT accessor, and the pattern that means the body reached past it.
#:
#: MEASURED 2026-09-05 on two of my own files. `pick_band_specs.py` globbed the model store and
#: `r2_probe.py` built a boto3 client; `model_discovery.list_versions_for_slots` and
#: `create_storage_backend` already existed. Neither tripped the NAME check and that is structural,
#: not a tuning miss: `significant_tokens` needs two shared tokens, and the file that mattered
#: (`audit_r2_local_model_tiers.py`) shares zero with `r2_probe`. A name cannot find a duplicate
#: whose author chose other words. So this asks what the body DOES.
#:
#: Cost of the miss: the hand-rolled selector read the LOCAL tree, chose a version whose joblib is
#: absent from R2, and the cert died on FileNotFoundError. The accessor is backend-aware, so the
#: failure was unreachable through it.
_HANDROLLED_ACCESS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "the MODEL STORE",
        re.compile(r"(?:r?glob|iterdir)\s*\(\s*[^)]*(?:metadata\.json|model\.joblib|btc_usdt)", re.I),
        "src.infrastructure.ml.model_discovery.list_versions_for_slots",
    ),
    (
        "OBJECT STORAGE",
        re.compile(r"boto3\.(?:client|resource)\s*\(|\.r2\.cloudflarestorage", re.I),
        "src.infrastructure.ml.storage_backends.create_storage_backend",
    ),
)


def hand_rolled_access(content: str) -> tuple[str, str]:
    """(surface, accessor) when the body reaches a surface directly, else ('', '')."""
    for surface, pattern, accessor in _HANDROLLED_ACCESS:
        if pattern.search(content or ""):
            return surface, accessor
    return "", ""


def _access_is_answered(content: str, accessor: str) -> bool:
    """True when the body IMPORTS the accessor, or a REUSE-AUDIT names it.

    Deliberately NOT satisfied by `recent_investigate`. If a search ran it found the accessor and
    the code went around it anyway -- the same reasoning the SoT-fork branch already applies.
    """
    leaf = accessor.rsplit(".", 1)[-1]
    if leaf in (content or "") and re.search(rf"(?:import|from)\b[^\n]*\b{re.escape(leaf)}\b", content or ""):
        return True
    if not has_reuse_audit(content):
        return False
    audit = content[content.upper().find("REUSE-AUDIT:") :][:1200]
    return leaf in audit


def _hand_rolled_reason(basename: str, surface: str, accessor: str) -> str:
    return "\n".join(
        [
            f"BLOCKED — {basename} reaches {surface} directly instead of through its SoT.",
            "",
            f"Use: {accessor}",
            "",
            "The NAME check cannot catch this: it needs two shared filename tokens, and a",
            "duplicate whose author chose different words shares none. Measured 2026-09-05 —",
            "a hand-rolled model-store scan read the LOCAL tree, picked a version whose joblib",
            "is absent from R2, and the cert died on FileNotFoundError. The accessor is",
            "backend-aware, so that failure cannot happen through it.",
            "",
            "Answer it either way:",
            f"  * import {accessor.rsplit('.', 1)[-1]} and use it, or",
            f"  * REUSE-AUDIT: considered {accessor.rsplit('.', 1)[-1]}; not extending because <reason>.",
            "",
            "A recent codebase search is NOT an escape here — if it ran, it found the accessor.",
        ]
    )


def is_git_ignored(path: str, root: str) -> bool:
    """True when git ignores `path`, so it can never be tracked, shipped, or fork a SoT module.

    HOOKRT-1, 2026-09-23: 7 denials in one session on one-shot scripts in the gitignored
    `.scratch/agent/` -- the dir the facts guard's own docstring sends agent scripts to. A REUSE-AUDIT
    on a file that can never be committed protects nothing. Fails to False (judge it) on any error.
    """
    try:
        completed = subprocess.run(
            ["git", "check-ignore", "-q", path],
            cwd=root,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return False
    return completed.returncode == 0


def should_block_new_write(
    path: str,
    content: str,
    *,
    repo_root: str | None = None,
) -> tuple[bool, str]:
    """Return (block?, reason). Pure-ish; git listing injectable via list_tracked_files patch."""
    if not path:
        return False, ""
    # Edits to existing files are not "reinvent" — extend in place.
    if os.path.exists(path):
        return False, ""

    sot = _load_sot()
    min_score = int(sot.get("name_collision_min_score") or 2)
    window = int(sot.get("investigate_window_seconds") or 1800)

    root = repo_root
    if not root:
        try:
            root = (
                subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=os.path.dirname(path) or ".",
                ).stdout.strip()
                or None
            )
        except Exception:
            root = None
    if not root:
        return False, ""
    if is_git_ignored(path, root):
        return False, ""

    tracked = list_tracked_files(root)
    similar = find_similar_tracked(path, tracked)
    strong = [(s, p) for s, p in similar if s >= min_score]
    basename = os.path.basename(path)
    sot_hit = is_sot_fork_body(basename, content, sot)

    # HAND-ROLLED ACCESS is judged before the name check, because the name check cannot see it.
    # Answered by importing the accessor or by a REUSE-AUDIT naming it; a recent search is NOT an
    # escape here, for the same reason it is not one for a SoT fork.
    surface, accessor = hand_rolled_access(content)
    if surface and not _access_is_answered(content, accessor):
        return True, _hand_rolled_reason(basename, surface, accessor)

    if not strong and not sot_hit:
        return False, ""

    # TWO DIFFERENT BARS, because the two hits mean different things.
    #
    # A NAME COLLISION asks "did you look?" — a written audit or a recent search is honest evidence,
    # and that stays exactly as it was.
    #
    # A SOT FORK is not a question about looking. The body already reproduces a registered SoT
    # module, so "I searched" is the opposite of exculpatory (the search found it and it was forked
    # anyway), and a written audit is a sentence. Only an actual import of something the audit names
    # proves reuse, and no rephrasing produces an import.
    #
    # MEASURED 2026-08-30, on my own two forks of the cert SoT: both carried a fluent
    # `REUSE-AUDIT: considered <SoT>.py …` and neither imported it, and gortex searches ran
    # continuously so `recent_investigate` was true at every Write. Both escapes were open at once;
    # the guard fired zero times and the owner had to catch the forks by reading the diff.
    if sot_hit:
        if reuse_audit_is_proved(content):
            return False, ""
    else:
        if has_reuse_audit(content):
            # AND IT MUST ANSWER THE FILE THIS GUARD JUST FOUND. Any-audit-passes was the hole,
            # measured 2026-09-01 on a test that duplicated an existing test's assertion: the
            # collision check surfaced the sibling as its FIRST hit, the new file carried a fluent
            # audit naming a decorator and a classifier instead, and the Write went through. An
            # audit answering a question nobody asked is the SoT-fork escape wearing a smaller
            # hat — something you TYPE, passing a check about something you DID.
            if reuse_audit_addresses(content, strong):
                return False, ""
        elif recent_investigate(window):
            # Kept deliberately. For a plain name collision a real search IS honest evidence — the
            # comment above spells out why that differs from a SoT fork — and no measurement in
            # hand argues against it. The hole being closed is narrower: an audit that is present
            # but points elsewhere.
            return False, ""

    lines = [
        "BLOCKED — reinvent-the-wheel / DRY violation without a reuse investigation.",
        "",
        f"New file: {basename}",
        "",
        "You are creating a NEW file that looks like a parallel copy of existing code,",
        "without evidence you searched the codebase (Phase 0) or documented why reuse fails.",
        "",
    ]
    if strong:
        lines.append(f"Name collisions (token score ≥ {min_score}):")
        for score, rel in strong[:8]:
            lines.append(f"  [{score}] {rel}")
        lines.append("")
    if sot_hit:
        lines.append(
            f"SoT fork smell matched rule `{sot_hit}` — extend the allowlisted harness "
            "(or hunt_loop_runner / run_edge_capital_x_exit_grid), do not clone it."
        )
        lines.append("")
    lines.extend(
        [
            "FIX (pick one):",
            "  1. EXTEND the existing SoT/helper (add --leaf / flag / call site) — prefer this.",
            "  2. Run a real codebase search first (rg / gortex smart_context / search_symbols),",
            "     then retry the Write within the investigate window.",
            "  3. If genuinely greenfield after search, put in the new file:",
            "       REUSE-AUDIT: considered <path.py>; not extending because <reason>.",
            "     A REUSE-AUDIT naming CODE modules must IMPORT one of them — 'considered X'",
            "     without `import X` is a claim, and claims are what this guard now refuses.",
            "     (Citing only .md is fine; docs are context, not something you could import.)",
            "",
            "Soft reuse-check.sh warns; THIS hook denies. Config: reinvent_wheel_sot.json "
            "(extend_not_clone is dynamic — add SoT entries, don't invent one-off clones).",
        ]
    )
    return True, "\n".join(lines)


def _deny(reason: str) -> None:
    print_tool_denial(reason)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    event = str(payload.get("hook_event_name") or "")
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") or {}

    # Stamp investigate evidence from search-ish tools.
    if event == "PostToolUse":
        if tool == "Bash" and is_investigate_command(str(tool_input.get("command") or "")):
            st = _load_state()
            st["last_investigate_at"] = time.time()
            _save_state(st)
        # MCP / Task explore often lands as tool names containing these substrings.
        if re.search(r"(smart_context|search_symbols|search_text|find_files|Grep|Glob)", tool, re.I):
            st = _load_state()
            st["last_investigate_at"] = time.time()
            _save_state(st)
        return 0

    if event != "PreToolUse" or tool != "Write":
        return 0

    path = str(tool_input.get("file_path") or "")
    content = str(tool_input.get("content") or "")
    try:
        block, reason = should_block_new_write(path, content)
        if not block:
            return 0
        _deny(reason)
        return 2
    except Exception:
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0)
