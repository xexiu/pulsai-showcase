# ADR-008: Training Data Caching Strategy

## Status

**ACCEPTED** - 2026-01-29

## Context

When training ML models, we need historical OHLCV data. Currently, we fetch fresh data from Binance for each training run. This works but has trade-offs.

### Reference Implementation (trading_bots project)

The `trading_bots/backend/core/helpers/binance_data.py` uses this pattern:

```python
class BinanceData:
    def get_data(self):
        # 1. Try local CSV first
        if os.path.exists(f"{path}.csv"):
            return pd.read_csv(path), has_local_data=True

        # 2. Fall back to fresh fetch
        return self.get_binance_data(), has_local_data=False

    def save_data(self, data):
        # Save preprocessed data: {symbol}_{interval}_{market}_preprocessed.csv
        data.to_csv(f"{path}.csv", index=False)
```

Key insight: They save **preprocessed** data (with indicators calculated), not just raw OHLCV.

### Current PulsAI Implementation

```
Training Run:
1. Fetch OHLCV from Binance (5-10 seconds)
2. Calculate features (~15-20 seconds)
3. Train model (1-30 minutes)
4. Discard OHLCV data
```

No caching. Fresh fetch every time.

## Options Considered

### Option A: No Caching (Current)

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Binance   │───►│  Calculate  │───►│    Train    │
│   Fresh     │    │  Features   │    │    Model    │
└─────────────┘    └─────────────┘    └─────────────┘
     5-10s             15-20s            1-30 min
```

**Pros:**

- Simple, no cache invalidation needed
- Always fresh data
- No storage costs

**Cons:**

- 5-10s fetch time per training run
- API rate limits could throttle
- Wasted computation if same data used multiple times

### Option B: Raw OHLCV Cache Only

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Binance   │───►│   Cache     │───►│  Calculate  │───►│    Train    │
│   (first)   │    │   Raw CSV   │    │  Features   │    │    Model    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘

Storage: cache/raw/{symbol}_{timeframe}.parquet
Size: ~50MB per 2 years of 1h data
```

**Pros:**

- Saves API calls
- Raw data is always valid (no version issues)

**Cons:**

- Still recalculates features every time (15-20s)
- Need cache invalidation strategy
- Storage grows with symbols/timeframes

### Option C: Preprocessed Cache (trading_bots approach)

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Binance   │───►│   Cache     │───►│    Train    │
│   (first)   │    │  Processed  │    │    Model    │
└─────────────┘    │   Parquet   │    │             │
                   └─────────────┘    └─────────────┘

Storage: cache/processed/{symbol}_{timeframe}_v{features_version}.parquet
Size: ~200MB per 2 years of 1h data (30+ features)
```

**Pros:**

- Fastest: Skip both fetch AND feature calculation
- Good for rapid experimentation

**Cons:**

- **VERSION HELL**: If you add/remove/modify a feature, ALL cached data is invalid
- Need versioning system for feature sets
- Higher storage (features add columns)
- Debugging harder (can't verify raw data)

### Option D: Hybrid (Raw + Preprocessed)

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Binance   │───►│   Cache     │───►│   Cache     │───►│    Train    │
│   (first)   │    │   Raw       │    │  Processed  │    │    Model    │
└─────────────┘    │   Parquet   │    │   Parquet   │    │             │
                   └─────────────┘    └─────────────┘    └─────────────┘

Storage:
  cache/raw/{symbol}_{timeframe}.parquet                    (~50MB)
  cache/processed/{symbol}_{timeframe}_v{version}.parquet   (~200MB)
```

**Pros:**

- Best of both worlds
- Can regenerate preprocessed from raw if features change
- Audit trail (raw data preserved)

**Cons:**

- Most complex
- Highest storage (~250MB per symbol/timeframe combo)
- Need to manage two cache layers

## Decision

**Option A: No Caching (for MVP)**

With future migration path to **Option B (Raw OHLCV Cache)** in Phase 2.

### Rationale

```
┌─────────────────────────────────────────────────────────────────────────┐
│  WHY NO CACHING FOR MVP?                                                │
├─────────────────────────────────────────────────────────────────────────┤
│  1. Training is RARE (weekly/monthly) vs Inference (every minute)       │
│     → Optimize inference, not training                                  │
│                                                                         │
│  2. Features are UNSTABLE in MVP                                        │
│     → Adding/removing features would invalidate preprocessed cache      │
│     → Version management overhead not worth it yet                      │
│                                                                         │
│  3. 5-10 second fetch is ACCEPTABLE                                     │
│     → Training takes 1-30 minutes anyway                                │
│     → 10 seconds is < 1% of total training time                         │
│                                                                         │
│  4. YAGNI (You Aren't Gonna Need It)                                    │
│     → Build caching when it becomes a bottleneck                        │
│     → Not before                                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Caching Strategy Summary

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CACHING STRATEGY (FINAL)                              │
├─────────────────────────────────────────────────────────────────────────┤
│  TRAINING DATA:       ❌ Not cached - fetch fresh from exchange         │
│  INFERENCE DATA:      ✅ TimescaleDB + Redis for real-time signals      │
│  FEATURE CALCS:       ✅ JIT compiled (numba cache=True)                │
│  MODEL ARTIFACTS:     ✅ Stored in /models with versioning              │
└─────────────────────────────────────────────────────────────────────────┘
```

