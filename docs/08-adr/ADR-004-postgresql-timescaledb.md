# ADR-004: PostgreSQL with TimescaleDB

## Status

**Accepted** - 2026-01-25 · **Hosting choice superseded 2026-05-19** · **PG18 / UUIDv7 stance recorded 2026-08-07** (see updates below)

## Update — 2026-08-07: PostgreSQL 18 — NO-GO (stay on PG17 + Timescale)

**Decision:** Do **not** upgrade PulsAI to PostgreSQL 18 now. Local and compose remain on `timescale/timescaledb:latest-pg17`; production remains Railway Timescale on the PG17 line.

**Why (measured against product bottleneck, not blog hype):**

1. Money path is honest-edge + leverage capital-cert on the 4h/8h/12h/1d grid — not a Postgres major bump.
2. Time-series hot path is already owned by **Timescale hypertables / compression / retention**, not vanilla PG18 marketing features (planner polish, skip scan, JSON path tweaks).
3. A major upgrade on Railway Timescale is restore-drill + downtime risk; PG17 is already current and supported by Timescale.

**Revisit only when ALL of these are true:**

| Trigger                                                         | Evidence required                                                                                                                       |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Railway / our Timescale image exposes a supported **PG18** path | Documented image/plugin tag we can pin (not a one-off community template alone)                                                         |
| Restore drill passes on a PG18 target                           | Follow [DB_BACKUP_AND_RESTORE.md](../06-devops/DB_BACKUP_AND_RESTORE.md) on a throwaway volume                                          |
| Measured need                                                   | Prod incident or A/B showing I/O, vacuum, or planner pain that PG18 specifically fixes (async I/O or equivalent), not anecdotal latency |

Until then: treat medium/blog “PG18 is a turning point” posts as **non-actionable**. Prefer edge-hunt and publish work over DB major upgrades.

## Update — 2026-08-07: Primary keys — keep app-minted UUIDv4

**Decision:** Keep minting entity PKs in Python via `uuid4()` / SQLAlchemy `default=lambda: str(uuid4())` (current pattern across persistence models). Do **not** migrate to PostgreSQL 18 `uuidv7()` / DB `DEFAULT` as a drive-by.

**Evidence:** Persistence layer consistently uses application-side UUIDv4 string PKs; OHLCV and other hypertables use composite/time keys, not UUID insert storms as the scale bottleneck.

**Revisit only when:**

- We add a **new** high-insert UUID-keyed table where index locality is measured as a write hotspot, **and**
- Postgres major ≥ 18 is already live (so native `uuidv7()` is available without a separate major upgrade), **and**
- Migration cost (backfill / dual-write / client contract) is accepted in an explicit ADR update.

Until then: no schema churn for UUIDv7.

## Update — 2026-05-19: hosting moved to Railway-bundled Timescale

The **technology decision (PostgreSQL + TimescaleDB) still stands** and is in production. What changed is the **hosting choice**: this ADR's "Considered hosting" table recommends **Supabase as the MVP host**; pulsai actually ships on **Railway** with the bundled Postgres+TimescaleDB plugin. Supabase was never wired into the API — no `SUPABASE_URL` / `SUPABASE_KEY` exists anywhere in `apps/api/src/`.

The reasons for the divergence (documented here for historical traceability, not as a re-decision):

- Railway already hosts every other compute tier (FastAPI container, Celery workers, Redis), so co-locating Timescale on the same project gives private-network access (`timescale.railway.internal`) and eliminates a cross-vendor hop.
- Single-vendor billing (one Railway invoice) was operationally simpler at our scale than splitting compute on Railway and data on Supabase.
- The TimescaleDB extension is available on the Railway plugin, so the technology decision (rows 1–4 below) is unaffected.

The schema-design recommendations (hypertables, retention, continuous aggregates), the indexing strategy, and the **technology choice** documented elsewhere in this ADR remain authoritative. The "Use for MVP" recommendation in the _Hosting comparison_ table is therefore **historical only** — do not act on it.

See [ARCHITECTURE.md](../02-technical/ARCHITECTURE.md) for the current high-level deployment diagram, and [CONCURRENCY_INVARIANTS.md](../04-structural/CONCURRENCY_INVARIANTS.md) for how Timescale interacts with the worker pool.

## Context

We need to choose a database for storing:

- User data (profiles, settings, subscriptions)
- Trading data (trades, positions, orders)
- Time-series data (OHLCV candles, signals, indicators)

Time-series data is the critical challenge:

- 1 year of 1-minute BTC data = 525,600 rows
- With 10 symbols and 5 timeframes = 26 million rows
- Queries must be fast for real-time charts

## Decision Drivers

1. **Time-series performance**: Fast queries on large time-series data
2. **ACID compliance**: Financial data requires transactional integrity
3. **SQL support**: Team familiarity with SQL
4. **Managed options**: Easy deployment and maintenance
5. **Cost**: Free tier available for MVP

## Considered Options

### Option A: PostgreSQL + TimescaleDB (Chosen)

**Description**: PostgreSQL with TimescaleDB extension for time-series optimization.

**Pros**:

- **TimescaleDB hypertables**: Auto-partitioned by time, 10-100x faster queries
- Full ACID compliance
- Standard SQL (easy to use)
- Automatic data compression
- Retention policies for old data
- Managed options: Supabase, Railway, Neon
- Can handle both relational AND time-series data

**Cons**:

- Need to enable TimescaleDB extension
- Slightly more complex than plain PostgreSQL

