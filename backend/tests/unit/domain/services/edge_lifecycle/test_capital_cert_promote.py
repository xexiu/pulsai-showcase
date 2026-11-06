"""Behaviour: staged CryptoBT capital cert drives EDGE promote (smoke compound alone is not enough)."""

from __future__ import annotations

from typing import Any

from src.domain.services.edge_lifecycle.capital_cert_promote import (
    CAPITAL_CERT_STATUS_CERTIFIED,
    CAPITAL_CERT_STATUS_FAILED,
    CAPITAL_CERT_STATUS_INAPPLICABLE,
    CERT_HEADLINE_DSR_KEY,
    CERT_HEADLINE_DSR_PRESENT_KEY,
    CERT_WINDOW_IN_SAMPLE_KEY,
    best_clean_lane_wealth,
    build_inapplicable_capital_certification,
    build_pending_capital_certification,
    capital_cert_headline_deflation_present,
    capital_cert_lanes,
    capital_cert_window_flag,
    cert_artifact_supports_production_promote,
    cryptobt_capital_cert_passes,
    resolve_promote_capital_pass,
)

#: Every fixture below is about some OTHER axis (spot growth, leverage route, orphaned artifact),
#: so each one has to declare its window or it fails on the in-sample gate instead of on the thing
#: it names. A test that goes green for the wrong reason is worse than one that is red.
_OOS_WINDOW: dict[str, Any] = {"window_is_in_sample": False}


def _modes(*, spot_final: float, perp_3x_final: float, init: float = 10_000.0) -> dict[str, Any]:
    return {
        "spot_10k": {
            "lane": "spot_10k",
            "initial_capital": init,
            "final_balance": spot_final,
            "final_capital": spot_final,
        },
        "perp_3x": {
            "lane": "perp_3x",
            "initial_capital": init,
            "final_balance": perp_3x_final,
            "final_capital": perp_3x_final,
        },
        "perp_5x": {
            "lane": "perp_5x",
            "initial_capital": init,
            "final_balance": spot_final,
            "final_capital": spot_final,
        },
        "perp_8x": {
            "lane": "perp_8x",
            "initial_capital": init,
            "final_balance": 0.0,
            "final_capital": 0.0,
        },
    }


class TestCertIsSelfDescribing:
    """One extraction, in the domain, instead of three hand-rolled copies at the call sites.

    The copies did not merely duplicate — they DISAGREED, and one was dead:

    * `ship_chart_inventory_tier` looked up ``window["is_in_sample"]``. Nothing in the repo
      writes that key (the runner writes ``window_is_in_sample``), so the nested lookup could
      never hit and the in-sample check was permanently disarmed on the chart-ship path.
    * `cert_run_tasks` read the nested key only, so a top-level flag was invisible to it.
    * Both hand-rolled the deflation-vintage lookup too, and disagreed on a cert carrying an
      explicit ``headline_deflated_sharpe_present`` boolean.

    Making the payload self-describing is what removes the whole class: a caller cannot forget
    to arm a gate it never has to wire up.
    """

    def test_window_flag_is_read_from_either_level(self) -> None:
        assert capital_cert_window_flag({CERT_WINDOW_IN_SAMPLE_KEY: True}) is True
        assert capital_cert_window_flag({"window": {CERT_WINDOW_IN_SAMPLE_KEY: False}}) is False
        assert capital_cert_window_flag({}) is None
        # Top level wins over the nested block when both are present.
        assert capital_cert_window_flag({CERT_WINDOW_IN_SAMPLE_KEY: False, "window": {CERT_WINDOW_IN_SAMPLE_KEY: True}}) is False

    def test_the_dead_is_in_sample_alias_is_not_honoured(self) -> None:
        """Regression: do NOT resurrect the typo the consolidation deleted.

        Accepting ``is_in_sample`` here would keep the bug alive under a nicer name, and worse,
        would make a cert that never declared its window read as out-of-sample.
        """
        assert capital_cert_window_flag({"window": {"is_in_sample": False}}) is None

    def test_non_bool_flags_are_unknown_not_truthy(self) -> None:
        junk: object
        for junk in ("false", 0, 1, [], None):
            assert capital_cert_window_flag({CERT_WINDOW_IN_SAMPLE_KEY: junk}) is None

    def test_deflation_presence_prefers_the_explicit_boolean(self) -> None:
        assert capital_cert_headline_deflation_present({CERT_HEADLINE_DSR_PRESENT_KEY: False}) is False
        assert capital_cert_headline_deflation_present({CERT_HEADLINE_DSR_PRESENT_KEY: True}) is True
        assert capital_cert_headline_deflation_present({CERT_HEADLINE_DSR_KEY: 1.2}) is True
        # Key present but null = the engine looked and had nothing: a STALE cert, not an unknown one.
        assert capital_cert_headline_deflation_present({CERT_HEADLINE_DSR_KEY: None}) is False
        # Silent cert: unknown, which the gate must not treat as a failure.
        assert capital_cert_headline_deflation_present({}) is None

    def test_gate_arms_itself_from_the_cert_without_any_caller_wiring(self) -> None:
        """The behaviour the three copies existed to provide, now free at every call site."""
        modes = {
            "spot_10k": {"initial_capital": 10_000.0, "final_capital": 15_000.0},
            "perp_3x": {"initial_capital": 10_000.0, "final_capital": 50_000.0},
        }
        oos = {"status": "certified", "capital_modes": modes, "window": {CERT_WINDOW_IN_SAMPLE_KEY: False}}
        in_sample = {"status": "certified", "capital_modes": modes, "window": {CERT_WINDOW_IN_SAMPLE_KEY: True}}
        null_dsr = {**oos, CERT_HEADLINE_DSR_KEY: None}

        assert cryptobt_capital_cert_passes(oos) is True
        assert cryptobt_capital_cert_passes(in_sample) is False
        assert cryptobt_capital_cert_passes(null_dsr) is True  # LENIENT-4: disclosed, not a veto


