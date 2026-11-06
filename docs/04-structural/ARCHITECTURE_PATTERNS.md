# PulsAI Architecture Patterns — fit, anti-fit, and what it costs us

Sibling to [DDD_PATTERNS.md](./DDD_PATTERNS.md), which answers **where DDD applies**. This file
answers a different question: **which pattern solves the problem in front of you, and which one
will quietly cost you a week.**

> **CRITICAL, same spirit as DDD_PATTERNS:** a pattern is a liability until the problem is real.
> Every row below carries an anti-fit column, and the anti-fit is the load-bearing half.

Distilled 2026-09-02 from seven external write-ups (listed at the bottom) and then **checked
against this repo**. Where a row claims PulsAI uses something, it is a usage I verified; where we
do not use it, the row says so rather than inventing an example.

---

## How to use this file

1. Name the problem first (latency? consistency? blast radius? coupling?).
2. Find the row. Read the **anti-fit** before the fit.
3. If you are adding a pattern, say in the PR/commit which row you are invoking and why the
   anti-fit does not apply. "It felt cleaner" is not a reason — see **Golden hammer** below.

---

## 1. Object construction and wiring

| Pattern       | Solves                                                        | Anti-fit — do NOT reach for it when…                                                                                                                                                                                                                |
| ------------- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Singleton** | one owner for a shared resource (pool, cache, config)         | it is really global mutable state. Hidden global state is the #1 source of "passes alone, fails in the suite". We have felt this exact shape: a shared registry mutated per test needed an explicit swap-and-restore (`HR._active`) to stay honest. |
| **Factory**   | construction depends on env/config, or you want a plugin seam | the constructor is one line. Indirection with no variation is cost without payoff.                                                                                                                                                                  |
| **Builder**   | many optional fields, immutability matters                    | a dataclass already says it. Python `@dataclass(frozen=True)` covers most of what Builder exists for.                                                                                                                                               |

**PulsAI — verified, and the first draft of this line was WRONG:**

- **Singleton:** `get_settings()` in `infrastructure/config/settings.py` — genuinely one instance
  (`@lru_cache`, plus a module-level `settings = get_settings()`). Legitimate: config is read-only
  after construction, so the usual singleton hazard (shared _mutable_ state) does not apply.
- **Factory:** `get_model_storage()` in `infrastructure/ml/model_storage_factory.py`. This file
  originally called it a singleton. It is not — there is no cache; it builds a fresh `ModelStorage`
  every call, takes a `base_path` override, and decides the backend at construction time via
  `effective_model_backend(...)`. That decision is the whole point, and it is load-bearing: its own
  comment records a laptop training run writing into the LIVE R2 bucket on 2026-08-21 because the
  _configured_ backend was not the _permitted_ one. A plain constructor could not have carried that
  policy — which is exactly when Factory earns its indirection.

New singletons need a reason beyond convenience, and "we call it once" is not one.

---

## 2. Structural seams

| Pattern        | Solves                                                                     | Anti-fit                                                                                                                                                                              |
| -------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Adapter**    | a third-party shape ≠ our domain shape                                     | our own modules already agree. An adapter between two things we control is usually two things that should have agreed.                                                                |
| **Decorator**  | cross-cutting behaviour (logging, metrics, retry) without editing the core | chains get deep. Three decorators are a design; six are a stack trace nobody can read.                                                                                                |
| **Proxy**      | lazy load, remote call, access check                                       | it hides a network call behind an attribute access. A "free-looking" property that does I/O is how a p95 doubles with no diff to blame.                                               |
| **Repository** | domain talks to storage through an interface                               | it degenerates to CRUD passthrough, or it leaks the DB — e.g. a `limit` that means _rows_ when the caller means _bars_. That exact leak cost us the 1d chart's markers on 2026-09-02. |

**PulsAI:** `SignalRepository` (+ `SignalRepositoryProtocol` port) is the reference implementation.
Note what it does right after that bug: the bar-window read is a **named method with intent**
(`get_history_for_recent_bars`), not another `limit` for the caller to misread.

