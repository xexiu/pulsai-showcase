"""Tests for the shared Bash-command classifier.

This module had NO tests, which is how a defect documented in its own docstring survived
inside it. Case #2 of that docstring reads: "a `git commit -F - <<'MSG'` heredoc whose
message DESCRIBED a bug blocked its own commit, because splitting on newlines turns each
prose line into a pseudo-command."

That was fixed for HEREDOCS (`strip_heredoc_bodies`) and left unfixed for the far commoner
shape: a multi-line `git commit -m "..."`. `SEGMENT_SPLIT` still contains a newline, so
every line of a commit BODY became its own candidate command.

MEASURED 2026-09-01: a commit whose message read "I wrote a confident message over run.sh
and run_dev_apps.sh without reading either" was DENIED by localhost_stack_alive_guard as a
stack restart. `git` is in READER_COMMANDS so the first line was correctly dropped -- but
the prose lines after it were not, and one of them named the launcher.

REUSE-AUDIT: considered .claude/hooks/_hook_evidence.py (buckets a command into evidence
KINDS for Stop hooks) and .claude/hooks/_hook_exclusions.py (path filtering). Neither
classifies invocation-vs-mention, and neither had coverage for this module.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

_MODULE = pathlib.Path(__file__).resolve().parent / "_hook_command.py"
_spec = importlib.util.spec_from_file_location("_hook_command", _MODULE)
assert _spec and _spec.loader
hook_command = importlib.util.module_from_spec(_spec)
sys.modules["_hook_command"] = hook_command
_spec.loader.exec_module(hook_command)

executable_segments = hook_command.executable_segments
command_word = hook_command.command_word
is_reader_segment = hook_command.is_reader_segment
invokes = hook_command.invokes

_RUN_SH = re.compile(r"run\.sh")


class TestAQuotedStringIsOneArgumentNotManyCommands:
    """Separators INSIDE quotes are text. Only unquoted ones separate commands."""

    def test_a_multiline_commit_message_yields_no_executable_segment(self) -> None:
        command = 'git commit -q -m "feat: x\n\nI wrote it over run.sh without\nreading it.\n"'
        assert executable_segments(command) == []

    def test_a_launcher_named_in_a_multiline_message_is_not_invoked(self) -> None:
        command = 'git commit -m "docs: why\n\n./scripts/run.sh all tears the stack down\n"'
        assert invokes(command, _RUN_SH) is False

    def test_a_semicolon_inside_quotes_does_not_split(self) -> None:
        assert executable_segments('git commit -m "fix: a; b; c"') == []

    def test_a_pipe_inside_quotes_does_not_split(self) -> None:
        assert executable_segments('echo "a | b"') == []

    def test_single_quotes_protect_too(self) -> None:
        assert executable_segments("git commit -m 'feat: x\n\n./scripts/run.sh all\n'") == []


class TestTheOneSplitterKeepsBackgroundLongCommandGuardsRules:
    """GATE-TRANSCRIPTS 3/n: background_long_command_guard held its own copy of split_segments, and the copy had drifted
    AHEAD of this home on two rules. One splitter now, with both."""

    def test_a_backslash_inside_single_quotes_is_literal_so_the_quote_still_closes(self) -> None:
        # bash: 'a\' is the two characters a and \ -- the quote closes, and the `;` separates the next command.
        assert invokes("echo 'a\\' ; ./scripts/run.sh all", _RUN_SH) is True

    def test_an_unbalanced_quote_over_splits_rather_than_swallowing_a_real_run(self) -> None:
        # A shell would reject the line; the conservative failure is a false block, never a silent miss.
        assert invokes('echo "unterminated; ./scripts/run.sh all', _RUN_SH) is True


class TestRealSeparatorsStillSplit:
    def test_the_surviving_segment_is_the_real_invocation(self) -> None:
        segments = executable_segments("git add a.py && ./scripts/run.sh all")
        assert segments and "run.sh" in segments[0]

    def test_a_newline_between_real_commands_still_splits(self) -> None:
        assert len(executable_segments("./scripts/run.sh api\npnpm app:web")) == 2

    def test_a_pipeline_keeps_the_launcher_half(self) -> None:
        # `tee` genuinely RUNS, so two executable segments is correct here; what matters
        # is that the launcher half survives to be matched.
        assert invokes("./scripts/run.sh all | tee log", _RUN_SH) is True

    def test_a_real_invocation_is_still_found(self) -> None:
        assert invokes("cd /tmp && ./scripts/run.sh web", _RUN_SH) is True


class TestReaderSegmentsAreStillDropped:
    def test_grep_of_a_launcher_is_a_read(self) -> None:
        assert executable_segments('grep -n "preflight" scripts/run.sh') == []

    def test_git_is_a_reader(self) -> None:
        assert is_reader_segment("git status --short") is True

    def test_command_word_skips_env_assignments(self) -> None:
        assert command_word("FOO=1 ./scripts/run.sh api") == "run.sh"

    def test_command_word_skips_wrapper_prefixes(self) -> None:
        assert command_word("nohup ./scripts/run.sh api") == "run.sh"


class TestHeredocBodiesStayStripped:
    def test_a_heredoc_body_is_not_a_command(self) -> None:
        # `python - <<'PY'` itself still runs, so the segment list is not empty; the point
        # is that the launcher named INSIDE the body is never treated as invoked.
        assert invokes("python - <<'PY'\n./scripts/run.sh all\nPY", _RUN_SH) is False