class TestCryptobtCapitalCertPasses:
    def test_an_unknown_in_sample_window_is_refused(self) -> None:
        """FAIL CLOSED on "nobody checked" — the exemption's premise has expired.

        The gate rejected only `window_is_in_sample is True`; both `False` and a MISSING key
        passed, and the code stated the reason: "27 of 28 legacy certs never recorded their
        window, and blocking on unknown would invalidate the whole corpus on a technicality."

        True when written, checkable now. Measured across every cert under `apps/api/models`
        on 2026-08-09, after today's stamping: True 12, False 18, **MISSING 0**. The corpus is
        stamped, so failing closed costs nothing — and it shuts the path that kept two batches
        of unstamped full-span certs promotion-eligible, including v10's $2,017,894 cell at
        -78% DD with 7 liquidations.

        Promotion puts money in front of users. "We did not check" is not evidence.
        """
        modes = {
            "spot_10k": {"initial_capital": 10_000.0, "final_capital": 15_000.0, "liquidation_exits": 0, "account_bankrupt": False},
            "perp_3x": {"initial_capital": 10_000.0, "final_capital": 50_000.0, "liquidation_exits": 0, "account_bankrupt": False, "leverage": 3},
        }
        cert = {"status": "certified", "capital_modes": modes, "headline_deflated_sharpe": 1.2}

        assert cryptobt_capital_cert_passes(cert, window_is_in_sample=False) is True
        assert cryptobt_capital_cert_passes(cert, window_is_in_sample=True) is False
        assert cryptobt_capital_cert_passes(cert, window_is_in_sample=None) is False
        # A caller that simply omits it must not land on the permissive branch by accident.
        assert cryptobt_capital_cert_passes(cert) is False

    def test_passes_when_spot_grows_and_perp_3x_not_wiped(self) -> None:
        assert (
            cryptobt_capital_cert_passes(
                {"status": CAPITAL_CERT_STATUS_CERTIFIED, "capital_modes": _modes(spot_final=15_000, perp_3x_final=50_000), "window": _OOS_WINDOW}
            )
            is True
        )

    def test_fails_when_spot_does_not_grow(self) -> None:
        assert (
            cryptobt_capital_cert_passes(
                {"status": CAPITAL_CERT_STATUS_FAILED, "capital_modes": _modes(spot_final=9_000, perp_3x_final=50_000), "window": _OOS_WINDOW}
            )
            is False
        )

    def test_fails_when_perp_3x_wiped(self) -> None:
        assert (
            cryptobt_capital_cert_passes(
                {"status": CAPITAL_CERT_STATUS_CERTIFIED, "capital_modes": _modes(spot_final=15_000, perp_3x_final=0.0), "window": _OOS_WINDOW}
            )
            is False
        )


