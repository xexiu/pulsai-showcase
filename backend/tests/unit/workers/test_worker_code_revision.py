"""The worker's boot-time code identity must be resolved once, not on every task or poll.

IMPORTERS / CALLERS: pytest only. Exercises src.workers.worker_code_revision.
AFFECTED API: none directly -- consumed by task_heartbeat.heartbeat_meta (see
test_task_heartbeat_code_revision.py) and by
src.api.admin.research_loop_admin_routes.research_loop_celery_task_status (see
test_research_loop_poll_code_revision.py).

WHY THIS EXISTS. MEASURED three times in one session (2026-09-21, STALEWORKER-1): a training
worker kept running code from its boot commit while API-visible commits landed 5-20 minutes
later -- `unknown hypothesis tv_harvest_strategies`, `unexpected keyword argument window_start`,
a heartbeat fix that was not live. Nothing told an operator the WORKER's code and the API's code
had diverged; this module is the one place that answer is computed.
"""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from src.workers import worker_code_revision as wcr


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """`boot_code_revision` is `lru_cache`d for the process lifetime in production -- exactly the
    behaviour under test -- so every test must start from a cold cache rather than leak into the
    next one."""
    wcr.boot_code_revision.cache_clear()
    yield
    wcr.boot_code_revision.cache_clear()


class TestBootCodeRevisionPrefersTheBakedInEnvVar:
    def test_uses_settings_app_build_sha_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.infrastructure.config.settings import settings

        monkeypatch.setattr(settings, "app_build_sha", "abc123def456")

        def _boom(*_a: Any, **_k: Any) -> Any:
            raise AssertionError("git must not be shelled out to when the env var is set")

        monkeypatch.setattr(wcr.subprocess, "run", _boom)

        assert wcr.boot_code_revision() == "abc123def456"

    def test_falls_back_to_git_when_the_env_var_is_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.infrastructure.config.settings import settings

        monkeypatch.setattr(settings, "app_build_sha", "")
        monkeypatch.setattr(
            wcr.subprocess,
            "run",
            lambda *_a, **_k: subprocess.CompletedProcess(args=[], returncode=0, stdout="deadbeef00\n", stderr=""),
        )

        assert wcr.boot_code_revision() == "deadbeef00"


class TestBootCodeRevisionFailsOpen:
    def test_returns_none_when_git_is_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.infrastructure.config.settings import settings

        monkeypatch.setattr(settings, "app_build_sha", "")

        def _missing(*_a: Any, **_k: Any) -> Any:
            raise FileNotFoundError("git not found")

        monkeypatch.setattr(wcr.subprocess, "run", _missing)

        assert wcr.boot_code_revision() is None

    def test_returns_none_on_a_non_git_directory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A container built without `.git` -- a real deploy shape, not a hypothetical."""
        from src.infrastructure.config.settings import settings

        monkeypatch.setattr(settings, "app_build_sha", "")
        monkeypatch.setattr(
            wcr.subprocess,
            "run",
            lambda *_a, **_k: subprocess.CompletedProcess(args=[], returncode=128, stdout="", stderr="fatal: not a git repository"),
        )

        assert wcr.boot_code_revision() is None

    def test_returns_none_on_timeout_rather_than_hanging_a_boot(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.infrastructure.config.settings import settings

        monkeypatch.setattr(settings, "app_build_sha", "")

        def _hangs(*_a: Any, **_k: Any) -> Any:
            raise subprocess.TimeoutExpired(cmd="git", timeout=wcr.GIT_REV_PARSE_TIMEOUT_SECONDS)

        monkeypatch.setattr(wcr.subprocess, "run", _hangs)

        assert wcr.boot_code_revision() is None


class TestBootCodeRevisionIsComputedOnce:
    def test_a_second_call_returns_the_cached_value_without_shelling_out_again(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from src.infrastructure.config.settings import settings

        monkeypatch.setattr(settings, "app_build_sha", "")
        calls = {"n": 0}

        def _count(*_a: Any, **_k: Any) -> Any:
            calls["n"] += 1
            return subprocess.CompletedProcess(args=[], returncode=0, stdout=f"sha-{calls['n']}\n", stderr="")

        monkeypatch.setattr(wcr.subprocess, "run", _count)

        first = wcr.boot_code_revision()
        second = wcr.boot_code_revision()

        assert calls["n"] == 1, "the git subprocess ran more than once for one process"
        assert first == second == "sha-1"


class TestCodeRevisionStaleIsThreeValued:
    def test_matching_revisions_are_not_stale(self) -> None:
        assert wcr.code_revision_stale("abc123", "abc123") is False

    def test_differing_revisions_are_stale(self) -> None:
        assert wcr.code_revision_stale("abc123", "def456") is True

    def test_either_side_unknown_is_unknown_not_false_or_true(self) -> None:
        assert wcr.code_revision_stale(None, "def456") is None
        assert wcr.code_revision_stale("abc123", None) is None
        assert wcr.code_revision_stale(None, None) is None