### Option B: Plain PostgreSQL - Rejected

**Pros**:

- Simplest option
- Most managed hosting options

**Cons**:

- **Poor time-series performance at scale**
- Need manual partitioning
- No automatic compression
- 50x slower on time-series queries vs TimescaleDB

### Option C: InfluxDB - Rejected

**Description**: Purpose-built time-series database.

**Pros**:

- Excellent time-series performance
- Built-in compression

**Cons**:

- **No ACID transactions**
- Different query language (Flux, not SQL)
- Cannot store relational data (users, trades)
- Would need TWO databases

### Option D: MongoDB - Rejected

**Description**: Document database.

**Pros**:

- Flexible schema
- Good for rapid prototyping

**Cons**:

- **No ACID by default**
- Not optimized for time-series
- Different query paradigm
- Would need time-series workarounds

### Option E: Firebase Firestore - Rejected

**Description**: Google's NoSQL cloud database.

**Pros**:

- Serverless
- Real-time subscriptions
- Free tier

**Cons**:

- **Not optimized for time-series**
- No SQL
- Expensive at scale
- Vendor lock-in
- No TimescaleDB-like features

## Decision

**Choose Option A: PostgreSQL + TimescaleDB**

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   PostgreSQL 15                          │
│                                                         │
│  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ Regular Tables  │  │  TimescaleDB Hypertables    │  │
│  │                 │  │                             │  │
│  │ • users         │  │ • ohlcv (candles)           │  │
│  │ • trades        │  │ • signals                   │  │
│  │ • positions     │  │ • indicators                │  │
│  │ • subscriptions │  │                             │  │
│  └─────────────────┘  └─────────────────────────────┘  │
│                                                         │
│  ACID Compliance    │    Automatic Partitioning        │
│  SQL Queries        │    10-100x Faster Time Queries   │
│  Relational Model   │    Compression + Retention       │
└─────────────────────────────────────────────────────────┘
```

### Performance Comparison

```sql
-- Query: Get last 30 days of BTC 1h candles
SELECT * FROM ohlcv
WHERE symbol = 'BTC/USDT'
AND time > NOW() - INTERVAL '30 days';

-- Results (1 million total rows):
┌──────────────────────┬─────────────┬──────────────┐
│ Database             │ Query Time  │ With Index   │
├──────────────────────┼─────────────┼──────────────┤
│ Plain PostgreSQL     │ 2.5 seconds │ 800ms        │
│ TimescaleDB          │ 50ms        │ 50ms         │
│ InfluxDB             │ 40ms        │ N/A          │
└──────────────────────┴─────────────┴──────────────┘
```

### Hypertable Configuration

```sql
-- Create OHLCV table
CREATE TABLE ohlcv (
    time TIMESTAMP WITH TIME ZONE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open DECIMAL(20, 8) NOT NULL,
    high DECIMAL(20, 8) NOT NULL,
    low DECIMAL(20, 8) NOT NULL,
    close DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(30, 8) NOT NULL,
    PRIMARY KEY (time, symbol, timeframe)
);

-- Convert to hypertable (auto-partitioned by time)
SELECT create_hypertable('ohlcv', 'time',
    chunk_time_interval => INTERVAL '1 day'
);

-- Enable compression (saves 90%+ storage)
ALTER TABLE ohlcv SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol,timeframe'
);

-- Compress data older than 7 days
SELECT add_compression_policy('ohlcv', INTERVAL '7 days');

-- Delete data older than 2 years
SELECT add_retention_policy('ohlcv', INTERVAL '2 years');
```

## Consequences

### Positive

- Single database for all data types
- 50x faster time-series queries
- Automatic data management (compression, retention)
- Standard SQL for all queries
- ACID compliance for financial data
- Supabase supports TimescaleDB extension

### Negative

- Need to enable TimescaleDB extension (one-time setup)
- Slightly steeper learning curve for hypertables
- Some managed providers don't support TimescaleDB

### Hosting Decision

| Provider        | TimescaleDB  | Free Tier    | Recommendation    |
| --------------- | ------------ | ------------ | ----------------- |
| **Supabase**    | ✅ Extension | 500MB        | **Use for MVP**   |
| Neon            | ❌           | 512MB        | Reject            |
| Railway         | ✅ Manual    | $5/mo        | Backup option     |
| Timescale Cloud | ✅ Native    | 30-day trial | Production option |

## Implementation Notes

```python
# SQLAlchemy 2.0 model for hypertable
from sqlalchemy import Index
from sqlalchemy.orm import Mapped, mapped_column

class OHLCV(Base):
    __tablename__ = "ohlcv"

    time: Mapped[datetime] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    timeframe: Mapped[str] = mapped_column(String(10), primary_key=True)
    open: Mapped[Decimal]
    high: Mapped[Decimal]
    low: Mapped[Decimal]
    close: Mapped[Decimal]
    volume: Mapped[Decimal]

# Index for common queries
Index('idx_ohlcv_symbol_time', OHLCV.symbol, OHLCV.time.desc())
```

## References

- [TimescaleDB Documentation](https://docs.timescale.com/)
- [TimescaleDB vs InfluxDB](https://www.timescale.com/blog/timescaledb-vs-influxdb/)
- [Supabase TimescaleDB Setup](https://supabase.com/docs/guides/database/extensions/timescaledb)
- [docs/02-technical/DATABASE_SCHEMA.md](../02-technical/DATABASE_SCHEMA.md)