class TestBothRoutesMustBeatHolding:
    """The two routes had two different bars for the same question.

    The leverage route always required `lane_final > bh_final`. The spot route required only that
    spot GREW — so $10,000 -> $10,100 passed while buy-and-hold made $12,000, and the identical
    book at leverage did not. `main-objective-find-profitable-signal` is explicit that the honest
    gate is beats-B&H, not "ended above the stake".

    MEASURED BEFORE THE CHANGE (`investigate-before-changing-a-gate`), 63 certs under
    `apps/api/models`: 8 pass, 4 via the spot route, **0 of those 4 lose to B&H**. On that corpus
    this is a no-op — which is why it would NOT be worth making for that corpus alone.

    It is worth making because the SAME predicate gates the continuous-book corpus, where the
    shape is live: `lowvol 1d` printed `promote_gate=True` beside `beats_bh=False`, and VT-17's
    1h leaf grew to $11,654 while holding made $12,062. Concluding "no impact" from
    `apps/api/models` alone would be the one-drawer mistake `capital_cert_lanes` documents.

    CORRECTED 2026-09-21, alongside the spot-route-exclusive-branching fix (GATE_INVENTORY row
    11c). This class's own fixture used to pin ``perp_3x_final`` to a hardcoded $50,000 windfall,
    unrelated to any test's ``spot_final``/``bh_final`` — harmless while the leverage route was
    only ever consulted when spot LOST outright (this class's own fixtures always grow spot), but
    once the gate falls through to the leverage route whenever the SPOT route fails for ANY
    reason (trails B&H, matches it exactly, or its own min-lev lane is wiped), that windfall
    became a silent backdoor: three of this class's tests asserted ``False`` for a cert that, by
    construction, also carried a genuine $50,000 clean committable leverage lane. ``_cert`` now
    tracks ``perp_3x_final`` to the test's own ``spot_final`` (still "not wiped", never an
    independent windfall), which is what the three affected tests below needed to keep testing
    the SPOT route's own bar in isolation.
    """

    @staticmethod
    def _cert(*, spot_final: float, bh_final: float | None) -> dict[str, Any]:
        cert: dict[str, Any] = {
            "status": CAPITAL_CERT_STATUS_CERTIFIED,
            "capital_modes": _modes(spot_final=spot_final, perp_3x_final=spot_final),
            "window": _OOS_WINDOW,
        }
        if bh_final is not None:
            cert["spot_bh_final"] = bh_final
        return cert

    def test_a_book_that_grows_but_trails_holding_no_longer_passes(self) -> None:
        """The lowvol/VT-17-1h shape: grew the account, lost to the market, and no OTHER lane
        in this cert beats holding either (`perp_3x`/`perp_5x` both mirror the same spot_final)."""
        assert cryptobt_capital_cert_passes(self._cert(spot_final=11_654.0, bh_final=12_062.0)) is False

    def test_a_book_that_grows_and_beats_holding_still_passes(self) -> None:
        assert cryptobt_capital_cert_passes(self._cert(spot_final=14_927.0, bh_final=12_045.0)) is True

    def test_matching_the_benchmark_exactly_is_not_beating_it(self) -> None:
        assert cryptobt_capital_cert_passes(self._cert(spot_final=12_045.0, bh_final=12_045.0)) is False

    def test_no_benchmark_recorded_still_passes_on_growth(self) -> None:
        """FAILS OPEN here, unlike the leverage route, and the asymmetry is deliberate.

        Without a benchmark the LEVERAGE claim ("beats holding at leverage") cannot be made at
        all. The spot claim ("spot grew") is still fully evidenced, so refusing it would
        invalidate every legacy cert on a technicality rather than on a finding.
        """
        assert cryptobt_capital_cert_passes(self._cert(spot_final=14_000.0, bh_final=None)) is True

    def test_a_wiped_min_lev_lane_still_fails_when_no_other_lane_survives(self) -> None:
        """Isolates the SPOT route's own internal ordering: renamed from "...still fails before
        the benchmark is consulted" (2026-09-21) -- that phrase described `_spot_route_passes`
        returning early on a wiped min-lev lane WITHOUT reading `bh_final`, which remains true,
        but it is no longer the whole story: the GATE now falls through to the leverage route
        after a failed spot route. This fixture also wipes `perp_5x`/`perp_8x` (which `_modes()`
        otherwise mirrors to `spot_final`) so there is genuinely no surviving lane left to rescue
        the cert -- see the sibling test directly below for the case where one does survive.
        """
        cert = self._cert(spot_final=14_927.0, bh_final=12_045.0)
        for lane in ("perp_3x", "perp_5x", "perp_8x"):
            cert["capital_modes"][lane]["final_capital"] = 0.0
            cert["capital_modes"][lane]["final_balance"] = 0.0

        assert cryptobt_capital_cert_passes(cert) is False

    def test_a_wiped_min_lev_lane_no_longer_sinks_the_whole_cert_when_another_lane_survives(self) -> None:
        """The behaviour change this correction documents: a wiped `perp_3x` used to be read as
        the final word on the whole cert. It is now read as a failed SPOT route only -- if a
        DIFFERENT, clean, committable lane in the same grid survives and beats the same-window
        B&H, that is a real money-maker and the rule (`ml-gate-leverage-capital-cert.md`) says it
        must count, regardless of what happened on an unrelated lower-leverage lane.
        """
        cert = self._cert(spot_final=14_927.0, bh_final=12_045.0)
        cert["capital_modes"]["perp_3x"]["final_capital"] = 0.0
        cert["capital_modes"]["perp_3x"]["final_balance"] = 0.0
        # perp_5x (leverage 5, at the committable cap) is untouched: still mirrors spot_final and
        # beats bh_final, liquidation-clean.

        assert cryptobt_capital_cert_passes(cert) is True


