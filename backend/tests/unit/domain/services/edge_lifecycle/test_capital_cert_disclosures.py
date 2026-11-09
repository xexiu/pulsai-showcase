"""A null headline DSR is a DISCLOSURE on a capital cert, never a promote veto (LENIENT-4).

IMPORTERS/CALLERS: pytest only. AFFECTED API: none. DATA SCHEMAS: none -- pins
capital_cert_promote.cryptobt_capital_cert_passes and capital_cert_disclosures.

Split from test_capital_cert_promote.py, which sits over its file-size cap: this file holds the
LENIENT-4 contract (owner 2026-10-04: research/money gates must not be strict).
"""

from __future__ import annotations

from typing import Any

from src.domain.services.edge_lifecycle.capital_cert_promote import (
    CERT_HEADLINE_DSR_KEY,
    CERT_HEADLINE_DSR_PRESENT_KEY,
    CERT_WINDOW_IN_SAMPLE_KEY,
    DISCLOSURE_HEADLINE_DSR_MISSING,
    capital_cert_disclosures,
    cryptobt_capital_cert_passes,
)


class TestMissingHeadlineDsrIsADisclosureNotAVeto:
    """LENIENT-4 (owner, 2026-10-04): a statistical caution is disclosed beside the result, never a veto.

    The DSR-presence check blocked 9 modern, liq-clean certs that beat B&H on a null field.
    """

    @staticmethod
    def _money_maker_cert() -> dict[str, Any]:
        lane = {
            "leverage": 5.0,
            "initial_capital": 10_000.0,
            "final_capital": 20_000.0,
            "final_balance": 20_000.0,
            "liquidation_exits": 0,
            "account_bankrupt": False,
        }
        return {
            "capital_modes": {"perp_5x": lane},
            "spot_bh_final": 12_000.0,
            CERT_WINDOW_IN_SAMPLE_KEY: False,
            CERT_HEADLINE_DSR_KEY: None,
        }

    def test_null_headline_dsr_does_not_block_a_liq_clean_lane_beating_bh(self) -> None:
        assert cryptobt_capital_cert_passes(self._money_maker_cert()) is True

    def test_explicit_false_presence_flag_does_not_block_either(self) -> None:
        cert = {**self._money_maker_cert(), CERT_HEADLINE_DSR_PRESENT_KEY: False}
        assert cryptobt_capital_cert_passes(cert) is True

    def test_missing_dsr_is_reported_as_a_disclosure(self) -> None:
        assert capital_cert_disclosures(self._money_maker_cert()) == (DISCLOSURE_HEADLINE_DSR_MISSING,)

    def test_recorded_dsr_carries_no_disclosure(self) -> None:
        cert = {**self._money_maker_cert(), CERT_HEADLINE_DSR_KEY: 0.4}
        assert capital_cert_disclosures(cert) == ()

    def test_ruin_still_excludes_even_with_dsr_missing(self) -> None:
        cert = self._money_maker_cert()
        cert["capital_modes"]["perp_5x"]["liquidation_exits"] = 2
        assert cryptobt_capital_cert_passes(cert) is False

    def test_in_sample_window_still_cannot_prove_a_book(self) -> None:
        cert = {**self._money_maker_cert(), CERT_WINDOW_IN_SAMPLE_KEY: True}
        assert cryptobt_capital_cert_passes(cert) is False


class TestPreDeflationCertsCannotPromote:
    """History: until 2026-10-04 a missing headline DSR marked a cert as pre-2026-08-05 and barred it.

    LENIENT-4 made that a disclosure. What these tests still pin: a missing DSR GRANTS nothing (money must
    still be shown), and a recorded DSR is judged on its merit like any other cert.
    """

    def test_cert_without_deflation_gets_no_pass_it_did_not_earn(self) -> None:
        """Missing DSR no longer vetoes (LENIENT-4), but it grants nothing: money must still be shown."""
        cert = {"capital_modes": {"spot_10k": {"final_capital": 50_000.0}}}
        assert cryptobt_capital_cert_passes({**cert, CERT_HEADLINE_DSR_PRESENT_KEY: False}) is False

    def test_cert_with_deflation_recorded_is_still_judged_on_merit(self) -> None:
        """The gate only bars STALE certs -- it must not become a second money gate."""
        cert: dict[str, Any] = {"capital_modes": {}}
        assert cryptobt_capital_cert_passes({**cert, CERT_HEADLINE_DSR_PRESENT_KEY: True}) is False

    def test_unspecified_preserves_existing_behaviour(self) -> None:
        """Callers that do not check must not be silently flipped to reject."""
        cert = {"capital_modes": {"spot_10k": {"final_capital": 50_000.0}}}
        assert cryptobt_capital_cert_passes(cert) is not None
