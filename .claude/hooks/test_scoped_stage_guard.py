"""Staging must name FILES. `git add -A`, `git add .` and `git add <dir>` take other people's work.

Owner, verbatim and repeatedly: *"the commit and push make it on master branch directly please
(ONLY your files)"*.

THE VIOLATION (2026-08-15, mine). Committing a rename I ran:

    git add -A apps/api/src/research/edge_lab/ apps/api/tests/unit/research/

That swept in `vt_17_remeasure_8h_cert_dollars.py` — a NEW 151-line untracked file I did not
write — and a 2-line change to `walk_forward.py`. Nothing was lost or overwritten, and the commit
still read as mine, which is the point: the damage is silent. My OWN audit (`git show --stat`)
caught it, one commit too late.

Why the existing guards miss it: `parallel_dev_audit_guard` watches for the parallel dev's commits
arriving on master and demands they be REVIEWED. It has nothing to say about my staging command
pulling his uncommitted work into a commit of mine — the opposite direction.

The working tree in this repo is routinely dirty with another developer's files (353 at the time
of the violation), so "add the directory" is never a safe shorthand here.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HOOK = Path(__file__).resolve().parent / "scoped_stage_guard.py"
_spec = importlib.util.spec_from_file_location("ssg", _HOOK)
assert _spec and _spec.loader
ssg = importlib.util.module_from_spec(_spec)
sys.modules["ssg"] = ssg
_spec.loader.exec_module(ssg)


class TestTheCommandThatCausedThis:
    def test_the_exact_violation_is_blocked(self) -> None:
        command = "git add -A apps/api/src/research/edge_lab/ apps/api/tests/unit/research/"

        assert ssg.stages_beyond_named_files(command) is not None

    def test_the_scoped_form_of_the_same_commit_passes(self) -> None:
        """What I should have typed — and it must not be blocked, or the guard teaches evasion."""
        command = (
            "git add apps/api/src/research/edge_lab/precommit_block.py "
            "apps/api/tests/unit/research/test_precommit_block.py"
        )

        assert ssg.stages_beyond_named_files(command) is None


class TestEveryWayToStageEverything:
    def test_dash_A_is_blocked(self) -> None:
        assert ssg.stages_beyond_named_files("git add -A") is not None

    def test_dash_dash_all_is_blocked(self) -> None:
        assert ssg.stages_beyond_named_files("git add --all") is not None

    def test_dot_is_blocked(self) -> None:
        assert ssg.stages_beyond_named_files("git add .") is not None

    def test_a_bare_directory_is_blocked(self) -> None:
        assert ssg.stages_beyond_named_files("git add apps/api/") is not None

    def test_a_directory_without_a_trailing_slash_is_blocked(self) -> None:
        """`git add apps` stages a tree just as thoroughly as `apps/`."""
        assert ssg.stages_beyond_named_files("git add apps") is not None

    def test_a_glob_is_blocked(self) -> None:
        """The shell expands it, so what actually gets staged is unknown at review time."""
        assert ssg.stages_beyond_named_files("git add apps/api/*.py") is not None

    def test_commit_dash_a_is_blocked_too(self) -> None:
        """`-a` stages every tracked modification, which is the same hazard by another door."""
        assert ssg.stages_beyond_named_files('git commit -am "wip"') is not None
        assert ssg.stages_beyond_named_files('git commit -a -m "wip"') is not None


class TestAHeredocBodyIsDataNotACommand:
    """It blocked its own first commit, because the MESSAGE quoted the offending command.

    The commit was written as `git commit -F - <<'MSG' ... MSG` and cited `git add -A ...` as its
    own case study. The guard read the message body as a command line and refused to let itself be
    committed — the "a guard that blocks the correct fix teaches people to route around it" failure
    that same message argues against, reproduced by the guard while making the argument.
    """

    def test_the_commit_message_may_quote_the_command_it_forbids(self) -> None:
        command = (
            "git add a.py && git commit -q -F - <<'MSG'\n"
            "fix: staging must name files\n"
            "\n"
            "THE VIOLATION: git add -A apps/api/ swept in a file I did not write.\n"
            "\n"
            "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n"
            "MSG"
        )

        assert ssg.stages_beyond_named_files(command) is None

    def test_a_real_add_BEFORE_a_heredoc_is_still_caught(self) -> None:
        """Stripping bodies must not blind it to the line that opens them."""
        command = "git add -A && git commit -F - <<'MSG'\nharmless text\nMSG"

        assert ssg.stages_beyond_named_files(command) is not None

    def test_text_after_the_terminator_is_read_again(self) -> None:
        command = "git commit -F - <<'MSG'\nbody\nMSG\ngit add ."

        assert ssg.stages_beyond_named_files(command) is not None


class TestACommitMustDeclareItsAuthor:
    """A commit without the `Co-Authored-By: Claude` trailer is filed as the parallel dev's.

    MEASURED 2026-08-15, immediately: I committed this very guard with `git commit -m "..."`,
    dropped the trailer CLAUDE.md requires, and `parallel_dev_audit_guard` — correctly, by its own
    rule — flagged `60765cd55` as unaudited parallel-dev work and blocked the stop.

    The cost is not the one blocked stop. It is that MY commits enter the audit ledger, so the
    queue of things genuinely needing review fills with my own work and the signal for a real
    parallel-dev commit is diluted. `--amend` cannot fix it after the fact (the owner forbids
    amending on a shared master), so the only repair is not writing it that way.

    Same responsibility as the staging rule above, stated once: a commit must accurately declare
    WHAT it contains and WHO made it.
    """

    _TRAILER = "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"

    def test_a_dash_m_commit_without_the_trailer_is_blocked(self) -> None:
        assert ssg.stages_beyond_named_files('git commit -q -m "fix: a thing"') is not None

    def test_the_same_commit_with_the_trailer_passes(self) -> None:
        assert ssg.stages_beyond_named_files(f'git commit -q -m "fix: a thing\n\n{self._TRAILER}"') is None

    def test_a_heredoc_commit_carrying_the_trailer_passes(self) -> None:
        """The normal form in this repo — the body is stripped, so the trailer must still be seen."""
        command = f"git commit -q -F - <<'MSG'\nfix: a thing\n\n{self._TRAILER}\nMSG"

        assert ssg.stages_beyond_named_files(command) is None

    def test_a_heredoc_commit_WITHOUT_the_trailer_is_blocked(self) -> None:
        command = "git commit -q -F - <<'MSG'\nfix: a thing\nMSG"

        assert ssg.stages_beyond_named_files(command) is not None

    def test_commits_that_are_not_authoring_are_untouched(self) -> None:
        """`--amend`/`--no-edit` and reword flows are the owner's business, not this guard's."""
        assert ssg.stages_beyond_named_files("git commit --amend --no-edit") is None

    def test_a_message_file_carrying_the_trailer_passes(self, tmp_path: Path) -> None:
        """The `-F <path>` form, read from disk rather than from the command line."""
        message = tmp_path / "msg.txt"
        message.write_text(f"fix: a thing\n\n{self._TRAILER}\n", encoding="utf-8")

        assert ssg.stages_beyond_named_files(f"git commit -F {message}") is None

    def test_an_unreadable_message_file_says_so_instead_of_blaming_the_trailer(
        self, tmp_path: Path
    ) -> None:
        """The diagnostic must name the REAL fault, and this one cost a real debugging detour.

        `git commit -F $S/msg8.txt` was blocked with "carries no Co-Authored-By trailer" while
        the file it pointed at held the trailer on its last line. The guard tokenises raw command
        TEXT, so `$S` is never expanded and the path never resolves -- the read fails, the code
        falls back to scanning the command line, and the fallback's verdict was reported as
        though the message itself were at fault.

        Refusing to expand shell is CORRECT: a guard that evaluates arbitrary shell to decide
        whether to allow a command has given away the thing it was guarding. So the fix is the
        message, not the parsing -- say which file could not be read, and why a literal path is
        required.
        """
        missing = tmp_path / "definitely-not-here.txt"

        reason = ssg.stages_beyond_named_files(f"git commit -F {missing}")

        assert reason is not None
        assert "could not be read" in reason
        assert missing.name in reason, "the message must name the file it failed to open"
        assert "carries no" not in reason, "it must not blame the message it never read"

    def test_the_unreadable_message_names_the_shell_variable_trap(self) -> None:
        """Because that is the form this actually failed in, and the cause is invisible."""
        reason = ssg.stages_beyond_named_files("git commit -F $SCRATCH/msg8.txt")

        assert reason is not None
        assert "could not be read" in reason
        assert "literal" in reason.lower(), "the fix must be stated, not just the fault"

    def test_a_readable_file_without_the_trailer_still_blames_the_trailer(
        self, tmp_path: Path
    ) -> None:
        """The original check must survive: a file that IS read and lacks the trailer is caught."""
        message = tmp_path / "msg.txt"
        message.write_text("fix: a thing with no attribution\n", encoding="utf-8")

        reason = ssg.stages_beyond_named_files(f"git commit -F {message}")

        assert reason is not None
        assert "carries no" in reason
        assert "could not be read" not in reason


class TestItStaysOutOfTheWay:
    def test_naming_one_file_passes(self) -> None:
        assert ssg.stages_beyond_named_files("git add apps/api/src/thing.py") is None

    def test_naming_several_files_passes(self) -> None:
        assert ssg.stages_beyond_named_files("git add a/b.py c/d.ts e/f.md") is None

    def test_unstaging_is_not_staging(self) -> None:
        """`git reset` and `git restore --staged` narrow the commit; they never widen it."""
        assert ssg.stages_beyond_named_files("git reset HEAD apps/") is None

    def test_other_git_commands_are_untouched(self) -> None:
        for command in ("git status", "git show --stat HEAD", "git diff --cached", "git log -1"):
            assert ssg.stages_beyond_named_files(command) is None

    def test_a_non_git_command_is_untouched(self) -> None:
        assert ssg.stages_beyond_named_files("pytest -q") is None

    def test_add_inside_a_longer_pipeline_is_still_caught(self) -> None:
        """Agents chain commands; the hazard does not disappear behind a `&&`."""
        assert ssg.stages_beyond_named_files("cd apps/api && git add -A && git commit -m x") is not None


# ---------------------------------------------------------------------------
# THE FILE/DIRECTORY TEST WAS AN EXTENSION ALLOWLIST, AND IT BLOCKED REAL EVIDENCE.
#
# `_FILE_SUFFIXES` lists .py/.ts/.json/.md/... and `_names_a_file` is
# `any(arg.endswith(suffix) for suffix in _FILE_SUFFIXES)`. Anything outside that list is treated as
# a DIRECTORY and the stage is denied.
#
# MEASURED 2026-08-20: `.jsonl` is not on the list, so
#   git add apps/api/src/research/artifacts/vt_17_momentum/forward_tape.jsonl
# was refused as "stages a DIRECTORY" -- a single, existing, tracked FILE. `.md` in the same commit
# staged fine.
#
# That is not cosmetic. The forward TAPES are all `.jsonl`, and a forward tape is the evidence
# EDGEFOUND-1 requires (">= 40 clean forward-tape days"). An allowlist missing one extension meant
# the one artifact class the main objective depends on could never be committed at all.
#
# DERIVED, NOT ENUMERATED: the filesystem already knows. `Path(arg).is_dir()` answers it for every
# extension that exists now or later, and for a path that no longer exists (staging a DELETION) the
# answer is "not a directory", which is correct -- a deleted file is still a file.
#
# The guard's real job is untouched and re-asserted below: `git add -A`, a bare directory, and `.`
# are still refused, because those are what swept in someone else's work.
# ---------------------------------------------------------------------------


class TestFileDetectionIsFilesystemNotExtensionList:
    def test_a_jsonl_file_is_a_file(self, tmp_path: Path) -> None:
        tape = tmp_path / "forward_tape.jsonl"
        tape.write_text('{"day": 1}\n', encoding="utf-8")

        assert ssg._names_a_file(str(tape)) is True

    def test_an_extension_nobody_listed_is_still_a_file(self, tmp_path: Path) -> None:
        """The point of deriving: extensions this repo has never seen must work too."""
        for name in ("weights.safetensors", "notes.rst", "data.parquet", "Makefile"):
            path = tmp_path / name
            path.write_text("x", encoding="utf-8")
            assert ssg._names_a_file(str(path)) is True, name

    def test_a_real_directory_is_still_a_directory(self, tmp_path: Path) -> None:
        (tmp_path / "pkg").mkdir()

        assert ssg._names_a_file(str(tmp_path / "pkg")) is False

    def test_a_deleted_file_still_counts_as_a_file(self, tmp_path: Path) -> None:
        """Staging a deletion is normal; the path is gone but it was never a directory."""
        gone = tmp_path / "removed_result.jsonl"

        assert ssg._names_a_file(str(gone)) is True


class TestASymlinkIsOneIndexEntryNotADirectory:
    """`Path.is_dir()` FOLLOWS a symlink, so a link to a directory read as a directory.

    Measured 2026-09-22, registering the `quick-recap` skill. Every entry in `.claude/skills/`
    is a symlink into `.agents/skills/`, so the fix was one link:

        .claude/skills/quick-recap -> ../../.agents/skills/quick-recap

    The guard refused it as "stages a DIRECTORY -- whatever happens to be dirty in it", and its
    advice ("NAME THE FILES") could not be followed: the only thing git tracks at that path IS
    the link. `git add <symlink>` writes exactly ONE index entry, mode 120000, holding the target
    PATH as its blob. It cannot reach the target's contents, so it cannot sweep in anybody's
    dirty work -- which is this guard's entire reason to exist.

    The module already states the intent this restores, at `_names_a_file`: "only a real
    directory is refused". A symlink is not a real directory.
    """

    def test_a_symlink_to_a_directory_is_a_file_to_stage(self, tmp_path: Path) -> None:
        target = tmp_path / "skills_source"
        target.mkdir()
        (target / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        link = tmp_path / "linked_skill"
        link.symlink_to(target)

        assert link.is_dir() is True, "precondition: the naive check says directory"
        assert ssg._names_a_file(str(link)) is True

    def test_a_symlink_to_a_file_is_a_file(self, tmp_path: Path) -> None:
        target = tmp_path / "notes.md"
        target.write_text("x", encoding="utf-8")
        link = tmp_path / "notes_link.md"
        link.symlink_to(target)

        assert ssg._names_a_file(str(link)) is True

    def test_a_broken_symlink_is_a_file(self, tmp_path: Path) -> None:
        """A dangling link is still one index entry, and still not a directory to sweep."""
        link = tmp_path / "dangling"
        link.symlink_to(tmp_path / "never_existed")

        assert ssg._names_a_file(str(link)) is True

    def test_a_real_directory_is_STILL_refused(self, tmp_path: Path) -> None:
        """The canary. If this ever passes, the fix opened the door the guard exists to hold."""
        (tmp_path / "pkg").mkdir()

        assert ssg._names_a_file(str(tmp_path / "pkg")) is False

    def test_the_bulk_forms_are_STILL_refused(self) -> None:
        """Second canary: the violation that created this guard must stay blocked."""
        for command in (
            "git add -A apps/api/src/research/edge_lab/",
            "git add .",
            "git add apps",
        ):
            assert ssg.stages_beyond_named_files(command) is not None, command


class TestAVariableAssignedInTheSameCommandIsExpanded:
    """HOOKRT-1, measured 2026-09-23: `F="<22 literal file paths>" && git add -- $F` was refused as
    "stages a DIRECTORY". The value sat in the same command; expanding it is a pure function of the
    text, so the guard judges the literal paths instead of costing a rewrite."""

    def test_named_files_behind_a_variable_pass(self) -> None:
        command = 'F=".claude/hooks/a_guard.py .cursor/hooks.json" && git add -- $F'
        assert ssg.stages_beyond_named_files(command) is None

    def test_braced_spelling_passes_too(self) -> None:
        assert ssg.stages_beyond_named_files("F='x.py y.py'; git add -- ${F}") is None

    def test_the_zsh_splitting_spelling_passes_too(self) -> None:
        """zsh does not word-split a bare `$F`; `${=F}` is how this repo's shell spells it."""
        assert ssg.stages_beyond_named_files('F="x.py y.py" && git add -- ${=F}') is None

    def test_falsifier_a_directory_behind_a_variable_is_still_refused(self) -> None:
        assert ssg.stages_beyond_named_files('F="apps .claude" && git add -- $F') is not None

    def test_falsifier_an_unassigned_variable_is_still_refused_and_says_why(self) -> None:
        reason = ssg.stages_beyond_named_files("git add -- $NEVER_ASSIGNED")
        assert reason is not None and "variable" in reason