class TestResolvePromoteCapitalPass:
    def test_edge_without_cert_does_not_pass_even_if_smoke_grows(self) -> None:
        assert (
            resolve_promote_capital_pass(
                verdict="edge",
                smoke_initial=10_000.0,
                smoke_final=14_000.0,
                capital_certification=None,
            )
            is False
        )

    def test_edge_with_pending_cert_does_not_pass(self) -> None:
        assert (
            resolve_promote_capital_pass(
                verdict="edge",
                smoke_initial=10_000.0,
                smoke_final=14_000.0,
                capital_certification=build_pending_capital_certification(),
            )
            is False
        )

    def test_edge_with_passing_cryptobt_cert_passes(self) -> None:
        cert = {
            "status": CAPITAL_CERT_STATUS_CERTIFIED,
            "capital_modes": _modes(spot_final=29_675.0, perp_3x_final=234_000.0),
            "window": _OOS_WINDOW,
        }
        assert (
            resolve_promote_capital_pass(
                verdict="edge",
                smoke_initial=10_000.0,
                smoke_final=14_000.0,
                capital_certification=cert,
            )
            is True
        )

    def test_inapplicable_falls_back_to_smoke_compound(self) -> None:
        cert = build_inapplicable_capital_certification(
            harness="inapplicable_vrp_venue",
            reason="VRP venue book",
        )
        assert cert["status"] == CAPITAL_CERT_STATUS_INAPPLICABLE
        assert (
            resolve_promote_capital_pass(
                verdict="edge",
                smoke_initial=10_000.0,
                smoke_final=39_000.0,
                capital_certification=cert,
            )
            is True
        )

    def test_non_edge_uses_smoke_when_cert_absent(self) -> None:
        assert (
            resolve_promote_capital_pass(
                verdict="candidate",
                smoke_initial=10_000.0,
                smoke_final=12_000.0,
                capital_certification=None,
            )
            is True
        )
        assert (
            resolve_promote_capital_pass(
                verdict="scout",
                smoke_initial=10_000.0,
                smoke_final=8_000.0,
                capital_certification=None,
            )
            is False
        )


class TestSpotNegativePerpPositivePasses:
    """A spot-negative / perp-profitable model MUST be certifiable (owner ml-gate rule).

    ``cryptobt_capital_cert_passes`` required ``capital_backtest_passes(init, spot_final)`` — spot
    had to GROW — and then only checked ``perp_3x_final > 0``. That is a spot-AND gate, so a model
    that loses on spot but compounds profitably at leverage without liquidating could NEVER be
    certified, no matter how much money the perp lane made. The rule says the opposite:

      "A model that is marginal or even negative on SPOT but compounds profitably at leverage
       without liquidating ... IS a valid, promotable ML signal."
      "Verdict tier = best over {spot-honest-gate, beats-B&H at the max surviving leverage lane}"

    So the predicate is spot-OR-leverage: spot grew, OR a liquidation-clean leverage lane beat the
    same-window spot B&H final.
    """

    @staticmethod
    def _cert(*, spot_final: float, perp_final: float, bh_final: float | None = None, liq: int = 0, bankrupt: bool = False) -> dict[str, Any]:
        modes = {
            "spot_10k": {"initial_capital": 10_000.0, "final_capital": spot_final, "liquidation_exits": 0, "account_bankrupt": False},
            "perp_3x": {
                "initial_capital": 10_000.0,
                "final_capital": perp_final,
                "liquidation_exits": liq,
                "account_bankrupt": bankrupt,
                "leverage": 3,
            },
        }
        cert: dict[str, Any] = {"status": "certified", "capital_modes": modes, "window": _OOS_WINDOW}
        if bh_final is not None:
            cert["spot_bh_final"] = bh_final
        return cert

    def test_spot_negative_but_perp_beats_bh_passes(self) -> None:
        # spot loses (10k -> 8k) but perp_3x makes 60k vs a 22.4k spot B&H, liquidation-clean
        cert = self._cert(spot_final=8_000.0, perp_final=60_000.0, bh_final=22_448.0)
        assert cryptobt_capital_cert_passes(cert) is True

    def test_spot_negative_and_perp_below_bh_fails(self) -> None:
        cert = self._cert(spot_final=8_000.0, perp_final=15_000.0, bh_final=22_448.0)
        assert cryptobt_capital_cert_passes(cert) is False

    def test_spot_negative_and_perp_liquidated_fails(self) -> None:
        """Money at leverage only counts when the lane survives (liquidation-clean)."""
        cert = self._cert(spot_final=8_000.0, perp_final=60_000.0, bh_final=22_448.0, liq=3)
        assert cryptobt_capital_cert_passes(cert) is False

    def test_spot_negative_and_perp_bankrupt_fails(self) -> None:
        cert = self._cert(spot_final=8_000.0, perp_final=60_000.0, bh_final=22_448.0, bankrupt=True)
        assert cryptobt_capital_cert_passes(cert) is False

    def test_spot_growth_path_still_passes_unchanged(self) -> None:
        """The pre-existing spot-grew route must keep working exactly as before."""
        cert = self._cert(spot_final=14_000.0, perp_final=1.0)
        assert cryptobt_capital_cert_passes(cert) is True

    def test_spot_negative_without_a_bh_reference_cannot_pass_on_leverage(self) -> None:
        """No same-window B&H to beat => cannot claim money-at-leverage; fail closed."""
        cert = self._cert(spot_final=8_000.0, perp_final=60_000.0, bh_final=None)
        assert cryptobt_capital_cert_passes(cert) is False


