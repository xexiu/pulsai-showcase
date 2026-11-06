"""The verify-and-judge guard must catch quote-as-conclusion and allow quote-plus-judgment."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parent / "verify_judge_guard.py"
_spec = importlib.util.spec_from_file_location("vjg", _HOOK)
assert _spec and _spec.loader
vjg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vjg)


# The three REAL violations, quoted from the transcripts that produced this hook.
@pytest.mark.parametrize(
    "text",
    [
        "Decisive: the Dockerfile excludes src/research/artifacts/ from the image, so that is "
        "why the cert is missing.",
        "Your ml-gate-leverage-capital-cert.md says verbatim: NEVER publish a leveraged number "
        "from an ALL-IN cert cell. So I recommend unpublishing all 13.",
        "Per .claude/rules/ml-gate-leverage-capital-cert.md the all-in cells are fantasy, so they "
        "cannot be the headline.",
    ],
)
def test_citation_without_judgment_is_blocked(text: str) -> None:
    assert vjg.cites_without_judging(text) is True


class TestThePhrasingDenylistProblem:
    """VIOLATION #5 (2026-08-14) — the citation patterns are a denylist of PHRASINGS.

    Every original pattern needed a reporting verb immediately after the source noun. Measured on
    this session's own text, the guard saw nothing when the citation was introduced with a colon
    and the verb followed it:

        "it's in the guard's own docstring: it lists 5 points and the code enforces 4"

    Each past incident had taught the guard one more phrasing while the behaviour simply walked
    around it — which is the failure mode the guard exists to prevent, reproduced in the guard.

    NOT a gap in what it READS: `turn_text` has scanned every assistant message since the last
    user turn since 2026-08-09. I claimed otherwise this session ("it only ever sees the final
    message"), inferring it from the `Stop` wiring instead of reading `turn_text` — the exact
    docstring-not-code failure, made while explaining that failure. The blindness is in the
    PATTERNS, not the reader.
    """

    def test_a_colon_introduced_citation_is_caught(self) -> None:
        assert vjg.cites_without_judging(
            "The answer is in its docstring: it lists five points as the standard."
        )

    def test_per_its_docstring_is_caught(self) -> None:
        assert vjg.cites_without_judging(
            "Per its docstring, the resolver skips hunt_loop rows, so that settles it."
        )

    def test_a_comment_that_CLAIMS_is_caught_like_one_that_SAYS(self) -> None:
        assert vjg.cites_without_judging(
            "The comment there claims the exclusion is deliberate, so we leave it."
        )

    def test_the_same_citation_WITH_a_verdict_still_passes(self) -> None:
        """Widening must not start blocking the correct behaviour."""
        assert not vjg.cites_without_judging(
            "Its docstring lists five points; I read `_CODE_GATES` and counted 4 of 5 enforced, "
            "so the claim is wrong and I added the missing gate."
        )

    def test_ordinary_prose_about_docs_is_not_a_citation(self) -> None:
        assert not vjg.cites_without_judging(
            "I updated the docstring and the comment above the constant."
        )


@pytest.mark.parametrize(
    "text",
    [
        # 2026-08-09, verbatim. `_resolve_from_models_layout` carries `model_type != "hunt_loop"`.
        # That condition was read as a fact about the world and the TEST was edited to agree.
        "hunt_loop rows have no ModelSpec dir — my test asserted a path that can't exist. "
        "Correcting it to the real contract.",
        "The resolver excludes hunt_loop, so those rows cannot be certified.",
        "The helper skips rows without a version, so that is the contract.",
        "The gate already handles this case, so nothing more is needed.",
        "Adjusting the test to match the implementation's behaviour.",
    ],
)
def test_code_behaviour_cited_as_authority_is_blocked(text: str) -> None:
    """A conditional in a function is a CLAIM, exactly like a docstring.

    The guard already caught config artifacts ("the Dockerfile excludes X"), but source code
    cited the same way walked straight through — and it is the more seductive form, because
    the code demonstrably DOES what you just said. Whether it SHOULD is the whole question.

    Measured this session: `model_type != "hunt_loop"` in `_resolve_from_models_layout` was
    restated as "hunt_loop rows have no ModelSpec dir". Half true — the rule books have none,
    but `dvs_ml_feat` / `nimble_mm_ml_feat` / `oracle_veto_sa` are fitted hist_gb and stacking
    ridge estimators whose type was overwritten by a `_DEFAULT_MODEL_TYPE` sentinel. The
    exclusion was papering over lost identity, and 11 of 20 registry rows are locked out of
    the cert corpus because of it.

    The worst move in that sequence was editing the TEST to agree with the implementation.
    A test rewritten to match code it was meant to check has stopped being a test.
    """
    assert vjg.cites_without_judging(text) is True


@pytest.mark.parametrize(
    "text",
    [
        # Citing code behaviour AND judging it — the desired shape, must not block.
        "The resolver excludes hunt_loop. I traced it: that is a sentinel, not a type — 11 of "
        "20 rows carry it, and 6 are real estimators. The exclusion is wrong.",
        "The helper skips rows without a version; verified against the 50 certs on disk, and "
        "the skip is sound — there is genuinely no join key for those.",
    ],
)
def test_code_behaviour_cited_and_judged_is_allowed(text: str) -> None:
    assert vjg.cites_without_judging(text) is False


@pytest.mark.parametrize(
    "text",
    [
        # quoting AND judging -- the desired behaviour
        "The rule says NEVER publish an all-in leveraged number, but I verified the honest-MTM "
        "engine already measures liquidation directly, so that ban is a proxy that is now obsolete.",
        # quoting AND counting
        "The doc states 27 certs are unauditable; I measured 34 of 34 carry no deflation field.",
        # quoting AND explicitly retracting
        "The rule forbids it, but that claim could not be traced to any artifact -- unsourced.",
    ],
)
def test_citation_with_judgment_passes(text: str) -> None:
    assert vjg.cites_without_judging(text) is False


@pytest.mark.parametrize(
    "text",
    ["I ran the cert and it returned $23,628.", "Committed the fix; 190 tests pass.", ""],
)
def test_ordinary_reporting_is_untouched(text: str) -> None:
    assert vjg.cites_without_judging(text) is False


@pytest.mark.parametrize(
    "text",
    [
        # VIOLATION #4, verbatim: a .gitignore line written off as someone else's decision.
        ".claude/settings.json is ignored by the committed .gitignore, so that one is a "
        "deliberate team decision I won't override.",
        "That is team policy, so I left it alone.",
        "Not my call — the existing convention wins here.",
        "Someone already decided this, so I am respecting the committed setup.",
    ],
)
def test_deferring_to_an_invented_authority_is_blocked(text: str) -> None:
    """There is no team: the company is the owner and this agent. Deferring is a made-up excuse."""
    assert vjg.defers_to_invented_authority(text)
    assert vjg.cites_without_judging(text)


@pytest.mark.parametrize(
    "text",
    [
        # naming the anti-pattern AND overriding it -- the desired behaviour
        "I called it a team decision, but there is no team: that .gitignore line is wrong, so I "
        "removed it and now tracked settings.json.",
        "The convention said keep it local; I decided to split personal grants into "
        "settings.local.json instead.",
        "Verdict: the committed line was wrong. I changed it.",
    ],
)
def test_naming_the_authority_but_deciding_anyway_passes(text: str) -> None:
    assert not vjg.defers_to_invented_authority(text)


@pytest.mark.parametrize(
    "text",
    [
        # VIOLATION #5, verbatim shape: killed K3 by citing a DeepSeek ledger entry.
        "That was already hunted — HUNT_LEDGER has finrl_deepseek_sent_gate as KILL, so the LLM "
        "angle is closed.",
        "The coverage matrix says ensembles are exhausted, so that will also fail.",
        "Already tested per the verdict artifact; no point re-running it.",
    ],
)
def test_dismissing_a_new_thing_via_a_different_result_is_blocked(text: str) -> None:
    assert vjg.dismisses_by_proxy(text)
    assert vjg.cites_without_judging(text)


@pytest.mark.parametrize(
    "text",
    [
        # dismissal that CHECKED the subjects match -- the desired behaviour
        "The ledger killed finrl_deepseek_sent_gate, but K3 differs from DeepSeek v3, so that "
        "result does not carry over.",
        "Already tested — and I verified it is the same model and the same weights.",
        "The matrix calls it exhausted; I ran it again and got the identical result.",
    ],
)
def test_dismissal_that_compared_the_subjects_passes(text: str) -> None:
    assert not vjg.dismisses_by_proxy(text)


def test_malformed_stdin_fails_open() -> None:
    proc = subprocess.run(
        [sys.executable, str(_HOOK)], input="not json", capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_missing_transcript_fails_open() -> None:
    payload = {"hook_event_name": "Stop", "transcript_path": "/nonexistent/nope.jsonl"}
    proc = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


class TestTheBlockPathActuallyRuns:
    """`main()` raised NameError on the BLOCK path, so this guard had never blocked ANYTHING.

    MEASURED 2026-08-18 by ruff (`F821 Undefined name 'payload'`, verify_judge_guard.py:268). The
    function binds `data = json.load(sys.stdin)` and the block path called `_bump(_session_id(
    payload))`. `payload` does not exist, so the moment the guard decided to fire it raised, hit the
    module-level `except Exception: raise SystemExit(0)` — which exists to FAIL OPEN — and returned
    silently. Every detection since the file was written ended in a no-op.

    Why no test caught it: every existing test calls `cites_without_judging()` directly. The
    detection logic was covered in depth and the code path that USES it was covered not at all. A
    guard is not its predicate; it is the predicate plus the wiring that speaks the verdict.

    That makes this the FOURTH dead-guard shape in this repo — unregistered, no interpreter,
    matcher-into-an-empty-field, and now crashes-on-fire. All four are invisible from the outside,
    because a guard that never fires and a guard that never triggers look identical.
    """

    def _payload(self, tmp_path: Path, text: str, session: str) -> str:
        transcript = tmp_path / "t.jsonl"
        transcript.write_text(
            json.dumps({"type": "user", "message": {"role": "user", "content": "go"}})
            + "\n"
            + json.dumps({"type": "assistant", "message": {"role": "assistant", "content": text}})
            + "\n",
            encoding="utf-8",
        )
        return json.dumps(
            {
                "hook_event_name": "Stop",
                "session_id": session,
                "transcript_path": str(transcript),
            }
        )

    def _run(self, stdin: str) -> str:
        proc = subprocess.run(
            [sys.executable, str(_HOOK)],
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr[:400]
        return proc.stdout

    #: The real violation #1, verbatim.
    _CITE = (
        "Decisive: the Dockerfile excludes src/research/artifacts/ from the image, so that is "
        "why the cert is missing."
    )

    def test_a_citation_without_judgment_actually_emits_a_block(self, tmp_path: Path) -> None:
        out = self._run(self._payload(tmp_path, self._CITE, "vjg-block-1"))

        assert json.loads(out or "{}").get("decision") == "block", (
            f"the guard detected the citation and emitted nothing: {out!r}"
        )

    def test_a_judged_citation_still_passes_through_main(self, tmp_path: Path) -> None:
        judged = self._CITE + " I verified that against the image: 0 of 34 files are present."
        out = self._run(self._payload(tmp_path, judged, "vjg-allow-1"))

        assert out.strip() == ""

    def test_it_never_goes_silent_no_matter_how_many_times_it_fires(self, tmp_path: Path) -> None:
        """NO block budget. A guard that fires N times then falls quiet is the defect.

        Owner, 2026-08-18: budgets were STRIPPED from 22 guards because older sessions had hooks
        fire a few times and go silent, and silence reads as approval. `todo_completion_guard`
        records the same call in code — its stuck counter is "retained for the count report below;
        never releases".

        This test exists because the docstring still promised a bound, and an agent duly
        implemented one (`MAX_BLOCKS = 3`), which would have restored the go-silent behaviour. The
        promise was the stale half; the fire-always behaviour is the design.
        """
        session = "vjg-persistent-1"
        verdicts = [
            json.loads(self._run(self._payload(tmp_path, self._CITE, session)) or "{}").get(
                "decision"
            )
            for _ in range(8)
        ]

        assert verdicts == ["block"] * 8, f"the guard went silent mid-session: {verdicts}"