class TestARelativeMessageFileResolvesWhereTheCommandRuns:
    """HOOKRT-1, measured 2026-09-23: `cd <repo> && git commit -F .scratch/agent/msg.txt -- $F` was
    refused as "message file could not be read" -- the guard opened the relative path from the
    HOOK's cwd (.claude/hooks), not from the directory the command had just cd'd into."""

    def test_a_cd_earlier_in_the_command_is_honoured(self, tmp_path: Path) -> None:
        (tmp_path / "m").mkdir()
        (tmp_path / "m" / "msg.txt").write_text("fix: x\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n")
        command = f"cd {tmp_path} && git commit -q -F m/msg.txt -- a.py"
        assert ssg.stages_beyond_named_files(command, cwd="/") is None

    def test_the_payload_cwd_is_honoured(self, tmp_path: Path) -> None:
        (tmp_path / "msg.txt").write_text("fix: x\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n")
        assert ssg.stages_beyond_named_files("git commit -F msg.txt -- a.py", cwd=str(tmp_path)) is None

    def test_falsifier_a_file_that_truly_is_not_there_is_still_reported(self, tmp_path: Path) -> None:
        reason = ssg.stages_beyond_named_files("git commit -F nope.txt -- a.py", cwd=str(tmp_path))
        assert reason is not None and "could not be read" in reason