class TestSpotRouteFallsThroughToTheLeverageRouteWhenItTrailsHolding:
    """GATE_INVENTORY row 11c: spot-route-exclusive branching rejected 5 live money-makers.

    ``cryptobt_capital_cert_passes`` did ``if spot_final ...: return _spot_route_passes(...)`` --
    a spot-EXCLUSIVE branch, not "best of both". Once spot posted ANY positive growth, however
    marginal, the leverage lanes were never even inspected, even when spot TRAILED buy-and-hold.

    Fixture is ``btc_usdt_4h/hist_gradient_boosting_clf/v400/capital_certification.json`` verbatim
    (window 2026-04-03 -> 2026-09-10, a SELECT window, ``window_is_in_sample: false``)::

        spot_bh_final   $11,549.55
        spot_10k        $10,214.53   grew, but TRAILS B&H -- old code stopped here, returned False
        perp_3x         $12,561.75   0 liq, beats B&H -- never inspected by the old code
        perp_4x         $13,415.67   0 liq, beats B&H -- never inspected by the old code
        perp_5x         $14,269.58   0 liq, beats B&H -- never inspected by the old code
        perp_6x/7x/8x   beat B&H too, 0 liq -- never inspected by the old code

    NO LEVERAGE CAP HERE, deliberately. A first draft of this fix also refused any lane above
    ``MAX_COMMITTABLE_LEVERAGE``. Measured over 759 certs it rejected 2 liquidation-clean books the
    fix admits (4h v396, v398), and the cap is a SELECTION rule that select-confirm already applies
    when it freezes levers -- ``ml-gate-leverage-capital-cert.md`` records that a grading-side
    committable filter was removed because it could only ever fire on a survivor.

    ``ml-gate-leverage-capital-cert.md``: "Verdict tier = best over {spot-honest-gate, beats-B&H at
    the max surviving leverage lane}." The code did not try both -- fixed here to fall through to
    the leverage route when spot grew but still lost the comparison, exactly as it already did when
    spot lost outright.
    """

    @staticmethod
    def _v400_shaped(*, liquidate_every_levered_lane: bool = False) -> dict[str, Any]:
        modes = {
            "spot_10k": {
                "initial_capital": 10_000.0,
                "final_capital": 10_214.527380237283,
                "leverage": 0,
                "liquidation_exits": 0,
                "account_bankrupt": False,
            },
            "perp_3x": {
                "initial_capital": 10_000.0,
                "final_capital": 12_561.750369986294,
                "leverage": 3,
                "liquidation_exits": 0,
                "account_bankrupt": False,
            },
            "perp_4x": {
                "initial_capital": 10_000.0,
                "final_capital": 13_415.667159981725,
                "leverage": 4,
                "liquidation_exits": 0,
                "account_bankrupt": False,
            },
            "perp_5x": {
                "initial_capital": 10_000.0,
                "final_capital": 14_269.58394997716,
                "leverage": 5,
                "liquidation_exits": 0,
                "account_bankrupt": False,
            },
            "perp_6x": {
                "initial_capital": 10_000.0,
                "final_capital": 15_123.50073997259,
                "leverage": 6,
                "liquidation_exits": 0,
                "account_bankrupt": False,
            },
            "perp_7x": {
                "initial_capital": 10_000.0,
                "final_capital": 15_977.417529968021,
                "leverage": 7,
                "liquidation_exits": 0,
                "account_bankrupt": False,
            },
            "perp_8x": {
                "initial_capital": 10_000.0,
                "final_capital": 16_831.33431996345,
                "leverage": 8,
                "liquidation_exits": 0,
                "account_bankrupt": False,
            },
        }
        if liquidate_every_levered_lane:
            for lane, row in modes.items():
                if lane != "spot_10k":
                    row["liquidation_exits"] = 2
        return {
            "status": "certified",
            "spot_bh_final": 11_549.547033493238,
            "window": _OOS_WINDOW,
            "capital_modes": modes,
        }

    def test_v400_shaped_cert_now_passes_via_its_leverage_lanes(self) -> None:
        assert cryptobt_capital_cert_passes(self._v400_shaped()) is True

    def test_the_fall_through_still_refuses_lanes_that_liquidated(self) -> None:
        """Same dollars, every levered lane liquidated twice: the fall-through opens the route,
        never the ruin screen. Spot still trails B&H, so nothing may pass."""
        assert cryptobt_capital_cert_passes(self._v400_shaped(liquidate_every_levered_lane=True)) is False

    def test_spot_route_still_passes_unchanged_when_spot_beats_holding(self) -> None:
        """The spot route's own bar (spot beats B&H) is untouched by the new fallback."""
        cert = self._v400_shaped()
        cert["capital_modes"]["spot_10k"]["final_capital"] = 12_000.0  # now beats the $11,549.55 B&H
        assert cryptobt_capital_cert_passes(cert) is True


