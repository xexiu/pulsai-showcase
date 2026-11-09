"""`tpsl_8_3` means SL=8, TP=3 — the name lies, so nobody may decode it by hand.

THE COST OF NOT HAVING THIS, measured 2026-08-12. Replicating `1d lightgbm v41`'s cert cell in
prod, I read `tpsl_8_3` as take-profit 8 / stop-loss 3 — the order the NAME implies. Result:

    wrong decode (TP=8, SL=3)   -6.0%   73 trades   win_rate 34.2%
    right decode (SL=8, TP=3)  +18.0%   71 trades   win_rate 74.6%   <- matches the cert exactly

Textbook: a tight 3% target against a wide 8% stop wins often with small wins; a wide 8% target
against a tight 3% stop wins rarely. From that one inversion I concluded the cert engine could not
be trusted for ANY book and wrote it into the ledger as the session's biggest finding. It was a
false alarm that cost hours.

The label is CONSISTENT across all four construction sites — scout_exit_grid_kernels,
rl_edge/experiment, infrastructure/ml/exit_grid, and btc_meta_walkforward_matrix's
`ExitKernel(label, strategy, stop_loss_pct, take_profit_pct, ...)`. The order is not the bug.
**The NAME is**: `tpsl` reads take-profit-then-stop-loss and encodes the reverse.

Renaming the prefix would invalidate every artifact on disk, so the fix is a codec: one place
that knows the order, with the surprise stated at the point of use.
"""

from __future__ import annotations

import pytest

from src.domain.services.exit_label_codec import (
    ExitLevels,
    decode_exit_label,
    encode_tpsl_label,
    exit_has_stop_at_entry,
)
from tests.helpers.api_paths import API_ROOT


class TestDecodeRegression:
    def test_the_v41_case_that_caused_the_false_alarm(self) -> None:
        """SL=8, TP=3 — reproduces the cert digit-for-digit; the inverse does not."""
        levels = decode_exit_label("tpsl_8_3")

        assert levels == ExitLevels(stop_loss_pct=8.0, take_profit_pct=3.0)

    @pytest.mark.parametrize(
        ("label", "sl", "tp"),
        [
            ("tpsl_8_7", 8.0, 7.0),  # 1d gb v10's cell
            ("tpsl_8_1", 8.0, 1.0),  # 8h v149
            ("tpsl_5_1", 5.0, 1.0),  # 4h v6
            ("tpsl_2_1", 2.0, 1.0),  # 12h v8 / v9
            ("tpsl_5_6", 5.0, 6.0),  # 12h v2 -- TP > SL, still SL first
        ],
    )
    def test_real_cells_from_the_corpus(self, label: str, sl: float, tp: float) -> None:
        levels = decode_exit_label(label)

        assert levels is not None
        assert (levels.stop_loss_pct, levels.take_profit_pct) == (sl, tp)

    def test_a_decimal_uses_p_as_the_separator(self) -> None:
        """The encoder writes `.` as `p` so the label stays filesystem-safe."""
        levels = decode_exit_label("tpsl_2p5_1p5")

        assert levels == ExitLevels(stop_loss_pct=2.5, take_profit_pct=1.5)


class TestDecodeRejectsNonGridExits:
    @pytest.mark.parametrize("label", ["dyn_tpsl_x3", "trail_1_1", "breakeven", "hold", "", "tpsl_", "tpsl_8"])
    def test_non_tpsl_labels_return_none_rather_than_a_guess(self, label: str) -> None:
        """A guessed lever is worse than no lever: it silently runs a different book."""
        assert decode_exit_label(label) is None

    def test_none_input_is_handled(self) -> None:
        assert decode_exit_label(None) is None


class TestStopAtEntry:
    """Which exit families attach a stop when the trade opens -- the money grade's risk-managed test reads this."""

    @pytest.mark.parametrize("label", ["tpsl_4_8", "trail_1_1", "atr_x3", "rr_4_2", "dyn_tpsl_x3", "thin_0p3"])
    def test_a_stop_family_attaches_a_stop(self, label: str) -> None:
        assert exit_has_stop_at_entry(label)

    @pytest.mark.parametrize("label", ["hold_24", "breakeven_2", "", None])
    def test_a_hold_or_breakeven_exit_or_no_label_attaches_none(self, label: str | None) -> None:
        assert not exit_has_stop_at_entry(label)


class TestEncodeDecodeRoundTrip:
    @pytest.mark.parametrize(("sl", "tp"), [(8.0, 3.0), (2.0, 1.0), (5.0, 6.0), (2.5, 1.5), (10.0, 0.5)])
    def test_round_trip_preserves_the_pair(self, sl: float, tp: float) -> None:
        assert decode_exit_label(encode_tpsl_label(sl, tp)) == ExitLevels(sl, tp)

    def test_the_encoder_puts_stop_loss_first(self) -> None:
        """Pinning the ORDER itself: if this flips, every artifact on disk is misread."""
        assert encode_tpsl_label(stop_loss_pct=8.0, take_profit_pct=3.0) == "tpsl_8_3"

    def test_the_encoder_matches_the_existing_grid_format(self) -> None:
        """Byte-identical to scout_exit_grid_kernels.py:41 -- `f"tpsl_{sl:g}_{tp:g}"`, `.`->`p`."""
        assert encode_tpsl_label(2.5, 1.0) == "tpsl_2p5_1"


class TestBehaviourAsymmetry:
    def test_a_wide_stop_with_a_tight_target_is_not_the_same_book(self) -> None:
        """The two readings are different strategies, which is why the mix-up was invisible.

        SL 8 / TP 3 risks 8 to make 3 -- wins often, loses big and rarely.
        SL 3 / TP 8 risks 3 to make 8 -- wins rarely, loses small and often.
        Both are coherent books; swapping them silently changes the answer, not just the numbers.
        """
        wide_stop = decode_exit_label("tpsl_8_3")
        tight_stop = decode_exit_label("tpsl_3_8")

        assert wide_stop is not None
        assert tight_stop is not None
        assert wide_stop.stop_loss_pct > wide_stop.take_profit_pct
        assert tight_stop.stop_loss_pct < tight_stop.take_profit_pct
        assert wide_stop != tight_stop


class TestIntegrationWithRealCerts:
    def test_every_tpsl_cell_in_the_corpus_decodes(self) -> None:
        """Integration: no cert on disk carries a tpsl label this codec cannot read."""
        import json

        models = API_ROOT / "models"
        seen = failed = 0
        for cert_path in models.glob("*/*/v*/capital_certification.json"):
            try:
                cert = json.loads(cert_path.read_text())
            except OSError, ValueError:
                continue  # an unreadable artifact is a different test's problem
            for cell in (cert.get("capital_modes") or {}).values():
                label = (cell or {}).get("exit_label") if isinstance(cell, dict) else None
                if not isinstance(label, str) or not label.startswith("tpsl_"):
                    continue
                seen += 1
                if decode_exit_label(label) is None:
                    failed += 1

        assert failed == 0, f"{failed} of {seen} tpsl labels on disk failed to decode"
