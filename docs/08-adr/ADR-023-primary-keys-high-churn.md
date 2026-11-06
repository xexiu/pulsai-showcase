# ADR-023: Primary keys for high-churn tables — bigint (or UUIDv7), not UUIDv4

## Status

**Accepted** — 2026-08-07

## Context

Random UUIDv4 primary keys fragment B-tree indexes under heavy append load
(page splits, half-full leafs, PK lookups that burn tens of thousands of buffer
reads). That storage physics is well-known; a 2026 field write-up of a ~200M-row
Postgres table made the failure mode concrete again.

PulsAI already chose correctly in two places:

- `audit_logs.id` is **BIGSERIAL** (high-volume append stream).
- `ohlcv` uses a Timescale **composite** key, not UUID.

Most other entities still use UUIDv4 PKs (`users`, paper/demo trades, signals,
training jobs, carry, …). That is fine while row counts stay modest; it is the
wrong default for **new** tables that will absorb continuous inserts.

## Decision

1. **New high-churn append tables** (order/fill/signal streams, heatmap ticks,
   idempotency receipts that grow without bound, similar): use
   `BIGINT GENERATED ALWAYS AS IDENTITY` as the **primary key**.
2. If clients need an opaque external id, add `public_id UUID NOT NULL DEFAULT
gen_random_uuid()` (or UUIDv7 when Postgres/extension support is available in
   our stack) with a **UNIQUE** index — not as the clustered PK.
3. **New low-churn entity tables** (users, config, automations, billing
   connections): UUIDv4 PK remains acceptable; UUIDv7 is preferred when starting
   a greenfield table that still wants a single opaque id.
4. **Do not** big-bang migrate existing UUID PK tables. Migrate only after
   measured index bloat / PK-lookup buffer pain, via expand–contract.

## Considered options

| Option                   | Why not default                                             |
| ------------------------ | ----------------------------------------------------------- |
| UUIDv4 everywhere        | Index write amplification at scale                          |
| Rewrite all UUID PKs now | FK blast radius; no measured pain on most tables            |
| Snowflake / ULID only    | Extra type/tooling; bigint + optional public UUID is enough |

## Consequences

- Authors of new Alembic migrations for append-heavy tables follow this ADR.
- `audit_logs` remains the reference pattern for bigint PKs.
- Public APIs that today expose UUID ids keep doing so via `public_id` or
  existing entity UUIDs — internal join keys may be bigint on new tables.
- Future “should we use UUIDs?” debates point here instead of re-arguing physics.

## Measurement (local, 2026-08-07)

### Live tables

Local `pulsai-postgres` via
`apps/api/src/research/artifacts/uuid_pk_health_measure.sql`.

| Fact                       | Value                          |
| -------------------------- | ------------------------------ |
| Hottest UUID-PK table      | `signals` — **7,631** rows     |
| PK lookup                  | **0.146 ms**, shared hit=**3** |
| Article failure mode       | **Not observed**               |
| Migrate existing UUID PKs? | **No**                         |

### Mock stress (1M users + 1M signals)

`src/research/uuid_pk_stress_run.py` (disposable schema).

| Fact                          | Value                                                   |
| ----------------------------- | ------------------------------------------------------- |
| UUID / bigint PK lookup at 1M | **~0.05 ms**, **0** disk reads                          |
| UUID PK index vs bigint at 1M | **~37.5 MB** vs **~22.5 MB** (~1.7×)                    |
| Article failure at 1M?        | **No**                                                  |
| Migrate existing?             | Still **No** — ADR applies to **new** high-churn tables |

Write-ups: `UUID_PK_HEALTH_FINDINGS.md`, `UUID_PK_STRESS_FINDINGS.md`.
