"""C-1 -- ONE Certification shape, and what it refuses to hold.

IMPORTERS / CALLERS: none -- pytest collects it.
AFFECTED API: `src.cert.certification.Certification`, the schema C-2 will emit from
  `python -m src.cert` and C-6 will migrate every book's cert onto.
DATA SCHEMAS: identity / windows[] / levers / result / lane_ladder[] / disclosures, validated from
  plain dicts shaped like the cells already on disk.

WHY A SCHEMA, measured rather than argued. The corpus holds TWO cert layouts
(`capital_modes.<lane>` and `capital_x_exit.best_by_capital_lane.<lane>.best`, see
`capital_cert_lanes`) plus the `select_confirm_*` envelope, and every reader guesses which one it
has. A window with no role is how an in-sample grid gets graded as unseen evidence; a window with
no bar count is how `1d lightgbm v33` was graded on ELEVEN bars. Both fields are therefore
REQUIRED, which is this slice's PASS criterion.

NO STORED VERDICT. A tier written into the artifact goes stale the moment a gate changes, and C-0
just measured the cost: v42, prod v2 and v12 each carried a verdict-shaped number (`$12,815`,
`$26,244`, `$13,404`) that the fixed engine turns into `$0.00`. The verdict is derived at READ time
(plan item C-5), so the schema forbids unknown keys and a `verdict`/`tier` key is refused outright.

REUSE-AUDIT: imports `src.domain.services.edge_lifecycle.capital_cert_promote` for the window-role
vocabulary (`CERT_WINDOW_ROLE_SELECT` / `CERT_WINDOW_ROLE_CONFIRM`) instead of retyping "select" and
"confirm". Considered `src/research/edge_hunt/edge_inventory_capital_shapes.CapitalLaneRow` --
not reused because it is a TypedDict under `scripts/`, which `src/` may not import, and it validates
nothing at runtime, which is the whole job here.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from src.cert.certification import Certification
from src.domain.services.edge_lifecycle.capital_cert_promote import CERT_WINDOW_ROLE_CONFIRM, CERT_WINDOW_ROLE_SELECT


def _payload(**overrides: Any) -> dict[str, Any]:
    """A cert shaped like `1d lightgbm v42` after C-0: the confirm lane genuinely wiped."""
    payload: dict[str, Any] = {
        "identity": {"spec": "BTC/USDT:1d:42:lightgbm", "harness": "select_confirm_precommit"},
        "windows": [
            {"role": CERT_WINDOW_ROLE_SELECT, "start": "2025-06-01", "end": "2026-01-01", "bars": 214},
            {"role": CERT_WINDOW_ROLE_CONFIRM, "start": "2026-01-01", "end": "2026-08-12", "bars": 223},
        ],
        "levers": {
            "lane": "perp_8x",
            "exit_label": "tpsl_7_5",
            "sizing": "10pct",
            "holding_periods": 24,
            "dca_depth": None,
            "min_confidence_pct": None,
            "min_compound_step_pct": None,
        },
        "result": {"initial_capital": 10_000.0, "final_capital": 0.0, "spot_bh_final": 7_159.01, "num_trades": 104, "max_drawdown": -1.0},
        "lane_ladder": [
            {
                "lane": "spot_10k",
                "leverage": 0,
                "final_capital": 10_361.79,
                "max_drawdown": -0.0567,
                "drawdown_basis": "mark_to_market",
                "liquidation_exits": 0,
                "account_bankrupt": False,
                "num_trades": 13,
            },
            {
                "lane": "perp_8x",
                "leverage": 8,
                "final_capital": 0.0,
                "max_drawdown": -1.0,
                "drawdown_basis": "mark_to_market",
                "liquidation_exits": 1,
                "account_bankrupt": True,
                "num_trades": 104,
            },
        ],
        "disclosures": {
            "liquidation_exits": 1,
            "account_bankrupt": True,
            "fantasy_post_ruin_trades": 0,
            "drawdown_contradicts_capital": False,
            "thin_sample": False,
        },
    }
    payload.update(overrides)
    return payload


def _window(**changes: Any) -> dict[str, Any]:
    window: dict[str, Any] = {"role": CERT_WINDOW_ROLE_CONFIRM, "start": "2026-01-01", "end": None, "bars": 223}
    window.update(changes)
    return window


class TestARealCertValidates:
    def test_the_v42_cert_is_accepted(self) -> None:
        cert = Certification.model_validate(_payload())

        assert [w.role for w in cert.windows] == [CERT_WINDOW_ROLE_SELECT, CERT_WINDOW_ROLE_CONFIRM]
        assert cert.disclosures.account_bankrupt is True

    def test_it_round_trips_without_loss(self) -> None:
        """What C-2 writes must be exactly what C-7 reads back."""
        cert = Certification.model_validate(_payload())

        assert Certification.model_validate(cert.model_dump()) == cert

    def test_an_open_ended_confirm_window_is_allowed(self) -> None:
        """Every `_{split}.json` artifact on disk confirms to 'now'; `end` must be able to be None."""
        cert = Certification.model_validate(_payload(windows=[_window(end=None)]))

        assert cert.windows[0].end is None


class TestAWindowMustSayWhatItIsAndHowLongItIs:
    """THE PASS CRITERION: role and bars are required, and each is checked, not merely present."""

    def test_a_window_without_a_role_is_refused(self) -> None:
        window = _window()
        del window["role"]

        with pytest.raises(ValidationError, match="role"):
            Certification.model_validate(_payload(windows=[window]))

    def test_a_window_without_bars_is_refused(self) -> None:
        """v33 was once graded on ELEVEN bars; an absent count cannot even show that."""
        window = _window()
        del window["bars"]

        with pytest.raises(ValidationError, match="bars"):
            Certification.model_validate(_payload(windows=[window]))

    @pytest.mark.parametrize("bars", [0, -5])
    def test_a_window_with_no_bars_in_it_is_refused(self, bars: int) -> None:
        with pytest.raises(ValidationError, match="bars"):
            Certification.model_validate(_payload(windows=[_window(bars=bars)]))

    def test_a_role_outside_the_shared_vocabulary_is_refused(self) -> None:
        """'holdout' reads plausibly and means nothing to the grader."""
        with pytest.raises(ValidationError, match="role"):
            Certification.model_validate(_payload(windows=[_window(role="holdout")]))

    def test_both_shared_roles_are_accepted(self) -> None:
        """Non-vacuity: the refusal above must not be refusing everything."""
        for role in (CERT_WINDOW_ROLE_SELECT, CERT_WINDOW_ROLE_CONFIRM):
            assert Certification.model_validate(_payload(windows=[_window(role=role)])).windows[0].role == role

    def test_a_cert_with_no_windows_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="windows"):
            Certification.model_validate(_payload(windows=[]))


class TestNoStoredVerdict:
    """A verdict on disk goes stale with every gate change; it is derived at read time (C-5)."""

    @pytest.mark.parametrize("key", ["verdict", "tier", "precommit_tier"])
    def test_a_stored_verdict_is_refused(self, key: str) -> None:
        with pytest.raises(ValidationError, match=key):
            Certification.model_validate(_payload(**{key: "candidate"}))

    def test_an_unknown_field_inside_a_section_is_refused(self) -> None:
        """Forbidding extras only at the top would let a verdict hide one level down."""
        disclosures = {**_payload()["disclosures"], "tier": "edge"}

        with pytest.raises(ValidationError, match="tier"):
            Certification.model_validate(_payload(disclosures=disclosures))


class TestTheLadderIsTheWholeLadder:
    def test_a_cert_with_no_lanes_is_refused(self) -> None:
        """A lane that liquidates condemns the LANE; with no ladder there is nothing to grade."""
        with pytest.raises(ValidationError, match="lane_ladder"):
            Certification.model_validate(_payload(lane_ladder=[]))

    def test_a_lane_must_disclose_whether_the_account_survived(self) -> None:
        lane = {**_payload()["lane_ladder"][1]}
        del lane["account_bankrupt"]

        with pytest.raises(ValidationError, match="account_bankrupt"):
            Certification.model_validate(_payload(lane_ladder=[lane]))
