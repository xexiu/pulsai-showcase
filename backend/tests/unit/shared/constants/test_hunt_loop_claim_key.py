"""The hunt-loop enqueue claim key identifies a RUN, not just a hypothesis.

REUSE-AUDIT: considered src/infrastructure/cache/redis_ttl_lock.py (the SETNX primitive this builds
on and does not replace); src/shared/constants/runtime.py::build_training_lock_key (the sibling key
builder whose shape and placement this follows); src/workers/tasks/training_job_lock.py (the sync
client + non-blocking lock pattern for the worker side). No existing key covers hunt-loop enqueues.

WHY THIS EXISTS. MEASURED on the live broker 2026-08-30: the `training` queue held 21
`run_hunt_loop_now` messages, of which 18 were the identical
`(['seasonality'], high_timeframes=True, apply=True)` triple. They were NOT redeliveries - 21
distinct task ids, `retries=0` on every one, from 9 different API processes. Each was a fresh
`POST /admin/research-registry/run-loop`, re-asked over days because the previous one had not
finished. Two `run_capital_cert_task` messages - the money work - sat behind all of them.

The claim must key on the same triple the worker actually runs with, because
`run_hunt_loop_now` takes `high_timeframes` and `apply` as per-run arguments bound at enqueue.
Keying on the hypothesis alone would wrongly collapse a dry run and an applying run into one.
"""

from __future__ import annotations

from src.shared.constants.runtime import (
    HUNT_LOOP_CLAIM_KEY_PREFIX,
    build_hunt_loop_claim_key,
)


class TestTheKeyIdentifiesTheWholeRun:
    def test_same_triple_gives_the_same_key(self) -> None:
        first = build_hunt_loop_claim_key("seasonality", high_timeframes=True, apply=True)
        second = build_hunt_loop_claim_key("seasonality", high_timeframes=True, apply=True)

        assert first == second

    def test_a_dry_run_is_not_the_same_claim_as_an_applying_run(self) -> None:
        """`apply` changes what the run DOES, so it must not be deduplicated against."""
        dry = build_hunt_loop_claim_key("seasonality", high_timeframes=True, apply=False)
        applying = build_hunt_loop_claim_key("seasonality", high_timeframes=True, apply=True)

        assert dry != applying

    def test_the_timeframe_band_is_part_of_the_identity(self) -> None:
        high = build_hunt_loop_claim_key("seasonality", high_timeframes=True, apply=True)
        low = build_hunt_loop_claim_key("seasonality", high_timeframes=False, apply=True)

        assert high != low

    def test_different_hypotheses_never_collide(self) -> None:
        seasonality = build_hunt_loop_claim_key("seasonality", high_timeframes=True, apply=True)
        carry = build_hunt_loop_claim_key("carry_vt17_validate", high_timeframes=True, apply=True)

        assert seasonality != carry

    def test_the_key_is_namespaced_like_its_siblings(self) -> None:
        """A bare key would collide across test and dev runtimes sharing one Redis."""
        key = build_hunt_loop_claim_key("seasonality", high_timeframes=True, apply=True)

        assert key.startswith(HUNT_LOOP_CLAIM_KEY_PREFIX)
        assert HUNT_LOOP_CLAIM_KEY_PREFIX.startswith("pulsai:")

    def test_whitespace_and_case_do_not_create_a_second_claim(self) -> None:
        """The route strips the name; the key must not be fooled by what it does not strip."""
        plain = build_hunt_loop_claim_key("seasonality", high_timeframes=True, apply=True)
        padded = build_hunt_loop_claim_key("  Seasonality  ", high_timeframes=True, apply=True)

        assert plain == padded
