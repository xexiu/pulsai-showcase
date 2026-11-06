# ADR-022: API idempotency posture — money path is covered; defer automated-dispatch dedup hardening

## Status

**Accepted** — 2026-06-20

Records a decision and ships no code. The one residual hardening (Decision §3)
is a separate, research-first + product-signed-off TDD slice.

## Context

A "4 advanced REST patterns senior engineers use" article (Stackademic) put
**idempotency keys** forward as a senior pattern most APIs lack. An
investigation of the PulsAI money/trade path (2026-06-20) found the opposite:
idempotency is already implemented broadly — and more robustly than the
article's naive "cache the result for 24h" (which has a check-then-act race).
This ADR exists because the posture was not captured in one place.

### Existing idempotency mechanisms (audit 2026-06-20)

| Mechanism              | Anchor                                                                  | Protects                              | Race-safe?   |
| ---------------------- | ----------------------------------------------------------------------- | ------------------------------------- | ------------ |
| General HTTP primitive | `application/services/api_http_idempotency_service.py` (`run()`)        | All keyed mutating endpoints (replay) | YES          |
| Shared lock infra      | `infrastructure/persistence/{advisory_lock,idempotency_scope_mixin}.py` | Concurrent duplicate-submission race  | YES          |
| Stripe webhook dedup   | `application/billing/stripe_webhook_handlers.py::claim_stripe_event_id` | Retried Stripe deliveries             | YES          |
| Demo order placement   | `infrastructure/persistence/demo_trading_repository.py`                 | Demo `POST /orders` double-placement  | YES          |
| Paper trade placement  | `alembic/.../20260420_paper_trading_idempotency.py`                     | Paper order double-placement          | YES (UNIQUE) |
| Automation tick dedupe | `application/services/automation_executor_run_service.py`               | Same-signal-bar double-fire           | Coarse (bar) |

The general primitive (`ApiHttpIdempotencyService`) combines a PG
`pg_advisory_xact_lock`, a `UNIQUE(user_id, idempotency_key)` receipt row, JSON
response replay, and key-reuse rejection — it is already injected as a FastAPI
dependency across billing checkout/portal, admin refund, automation
create/promote/patch/select, exchange connect/verify/disconnect, and admin
user/system actions. The Stripe path uses
`INSERT … ON CONFLICT DO NOTHING RETURNING` on the `stripe_event_id` primary
key. Both are strictly stronger than the article's pattern.

### Residual gap

`application/services/ccxt_auto_order_dispatcher.py::CcxtAutoOrderDispatcher.place_auto_order`
(automated live/paper, Celery-triggered) passes `idempotency_key` as the venue
`clientOrderId` and calls `exchange.create_order(...)` directly, with **no
BE-side dedup claim before submission**. A Celery retry after a network timeout
(order sent, response lost) re-enters the method and re-submits; the only guard
is the exchange's own `clientOrderId` handling, which is venue-specific and
neither validated nor persisted by the BE. The per-bar `_same_closed_bar_dedupe`
covers the common double-fire but not retry-after-timeout within the same bar.

## Decision Drivers

1. Don't reinvent — the reusable primitive (`ApiHttpIdempotencyService`,
   `IdempotencyScopeMixin`) already exists.
2. The residual gap is in **live real-money order dispatch** — the highest
   blast radius in the system.
3. Correct BE-side dedup depends on actual venue retry semantics (Binance /
   Bitget duplicate-`clientOrderId` behaviour on a `create_order` retry), which
   is currently unverified.
4. Don't build safety-critical money code mid-session into a tree carrying ~580
   unrelated parallel-dev changes (can't be cleanly coverage-gated).

## Considered Options

### Option A — Capture posture, defer dispatch hardening behind research + sign-off (Chosen)

### Option B — Add BE-side dedup to `place_auto_order` now — Rejected

Touches live money execution on an article's prompt, without validating venue
semantics, and cannot be cleanly coverage-gated in the current tree. Risk ≫
benefit: exchange `clientOrderId` + the per-bar dedupe already cover the common
cases.

### Option C — Add idempotency to `POST /orders/cancel` — Rejected

Cancel is state-machine-protected: a duplicate cancel of an already-cancelled
order is a benign no-op error, not financial harm. Adding receipt machinery is
gold-plating and changes the endpoint contract.

## Decision

1. **No production code** in this change.
2. **Affirm the existing posture:** any new mutating endpoint MUST reuse
   `ApiHttpIdempotencyService` (add the dependency + `Idempotency-Key` header +
   an `HTTP_IDEM_OP_*` constant) — never hand-roll dedup.
3. **Defer** BE-side dedup for `CcxtAutoOrderDispatcher` to a dedicated slice
   gated on the criteria below; treat it as a money-path change requiring
   product sign-off.

## Success Criteria

- `place_auto_order` claims a dedup receipt (reusing `IdempotencyScopeMixin` /
  the advisory lock) **before** `exchange.create_order`; a retry with the same
  key returns the original outcome without a second submission.
- Behaviour is verified against **documented venue semantics**, not assumed.
- **Zero** new bespoke dedup primitive — existing infrastructure is reused.

## Validation Criteria

- A research note records Binance + Bitget duplicate-`clientOrderId` behaviour
  on `create_order` retry-after-timeout (including how CCXT surfaces it), with
  citations.
- Behaviour tests: (a) duplicate key → single submission + replayed outcome;
  (b) distinct keys → two submissions; (c) concurrent duplicates serialize via
  the advisory lock. Targeted suite green; BE coverage ≥ 80% on touched files.
- A documented testnet/sandbox integration check confirms no double-fill on a
  forced retry.

## Consequences

### Positive

- The idempotency posture is documented in one place; reuse is enforced.
- The safety-critical change is gated, not rushed.

### Negative / Trade-offs

- The retry-after-timeout window on automated dispatch persists until the slice
  lands — mitigated by exchange `clientOrderId` + the per-bar dedupe.

### Non-goal

- This ADR ships no code; the deferred slice carries the Success / Validation
  criteria above as its done-definition.

## References

- Article: "Stop Designing REST APIs Like a Mid-Level Dev — 4 Advanced
  Patterns" (Stackademic).
- Investigation 2026-06-20: `api_http_idempotency_service.py`,
  `idempotency_scope_mixin.py`, `advisory_lock.py`, `demo_trading_repository.py`,
  `ccxt_auto_order_dispatcher.py`, `stripe_webhook_handlers.py`.
- Related: [ADR-003](../04-structural/adr/003-concurrency-defense-without-fencing-tokens.md)
  (concurrency defense without fencing tokens),
  [BILLING_API_SECURITY.md](../02-technical/BILLING_API_SECURITY.md),
  [LIVE_DIRECT_ARCHITECTURE.md](../02-technical/LIVE_DIRECT_ARCHITECTURE.md).
