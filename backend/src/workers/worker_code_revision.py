"""Boot-time git commit identity, so a worker that has not restarted can be told apart from the
code the API process is currently serving.

IMPORTERS / CALLERS: ``src.workers.task_heartbeat.heartbeat_meta`` (via ``task_heartbeat``) stamps
the WORKER's boot revision into every heartbeat beat; ``src.api.admin.research_loop_admin_routes.
research_loop_celery_task_status`` calls ``boot_code_revision()`` again for the API's OWN current
revision and compares the two with ``code_revision_stale``.
AFFECTED API: ``CertRunStatusResponse`` gains three OPTIONAL fields (worker_code_revision,
api_code_revision, worker_code_stale).
DATA SCHEMAS: the worker's revision rides inside the existing heartbeat meta dict written to the
Celery result backend (``code_revision`` key); the API's own revision is computed live per request
and never persisted.

REUSE-AUDIT: considered ``settings.app_build_sha`` (``SettingsCoreMixin``) alone -- it already
resolves RAILWAY_GIT_COMMIT_SHA / GITHUB_SHA / VERCEL_GIT_COMMIT_SHA / SOURCE_VERSION /
APP_BUILD_SHA, and this module PREFERS it rather than re-deriving those env names. But on
localhost none of them are set (measured: a bare ``Settings()`` has ``app_build_sha == ""``),
which is exactly where the staleness this ticket exists to catch actually happens -- the API runs
with ``--reload`` and bounces on every change, the worker does not. So a ``git rev-parse HEAD``
fallback is required for the case that matters most. Extending ``settings_core.py`` to shell out
was considered and rejected: a subprocess call does not belong in a Pydantic settings field
resolved at import time for every process, including scripts and tests that should never shell
out just to construct ``Settings()``.

WHY A SEPARATE MODULE FROM ``task_heartbeat.py`` (the other option this ticket named). That
module's own docstring scopes it to LIVENESS -- is the process still running. This is IDENTITY --
which commit did it start with. They are read together (a poll needs both), but they are computed
differently (one is a timer thread, the other is a cached subprocess/env lookup) and consumed by
different callers: the API route needs ITS OWN revision with no Celery task object in hand at all,
only ``task_heartbeat`` needs a bound task. Folding identity into the liveness module would force
the API to import Celery's task-heartbeat threading machinery merely to ask "what commit am I on"
-- a needless coupling for a module whose docstring-declared SRP is liveness, not identity.

WHY THIS EXISTS. MEASURED three times in one session (2026-09-21, STALEWORKER-1): a training
worker kept running the code it booted with while commits landed 5-20 minutes later --
``unknown hypothesis tv_harvest_strategies``, ``unexpected keyword argument window_start``, a
heartbeat fix that was not live. Nothing told an operator the WORKER's code and the API's code had
diverged; this module is the one place that answer is computed.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

#: Bounded so a hung `git` process (a lock held by another process, an NFS-mounted `.git`) can
#: never delay a worker boot or an API request. 2s is generous for a local `rev-parse` -- it
#: touches no network -- and short enough that a caller waiting on it never notices.
GIT_REV_PARSE_TIMEOUT_SECONDS: Final[float] = 2.0

__all__ = [
    "GIT_REV_PARSE_TIMEOUT_SECONDS",
    "boot_code_revision",
    "code_revision_stale",
]


def _repo_root() -> Path:
    """apps/api/src/workers/<this file> -> workers -> src -> api -> apps -> repo root."""
    return Path(__file__).resolve().parents[4]


def _git_head_sha() -> str | None:
    """Best-effort ``git rev-parse HEAD``. Fails OPEN to None -- a container built without
    ``.git`` (a real deploy shape, not a hypothetical one) must never crash a boot or a request
    over a diagnostic value."""
    # RESOLVED to an absolute path rather than suppressing S607: the binary lives in different
    # places per environment (Homebrew vs a Docker image), so `which` answers per environment and
    # a missing `git` returns None here exactly as an unreadable repo does.
    git = shutil.which("git")
    if git is None:
        return None
    try:
        completed = subprocess.run(
            [git, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=GIT_REV_PARSE_TIMEOUT_SECONDS,
            cwd=_repo_root(),
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if completed.returncode != 0:
        return None
    sha = completed.stdout.strip()
    return sha or None


@lru_cache(maxsize=1)
def boot_code_revision() -> str | None:
    """The git commit THIS PROCESS was loaded with, resolved once and cached for its lifetime.

    Prefers ``settings.app_build_sha`` -- baked into the image at BUILD time on Railway/GitHub, so
    it is correct even in a container with no ``.git`` directory -- and falls back to a live
    ``git rev-parse HEAD`` for local dev, where none of those env vars are set. Two DIFFERENT
    processes each calling this independently (a worker at its boot, the API per admin-poll
    request) is what makes the comparison meaningful: a worker that has not restarted keeps
    returning the value it cached at import, while a ``--reload``-cycled or freshly-deployed API
    process returns the value current at ITS boot.

    ``lru_cache`` rather than a module-level constant computed at import time: the git subprocess
    still runs at most once per process (satisfying "compute it once, not per task"), but a cache
    can be cleared in tests without reloading the module, and a constant would need exactly that
    to be testable at all.
    """
    from src.infrastructure.config.settings import settings

    build_sha = (settings.app_build_sha or "").strip()
    if build_sha:
        return build_sha
    return _git_head_sha()


def code_revision_stale(worker_revision: str | None, api_revision: str | None) -> bool | None:
    """Three-valued comparison, mirroring ``task_heartbeat.HeartbeatReading.stale``.

    ``None`` when EITHER side is unknown -- collapsing an unknown revision into a match or a
    mismatch would invent a fact, the exact failure the sibling heartbeat field is documented not
    to commit.
    """
    if worker_revision is None or api_revision is None:
        return None
    return worker_revision != api_revision
