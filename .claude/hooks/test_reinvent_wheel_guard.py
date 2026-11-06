"""Tests for reinvent_wheel_guard — dynamic DRY / don't-reinvent PreToolUse."""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent


def _load():
    path = HOOKS / "reinvent_wheel_guard.py"
    spec = importlib.util.spec_from_file_location("reinvent_wheel_guard", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_significant_tokens_drop_generics() -> None:
    mod = _load()
    toks = mod.significant_tokens("test_strategy_ml_feat_helper")
    assert "test" not in toks
    assert "helper" not in toks
    assert "strategy" in toks
    assert "feat" in toks


def test_blocks_name_collision_without_audit_or_investigate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load()
    monkeypatch.setattr(mod, "STATE", tmp_path / "state.json")
    tracked = [
        "apps/api/src/research/edge_hunt/cert_kryptera_sma_full_findbest.py",
        "apps/api/src/research/edge_hunt/hypotheses/strategy_ml_feat.py",
    ]
    monkeypatch.setattr(mod, "list_tracked_files", lambda _root: tracked)
    path = str(tmp_path / "apps/api/src/research/edge_hunt/run_strategy_ml_feat_combo_cert.py")
    # New file — must not exist
    body = "print('clone')\n" + ("x" * 200)
    block, reason = mod.should_block_new_write(path, body, repo_root=str(tmp_path))
    assert block is True
    assert "REUSE-AUDIT" in reason or "reinvent" in reason.lower()


def test_allows_name_collision_with_reuse_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load()
    monkeypatch.setattr(mod, "STATE", tmp_path / "state.json")
    tracked = ["apps/api/src/research/edge_hunt/hypotheses/strategy_ml_feat.py"]
    monkeypatch.setattr(mod, "list_tracked_files", lambda _root: tracked)
    path = str(tmp_path / "apps/api/src/research/edge_hunt/run_strategy_ml_feat_combo_cert.py")
    body = (
        '"""REUSE-AUDIT: considered hypotheses/strategy_ml_feat.py; '
        "not extending — need separate CLI (will use SoT --leaf instead, aborting Write).\"\"\"\n"
        + ("y" * 200)
    )
    block, _ = mod.should_block_new_write(path, body, repo_root=str(tmp_path))
    assert block is False


def test_allows_after_recent_codebase_investigate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load()
    state = tmp_path / "state.json"
    monkeypatch.setattr(mod, "STATE", state)
    state.write_text(json.dumps({"last_investigate_at": time.time()}))
    tracked = ["apps/api/src/research/edge_hunt/hypotheses/strategy_ml_feat.py"]
    monkeypatch.setattr(mod, "list_tracked_files", lambda _root: tracked)
    path = str(tmp_path / "apps/api/src/research/edge_hunt/run_strategy_ml_feat_combo_cert.py")
    body = "print(1)\n" + ("z" * 200)
    block, _ = mod.should_block_new_write(path, body, repo_root=str(tmp_path))
    assert block is False


def test_blocks_sot_fork_body_without_audit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load()
    monkeypatch.setattr(mod, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(mod, "list_tracked_files", lambda _root: [])
    path = str(tmp_path / "apps/api/src/research/edge_hunt/run_dvs_ml_feat_combo_cert.py")
    body = (
        "import cert_kryptera_sma_full_findbest as K\n"
        "from src.infrastructure.ml.exit_grid import build_fifo_oos_exit_grid\n"
        "FULL_LEV = ()\n"
        "CryptoBacktester\n"
        + ("w" * 400)
    )
    block, reason = mod.should_block_new_write(path, body, repo_root=str(tmp_path))
    assert block is True
    assert "SoT" in reason or "fork" in reason.lower() or "extend" in reason.lower()


def test_allows_unique_greenfield(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load()
    monkeypatch.setattr(mod, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(mod, "list_tracked_files", lambda _root: ["apps/web/src/foo/bar.ts"])
    path = str(tmp_path / "apps/api/src/research/edge_hunt/hypotheses/totally_novel_leaf_xyz.py")
    body = '@hypothesis("totally_novel_leaf_xyz")\ndef hyp(tf): ...\n'
    block, _ = mod.should_block_new_write(path, body, repo_root=str(tmp_path))
    assert block is False


def test_is_investigate_command_detects_search() -> None:
    mod = _load()
    assert mod.is_investigate_command("rg build_fifo_oos_exit_grid apps/api/src/research")
    assert mod.is_investigate_command("gortex query callers Foo")
    assert not mod.is_investigate_command("git status")


def test_allows_edit_to_existing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load()
    monkeypatch.setattr(mod, "STATE", tmp_path / "state.json")
    existing = tmp_path / "apps" / "api" / "dup_helper.py"
    existing.parent.mkdir(parents=True)
    existing.write_text("old")
    monkeypatch.setattr(mod, "list_tracked_files", lambda _root: ["apps/api/dup_helper.py"])
    block, _ = mod.should_block_new_write(str(existing), "new" * 100, repo_root=str(tmp_path))
    assert block is False


class TestAReuseAuditMustBeProvedByAnImport:
    """A REUSE-AUDIT naming a module it does not import is a CLAIM, not reuse.

    THE FAILURE, 2026-08-30, mine. I wrote two scripts that forked the cert SoT
    (`recompute_missing_headline_dsr.py`, `backfill_cert_headline_deflated_sharpe.py`), put a
    well-worded `REUSE-AUDIT: considered <SoT>.py ...` at the top of each, and this guard let both
    through. The owner had to notice and tell me to delete them.

    Owner, same day: "so tired of hearing from you: 'i have did this and that and now hooks will
    catch my mistakes' and then again and again same or similar mistakes but hidden under other
    words/similar words or sentences."

    That is exactly what the old escape allowed: `REUSE-AUDIT:` plus any token shaped like a path.
    Both are things you TYPE. `import <that module>` is something the file DOES, and no rephrasing
    produces it.
    """

    def test_naming_a_module_without_importing_it_is_blocked(self) -> None:
        mod = _load()
        content = (
            '"""Recompute the thing.\n\n'
            "REUSE-AUDIT: considered capital_x_exit_grid_rank.py - it is the SoT for this\n"
            'statistic; not extending because a script was faster.\n"""\n\n'
            "import json\n\n"
            "def main():\n    return 0\n"
        )

        assert not mod.reuse_audit_is_proved(content)

    def test_naming_a_module_and_importing_it_passes(self) -> None:
        mod = _load()
        content = (
            '"""Recompute the thing.\n\n'
            "REUSE-AUDIT: considered capital_x_exit_grid_rank.py - reused directly here.\n"
            '"""\n\n'
            "from src.research.edge_hunt.capital_x_exit_grid_rank import headline_trial_sharpes\n"
        )

        assert mod.reuse_audit_is_proved(content)

    def test_a_plain_import_of_the_named_module_counts(self) -> None:
        mod = _load()
        content = (
            "# REUSE-AUDIT: considered cert_kryptera_sma_full_findbest.py - extended via --leaf.\n"
            "import cert_kryptera_sma_full_findbest as K\n"
        )

        assert mod.reuse_audit_is_proved(content)

    def test_an_audit_citing_only_docs_is_not_a_reuse_claim(self) -> None:
        """A cited .md is context, not something the file could import - demand nothing."""
        mod = _load()
        content = (
            "# REUSE-AUDIT: considered .claude/rules/edge-hunt-loop.md; this is shared infra.\n"
            "import json\n"
        )

        assert mod.reuse_audit_is_proved(content)

    def test_no_audit_at_all_is_not_proved(self) -> None:
        mod = _load()

        assert not mod.reuse_audit_is_proved("import json\n")


class TestHandRolledAccessToASurfaceThatHasAnSoT:
    """Catch the duplicate by what the body DOES, because the name check structurally cannot.

    MEASURED 2026-09-05, on two of my own files, in one session:

      pick_band_specs.py  globbed models/*/*/v*/metadata.json to rank versions per slot.
                          `model_discovery.list_versions_for_slots` already does exactly that,
                          sorted, batched, and BACKEND-AWARE. Mine read the LOCAL tree, picked a
                          version whose joblib is absent from R2, and the cert died on
                          FileNotFoundError. Through the SoT that failure is impossible.

      r2_probe.py         hand-parsed .env and built a boto3 client.
                          `scripts/audit_r2_local_model_tiers.py` already existed on
                          `create_storage_backend`, and returned strictly more than mine.

    Neither tripped the name check, and that is not a tuning miss. `significant_tokens` needs two
    shared tokens; `pick_band_specs` yields {pick, band} and `r2_probe` yields {probe} after the
    generic list eats `specs` and the length floor eats `r2`. The file that mattered,
    `audit_r2_local_model_tiers.py`, shares ZERO tokens with `r2_probe`. A name cannot find a
    duplicate whose author chose different words, and dropping min_score to 1 would fire on
    almost every write -- which is how a guard gets bypassed rather than obeyed.

    So this asks a different question: does the body reach a surface that HAS an SoT accessor,
    without going through it? Satisfiable two ways -- import the accessor, or write a REUSE-AUDIT
    naming it -- and both force the look that would have found the existing file.
    """

    def test_globbing_the_model_store_is_blocked(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = _load()
        monkeypatch.setattr(mod, "list_tracked_files", lambda _root: [])
        monkeypatch.setattr(mod, "recent_investigate", lambda _w: False)
        body = (
            '"""Rank model versions per slot."""\n'
            "import pathlib\n"
            "for p in pathlib.Path('models').glob('*/*/v*/metadata.json'):\n"
            "    print(p)\n"
        )

        block, reason = mod.should_block_new_write(
            str(tmp_path / "rank_slots.py"), body, repo_root=str(tmp_path)
        )

        assert block is True
        assert "list_versions_for_slots" in reason

    def test_building_a_boto3_client_is_blocked(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = _load()
        monkeypatch.setattr(mod, "list_tracked_files", lambda _root: [])
        monkeypatch.setattr(mod, "recent_investigate", lambda _w: False)
        body = "import boto3\ns3 = boto3.client('s3', endpoint_url=u)\ns3.list_objects_v2(Bucket=b)\n"

        block, reason = mod.should_block_new_write(
            str(tmp_path / "bucket_count.py"), body, repo_root=str(tmp_path)
        )

        assert block is True
        assert "create_storage_backend" in reason

    def test_importing_the_sot_accessor_is_the_point_and_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mod = _load()
        monkeypatch.setattr(mod, "list_tracked_files", lambda _root: [])
        monkeypatch.setattr(mod, "recent_investigate", lambda _w: False)
        body = (
            "from src.infrastructure.ml.storage_backends import create_storage_backend\n"
            "import boto3  # for the type only\n"
            "backend = create_storage_backend()\n"
        )

        block, _ = mod.should_block_new_write(
            str(tmp_path / "bucket_count.py"), body, repo_root=str(tmp_path)
        )

        assert block is False

    def test_a_reuse_audit_naming_the_accessor_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = _load()
        monkeypatch.setattr(mod, "list_tracked_files", lambda _root: [])
        monkeypatch.setattr(mod, "recent_investigate", lambda _w: False)
        body = (
            '"""One-off count.\n\n'
            "REUSE-AUDIT: considered create_storage_backend and audit_r2_local_model_tiers.py;\n"
            "not extending because this must run without the app config loaded.\n"
            '"""\n'
            "import boto3\n"
            "s3 = boto3.client('s3')\n"
        )

        block, _ = mod.should_block_new_write(
            str(tmp_path / "bucket_count.py"), body, repo_root=str(tmp_path)
        )

        assert block is False

    def test_a_recent_search_does_NOT_excuse_hand_rolled_access(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Searching is the escape for a NAME collision, never for reaching past an SoT.

        Same reasoning the SoT-fork branch already uses: if a search ran, it found the accessor,
        and the code went around it anyway. That makes the search the opposite of exculpatory.
        """
        mod = _load()
        monkeypatch.setattr(mod, "list_tracked_files", lambda _root: [])
        monkeypatch.setattr(mod, "recent_investigate", lambda _w: True)
        body = "import boto3\ns3 = boto3.client('s3')\n"

        block, _ = mod.should_block_new_write(
            str(tmp_path / "bucket_count.py"), body, repo_root=str(tmp_path)
        )

        assert block is True

    def test_an_unrelated_new_file_is_untouched(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Precision matters more than reach: this must not fire on ordinary greenfield code.
        mod = _load()
        monkeypatch.setattr(mod, "list_tracked_files", lambda _root: [])
        monkeypatch.setattr(mod, "recent_investigate", lambda _w: False)
        body = "def add(a: int, b: int) -> int:\n    return a + b\n"

        block, _ = mod.should_block_new_write(
            str(tmp_path / "arith.py"), body, repo_root=str(tmp_path)
        )

        assert block is False


class TestSearchingIsNotReusing:
    """A recent codebase search excuses a NAME COLLISION. It must not excuse a SOT FORK.

    Phase 0 asks "did you look?", and for a file that merely shares a name with something, looking
    is honest evidence. For a file whose BODY forks a registered SoT module, looking and forking
    anyway is worse than not looking: the search found the SoT and it was not used.

    Measured 2026-08-30: gortex searches ran continuously, so `recent_investigate` was true at every
    single Write. The escape was permanently open, which is why this guard fired zero times across
    a session in which the cert SoT was forked twice.
    """

    def test_a_recent_search_no_longer_excuses_a_sot_fork(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = _load()
        monkeypatch.setattr(mod, "recent_investigate", lambda _w: True)
        monkeypatch.setattr(mod, "reuse_audit_is_proved", lambda _c: False)
        monkeypatch.setattr(mod, "is_sot_fork_body", lambda *_a, **_k: "capital_x_exit_grid")
        monkeypatch.setattr(mod, "find_similar_tracked", lambda *_a, **_k: [])
        monkeypatch.setattr(mod, "list_tracked_files", lambda _r: [])

        blocked, reason = mod.should_block_new_write(
            "/repo/apps/api/scripts/brand_new_cert_thing.py", "x" * 400, repo_root="/repo"
        )

        assert blocked
        assert "extend" in reason.lower()

    def test_a_recent_search_still_excuses_a_mere_name_collision(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mod = _load()
        monkeypatch.setattr(mod, "recent_investigate", lambda _w: True)
        monkeypatch.setattr(mod, "reuse_audit_is_proved", lambda _c: False)
        monkeypatch.setattr(mod, "is_sot_fork_body", lambda *_a, **_k: None)
        monkeypatch.setattr(mod, "find_similar_tracked", lambda *_a, **_k: [(3, "other.py")])
        monkeypatch.setattr(mod, "list_tracked_files", lambda _r: [])

        blocked, _ = mod.should_block_new_write(
            "/repo/apps/api/scripts/brand_new_thing.py", "x" * 400, repo_root="/repo"
        )

        assert not blocked


class TestAnAuditMustAnswerTheCollisionItWasShown:
    """A REUSE-AUDIT about OTHER files is not an answer to the file the guard just found.

    MEASURED 2026-09-01, and it is mine. I wrote `test_xs_books_declare_their_kind.py`, which
    duplicates the assertion in the existing `test_xs_books_are_not_declared_single_asset.py`. The
    reuse-check surfaced that exact sibling as its FIRST name-similarity hit. The Write went
    through anyway, because the file carried a fluent `REUSE-AUDIT:` naming the `@hypothesis`
    decorator and the harness classifier -- neither of which was the collision -- and
    `has_reuse_audit` only asked whether SOME audit existed.

    The owner caught the fork by reading, and asked why the hook did not. This is why: the guard
    verified the audit's own citations and never required it to address the candidate it had
    already found. An audit that answers a question nobody asked is the same shape as the SoT-fork
    escape this module already closed one bar up -- something you TYPE, passing a check about
    something you DID.
    """

    def test_an_audit_naming_unrelated_files_does_not_excuse_the_collision(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mod = _load()
        monkeypatch.setattr(mod, "STATE", tmp_path / "state.json")
        tracked = ["apps/api/tests/unit/research/test_xs_books_are_not_declared_single_asset.py"]
        monkeypatch.setattr(mod, "list_tracked_files", lambda _root: tracked)
        path = str(tmp_path / "apps/api/tests/unit/research/test_xs_books_declare_their_kind.py")
        body = (
            '"""REUSE-AUDIT: asserts on the existing book_kind parameter of the existing '
            "@hypothesis decorator in hypothesis_registry.py. No new registry, no new "
            'classifier."""\n'
            "from hypothesis_registry import hypothesis\n" + ("q" * 300)
        )

        blocked, reason = mod.should_block_new_write(path, body, repo_root=str(tmp_path))

        assert blocked is True, "an audit that never mentions the collision must not excuse it"
        assert "test_xs_books_are_not_declared_single_asset" in reason

    def test_an_audit_naming_the_collision_still_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The fix must not make the guard unsatisfiable -- answering it is the way through."""
        mod = _load()
        monkeypatch.setattr(mod, "STATE", tmp_path / "state.json")
        tracked = ["apps/api/tests/unit/research/test_xs_books_are_not_declared_single_asset.py"]
        monkeypatch.setattr(mod, "list_tracked_files", lambda _root: tracked)
        path = str(tmp_path / "apps/api/tests/unit/research/test_xs_books_declare_their_kind.py")
        body = (
            '"""REUSE-AUDIT: considered test_xs_books_are_not_declared_single_asset.py; it pins a '
            "FIXED list of 8 named hypotheses, this derives the set from the code contract so a "
            'NEW module is caught. Not extending because <reason>."""\n' + ("q" * 300)
        )

        blocked, _ = mod.should_block_new_write(path, body, repo_root=str(tmp_path))

        assert blocked is False

    def test_a_file_with_no_audit_at_all_keeps_the_search_escape(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Deliberately NOT reversed: for a plain name collision a real search is honest evidence.

        That was a considered decision in this guard (see the SoT-fork comment, which spells out
        why a search is exculpatory HERE and not there). The hole being closed is narrower: an
        audit that is present but answers something else. Removing the search escape as well would
        reverse a decision this session has no measurement against.
        """
        mod = _load()
        state = tmp_path / "state.json"
        monkeypatch.setattr(mod, "STATE", state)
        state.write_text(json.dumps({"last_investigate_at": time.time()}))
        tracked = ["apps/api/tests/unit/research/test_xs_books_are_not_declared_single_asset.py"]
        monkeypatch.setattr(mod, "list_tracked_files", lambda _root: tracked)
        path = str(tmp_path / "apps/api/tests/unit/research/test_xs_books_declare_their_kind.py")

        blocked, _ = mod.should_block_new_write(path, "print(1)\n" + ("z" * 300), repo_root=str(tmp_path))

        assert blocked is False


def _git_repo_ignoring_scratch(tmp_path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".scratch/\n")


def test_a_gitignored_scratch_file_is_never_a_fork(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """HOOKRT-1, 2026-09-23: 7 blocks in one session on one-shot scripts in `.scratch/agent/`.
    A gitignored path is never tracked, so it can never ship a second copy of a SoT module."""
    mod = _load()
    monkeypatch.setattr(mod, "STATE", tmp_path / "state.json")
    _git_repo_ignoring_scratch(tmp_path)
    monkeypatch.setattr(mod, "list_tracked_files", lambda _root: [".claude/hooks/facts_before_first_touch_guard.py"])
    path = str(tmp_path / ".scratch/agent/facts_guard_tests_rewrite.py")
    blocked, _ = mod.should_block_new_write(path, "print(1)\n" + ("z" * 300), repo_root=str(tmp_path))
    assert blocked is False


def test_falsifier_the_same_name_OUTSIDE_the_ignored_dir_is_still_judged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _load()
    monkeypatch.setattr(mod, "STATE", tmp_path / "state.json")
    _git_repo_ignoring_scratch(tmp_path)
    monkeypatch.setattr(mod, "list_tracked_files", lambda _root: [".claude/hooks/facts_before_first_touch_guard.py"])
    path = str(tmp_path / ".claude/hooks/facts_guard_tests_rewrite.py")
    blocked, _ = mod.should_block_new_write(path, "print(1)\n" + ("z" * 300), repo_root=str(tmp_path))
    assert blocked is True