## Future Implementation (Phase 2+)

If caching becomes necessary, implement Option B:

### File Structure

```
apps/api/
├── cache/
│   └── training/
│       ├── raw/
│       │   ├── BTCUSDT_1h.parquet
│       │   ├── ETHUSDT_1h.parquet
│       │   └── ...
│       └── .gitignore
```

### Cache Logic

```python
# infrastructure/cache/training_data_cache.py

class TrainingDataCache:
    """
    Simple raw OHLCV cache for training data.

    WHY RAW ONLY (not preprocessed)?
    - Features change frequently during development
    - Raw data doesn't expire (candles don't change)
    - Can always regenerate features from raw
    """

    def get_or_fetch(
        self,
        symbol: str,
        timeframe: str,
        since: datetime,
        until: datetime,
    ) -> pl.DataFrame:
        cache_path = self._get_cache_path(symbol, timeframe)

        if cache_path.exists():
            cached = pl.read_parquet(cache_path)

            # Check if cache covers requested range
            if self._covers_range(cached, since, until):
                return self._filter_range(cached, since, until)

            # Partial cache: fetch missing and merge
            return self._fetch_and_merge(cached, symbol, timeframe, since, until)

        # No cache: fetch and save
        data = self._fetch_fresh(symbol, timeframe, since, until)
        data.write_parquet(cache_path)
        return data

    def invalidate(self, symbol: str, timeframe: str) -> None:
        """Delete cache file (use if exchange had data corrections)."""
        cache_path = self._get_cache_path(symbol, timeframe)
        if cache_path.exists():
            cache_path.unlink()
```

### Cache Retention Strategy

**Why NOT time-based deletion (30/60/90 days)?**

- Training windows are 60/90/180/365 days
- Deleting after 30-90 days defeats caching purpose
- Raw OHLCV is tiny (~2 MB per symbol/year)

**Recommended: Size-based LRU (Least Recently Used)**

```python
MAX_CACHE_SIZE_MB = 100  # Generous for raw OHLCV

class CacheRetention:
    def cleanup_if_needed(self):
        total_size = self._get_cache_size_mb()

        if total_size > MAX_CACHE_SIZE_MB:
            # Delete least recently accessed files first
            files = sorted(
                self._get_cache_files(),
                key=lambda f: f.stat().st_atime
            )
            while total_size > MAX_CACHE_SIZE_MB * 0.8:
                oldest = files.pop(0)
                total_size -= oldest.stat().st_size / 1024 / 1024
                oldest.unlink()
```

**Cache Size Estimates:**

| Scenario                 | Storage |
| ------------------------ | ------- |
| 5 symbols × 1h × 1 year  | ~11 MB  |
| 5 symbols × 1h × 2 years | ~22 MB  |
| 5 symbols × 4h × 2 years | ~6 MB   |
| **Total worst case**     | ~50 MB  |

→ 100 MB limit is generous, rarely needs cleanup.

### Invalidation Strategy

| Trigger                                | Action                                |
| -------------------------------------- | ------------------------------------- |
| Exchange announces data correction     | `cache.invalidate(symbol, timeframe)` |
| New training with `force_refresh=True` | Skip cache, fetch fresh               |
| Cache size > 100 MB                    | LRU eviction of oldest files          |
| Manual cleanup                         | `cache.clear_all()` admin command     |

## Consequences

### Positive

- Simpler MVP implementation
- No cache invalidation bugs
- No storage management needed
- No version mismatch issues

### Negative

- 5-10 second fetch time per training run
- Redundant API calls if training same symbol multiple times

### Mitigations

- Fetch time is < 1% of total training time
- Training is rare (weekly/monthly)
- Can add caching later without breaking changes

## References

- `trading_bots/backend/core/helpers/binance_data.py` - Reference implementation
- `docs/02-technical/ML_PIPELINE.md` - Training data caching section
- `docs/02-technical/DATA_PROCESSING.md` - Feature calculation pipeline

## Decision Date

2026-01-29

## Decision Makers

- Main Architect (PulsAI)