class TestOrphanedCertIsNotEvidence:
    """A certification whose model artifact is gone cannot be verified, re-run, or deployed.

    Audit 2026-08-04: 15 of 26 local ``capital_certification.json`` files reference a model whose
    ``model.joblib`` no longer exists (wiped by a machine reset, absent from R2) — e.g.
    ``btc_usdt_1d/lightgbm/v3`` and ``btc_usdt_12h/gradient_boosting_clf/v5``, both of which fail
    the cert harness with FileNotFoundError. Those files still LOOK authoritative: they carry lane
    money, drawdowns and a status. Reading one as evidence is an unfalsifiable claim, so the
    predicate must reject it.

    The RULE lives here (pure, per DDD_PATTERNS: domain holds business rules and no I/O); resolving
    the path and stat-ing the artifact is the caller's job.
    """

    @staticmethod
    def _passing_cert() -> dict[str, Any]:
        return {
            "status": "certified",
            "window": _OOS_WINDOW,
            "capital_modes": {
                "spot_10k": {"initial_capital": 10_000.0, "final_capital": 14_000.0},
                "perp_3x": {"initial_capital": 10_000.0, "final_capital": 23_000.0},
            },
        }

    def test_orphaned_cert_cannot_pass(self) -> None:
        assert cryptobt_capital_cert_passes(self._passing_cert(), model_artifact_present=False) is False

    def test_present_artifact_passes_as_before(self) -> None:
        assert cryptobt_capital_cert_passes(self._passing_cert(), model_artifact_present=True) is True

    def test_unknown_artifact_state_preserves_existing_behaviour(self) -> None:
        """Default None = caller did not check; must not change any existing call site."""
        assert cryptobt_capital_cert_passes(self._passing_cert()) is True

    def test_orphan_check_beats_even_the_leverage_route(self) -> None:
        """A missing model invalidates the spot-negative/perp-positive route too."""
        cert = {
            "status": "certified",
            "window": _OOS_WINDOW,
            "spot_bh_final": 22_448.0,
            "capital_modes": {
                "spot_10k": {"initial_capital": 10_000.0, "final_capital": 8_000.0, "liquidation_exits": 0},
                "perp_5x": {"initial_capital": 10_000.0, "final_capital": 60_000.0, "liquidation_exits": 0},
            },
        }
        assert cryptobt_capital_cert_passes(cert, model_artifact_present=True) is True
        assert cryptobt_capital_cert_passes(cert, model_artifact_present=False) is False


class TestADeflatedComboHeadlineMustNotKillALaneMoneyMaker:
    """REGRESSION, and the most expensive lesson of 2026-08-15.

    I added a gate refusing any cert whose ``headline_deflated_sharpe`` fell under the 0.95
    research bar. It looked airtight: the value is computed, written to every cert, and was never
    read, and each cert even says ``"reason": "headline is best-of-N - read
    capital_x_exit.deflated_sharpe before citing it"``. It refused 8 of the 10 certs carrying one.

    It was WRONG, because the two numbers describe DIFFERENT CELLS:

        headline_deflated_sharpe   prices ``capital_x_exit.overall_combo_best`` - ONE cell picked
                                   from 6,000-20,000 combo cells, which is why it deflates to ~0
        this predicate             scores ``capital_modes`` - the SEVEN pre-specified leverage
                                   lanes. Picking among 7 fixed lanes is not a best-of-6,000 search

    Deflating a 7-lane result by a 6,000-cell trial count is wrong by ~three orders of magnitude,
    and it cost a real book. The fixture below is ``btc_usdt_1d/gradient_boosting_clf/v10``
    verbatim: ``headline_deflated_sharpe`` 6.2e-38, while ``capital_modes.perp_3x`` turned $10,000
    into **$14,664 against a $6,797 buy-and-hold - 2.16x, ZERO liquidations, out-of-sample**.

    The owner's question is the standard this test now enforces: *"Fails WHAT? Money maker or
    metrics?? What is your main objective?"* The objective is money. A book with a
    liquidation-clean lane beating buy-and-hold must not be refused by a statistic that belongs to
    a different cell.

    The DSR remains the right question WHERE THE COMBO HEADLINE IS CITED (ledger, publish, tier
    copy) - never where fixed lanes are scored. Corpus-level enforcement of the same principle:
    ``scripts/check_discarded_money_makers.py``, verify step 2h.
    """

    @staticmethod
    def _v10_shaped() -> dict[str, Any]:
        return {
            "status": "capital_x_exit_certified",
            "window": _OOS_WINDOW,
            "spot_bh_final": 6_796.614516542702,
            # ~0: the combo headline is best-of-thousands. It says nothing about the lanes below.
            CERT_HEADLINE_DSR_KEY: 6.178729527695393e-38,
            "capital_modes": {
                "spot_10k": {
                    "initial_capital": 10_000.0,
                    "final_capital": 10_201.76,
                    "liquidation_exits": 0,
                    "account_bankrupt": False,
                },
                "perp_3x": {
                    "initial_capital": 10_000.0,
                    "final_capital": 14_664.227946171812,
                    "liquidation_exits": 0,
                    "account_bankrupt": False,
                    "leverage": 3,
                },
            },
        }

    def test_a_lane_money_maker_survives_a_deflated_combo_headline(self) -> None:
        """2.16x buy-and-hold, liquidation-clean, out-of-sample - this must PASS."""
        assert cryptobt_capital_cert_passes(self._v10_shaped()) is True

    def test_the_money_verdict_does_not_move_with_the_combo_dsr(self) -> None:
        """The lane result is the same book whatever the combo grid's best-of-N deflates to."""
        for dsr in (0.0, 6.2e-38, 0.5, 0.9075, 0.99, 1.0):
            cert = self._v10_shaped()
            cert[CERT_HEADLINE_DSR_KEY] = dsr
            assert cryptobt_capital_cert_passes(cert) is True, f"combo DSR {dsr} moved a LANE verdict"

    def test_a_lane_that_loses_to_holding_still_fails(self) -> None:
        """Guard the other direction: this must not become a licence to pass losers."""
        cert = self._v10_shaped()
        cert[CERT_HEADLINE_DSR_KEY] = 1.0
        cert["spot_bh_final"] = 99_000.0
        assert cryptobt_capital_cert_passes(cert) is False

    def test_a_liquidated_lane_still_fails(self) -> None:
        """Money at leverage counts only from a lane that SURVIVED."""
        cert = self._v10_shaped()
        cert["capital_modes"]["spot_10k"]["final_capital"] = 8_000.0
        cert["capital_modes"]["perp_3x"]["liquidation_exits"] = 4
        assert cryptobt_capital_cert_passes(cert) is False


