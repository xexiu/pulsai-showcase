#!/usr/bin/env python3
"""Block a turn that CITES a written claim as the answer without judging it.

THE FAILURE THIS EXISTS FOR — three times, and the owner counted:

1. Quoted a Dockerfile comment ("the Dockerfile excludes src/research/artifacts/") as if it
   settled whether excluding it was CORRECT.
2. Repeated "prod's own honest_verdict says WF SR 0.42, fold_stab 2/5" — a claim that could not be
   traced to any artifact; prod's metadata has no such field.
   (4, added 2026-08-09) Read `model_type != "hunt_loop"` out of `_resolve_from_models_layout`,
   restated it as "hunt_loop rows have no ModelSpec dir", and EDITED A TEST to agree. It was half
   true: the rule books have no dir, but `dvs_ml_feat` / `nimble_mm_ml_feat` / `oracle_veto_sa` are
   fitted estimators whose type a default sentinel had overwritten — so the exclusion was hiding
   lost identity and locking 11 of 20 registry rows out of the cert corpus. Source code is the most
   seductive authority of all, because it demonstrably DOES what you just said.
3. Quoted `ml-gate-leverage-capital-cert.md` — _"NEVER ... publish a leveraged number from an ALL-IN
   cert cell"_ — as grounds to unpublish 13 production backtests. The ban was a PROXY for a defect
   the honest-MTM engine had already fixed, so the recommendation protected the wrong four and
   spared a book that liquidated users 26 times.

`.claude/rules/verify-and-judge-not-quote.md` has existed the whole time and was the ONLY rule in
the set with no hook behind it. A policy nobody enforces is a policy that gets violated three times.

## The standard

A comment, docstring, config note, rule file or `.md` tells you **what someone believed when they
wrote it**. It is a claim to be checked, never the conclusion. So:

1. VERIFY it against the running system — does the field exist, is the hook wired, is the value read?
2. JUDGE the decision — you are the lead architect. "The rule says X" is where analysis STARTS.
3. State the verdict: sound / sound-but-fragile / obsolete / wrong — and name the failure mode.

## Detection

Blocks when the final message cites a written source AS AUTHORITY and shows no sign of having
checked or judged it. Any evidence of verification (a measured count, a "verified/traced/I judge"
marker, an explicit verdict on the source) releases it — quoting a rule while ALSO judging it is
exactly the desired behaviour, not the failure.

Fails OPEN on any internal error. It does NOT self-release: there is no block budget, because a
guard that fires N times and then goes quiet is the defect (owner, 2026-08-18 — older sessions had
hooks fire a few times and fall silent, and silence reads as approval). The same conclusion is
already recorded in `todo_completion_guard`, where the stuck-counter is explicitly "retained for
the count report below; never releases". The count here is for the report only.

HISTORICAL NOTE, kept because it cost real time: this docstring used to claim the guard
"self-releases after a bounded number of blocks". It did not — `_blocks()` was never called by
`main()`. On 2026-08-18 an agent read that sentence, believed it, and IMPLEMENTED the bound to make
the code match, which would have re-introduced the exact go-silent behaviour the budgets were
stripped to remove. A stale docstring is not a harmless comment; it is a specification that gets
enforced by whoever trusts it next.
"""

from __future__ import annotations

#: Derived from the registration this guard already carries in settings.json, so
#: `register_guards --apply` can restore it if that file is ever regenerated.
HOOK_EVENT = ("PostToolUse", "Stop")
HOOK_MATCHER = "Bash|Edit|Write"

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_transcript import turn_text
from _hook_state import load_state, save_state
from _hook_evidence import had, record

