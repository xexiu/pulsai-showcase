# ADR-019: OHLCV hypertable chunk interval (7 days → 1 year)

## Status

**Accepted** — 2026-06-10

Implemented by Alembic revision
`20260610_db_hygiene_dead_indexes_ohlcv_chunk_interval`.

## Context

The `ohlcv` TimescaleDB hypertable was created in the initial migration
(`20260125_0001_001_initial`) with `create_hypertable('ohlcv', 'timestamp')`
and **no explicit `chunk_time_interval`**, so it inherited the TimescaleDB
default of **7 days**.

A read-only production probe on 2026-06-10 (PostgreSQL 17.10 + TimescaleDB)
found:

| Metric             | Value    |
| ------------------ | -------- |
| Rows               | ~52,500  |
| Chunks             | **461**  |
| Chunk interval     | 7 days   |
| Avg rows/chunk     | **~114** |
| `ohlcv` total size | ~37 MB   |

The table holds ~9 years of multi-symbol/timeframe history (2017→2026) that is
deliberately sparse: most symbol/timeframe/7-day windows contain very few rows.
The result is **461 nearly-empty chunks**, each carrying its own per-chunk
indexes. This is pure planning + maintenance overhead with no upside — the
classic "over-chunked hypertable" anti-pattern.

This was surfaced during a database review prompted by a "10 DB mistakes"
article. The same review confirmed the DB is **not a performance concern**
(73 MB total, fits in RAM many times over); this change is hygiene/correctness,
not a performance fix.

## Decision Drivers

1. Reduce chunk count toward TimescaleDB's guidance (chunks sized so recent
   chunks + their indexes fit comfortably in memory; thousands of rows per
   chunk, not ~100).
2. Keep all historical data — it is training/backtest ground truth.
3. Zero-risk, non-rewriting change (no data movement at our size).
4. Preserve prod/local parity.

## Considered Options

### Option A — Widen `chunk_time_interval` to 1 year (Chosen)

`SELECT set_chunk_time_interval('ohlcv', INTERVAL '365 days')`.

- Affects **future chunks only**; existing 461 chunks are untouched.
- At current ingest, a 1-year interval yields ~1 chunk/year (≈9 going forward),
  collapsing the chunk explosion without touching stored data.
- Reversible: `downgrade()` resets the interval to 7 days.

### Option B — Add retention + compression — Rejected

The "10 mistakes" review initially floated retention/compression. With the prod
numbers in hand both are **wrong here**:

- **Retention** would _delete_ history we explicitly keep for training/backtest.
- **Compression** is premature optimization at 37 MB and adds operational
  surface (compress/decompress policies, chunk immutability) for no measurable
  win.

### Option C — Re-chunk existing data to the new interval — Rejected

TimescaleDB cannot losslessly merge existing chunks in place; achieving it means
recreating the hypertable and re-inserting. At 37 MB the payoff (461 → ~9
historical chunks) does not justify the operational risk and downtime. New
chunks adopt the 1-year interval automatically, so the problem self-heals going
forward.

## Decision

Adopt **Option A**. Set `ohlcv` `chunk_time_interval` to 1 year via migration.
Leave existing chunks as-is; they age out naturally as a non-issue at this size.

## Consequences

### Positive

- Future chunk growth is ~1/year instead of ~52/year.
- Lower planning overhead and fewer per-chunk indexes over time.
- No data loss, no rewrite, fully reversible.

### Negative / Trade-offs

- Existing 461 chunks remain until a future deliberate re-chunk (acceptable —
  37 MB, in RAM).
- A 1-year chunk is large _if_ ingest volume grows by orders of magnitude
  (e.g. adding minute-level data across many symbols). Revisit the interval if
  any single chunk approaches the "fits in 25% of memory" guideline.

### Parity

The change runs in the migration path (guarded so it is a no-op on a plain
test DB without TimescaleDB). Local dev and prod both converge on a 1-year
interval after migrating.

## References

- Migration: `apps/api/alembic/versions/20260610_db_hygiene_dead_indexes_ohlcv_chunk_interval.py`
- [ADR-004: PostgreSQL with TimescaleDB](./ADR-004-postgresql-timescaledb.md)
- [TimescaleDB: about chunk intervals](https://docs.timescale.com/use-timescale/latest/hypertables/about-hypertables/#chunk-intervals)