class TestAMissingSpotRowMustNotDiscardALeverageMoneyMaker:
    """A cert with no ``spot_10k`` row returned False before the perp lanes were ever read.

    Owner, 2026-08-15: *"FIX!! ARE YOU MAKING MONKEY CODE?"* — about exactly this.

    ``cryptobt_capital_cert_passes`` did::

        spot_final = _lane_final(modes, _SPOT_LANE)
        if spot_final is None or _lane_is_bankrupt(modes, _SPOT_LANE):
            return False

    A MISSING spot row is not a losing spot row. It means the grid published no spot cell, which
    says nothing about the leverage lanes -- and ``ml-gate-leverage-capital-cert.md`` is explicit
    that a book "marginal or even negative on SPOT but compounding profitably at leverage without
    liquidating IS a valid, promotable ML signal". Bailing there denies the leverage route the
    rule exists to grant.

    MEASURED COST, 2026-08-15, over the 63 certs under ``apps/api/models`` -- 2 books, both real:

        btc_usdt_1d/lightgbm/v36                 $10,000 -> $16,165 vs $5,614 B&H = 2.88x
                                                 perp_8x, MTM DD -17.4%, ZERO liquidations, OOS
        btc_usdt_8h/hist_gradient_boosting_clf/v149  $10,000 -> $11,099 vs $7,248 B&H = 1.53x
                                                 perp_8x, MTM DD -5.6%, ZERO liquidations, OOS

    v36 nearly TRIPLED buy-and-hold out-of-sample and was filed as failed because a field was
    absent from a JSON file.

    Bankruptcy still fails closed: a spot row that EXISTS and is bankrupt is evidence, and
    ``_leverage_route_passes`` keeps requiring a liquidation-clean lane above the same-window
    benchmark, so this widens the gate only where there was never any evidence to weigh.
    """

    @staticmethod
    def _no_spot_row(*, perp_final: float, bh_final: float, liq: int = 0) -> dict[str, Any]:
        """v36-shaped: no spot_10k key at all, money in a clean perp lane."""
        return {
            "status": CAPITAL_CERT_STATUS_CERTIFIED,
            "window": _OOS_WINDOW,
            "spot_bh_final": bh_final,
            "capital_modes": {
                "perp_8x": {
                    "initial_capital": 10_000.0,
                    "final_capital": perp_final,
                    "liquidation_exits": liq,
                    "account_bankrupt": False,
                    "leverage": 8,
                }
            },
        }

    def test_v36_shaped_leverage_money_maker_is_no_longer_discarded(self) -> None:
        """2.88x buy-and-hold, liquidation-clean, out-of-sample, no spot row -> must PASS."""
        assert cryptobt_capital_cert_passes(self._no_spot_row(perp_final=16_165.0, bh_final=5_614.0)) is True

    def test_v149_shaped_smaller_but_real_money_maker_passes(self) -> None:
        assert cryptobt_capital_cert_passes(self._no_spot_row(perp_final=11_099.0, bh_final=7_248.0)) is True

    def test_a_liquidated_lane_still_fails_without_a_spot_row(self) -> None:
        """Widened for missing evidence only -- ruin is still ruin."""
        assert cryptobt_capital_cert_passes(self._no_spot_row(perp_final=16_165.0, bh_final=5_614.0, liq=2)) is False

    def test_a_lane_that_loses_to_holding_still_fails_without_a_spot_row(self) -> None:
        assert cryptobt_capital_cert_passes(self._no_spot_row(perp_final=6_000.0, bh_final=9_000.0)) is False

    def test_no_benchmark_and_no_spot_row_cannot_claim_anything(self) -> None:
        """With neither a spot claim nor a benchmark to beat, there is no evidence at all."""
        cert = self._no_spot_row(perp_final=16_165.0, bh_final=5_614.0)
        del cert["spot_bh_final"]
        assert cryptobt_capital_cert_passes(cert) is False

    def test_a_bankrupt_spot_row_that_exists_still_fails(self) -> None:
        """A present-and-bankrupt spot row is evidence; only ABSENCE is what this stops reading."""
        cert = self._no_spot_row(perp_final=16_165.0, bh_final=5_614.0)
        cert["capital_modes"]["spot_10k"] = {
            "initial_capital": 10_000.0,
            "final_capital": 0.0,
            "account_bankrupt": True,
        }
        assert cryptobt_capital_cert_passes(cert) is False