STATE = Path(__file__).resolve().parent / ".verify_judge_state.json"
_CITATION = re.compile(
    r"(says verbatim"
    r"|(?:the\s+)?(?:rule|doc|docs|docstring|comment|policy|spec|README|CLAUDE\.md|AGENTS\.md)\s+"
    r"(?:says|states|requires|forbids|mandates)"
    r"|per\s+[\w./_-]+\.md"
    r"|according to (?:the )?(?:rule|doc|docstring|comment|policy)"
    r"|as (?:the )?(?:rule|doc|docstring|comment) (?:says|states)"
    r"|\bthe .{0,24}\.md\b.{0,40}\b(?:says|states|forbids|requires)\b"
    # PHRASING, not just verbs (2026-08-14). Every pattern above needs a reporting VERB right
    # after the source noun. Measured on this session's own text: *"it's in the guard's own
    # docstring: it lists 5 points"* matched NOTHING, because the citation was introduced with a
    # COLON and the verb ("lists") sat after it. Same for "per its docstring, X" and "the
    # comment there claims X".
    #
    # This is the denylist problem the guard was built to avoid — each incident teaching one more
    # phrasing while the behaviour walks around it. Widened to: a source noun within a short
    # window of ANY assertion verb, plus the colon-introduced form.
    r"|\b(?:rule|doc|docs|docstring|comment|policy|spec|readme)\b[^.\n]{0,30}?"
    r"\b(?:says|states|lists|claims|notes|records|declares|describes|documents|asserts|"
    r"requires|forbids|mandates|promises)\b"
    r"|\bper\s+(?:its|the|that)\s+(?:docstring|comment|doc|rule|policy|spec)\b"
    r"|\baccording\s+to\s+[\w./_-]+\.(?:md|py|ts|json|ya?ml)\b"
    # "the Dockerfile excludes X" -- citing a build/config artifact's CONTENT as the explanation,
    # with no verb like "says". This is the exact shape of violation #1 and has no other tell.
    r"|\bthe\s+(?:dockerfile|makefile|\.gitignore|gitignore|pyproject|settings\.json|"
    r"compose[\w.]*|entrypoint|manifest)\s+\w+s\b"
    # CODE cited as authority (2026-08-09). The guard covered config artifacts but not the
    # more seductive form: a conditional inside a function, restated as a fact about the
    # world. `_resolve_from_models_layout` carries `model_type != "hunt_loop"`, and that was
    # read as "hunt_loop rows have no ModelSpec dir" — half true. The rule books have none;
    # dvs_ml_feat / nimble_mm_ml_feat / oracle_veto_sa are fitted hist_gb and stacking-ridge
    # estimators whose type a `_DEFAULT_MODEL_TYPE` sentinel overwrote. The exclusion was
    # papering over lost identity, and it locks 11 of 20 registry rows out of the cert corpus.
    # Code demonstrably DOES what you just said; whether it SHOULD is the whole question.
    r"|\bthe\s+(?:function|method|helper|resolver|builder|producer|writer|parser|guard|gate|"
    r"filter|check|validator|hook|service|handler|runner)\s+"
    r"(?:excludes?|skips?|ignores?|filters?\s+out|rejects?|drops?|already\s+handles?|"
    r"does\s+not\s+\w+)\b"
    r"|\b(?:excluded|skipped|ignored|filtered\s+out)\s+by\s+(?:the\s+)?"
    r"(?:function|helper|resolver|guard|gate|filter|code)\b"
    # TEST CONFORMED TO IMPLEMENTATION — the sharp end of the same move. A test edited to
    # agree with the code it exists to check has stopped being a test.
    r"|(?:correct(?:ing|ed)?|adjust(?:ing|ed)?|updat(?:ing|ed)|fix(?:ing|ed)?|relax(?:ing|ed))"
    r"\s+(?:it|the\s+(?:test|assertion|expectation|fixture)s?)\s+"
    r"(?:to\s+)?(?:match|agree\s+with|reflect|the\s+real\s+contract|the\s+actual)"
    r"|(?:my|the)\s+test\s+asserted\s+.{0,60}(?:can'?t|cannot|does\s+not)\s+exist)",
    re.IGNORECASE,
)

#: Evidence the claim was actually checked or judged rather than repeated.
_JUDGED = re.compile(
    r"(verified|traced|measured|i checked|i ran|the data says|counted"
    r"|obsolete|out of date|stale|no longer|superseded|retract"
    r"|my judgment|i judge|architect(?:ur)?al judgment"
    r"|sound-but-fragile|sound but fragile|is wrong|was wrong|does not hold|fails to"
    r"|proxy for|cannot be traced|could not be traced|unsourced"
    r"|\b\d[\d,]*\s*(?:of|/)\s*\d[\d,]*\b)",  # "34 of 34", "3/16" — a real count
    re.IGNORECASE,
)


