"""outside_repo_python_guard: a .py authored OUTSIDE the repo is refused (OUTSIDE-REPO-PY, owner 2026-10-20).

IMPORTERS/CALLERS: pytest only. AFFECTED API: none. DATA SCHEMAS: the PreToolUse payload (tool_name, tool_input, cwd).

THE CASE: this session wrote parity-check scripts into /tmp and the session scratchpad; none of them met a test run,
a linter, a type check, the reuse / one-definition / clone guards or a review, and the owner caught it ("now your
making script inside tmp folder?? ... to bypass hooks?"). gortex_first_guard refuses Bash writes INTO tracked source
only, so every shape below passed. The refused shapes are the real ones; the allowed ones are what must stay free --
writing code where it belongs, prose and data anywhere, a `git show` copy of tracked code fed to a checker.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

import outside_repo_python_guard as guard

_GUARD = Path(__file__).resolve().parent / "outside_repo_python_guard.py"
_REPO = Path(__file__).resolve().parents[2]
_SCRATCH_PY = "/private/tmp/claude-501/session/scratchpad/parity_check.py"


class TestAuthoringPythonOutsideTheRepoIsRefused:
    @pytest.mark.parametrize(
        "payload",
        [
            {"tool_name": "Write", "tool_input": {"file_path": _SCRATCH_PY, "content": "print(1)\n"}},
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/probe.py", "content": "x = 1\n"}},
            {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/probe.py", "old_string": "a", "new_string": "b"}},
            {"tool_name": "mcp__gortex__write_file", "tool_input": {"path": "/tmp/probe.pyi", "content": ""}},
            {
                "tool_name": "mcp__gortex__batch_edit",
                "tool_input": {"edits": [{"op": "edit_file", "path": "/tmp/p.py"}]},
            },
            {"tool_name": "Bash", "tool_input": {"command": "cat > /tmp/probe.py <<'EOF'\nprint(1)\nEOF"}},
            {"tool_name": "Bash", "tool_input": {"command": "echo 'print(1)' >> /tmp/probe.py"}},
            {"tool_name": "Bash", "tool_input": {"command": "printf 'x = 1' | tee /tmp/probe.py"}},
        ],
    )
    def test_it_is_refused(self, payload: dict[str, object]) -> None:
        assert guard.violation(payload, repo=_REPO) is not None, payload


_SCRIPTS_SAME_WINDOW = (
    "cd /Users/x/pulsai/apps/api && nice -n 19 .venv/bin/python - <<'EOF' > /tmp/log 2>&1; tail -60 /tmp/log\n"
    "from src.research.engine.replay.live_dollars import venue_walk\n"
    "pct = b.net_return * b.legs * margin * LEVERAGE\n"
    "EOF"
)


_INTERPRETERS = ("python", "python3", "python3.14", ".venv/bin/python", "/opt/homebrew/bin/python3", "ipython", "pypy3")
_WRAPPERS = (
    "{}",
    "nice -n 19 {}",
    "timeout 60 {}",
    "uv run {}",
    "poetry run {}",
    "env A=1 {}",
    "PYTHONPATH=. {}",
    "nohup {}",
    "./scripts/run-with-nohup.sh lbl -- {}",
    "cd apps/api && {}",
)
#: every way a line of Python reaches this repo's code; `research.` and `domain.` are packages under apps/api/src
_REACHES = (
    "from src.research.x import y",
    "import src.research.x",
    "from research.engine import y",
    "from domain.services import z",
    "from apps.api.src.lib import q",
    "import importlib; m = importlib.import_module(name)",
    "__import__(name)",
    "import sys; sys.path.insert(0, lab); import lab",
    "import runpy; runpy.run_module(name)",
)
_INLINE_FORMS = (
    '{py} -c "{code}"',
    '{py} -Ic "{code}"',
    '{py} -I -c "{code}"',
    "{py} - <<'EOF'\n{code}\nEOF",
    "{py} -I - <<'EOF'\n{code}\nEOF",
    "{py} <<EOF\n{code}\nEOF",
    'echo "{code}" | {py}',
    'echo "{code}" | {py} -',
    '{py} - <<\'EOF\' > /tmp/out.log 2>&1; tail -60 /tmp/out.log\n{code}\nEOF',
    'x=$({py} -c "{code}")',
)


def _bash(command: str, **extra: object) -> dict[str, object]:
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(_REPO), **extra}


class TestInlineCodeReachingTheRepoIsRefusedHoweverItIsSpelled:
    """2026-10-30: the 'every script' money tables were an inline heredoc with a hand-written % formula -- no file, so this
    guard never looked -- shown beside the wallet grade as if one measure. Owner: 'HOOK and BLOCK and ENFORCE', then, on a
    first fix that named that one command: 'only for your use case, not for future cases, other cases, similar cases'.
    So this is the CLASS: every interpreter x wrapper x inline form x way of reaching the repo."""

    def test_every_spelling_is_refused(self) -> None:
        missed, tried = [], 0
        for py, wrap, form, code in itertools.product(_INTERPRETERS, _WRAPPERS, _INLINE_FORMS, _REACHES):
            command = wrap.format(form.format(py=py, code=code))
            tried += 1
            if guard.violation(_bash(command), repo=_REPO) is None:
                missed.append(command)
        assert tried > 6_000  # a matrix that shrank to nothing would pass
        assert not missed, f"{len(missed)} of {tried} slipped through, first: {missed[:3]}"

    @pytest.mark.parametrize(
        "command",
        [
            _SCRIPTS_SAME_WINDOW,
            "bash -c \"python - <<'EOF'\nfrom src.x import y\nEOF\"",
            "sh -c 'python3 -c \"from src.x import y\"'",
            "zsh -c 'python -c \"import src.x\"'",
            "eval \"python -c 'from src.x import y'\"",
            "bash <<'EOF'\npython -c 'from src.x import y'\nEOF",
            "bash -s <<'EOF'\npython - <<'INNER'\nfrom src.x import y\nINNER\nEOF",
            "PYTHONPATH=apps/api python -c 'import lab_probe'",
        ],
    )
    def test_a_shell_around_it_hides_nothing(self, command: str) -> None:
        assert guard.violation(_bash(command), repo=_REPO) is not None, command


class TestRunningAFileTheGatesNeverSawIsRefused:
    """The suffix never mattered: a script in /tmp with no .py, or named .txt, runs exactly the same."""

    @pytest.mark.parametrize(
        "command",
        [
            "python /tmp/probe.txt",
            "python /tmp/probe",
            ".venv/bin/python -I /tmp/probe.py --flag",
            "nice -n 19 python3 .scratch/agent/probe.py",
            "python < /tmp/probe.txt",
        ],
    )
    def test_python_on_it_is_refused(self, command: str) -> None:
        assert guard.violation(_bash(command), repo=_REPO) is not None, command

    def test_a_shell_script_outside_the_repo_that_reaches_it_is_refused(self, tmp_path: Path) -> None:
        script = tmp_path / "run.sh"
        script.write_text("python -c 'from src.x import y'\n")
        assert guard.violation(_bash(f"bash {script}"), repo=_REPO) is not None
        assert guard.violation(_bash(f"source {script}"), repo=_REPO) is not None
        harmless = tmp_path / "ok.sh"
        harmless.write_text("echo hello\n")
        assert guard.violation(_bash(f"bash {harmless}"), repo=_REPO) is None

    @pytest.mark.parametrize(
        "payload",
        [
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/notes.txt", "content": "from src.research import x\n"}},
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/run", "content": "import src.lib\n"}},
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/run2", "content": "import importlib\nm = importlib.import_module(name)\n"}},
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/run3", "content": "import sys\nsys.path.insert(0, lab)\n"}},
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/nb.ipynb", "content": "{}"}},
            {"tool_name": "Edit", "tool_input": {"file_path": "/tmp/a.sh", "old_string": "a", "new_string": "from src.x import y"}},
            {"tool_name": "Bash", "tool_input": {"command": "cat > /tmp/run.sh <<'EOF'\nfrom src.x import y\nEOF"}},
        ],
    )
    def test_writing_repo_reaching_code_outside_is_refused_whatever_the_suffix(self, payload: dict[str, object]) -> None:
        assert guard.violation(payload, repo=_REPO) is not None, payload

    @pytest.mark.parametrize(
        "payload",
        [
            {"tool_name": "mcp__gortex__edit", "tool_input": {"operation": "write", "target": {"file": "/tmp/p.py"}, "content": "x = 1"}},
            {"tool_name": "mcp__gortex__edit", "tool_input": {"operation": "batch", "changes": [{"op": "edit_file", "path": "/tmp/p.py"}]}},
        ],
    )
    def test_the_gortex_edit_facade_is_judged_too(self, payload: dict[str, object]) -> None:
        """The matcher named write_file / edit_file / batch_edit; the tool in use since is mcp__gortex__edit."""
        assert guard.violation(payload, repo=_REPO) is not None, payload
        assert "mcp__gortex__edit" in guard.HOOK_MATCHER


class TestTheDoorsStayOpen:
    """The canaries: the matrix must not pass by refusing everything."""

    def test_modules_tests_tracked_scripts_and_data_reads_stay_free(self) -> None:
        blocked = []
        forms = (
            "{py} -m pytest tests/unit/research/pine -q",
            "{py} -m src.research.pine.article_ml_5m.news_arms --as-of 2026-10-29 --vol-dir W",
            "{py} apps/api/scripts/check_logs.py --since 1h",
            "{py} - <<'EOF'\nimport json\nprint(json.load(open('/tmp/a.json'))['pnl'][0])\nEOF",
            "{py} -c 'import json; print(json.dumps({{}}))'",
            "grep 'from src' notes.txt | {py} -c 'import sys; print(sys.stdin.read())'",
        )
        for py, wrap, form in itertools.product(_INTERPRETERS, _WRAPPERS, forms):
            if wrap.startswith("PYTHONPATH") and " -m " not in form and ".py " not in form:
                continue  # PYTHONPATH on inline text exists only to reach the repo: refused by design
            command = wrap.format(form.format(py=py))
            if guard.violation(_bash(command), repo=_REPO) is not None:
                blocked.append(command)
        assert not blocked, f"{len(blocked)} wrongly refused, first: {blocked[:3]}"

    @pytest.mark.parametrize(
        "payload",
        [
            _bash("git commit -q -m 'from src.research import news_arms is the door'"),
            _bash("cat <<'EOF' | wc -l\nfrom src.research import x\nEOF"),
            _bash("git commit -F - <<'EOF'\npython -c 'from src.x import y'\nEOF"),
            _bash("python3 - <<'EOF'\nimport json\nprint(json.load(open('apps/api/src/research/engine/validation/a.json')))\nEOF"),
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/notes.txt", "content": "plain prose\n"}},
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/mem.md", "content": "see apps/api/src/lib/x.py; the guard reads importlib and sys.path, an inline `from src.x import y` is refused\n"}},
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/commit.txt", "content": "fix(research): import src paths in the docs\n"}},
            {"tool_name": "Write", "tool_input": {"file_path": str(_REPO / "apps/api/src/research/x.py"), "content": "from src.lib import y\n"}},
            {"tool_name": "mcp__gortex__edit", "tool_input": {"operation": "write", "target": {"file": "pulsai/apps/api/src/x.py"}, "content": "x"}},
        ],
    )
    def test_prose_commits_and_tracked_paths_stay_free(self, payload: dict[str, object]) -> None:
        assert guard.violation(payload, repo=_REPO) is None, payload


class TestAGitIgnoredPathInsideTheRepoIsOutsideToo:
    """2026-10-21: `.scratch/agent/` sits under the repo root and git ignores it -- 243 .py there, 15 tracked files
    citing one as a measurement's source that no clone can re-run. Inside the root is not inside the gates."""

    @pytest.mark.parametrize(
        "payload",
        [
            {"tool_name": "Write", "tool_input": {"file_path": str(_REPO / ".scratch/agent/probe.py")}},
            {"tool_name": "Write", "tool_input": {"file_path": ".scratch/agent/probe.py"}, "cwd": str(_REPO)},
            {"tool_name": "mcp__gortex__write_file", "tool_input": {"path": str(_REPO / ".scratch/new_dir/probe.py")}},
            {
                "tool_name": "Bash",
                "tool_input": {"command": "cat > .scratch/agent/probe.py <<'EOF'\nx = 1\nEOF"},
                "cwd": str(_REPO),
            },
        ],
    )
    def test_it_is_refused(self, payload: dict[str, object]) -> None:
        reason = guard.violation(payload, repo=_REPO)
        assert reason is not None, payload
        assert "git ignores" in reason

    @pytest.mark.parametrize(
        "payload",
        [
            {"tool_name": "Write", "tool_input": {"file_path": str(_REPO / ".scratch/sol_v2_refit/calls.json")}},
            {
                "tool_name": "Bash",
                "tool_input": {"command": "python -m x > .scratch/sol_v2_refit/train.log"},
                "cwd": str(_REPO),
            },
        ],
    )
    def test_data_in_an_ignored_path_stays_free(self, payload: dict[str, object]) -> None:
        assert guard.violation(payload, repo=_REPO) is None, payload

    def test_canary_the_scratch_dir_is_really_ignored_here(self) -> None:
        """If .gitignore stops ignoring .scratch/, the refusals above prove nothing -- this fails first."""
        assert guard._ignored_by_git(_REPO / ".scratch/agent/probe.py")
        assert not guard._ignored_by_git(_REPO / "apps/api/src/probe.py")