---

## 3. Behaviour and flow

| Pattern                | Solves                                                 | Anti-fit                                                                                                                   |
| ---------------------- | ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- |
| **Strategy**           | interchangeable algorithms chosen at runtime           | there is exactly one implementation.                                                                                       |
| **Observer / pub-sub** | producer must not know its consumers                   | ordering matters, or nobody unsubscribes. Unremoved listeners leak; implicit fan-out becomes control flow you cannot grep. |
| **Command**            | the request must be queued, retried, audited or undone | it is a function call.                                                                                                     |

**PulsAI:** Strategy is the documented trading-mode design (`DemoModeHandler` /
`PaperModeHandler` / `LiveTradingModeHandler` — see DDD_PATTERNS, "composition, not `BaseTrading`
inheritance"). Observer is the FE `eventBus` (`signal:new`) and Celery on the BE. Command is the
Celery task itself — which is why a task routed to an unconsumed queue is a silent outage rather
than a slow path.

---

## 4. Consistency and distribution

| Pattern          | Solves                                                       | Anti-fit                                                                                                                                |
| ---------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| **CQRS**         | reads and writes have genuinely different shapes/scale       | a single modest workload. You buy eventual consistency plus a second model whose agreement with the first becomes your problem forever. |
| **Saga**         | multi-step workflow across services without two-phase commit | you cannot write the compensations. An un-compensatable step is not a saga, it is a hope.                                               |
| **Event-driven** | decouple producers from consumers, react in near-real-time   | you need a synchronous answer, or you need ordering guarantees you have not specified.                                                  |

**PulsAI:** read models over repositories are our CQRS-lite (per DDD_PATTERNS, paper and live share
queries with a ledger partition). We have **no Saga** and should not grow one casually — we are one
service plus workers, not a service mesh.

---

## 5. Resilience — and the honesty clause

| Pattern             | Solves                                       | Anti-fit / failure mode                                                                          |
| ------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **Retry**           | transient faults                             | unbounded retry converts a blip into a self-inflicted outage. Always bounded, always backed off. |
| **Circuit breaker** | stop hammering a dead dependency             | thresholds are guesses until measured. Too tight trips on noise; too loose never trips.          |
| **Bulkhead**        | one workload cannot eat everyone's resources | too many small pools starve each other. Sizing is the whole design.                              |

> **The honesty clause: a resilience pattern without observability is worse than none.** It converts
> a loud failure into a silent degradation. If it can trip, it must emit — and something must read
> what it emits. This repo has already paid for the inverse twice: a monitor whose `\bFATAL\b`
> matched "non-**fatal**" cried wolf every tick, and a latency gate that printed `SKIPPED` and
> exited 0 reported success while measuring nothing.

**PulsAI:** the Celery queue split (`training,email,signals,alerts` on prefork vs `monitoring` and
`ohlcv_stream` on solo pools, per ARCHITECTURE.md) **is** a bulkhead — its purpose is that a
C-extension crash in one queue cannot take the others down.

---

## 6. Data and storage

The data-architecture write-up catalogues twelve warehouse-scale patterns (medallion, lambda,
kappa, lake, warehouse, lakehouse, mesh, fabric, hub-and-spoke, vault, event-driven, streaming).
**Almost none of them apply to us, and saying so is the useful part.**

- We are **not** a data platform. We are one Postgres/TimescaleDB, one Redis, one object store.
- The one idea worth stealing is **staged refinement** (medallion's core): raw → cleaned →
  serving, each stage independently reprocessable. Our research corpus already works this way
  (raw OHLCV → features → certs), which is why re-certifying does not mean re-downloading.
- **Data mesh is an organisational pattern.** It presumes multiple owning teams. We have one
  developer and one agent; adopting it would be cargo-culting.

**Database concepts that DO bind us** (all directly applicable):

- **Index for the query you actually run**, added after measuring — not one per column.
- **Keep transactions short.** Lock duration is contention.
- **Normalise by default; denormalise only against a measurement.**
- **Isolation level is a correctness choice, not a performance knob.** Two writers racing for one
  row is our bread and butter (one bar, N models).
- **N+1 is the default failure of any ORM read path.** Fetch the set, not the loop.
- Partitioning / sharding / replication are scale tools we do **not** need yet; TimescaleDB
  already gives us time partitioning.

---

## 7. Concurrency — what actually happens under load

The concurrency write-up is framed on Spring, but the mechanics are ours too:

- **A request handler is shared; request state must not be.** Module-level mutables in a FastAPI
  app are shared across every concurrent request exactly as a singleton bean is.
- **Slow handlers exhaust the pool.** Throughput is bounded by handler latency. This is why our
  budgets exist (signal < 50 ms, API < 200 ms) and why heavy work inside the serving container
  pages the owner — see `.claude/rules/no-heavy-work-in-the-serving-container.md`.
- **Race → lost update** is the canonical bug: two readers, two writers, one survivor. If two
  requests can touch one row, the database must arbitrate (constraint, lock, or upsert), not the
  application layer.
- **Offload anything not needed for the response.** That is what the workers are for.

---

## 8. Wire formats

- **JSON** is our default and its sharp edges are real: no native date type (we pass ISO-8601
  strings and parse at the edge), no native binary, and **IEEE-754 means large integers lose
  precision**. Anything that must round-trip exactly (ids, money) travels as a string.
- **YAML** is config only, and `safe_load` only — never `load` on anything we did not write. Its
  implicit typing is a genuine trap (unquoted tokens coercing to booleans).
- **XML / Protobuf / MessagePack / CSV** — no current use. Protobuf would only earn its schema
  cost if we added gRPC; we have not.

---

## 9. The anti-patterns, which matter more than the patterns

1. **Golden hammer** — applying the pattern you like to the problem you have.
2. **Over-abstraction** — interfaces and factories so numerous that finding the real code is the
   hard part. Depth without leverage.
3. **Premature distribution** — CQRS / Saga / mesh before the load that justifies them.
4. **Unobservable resilience** — see the honesty clause in §5.
5. **Pattern-as-explanation** — naming a pattern in review instead of describing the behaviour. If
   you cannot state the failure it prevents, you are decorating, not designing.

---

## 10. On learning this

The system-design write-up's advice that survives contact with this repo: **learn the building
blocks in order** (network → storage → scaling → architecture), **draw the request path** before
arguing about it, and **defend trade-offs rather than hunt for the one right answer**. The
corollary we already enforce: state success and validation criteria BEFORE building, then loop
until they hold.

---

## Sources

Read 2026-09-02. Summarised and adapted; the fit/anti-fit verdicts and every PulsAI mapping are
ours, not the authors'.

- The Architect's Secret — patterns that solve most real-world problems (Stackademic)
- The 12 data architecture patterns every data engineer should master in 2026 (Data Science Collective)
- How I learned system design (Himanshu Singour)
- 10 database concepts every backend developer must understand
- JSON, XML and data formats: what every backend engineer should know
- What happens when multiple users hit your API at the same time
- Forget JWTs: server-side sessions cut our auth bugs by 70%

### A note on the JWT/sessions piece

It reports a migration (JWT → DB-backed sessions) with a large drop in auth bugs, on the argument
that "stateless" JWT plus a revocation blocklist is a stateful system wearing a stateless label.
**PulsAI currently uses JWT cookies** (`pulsai_at` / `pulsai_rt`, verified in the browser
2026-09-02). That is not a defect and this file does not propose changing it. What it does propose
is that the trade-off be stated honestly wherever we rely on it: **we cannot revoke an access token
before it expires without server-side state.** If instant force-logout becomes a product
requirement, that is the moment to revisit — not before, and not because an article said so.