#: Deferring to an authority that DOES NOT EXIST. There is no team, no PM, no second
#: engineer — the company is the owner (one junior dev) and this agent. So "that is a team
#: decision", "I won't override it", "not my call" are always an invented stakeholder standing
#: in for a judgement the LEAD ARCHITECT owes. Violation #4 (owner, 2026-08-06, "MAN, what
#: team??? What TEAM????"): `.claude/settings.json` was found gitignored, and instead of judging
#: the line the agent called it "a deliberate team decision I won't override" — leaving every
#: shared hook registered nowhere, i.e. shipped dead. The .gitignore line was simply WRONG.
_INVENTED_AUTHORITY = re.compile(
    r"(team\s+(?:decision|policy|convention|choice|preference|call)"
    r"|(?:the|a|our|your)\s+team\b"
    r"|deliberate\s+(?:team|project|repo|repository)\s+decision"
    r"|(?:i|we)\s+(?:won'?t|will not|shouldn'?t|should not|can'?t|cannot)\s+(?:override|touch|change)"
    r"|not\s+(?:my|mine|our)\s+(?:call|decision|place)"
    r"|defer(?:ring)?\s+to\s+(?:the\s+)?(?:team|convention|existing|committed)"
    r"|someone\s+(?:else\s+)?(?:already\s+)?decided"
    r"|respect(?:ing)?\s+the\s+(?:existing|committed|team))",
    re.IGNORECASE,
)

#: Evidence a DECISION was actually taken rather than handed to an imaginary stakeholder.
_DECIDED = re.compile(
    r"((?:i|we)\s+(?:decided|chose|changed|fixed|removed|tracked|split|overrode|corrected)"
    r"|decision:|verdict:|i am (?:changing|fixing|removing|tracking)"
    r"|now tracked|fixed it|changed it|that line is wrong|it was wrong)",
    re.IGNORECASE,
)


def defers_to_invented_authority(text: str) -> bool:
    """Handed a judgement to a stakeholder who does not exist, and decided nothing."""
    if not text or not _INVENTED_AUTHORITY.search(text):
        return False
    return not _DECIDED.search(text)


#: Dismissing something as already-settled.
_DISMISSAL = re.compile(
    r"(already (?:tested|tried|hunted|killed|covered|explored|done)"
    r"|has been (?:tested|tried|killed|covered)"
    r"|exhausted|closed cell|not (?:a )?new|nothing new|same (?:thing|angle|information set)"
    r"|will also (?:fail|kill)|would also (?:fail|kill)|no point (?:re-?)?(?:running|testing))",
    re.IGNORECASE,
)

#: Evidence the SUBJECTS were actually compared, not assumed equivalent.
_COMPARED = re.compile(
    r"(\bdiffers?\b|\bdifferent\b|not the same|\bunlike\b|is distinct|≠|!="
    r"|same model|identical|i tested|i ran it|benchmark|version|parameters|weights"
    r"|checked (?:whether|if|that)|verified (?:it|they|the))",
    re.IGNORECASE,
)


def dismisses_by_proxy(text: str) -> bool:
    """Dismissed a NEW thing by citing a result about a DIFFERENT thing.

    THE CASE (2026-08-06): the owner proposed Kimi K3 + ML + sentiment. The reply cited a
    HUNT_LEDGER entry — `finrl_deepseek_sent_gate`, KILLed 2026-07-22 — and concluded the LLM
    angle was closed. But K3 is not DeepSeek v3: a stronger scorer can extract more signal from
    the SAME headlines, so a KILL for one model is not a KILL for the class. The owner's
    response: *"how can you say that will also KILL without even testing??"* — correct.

    A ledger entry is evidence about what was RUN. Generalising it to a different model, a
    different venue, a different timeframe or a different library is an unverified leap.
    """
    if not text or not _DISMISSAL.search(text):
        return False
    if _COMPARED.search(text):
        return False
    return bool(_CITATION.search(text) or re.search(r"(ledger|artifact|verdict|matrix)", text, re.I))


def cites_without_judging(text: str) -> bool:
    """True when a written source is invoked as authority and nothing shows it was checked."""
    if not text:
        return False
    if defers_to_invented_authority(text) or dismisses_by_proxy(text):
        return True
    if not _CITATION.search(text):
        return False
    return not _JUDGED.search(text)



def _session_id(payload: dict) -> str:
    """The conversation this block-bound belongs to — see `_hook_state.scoped_to_session`."""
    return str(payload.get("session_id") or "")


def _blocks(session_id: str = "") -> int:
    """Blocks spent IN THIS SESSION. A new session starts at zero so the guard cannot die."""
    return int(load_state(STATE, session_id).get("blocks") or 0)