class TestEverythingElseStaysFree:
    @pytest.mark.parametrize(
        "payload",
        [
            {"tool_name": "Write", "tool_input": {"file_path": str(_REPO / "apps/api/tests/unit/test_probe.py")}},
            {"tool_name": "Write", "tool_input": {"file_path": "apps/api/src/probe.py"}, "cwd": str(_REPO)},
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/commit_msg.txt", "content": "fix: x\n"}},
            {"tool_name": "Write", "tool_input": {"file_path": "/Users/x/.claude/projects/p/memory/note.md"}},
            {"tool_name": "mcp__gortex__write_file", "tool_input": {"path": "pulsai/apps/api/src/probe.py"}},
            {"tool_name": "Bash", "tool_input": {"command": "git show HEAD:apps/api/src/x.py > /tmp/head_x.py"}},
            {"tool_name": "Bash", "tool_input": {"command": "apps/api/.venv/bin/python -m pytest -q tests/unit"}},
            {"tool_name": "Bash", "tool_input": {"command": "cat > /tmp/msg.txt <<'EOF'\nsee > /tmp/y.py\nEOF"}},
            {"tool_name": "Bash", "tool_input": {"command": 'echo "x" > "$S/thing.py"'}},
            {"tool_name": "Bash", "tool_input": {"command": "ls"}},
        ],
    )
    def test_it_is_allowed(self, payload: dict[str, object]) -> None:
        assert guard.violation(payload, repo=_REPO) is None, payload


class TestTheHookContract:
    @staticmethod
    def _run(stdin: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(_GUARD)], input=stdin, capture_output=True, text=True, check=False)

    def test_a_violation_exits_2_and_names_where_the_code_belongs(self) -> None:
        proc = self._run(json.dumps({"tool_name": "Write", "tool_input": {"file_path": _SCRATCH_PY}}))

        assert proc.returncode == 2
        assert "apps/api/tests" in proc.stderr and "src/research" in proc.stderr

    def test_a_clean_write_is_silent(self) -> None:
        proc = self._run(json.dumps({"tool_name": "Write", "tool_input": {"file_path": "/tmp/notes.txt"}}))

        assert (proc.returncode, proc.stdout, proc.stderr) == (0, "", "")

    def test_garbage_fails_open(self) -> None:
        assert self._run("not json").returncode == 0
