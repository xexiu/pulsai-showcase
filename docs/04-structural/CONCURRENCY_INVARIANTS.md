# Concurrency Invariants (SoT)

> **Last updated:** 2026-05-19 (audit slice after Slice-A activity gates + Slice-B optimistic-lock mappers)
> **Purpose:** Where pulsai's concurrency hazards live, which mechanism protects each one, and what NOT to add.
> **Policy authority:** [DDD_PATTERNS.md](./DDD_PATTERNS.md), [CODING_STANDARDS.md](./CODING_STANDARDS.md), ADR-003.

---

## Pulsai's concurrency model in one paragraph

Pulsai runs **one** uvicorn worker per API container (asyncio cooperative concurrency, no threads) and **N** Celery prefork workers per task container (multi-process parallelism, no in-process shared state across workers). C-extension threading is force-disabled at module load (`OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, etc.) so prefork's `fork()` semantics never re-enter unsafe C state. The monitoring + OHLCV-stream + alerts queues use `--pool=solo` to add a second layer of fork-safety for tasks that load PyTorch / FinBERT / persistent WebSocket clients.

That model means **the only shared state across concurrent actors is the database (PG/Timescale) and Redis**. Every concurrency invariant in pulsai is therefore enforced at the DB or Redis layer — never in-process.

---

## The two-layer defense (current SoT)

| Layer               | Mechanism                                                                                          | Role                                                                                   | Where                                                                                                                                                               |
| ------------------- | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1 — Performance** | Redis SETNX TTL lock                                                                               | Prevents _most_ concurrent execution of the same critical section. Cheap, best-effort. | [`infrastructure/cache/redis_ttl_lock.py`](../../apps/api/src/infrastructure/cache/redis_ttl_lock.py)                                                               |
| **2 — Correctness** | PG `version` column + `version_id_col` ORM mapper config + Core `WHERE id=? AND version=?` updates | Catches concurrent commits **even when Layer 1 expires mid-work**.                     | `paper_trading_model.py`, [`demo_trading_model.py`](../../apps/api/src/infrastructure/persistence/demo_trading_model.py), `paper_trading_repository_*_lifecycle.py` |

The **`version` column is the fencing token, and PG is the validator**. Any UPDATE that touches a `version`-bearing row emits `... WHERE version = :loaded` automatically (ORM flush) or explicitly (Core update). If the WHERE matches zero rows, the slow writer either gets `StaleDataError` (ORM) or `result.rowcount == 0` (Core) and must retry or abort.

This is functionally equivalent to Martin Kleppmann's fencing-token pattern, with `version` taking the role of the monotonically-increasing token. We do **not** maintain a separate fencing-token sequence — see [ADR-003](./adr/003-concurrency-defense-without-fencing-tokens.md).

---

## What each mechanism actually protects

| Concurrency hazard                                                          | Mechanism today                                                                                            | Status                                            |
| --------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| Two API workers receive the same `place_market_order` (HTTP retry)          | HTTP `Idempotency-Key` header → `DemoTradingIdempotency` / `PaperTradingIdempotency` unique-constraint row | ✅ at-most-once                                   |
| Two Celery workers grab same lifecycle reconciliation task                  | `paper_lifecycle_order_lock(user_id, ccxt_order_id)` Redis TTL lock                                        | ✅ layer 1                                        |
| Celery worker crashes mid-reconciliation, TTL expires, second worker enters | PG version check on every UPDATE (Core + ORM mapper)                                                       | ✅ layer 2                                        |
| Two pollers wake up and both try to close the same bracket                  | Redis TTL lock (per-order) + ORM `version_id_col` on `PaperOrder`                                          | ✅ both layers                                    |
| `+= 1` on a counter field across an `await` boundary in a FastAPI handler   | Manual code review — **no general protection**                                                             | ⚠️ no in-process protection, see "What NOT to do" |
| Worker forks an already-imported PyTorch/FinBERT pipeline                   | `--pool=solo` for the monitoring queue; `OMP_NUM_THREADS=1` etc. for prefork                               | ✅ design invariant                               |

---

## What NOT to do

1. **Do not add a counter field that's mutated by FastAPI handlers across `await` boundaries.** Asyncio cooperative scheduling is NOT atomic for read-modify-write. Either (a) push the counter into PG with `UPDATE x SET counter = counter + 1` (atomic at the DB), or (b) use Redis `INCR` (atomic at the broker). Never `obj.counter += 1; await session.commit()`.

2. **Do not bypass the version bump on a `version`-bearing model.** The current SoT for the bump is application code (see `version_id_generator=False` rationale in the model docstrings). Skipping the bump means the version stays stale, and the next concurrent writer may see a WHERE match it shouldn't. If you add a new mutation path, add `obj.version += 1` (or equivalent) before flush/commit.

3. **Do not introduce in-process `threading.Lock` / `asyncio.Lock` for cross-task coordination.** A lock in worker process A does not coordinate with worker process B. Use the Redis TTL lock for cross-process coordination. The only legitimate use of `asyncio.Lock` is **within a single asyncio event loop** to serialize coroutines (e.g. [`redis_client.py`](../../apps/api/src/infrastructure/cache/redis_client.py) singleton init).

4. **Do not assume prefork workers share module-level state.** `_FINBERT_PIPE`, `_redis_client`, and any other module-level singleton is **per-child-process** after fork. This is a feature (no races), not a bug.

5. **Do not raise `WEB_CONCURRENCY` casually — and it is now enforced, not just advised.**
   The API boots single-worker by design and **nothing elects a leader**, so every one of the 16
   `src/api/lifespan` steps runs once per worker: the Telegram poller answers `getUpdates` 409
   Conflict against itself, the spike watcher pages admins N times per incident, and the shared
   OHLCV fetcher opens N exchange connections. Rule 4 above then bites a second time — the
   redis / db / endpoint metric ring buffers, the loop-lag sampler and the offender streaks are
   all module-level, so each worker sees **1/N of traffic against a 20-sample alert floor**, and
   `/admin/health/observability` answers from whichever worker got the request. The pager quietly
   loses resolution exactly when load is highest.

   `ensure_worker_count_is_safe` (`shared/constants/api_runtime.py`, wired as the
   `verify_worker_count` startup step) refuses the boot unless `PULSAI_ALLOW_MULTI_WORKER=1`
   acknowledges those hazards. A malformed value still boots on one worker — a stray character
   must not be able to produce a dead API.

   **And it was measured, not assumed** (2026-09-06, one full dashboard load: 43 authenticated
   requests, every served timeframe x every indicator set, single worker, each arm after draining
   the loop-lag ring buffer):

   | client schedule         | loop lag max | redis EXISTS p95 | status |
   | ----------------------- | ------------ | ---------------- | ------ |
   | deferred (ships today)  | 0.045 s      | 0.010 s          | ok     |
   | burst (pre-`3d52fa586`) | 0.379 s      | 0.101 s          | warn   |

   The saturation that motivated scaling out was the **client's arrival pattern**, and fixing it
   there removed 8.5x of loop stall. One worker has headroom, so more workers would be premature
   distribution (ARCHITECTURE_PATTERNS section 9.3) bought at the cost of the hazards above.

   The worker count also has exactly **one spelling**: `WEB_CONCURRENCY`, which uvicorn reads
   natively when `--workers` is omitted. `docker-compose.prod.yml` used to hardcode `--workers 4`
   on the CLI, which bypasses the variable — so the documented knob and the real count disagreed,
   and the guard could not see that path at all.

6. **Do not implement fencing tokens.** See [ADR-003](./adr/003-concurrency-defense-without-fencing-tokens.md) — the two-layer defense is sufficient at pulsai's scale.

---

## Trading-activity gate (poller short-circuit)

A separate concurrency-adjacent mechanism: the four polling tasks (demo brackets, paper brackets, paper pending fills, paper limit lifecycle) gate their expensive HTTP + DB work behind a Redis flag set per subsystem. **This is NOT a correctness mechanism** — it's a cost optimization that avoids redundant work when no user has open activity in that subsystem. SoT:

- Subsystem ids: [`shared/constants/trading_activity_flags.py`](../../apps/api/src/shared/constants/trading_activity_flags.py)
- Flag operations: [`infrastructure/cache/trading_activity_flags.py`](../../apps/api/src/infrastructure/cache/trading_activity_flags.py)
- Lifecycle gate helper (extracted to keep facade under 150 LOC): `workers/tasks/paper_trading_lifecycle_gate.py`

The gate fails open: a Redis outage causes pollers to fall back to the existing DB-truth probe, never to silently skip work. The kill-switch env vars (`PAPER_TRADING_LIFECYCLE_SYNC_ENABLED`) remain the manual ops backup.

---

## Boot-time broker hygiene (orphan-beat protection)

A second concurrency-adjacent mechanism handles a failure mode that two-layer defense and the activity gate cannot: **stale broker messages from a beat process whose task module no longer exists**. When a Celery task module is deleted, lingering messages produced by an orphan beat (a prior dev-shell session that wasn't killed, or a crashed Railway deploy that briefly republished) sit in the priority-stepped Redis lists. Workers reject them with `Received unregistered task` but `task_acks_late=True` + an orphan producer faster than worker drain means the queue grows monotonically and error spam never stops on its own. Production incident on 2026-05-21 saw `monitoring\x06\x166` accumulate **28,072 messages** (~33% of them addressed to deleted modules) across five different orphan beat PIDs.

Two idempotent housekeeping passes run **before any worker comes online**, both wired into local dev (`scripts/lib/run_celery_workers.sh`) and Railway containers (`apps/api/entrypoint.sh`):

| Pass                  | What it prunes                                                                                                           | Where                                                                                     |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| RedBeat schedule sync | Static schedule entries in Redis whose key is gone from `BEAT_SCHEDULE`, plus schedule rows whose task isn't registered  | [`workers/redbeat_schedule_sync.py`](../../apps/api/src/workers/redbeat_schedule_sync.py) |
| Broker queue sync     | Broker list messages whose task isn't in `app.tasks`, across every `task_routes` queue × Kombu priority step `[0,3,6,9]` | [`workers/broker_queue_sync.py`](../../apps/api/src/workers/broker_queue_sync.py)         |

Both passes share [`workers/celery_app_introspection.py`](../../apps/api/src/workers/celery_app_introspection.py) for app resolution and task-module loading (SoT, no DRY). Both are atomic per queue (RENAME → filter → RPUSH) and tolerate interrupted prior runs (a shadow `<key>.pruning` key is recovered on the next boot). Both are CLI-invocable for ad-hoc cleanup: `python -m src.workers.{redbeat_schedule_sync,broker_queue_sync}`.

**Why this is a concurrency invariant**, not just hygiene: an orphan beat is a second writer to the broker that the running beat doesn't know about, and a deleted task module breaks the consumer-side invariant that "every queued task has a strategy". The boot-time prune restores both invariants before any worker observes them.

---

## Solo-pool warm-shutdown compatibility

Celery's warm-shutdown path (SIGINT/SIGTERM with an in-flight task) calls `pool.terminate_job(pid, signal)` on every active `Request`. For prefork pools that signals the child PID; for `--pool=solo` pools — which the monitoring and ohlcv_stream queues require for fork-safety (see ["Worker pool topology" in ARCHITECTURE.md](../02-technical/ARCHITECTURE.md)) — `terminate_job` inherits `BasePool`'s `NotImplementedError("...does not implement kill_job")`. The exception aborts the rest of the cancellation loop, so more messages get redelivered by `task_acks_late` than necessary and `Ctrl+C` produces a noisy traceback in dev.

[`workers/celery_solo_pool_compat.py`](../../apps/api/src/workers/celery_solo_pool_compat.py) overrides `solo.TaskPool.terminate_job` to be a logging no-op. The patch is applied once at `celery_app.py` import (idempotent). Solo runs tasks inline in the main worker process — there is no child to signal — so letting the in-flight task complete (or die with the worker) is the correct behaviour; `task_acks_late=True` then redelivers it cleanly on the next boot. Prefork's `terminate_job` is untouched (class-scoped patch).

A regression test pins the upstream limitation: when Celery eventually implements `solo.TaskPool.terminate_job` itself, `test_unpatched_solo_pool_raises_not_implemented` flips and the patch can be removed.

---

## Solo-pool memory guard (RSS watchdog)

`worker_max_memory_per_child` recycles prefork **children** once their RSS crosses a cap — but it is a **no-op for `--pool=solo`** workers, which run tasks inline in the main process with no child to recycle. The two solo workers (`monitoring`, `ohlcv_stream`) therefore had **no memory bound at all**: on Railway the monitoring worker grew from a 261 MB import baseline to ~2.4–2.8 GB resident (~46% of the memory bill) before this guard.

[`workers/celery_solo_rss_watchdog.py`](../../apps/api/src/workers/celery_solo_rss_watchdog.py) is the solo equivalent: a `task_postrun` handler samples resident memory after each task and, above the SoT cap `CELERY_SOLO_RSS_WATCHDOG_MAX_KIB` (env `CELERY_SOLO_RSS_WATCHDOG_MAX_KIB`, default 900 MiB; `0` disables), sends the worker a `SIGTERM` (Celery warm shutdown). With `task_acks_late=True` the in-flight message is redelivered and Railway's `restartPolicyType: ALWAYS` respawns a fresh worker — bounding memory deterministically **without any fork** (so the PyTorch/FinBERT fork-safety invariant above is preserved).

`arm_solo_rss_watchdog()` runs at `celery_app.py` import but self-gates on `--pool=solo` in argv, so prefork workers (which keep their own recycler), the API, and beat are never touched. Verify with `scripts/railway/railway_mem_snapshot.py watch` (per-service RSS over time should plateau below the cap). Tests: `tests/unit/workers/test_celery_solo_rss_watchdog.py`.

---

## Audit checklist for new code

Before merging code that mutates a row with a `version` column:

- [ ] All ORM flushes happen with the version-id mapper active (already wired on `DemoPortfolio`, `PaperOrder`, `PaperPosition`).
- [ ] All Core `update(...)` statements include `WHERE id=? AND version=?` and bump version on the SET clause.
- [ ] All callers handle `StaleDataError` (ORM) or `rowcount == 0` (Core) — retry, abort, or compensate.
- [ ] Long-running Celery tasks that hold a Redis TTL lock: the TTL is **larger** than the realistic task duration, AND the writes inside are independently protected by the version check (so a TTL expiry mid-work cannot corrupt state).

---

## Related

- [ADR-003: Concurrency defense without fencing tokens](./adr/003-concurrency-defense-without-fencing-tokens.md)
- [DDD_PATTERNS.md](./DDD_PATTERNS.md) — DDD layering keeps the version field on the entity, not in handlers
- [CODING_STANDARDS.md](./CODING_STANDARDS.md) §1 SRP/SOLID, §4 Error handling