def _bump(session_id: str = "") -> None:
    state = load_state(STATE, session_id)
    state["blocks"] = int(state.get("blocks") or 0) + 1
    save_state(STATE, state)

_REASON = (
    "STOP BLOCKED — you quoted a written claim as the answer instead of judging it.\n\n"
    "This message cites a rule / doc / docstring as authority with no sign you checked whether it "
    "is TRUE or still RIGHT. That is `.claude/rules/verify-and-judge-not-quote.md`, and it has now "
    "been violated three times:\n"
    "  1. a Dockerfile comment quoted as if it settled whether the exclusion was correct;\n"
    "  2. \"prod's honest_verdict says WF SR 0.42\" — untraceable, no such field exists;\n"
    "  3. the all-in-leverage ban quoted to unpublish 13 prod backtests — the ban was a PROXY for a "
    "defect the honest-MTM engine already fixed, so it protected the wrong four and spared a book "
    "that liquidated users 26 times.\n\n"
    "Before stopping:\n"
    "  1. VERIFY the claim against the running system — does the field exist, is the hook wired, "
    "is the value actually read? Run it, count it.\n"
    "  2. JUDGE the decision. You are the LEAD ARCHITECT. \"The rule says X\" is where the analysis "
    "STARTS, not where it ends. Is X still correct? What was it a proxy for? Has that been fixed?\n"
    "  3. State the verdict explicitly — sound / sound-but-fragile / obsolete / wrong — and name "
    "the failure mode.\n\n"
    "Quoting a rule AND judging it passes this guard. Quoting it instead of judging does not.\n\n"
    "VIOLATION #4 (2026-08-06) — INVENTED AUTHORITY. `.claude/settings.json` was found gitignored "
    "and the agent wrote it off as \"a deliberate team decision I won't override\". There IS no "
    "team: the company is the owner (one junior dev) and this agent. The line was simply WRONG — it "
    "left every shared guard registered nowhere, i.e. shipped dead. Inventing a stakeholder to defer "
    "to is the same defect as quoting a docstring: both replace a judgement you owe with an "
    "authority you made up.\n\n"
    "If you catch yourself writing \"team decision\", \"not my call\", \"I won't override\" — stop. "
    "Ask who exactly would decide. If the answer is not the owner personally (credentials, spend, "
    "publish, legal), the answer is YOU. Decide, act, and report the decision."
)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    # PostToolUse: record what this turn actually DID, so the Stop check can gate on
    # BEHAVIOUR. A guard released only by a PHRASE is satisfied by typing the phrase.
    if data.get("tool_name"):
        record(data)
        return 0
    if (data.get("hook_event_name") or "") != "Stop":
        return 0
    # WHOLE TURN: 30 cite-without-judge messages sit in the real corpus unseen, because this
    # read only the final message of a forty-message turn.
    if not cites_without_judging(turn_text(data.get("transcript_path", ""))):
        return 0

    # ACTION-GROUNDED RELEASE: citing a doc is fine when the turn actually went and CHECKED it.
    # Without this the guard can only ask whether I typed a judging phrase.
    if had("search"):
        return 0

    # `payload` was never bound here — the local is `data` — so the moment this guard DECIDED to
    # fire it raised NameError, hit the fail-open handler below, and returned silently. Measured
    # 2026-08-18 (ruff F821): the block path had never once executed to completion, which means a
    # guard written after three violations had never blocked any of them.
    session = _session_id(data)

    # NO BLOCK BUDGET, deliberately (owner, 2026-08-18). The docstring used to promise
    # "self-releases after a bounded number of blocks"; budgets were STRIPPED from 22 guards
    # because a guard that fires N times and then goes quiet is the defect — the violation is just
    # as wrong on the fourth attempt as on the first, and silence reads as approval.
    # `todo_completion_guard` records the same conclusion in code:
    # `_ = count > _MAX_STUCK_BLOCKS  # retained for the count report below; never releases`.
    # The count is kept for the REPORT, never as a release condition.
    _bump(session)
    print(
        json.dumps(
            {
                "decision": "block",
                "reason": f"{_REASON}\n\n[persistent guard: block {_blocks(session)} this session; "
                "no budget — it fires every time until the citation is judged]",
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        raise SystemExit(0)  # fail OPEN — a guard must never wedge the session