class TestBestCleanLaneWealth:
    """The money question, answerable from a cert without re-deriving it by hand.

    Every registry row carried `capital_final: null` while 29 certs held real money, because
    nothing in `src/` read the second lane layout. A tier nobody can audit is a claim, not
    evidence.
    """

    _GRID = {
        "spot_bh_final": 10_000.0,
        "capital_modes": {},
        "capital_x_exit": {
            "best_by_capital_lane": {
                "spot_10k": {"best": {"final_capital": 12_000.0, "liquidation_exits": 0}, "n_valid": 3},
                "perp_5x": {"best": {"final_capital": 90_000.0, "liquidation_exits": 4}, "n_valid": 3},
                "perp_3x": {"best": {"final_capital": 40_000.0, "liquidation_exits": 0}, "n_valid": 3},
            }
        },
    }

    def test_reads_the_grid_layout_not_only_capital_modes(self) -> None:
        assert set(capital_cert_lanes(self._GRID)) == {"spot_10k", "perp_5x", "perp_3x"}

    def test_picks_the_richest_liquidation_clean_lane(self) -> None:
        """perp_5x is far richer and liquidated 4 times - ranking on money alone promotes ruin."""
        best = best_clean_lane_wealth(self._GRID)
        assert best is not None
        assert best["lane"] == "perp_3x"
        assert best["final_capital"] == 40_000.0
        assert best["wealth_vs_bh"] == 4.0
        assert best["beats_bh_wealth"] is True

    def test_direct_capital_modes_still_work(self) -> None:
        """The `capital_modes` layout is read, and a PROFITABLE lane that trails B&H is reported.

        This test is about the LAYOUT, not about profitability. Its original fixture returned
        $8,000 from $10,000 and expected that lane back — which the later ABSOLUTE-GROWTH screen
        correctly skips, so the fixture, not the screen, was stale. A lane that grows the account
        while still trailing buy-and-hold is the case that actually exercises both branches.
        """
        cert = {
            "spot_bh_final": 20_000.0,
            "capital_modes": {"spot_10k": {"final_capital": 12_000.0}},
        }

        best = best_clean_lane_wealth(cert)

        assert best is not None
        assert best["wealth_vs_bh"] == 0.6
        assert best["beats_bh_wealth"] is False

    def test_a_lane_that_loses_money_is_skipped_even_when_it_beats_bh(self) -> None:
        """The absolute-growth screen, pinned on the capital_modes path too.

        Measured cost of not having it: `8h lightgbm v150` turned $10,000 into $9,457 and ranked
        SEVENTH on a 1.67x multiple, purely because buy-and-hold lost more. The objective is making
        money for users, not losing more slowly than BTC.
        """
        cert = {
            "spot_bh_final": 5_000.0,
            "capital_modes": {"spot_10k": {"final_capital": 8_000.0}},
        }

        assert best_clean_lane_wealth(cert) is None

    def test_no_benchmark_means_no_answer(self) -> None:
        """Without a same-window B&H the multiple is unanswerable; do not invent a flattering one."""
        assert best_clean_lane_wealth({"capital_modes": {"spot_10k": {"final_capital": 99_000.0}}}) is None

    def test_all_lanes_dirty_means_no_answer(self) -> None:
        cert = {
            "spot_bh_final": 10_000.0,
            "capital_modes": {"perp_8x": {"final_capital": 5e6, "account_bankrupt": True}},
        }
        assert best_clean_lane_wealth(cert) is None

    def test_carries_the_window_flag_so_a_multiple_is_never_read_bare(self) -> None:
        """A 7x multiple on an in-sample window is not the same claim as 4x on unseen data."""
        cert = {**self._GRID, "window": {"window_is_in_sample": True}}
        best = best_clean_lane_wealth(cert)
        assert best is not None
        assert best["window_is_in_sample"] is True


class TestCertArtifactSupportsProductionPromote:
    """production_promoted needs money-grade evidence, not an IC label plus a cert link."""

    def test_none_is_not_promotable(self) -> None:
        assert cert_artifact_supports_production_promote(None) is False

    def test_levered_without_funding_is_not_promotable(self) -> None:
        cert = {
            "harness": "levered_return_book",
            "funding_modelled": False,
            "spot_bh_final": 12_000.0,
            "variants": {
                "x": {
                    "lanes": {
                        "spot_10k": {
                            "publishable": True,
                            "leverage": 1.0,
                            "final_capital": 40_000.0,
                        },
                        "perp_3x": {
                            "publishable": False,
                            "leverage": 3.0,
                            "final_capital": 500_000.0,
                        },
                    }
                }
            },
        }
        assert cert_artifact_supports_production_promote(cert) is False

    def test_levered_with_funding_and_publishable_perp_is_promotable(self) -> None:
        cert = {
            "harness": "levered_return_book",
            "funding_modelled": True,
            "spot_bh_final": 12_000.0,
            "variants": {
                "x": {
                    "lanes": {
                        "perp_3x": {
                            "publishable": True,
                            "leverage": 3.0,
                            "final_capital": 40_000.0,
                            "liquidation_exits": 0,
                            "max_drawdown": -0.1,
                        }
                    }
                }
            },
        }
        assert cert_artifact_supports_production_promote(cert) is True