def test_a_relative_message_file_after_an_absolute_cd_is_read(tmp_path: Path) -> None:
    """2026-09-23: `...; cd <repo> && git commit -F .scratch/agent/msg.txt` was refused as
    'message file could not be read'. Pins that the relative path resolves from the cd target."""
    (tmp_path / "msgs").mkdir()
    (tmp_path / "msgs" / "m.txt").write_text("fix: x\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n")
    command = f"bash /x/count.sh; cd {tmp_path} && git add a.py && git commit -q -F msgs/m.txt && git log -1"

    assert ssg.stages_beyond_named_files(command, cwd="/somewhere/else") is None


class TestPathsResolveAgainstTheCommandsCwdNotTheHooks:
    """MEASURED 2026-09-24, two defects of ONE cause: `_names_a_file` resolved a relative path against
    the HOOK PROCESS's cwd, ignoring the command's own cwd (payload cwd + any `cd` segment).

    * FALSE POSITIVE: `git add .husky/pre-commit` (an extensionless FILE) was refused as a DIRECTORY
      from any cwd but the repo root -- off-disk it fell to the "no extension => directory" default.
    * FALSE NEGATIVE, the worse one: `git add .husky` (a real DIRECTORY) was ALLOWED -- off-disk the
      fallback regex read the leading dot of a dot-directory as a file extension, so a sweep of
      `.husky`, `.claude` or `.github` sailed through.
    """

    ROOT = str(Path(__file__).resolve().parents[2])

    def test_an_extensionless_file_is_a_file_when_the_payload_cwd_is_the_repo(self, monkeypatch) -> None:
        monkeypatch.chdir("/")  # the hook process's cwd must not decide anything
        assert ssg.stages_beyond_named_files("git add .husky/pre-commit", cwd=self.ROOT) is None

    def test_a_cd_segment_moves_the_resolution_base(self, monkeypatch) -> None:
        monkeypatch.chdir("/")
        command = f"cd {self.ROOT} && git add .husky/pre-commit"
        assert ssg.stages_beyond_named_files(command, cwd=f"{self.ROOT}/apps/api") is None

    def test_a_dot_directory_is_refused_on_disk(self, monkeypatch) -> None:
        monkeypatch.chdir("/")
        assert ssg.stages_beyond_named_files("git add .husky", cwd=self.ROOT) is not None

    def test_a_dot_directory_is_refused_even_off_disk(self, monkeypatch) -> None:
        """No cwd to resolve against: a leading dot is a dotfile/dot-dir name, never an extension."""
        monkeypatch.chdir("/")
        assert ssg.stages_beyond_named_files("git add .husky") is not None
        assert ssg.stages_beyond_named_files("git add apps/.claude") is not None

    def test_a_real_extension_off_disk_is_still_a_file(self, monkeypatch) -> None:
        monkeypatch.chdir("/")
        assert ssg.stages_beyond_named_files("git add apps/api/new_module.py") is None
