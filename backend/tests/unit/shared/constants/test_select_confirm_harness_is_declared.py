"""The select-confirm writer must stamp its harness, like every other cert writer.

REUSE-AUDIT: extends `src/shared/constants/capital_cert_harness.py`, whose own comment says
"extend this alongside a new writer, never spell one inline in the writer itself". Considered
tests/unit/research/test_hypothesis_cert_join_key_baseline.py — that is the RATCHET counting
undeclared certs; this pins the fix at the writer the ratchet caught.

MEASURED 2026-08-27. The ratchet failed at 130 undeclared certs against a budget of 125, and its
message says exactly what to do: "Stamp the harness at the WRITER — an undeclared one is chosen by
substring-matching the model name, so a rename moves the book to a different money harness in
silence."

Auditing the whole inventory by writer family:

    85  model_spec_capital_x_exit   (legacy backlog, all pre-dating the field)
    26  select_confirm              <- and the FIVE most recent undeclared certs, 2026-08-26
     3  bb ... and a long tail of ones and twos

So select-confirm is the writer still actively producing undeclared certs. The others are a
stationary backlog; this one moves the number.

WHY A FIFTH HARNESS RATHER THAN REUSING ONE. A select-confirm artifact is neither a continuous
return series (`levered_return_book`) nor a lane/combo grid over one ModelSpec
(`capital_mode_matrix` / `capital_x_exit_grid`). It is levers PRE-COMMITTED on a select window and
published on a disjoint confirm window — the construction `edge-hunt-loop.md` singles out, and the
only one whose headline is a pre-commitment rather than a search result. Folding it into an
existing name would make the field lie about which engine produced the number, which is precisely
what the ratchet exists to prevent.

FAILING CLOSED IS THE CORRECT PROMOTE BEHAVIOUR, and stamping makes it deliberate.
`supports_production_promote` branches on `levered_return_book`, then on a `capital_modes` mapping,
then returns False. A select-confirm payload carries neither, so it already fell through to False —
but by accident, via an empty harness string. Now it does so by name.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.shared.constants.capital_cert_harness import (
    ALL_CAPITAL_CERT_HARNESSES,
    CAPITAL_CERT_HARNESS_SELECT_CONFIRM,
)

_WRITER = Path(__file__).resolve().parents[4] / "src" / "research" / "edge_hunt" / "run_select_confirm_cert.py"


class TestTheHarnessIsPartOfTheTaxonomy:
    def test_it_is_a_recognised_harness(self) -> None:
        """A value the taxonomy does not know is the same as no value to every consumer."""
        assert CAPITAL_CERT_HARNESS_SELECT_CONFIRM in ALL_CAPITAL_CERT_HARNESSES

    def test_it_does_not_collide_with_an_existing_name(self) -> None:
        assert len(ALL_CAPITAL_CERT_HARNESSES) == len({h.lower() for h in ALL_CAPITAL_CERT_HARNESSES})

    def test_the_name_says_what_the_construction_is(self) -> None:
        """Pre-commitment is the distinguishing property — the name should carry it."""
        assert "select_confirm" in CAPITAL_CERT_HARNESS_SELECT_CONFIRM


class TestTheWriterStampsIt:
    def test_the_writer_imports_the_constant_rather_than_spelling_it(self) -> None:
        """`capital_cert_harness`: "never spell one inline in the writer itself"."""
        source = _WRITER.read_text(encoding="utf-8")

        assert "CAPITAL_CERT_HARNESS_SELECT_CONFIRM" in source
        assert f'"harness": "{CAPITAL_CERT_HARNESS_SELECT_CONFIRM}"' not in source, (
            "the literal is spelled inline; import the constant so a rename cannot desync"
        )

    def test_the_payload_carries_a_harness_key(self) -> None:
        source = _WRITER.read_text(encoding="utf-8")

        assert '"harness"' in source, "the written payload declares no harness at all"

    def test_the_writer_still_parses(self) -> None:
        """READING THE SOURCE IS NOT ENOUGH, and this test learned that the hard way.

        The two assertions above check that the file CONTAINS certain text. Both passed while the
        module had a SyntaxError: the import that stamps the harness had been inserted into the
        middle of a multi-line `from ... import (` statement, so `run_select_confirm_cert.py`
        could not be imported at all. Two unrelated tests elsewhere caught it by actually
        importing the module; this file, which exists to guard that exact writer, did not.

        A grep-shaped test proves a string is present. It proves nothing about whether the program
        still runs.
        """
        import ast

        ast.parse(_WRITER.read_text(encoding="utf-8"), filename=str(_WRITER))


class TestAPromoteDecisionStaysClosed:
    def test_a_select_confirm_cert_does_not_support_production_promote(self) -> None:
        """Fails closed BY NAME now, where before it fell through on an empty string."""
        from src.domain.services.edge_lifecycle.capital_cert_promote import (
            cert_artifact_supports_production_promote,
        )

        cert = json.loads(
            json.dumps(
                {
                    "harness": CAPITAL_CERT_HARNESS_SELECT_CONFIRM,
                    "spec": "BTC/USDT:1d:48:hist_gradient_boosting_clf",
                    "confirm": {"final_capital": 12345.0, "num_trades": 30},
                }
            )
        )

        assert cert_artifact_supports_production_promote(cert) is False
