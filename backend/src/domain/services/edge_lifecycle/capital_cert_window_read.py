"""Window/vintage readers and wire-contract keys of a capital cert (flag, role, DSR presence, disclosures).

Moved verbatim out of ``capital_cert_promote`` (god-split); that module re-exports the public names.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from src.domain.services.edge_lifecycle.cert_window_role import CERT_WINDOW_ROLE_KEY

#: Cert payload keys the promote gate reads. Public because they are a WIRE CONTRACT, not an
#: implementation detail: the research runner writes them and this gate reads them, across a
#: process boundary and a JSON file. They were previously spelled as literals at every site,
#: which is exactly how `ship_chart_inventory_tier` came to look up a key nothing writes.
CERT_WINDOW_KEY: Final = "window"
CERT_WINDOW_IN_SAMPLE_KEY: Final = "window_is_in_sample"
CERT_HEADLINE_DSR_KEY: Final = "headline_deflated_sharpe"
CERT_HEADLINE_DSR_PRESENT_KEY: Final = "headline_deflated_sharpe_present"

#: Disclosed beside a cert's money when its headline DSR is recorded as null. A caution, never a veto
#: (owner LENIENT-4, 2026-10-04): only ruin excludes, and an in-sample window still cannot prove a book.
DISCLOSURE_HEADLINE_DSR_MISSING: Final = "headline_dsr_missing"


def capital_cert_window_flag(capital_certification: Mapping[str, Any]) -> bool | None:
    """The cert's OWN out-of-sample answer — top level, else the nested ``window`` block.

    Certs are self-describing: ``run_edge_capital_x_exit_grid`` stamps
    ``CERT_WINDOW_IN_SAMPLE_KEY`` into ``window``. Without this read, the fail-closed gate below
    would be unconditional for the in-module callers that have no flag to forward — stamping
    every freshly built cert ``failed`` and freezing auto-promote. A gate that rejects
    everything is as useless as one that accepts everything.

    SoT for an extraction that existed in THREE hand-rolled copies, which is how it stayed
    broken: ``ship_chart_inventory_tier`` looked up ``window["is_in_sample"]`` — a key with
    **zero writers anywhere in the repo** — so the chart-inventory ship gate could never see a
    nested flag at all. ``cert_run_tasks`` read only the nested key and missed the top-level
    one. That typo is deliberately NOT carried forward here: enshrining a dead alias in the SoT
    preserves the bug under a nicer name.
    """
    for source in (capital_certification, capital_certification.get(CERT_WINDOW_KEY)):
        if isinstance(source, Mapping):
            flag = source.get(CERT_WINDOW_IN_SAMPLE_KEY)
            if isinstance(flag, bool):
                return flag
    return None


def capital_cert_window_role(capital_certification: Mapping[str, Any]) -> str | None:
    """Which window this cert's numbers describe: ``select``, ``confirm``, or ``None`` if unstamped.

    ``None`` means the artifact does not say, which is a finding about the artifact rather than a
    default. It must never be read as "confirm" -- absence has to be the unflattering answer here,
    because the flattering one is exactly what turns a search into a result.

    Reads the nested ``window`` block first and the top level second, matching
    `capital_cert_window_flag`: the slim cert the promote gate loads carries the whole window
    block, while older summaries stamped some keys at the top.
    """
    for source in (capital_certification.get(CERT_WINDOW_KEY), capital_certification):
        if isinstance(source, Mapping):
            role = source.get(CERT_WINDOW_ROLE_KEY)
            if isinstance(role, str) and role:
                return role
    return None


def capital_cert_headline_deflation_present(capital_certification: Mapping[str, Any]) -> bool | None:
    """Whether the cert records a deflated headline — the post-2026-08-05 engine vintage marker.

    Second SoT extraction, duplicated the same way: ``ship_chart_inventory_tier`` grew a
    three-branch version and ``cert_run_tasks`` a one-liner that disagreed with it on a cert
    carrying an explicit ``headline_deflated_sharpe_present`` boolean.

    ``None`` means the cert says nothing either way, which the gate treats as "caller did not
    check" rather than as a failure — unlike the window flag, absence here is the NORM for the
    hypothesis-route artifacts and refusing them all would be a blanket ban, not a gate.

    DO NOT "HARDEN" THIS TO REJECT ABSENCE. Measured across all 56 certs on 2026-08-10, after the
    re-cert batch that first gave the corpus this field at all:

        DSR present, non-null          10   judged on VALUE by `capital_cert_headline_deflation_value`
        null DSR, grid HAD candidates   0   <- the ONLY thing a stricter rule would catch
        null DSR, grid empty           22   made no claim; rejecting them is not a gate
        field absent (pre-fix vintage) 24   owed a re-cert, not a rejection

    That first line was FALSE when written and is corrected here: until 2026-08-15 the gate read
    this predicate ONLY for presence, so a recorded `headline_deflated_sharpe: 0.0` promoted
    exactly like a 0.99. Very likely the sentence is why nobody added the value check — it told
    every reader the job was already done. The value gate now lives in
    `capital_cert_headline_deflation_value` + `MIN_PROMOTE_DEFLATED_SHARPE`.

    A naive "reject absence" bars 46 of 56, most for reasons that are not the cert's fault. The
    honest predicate — reject a null DSR only where `deflation_n_trials > 0`, i.e. the grid could
    have deflated and did not — bars **zero**. Implementing it would be a no-op gate: green tests,
    clean linters, catching nothing, and reading as rigour. That is the exact 2026-08-05 failure
    `.claude/rules/investigate-before-changing-a-gate.md` was written after.

    The thing actually owed is DATA, not a stricter rule: 24 certs need a re-cert to acquire the
    field, and the 22 empty grids need a reason they produced no cells.
    """
    explicit = capital_certification.get(CERT_HEADLINE_DSR_PRESENT_KEY)
    if isinstance(explicit, bool):
        return explicit
    if CERT_HEADLINE_DSR_KEY in capital_certification:
        return capital_certification.get(CERT_HEADLINE_DSR_KEY) is not None
    return None


def capital_cert_disclosures(capital_certification: Mapping[str, Any]) -> tuple[str, ...]:
    """Statistical cautions to publish beside this cert's money, in reading order.

    A disclosure never disqualifies; ``cryptobt_capital_cert_passes`` does not read it.
    """
    if capital_cert_headline_deflation_present(capital_certification) is False:
        return (DISCLOSURE_HEADLINE_DSR_MISSING,)
    return ()
