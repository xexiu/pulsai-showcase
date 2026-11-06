# ADR-005: Sentiment Architecture Decision

## Status

**Accepted** - 2026-01-25

## Context

PulsAI's original architecture planned to use sentiment analysis as a feature input to the XGBoost ML model for trading signal generation. The assumption was that historical sentiment data could be obtained and aligned with OHLCV (price) data for model training.

### The Problem

After critical analysis, we discovered that **historical sentiment data is either non-existent or prohibitively expensive**:

| Data Source           | Historical Availability | Cost                  | Granularity |
| --------------------- | ----------------------- | --------------------- | ----------- |
| Twitter/X API         | 7 days only             | Free tier: 7 days max | Varies      |
| Santiment             | Full history            | $300-500/month        | Hourly      |
| LunarCrush            | Full history            | $300-500/month        | Hourly      |
| CryptoPanic           | Limited                 | Free tier limited     | Daily       |
| News APIs             | Limited archives        | Varies                | Daily       |
| On-chain (Fear/Greed) | Good                    | Free                  | Daily       |

**Key issues:**

1. **Data Alignment**: Sentiment data must align perfectly with OHLCV timestamps for ML training
2. **Granularity Mismatch**: Free sources provide daily data, but our models need hourly
3. **Cost**: Comprehensive historical data costs $300-500+/month
4. **Consistency**: Different sources have different scoring methods

## Decision

### MVP (Phase 1): Technical Indicators ONLY

**XGBoost will be trained exclusively on technical indicators:**

- RSI, MACD, Bollinger Bands, EMA, ATR
- Volume ratios, price returns
- 30+ technical features
- **NO sentiment features**

### Real-Time Sentiment: Display Only

**Sentiment will be displayed in the UI but NOT used in ML prediction:**

- LLM-based analysis of current news/social media
- Fear & Greed Index display
- Clearly marked as "informational only"

### Data Collection Strategy: Build Our Own History

**From Day 1, we collect and store sentiment data:**

- News sentiment (CryptoPanic, NewsAPI)
- Social sentiment (Twitter/X, Reddit)
- Fear & Greed Index
- Stored in TimescaleDB with timestamps aligned to OHLCV

### Phase 2+: Integrate Collected Data

**After 6+ months of data collection:**

- Retrain XGBoost with sentiment as feature
- OR use LLM to combine ML signal + real-time sentiment at inference

## Alternatives Considered

### Option A: Pay for Historical Sentiment (Rejected)

**Pros:**

- Immediate sentiment integration
- High-quality data

**Cons:**

- $300-500/month ongoing cost
- Vendor lock-in
- Data quality varies by provider
- May still have alignment issues

**Verdict**: Too expensive for MVP, doesn't guarantee quality

### Option B: Use Only Free Daily Sentiment (Rejected)

**Pros:**

- Free
- Some signal value

**Cons:**

- Daily granularity mismatches hourly models
- Would need significant interpolation
- Reduced model accuracy

**Verdict**: Technical data would be noisy, likely hurt model performance

### Option C: Synthetic Historical Sentiment (Rejected)

**Pros:**

- Could generate training data

**Cons:**

- Highly unreliable
- Would introduce bias
- Ethically questionable

**Verdict**: Bad practice, would compromise model integrity

### Option D: Technical Only + Collect for Future (Chosen)

**Pros:**

- Clean MVP with proven technical indicators
- No data quality issues
- Sentiment displayed for user context
- Building real data asset for Phase 2

**Cons:**

- MVP doesn't use sentiment in signals
- 6+ month delay for sentiment integration

**Verdict**: Best balance of quality, cost, and future value

## Consequences

### Positive

1. **Model Integrity**: XGBoost trained on clean, aligned technical data
2. **Cost Control**: No expensive data subscriptions for MVP
3. **Future Asset**: After 6 months, we have proprietary sentiment history
4. **User Value**: Users still see sentiment (just display-only)
5. **Honest Product**: Clear about what drives signals

### Negative

1. **Delayed Sentiment Integration**: Full sentiment-enhanced signals in Phase 2
2. **Competitor Comparison**: Some competitors claim sentiment signals (may be overstated)
3. **Collection Overhead**: Must build sentiment collection infrastructure for MVP

### Neutral

1. **Documentation Required**: Must clearly communicate sentiment is "display only"
2. **UI Design**: Sentiment panel must be visually separate from ML signals

## Implementation

### Database Schema

```sql
-- Sentiment data collected from Day 1
CREATE TABLE sentiment_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    news_score NUMERIC(5, 4),       -- -1.0 to +1.0
    social_score NUMERIC(5, 4),     -- -1.0 to +1.0
    fear_greed_index INTEGER,       -- 0 to 100
    combined_score NUMERIC(5, 4),   -- -1.0 to +1.0
    news_count INTEGER,
    social_mentions INTEGER,
    source_details JSONB,
    PRIMARY KEY (time, symbol)
);

SELECT create_hypertable('sentiment_data', 'time');
```

### API Endpoints

```yaml
# MVP: Display only
GET /api/v1/sentiment/current/{symbol}
  - Returns: Current sentiment scores
  - Used for: UI display only

# Future: When integrated with ML
GET /api/v1/signals/{id}
  - Returns: ML signal + sentiment context (not used in calculation)
```

### UI Component

```
┌─────────────────────────────────────┐
│ SENTIMENT (Display Only)            │
├─────────────────────────────────────┤
│ News:     🟢 +0.65 Bullish          │
│ Social:   🟡 +0.12 Neutral          │
│ F&G:      68 (Greed)                │
├─────────────────────────────────────┤
│ ⚠️ Informational only.              │
│ Not used in ML signal calculation.  │
└─────────────────────────────────────┘
```

## Timeline

| Phase         | Timeframe | Sentiment Status                        |
| ------------- | --------- | --------------------------------------- |
| Phase 1 (MVP) | Month 1-2 | Display only, collecting data           |
| Phase 2       | Month 3-4 | Still collecting, display only          |
| Phase 3       | Month 5-6 | Evaluate data quality                   |
| Phase 4       | Month 7+  | Integrate into model if data sufficient |

## Related Documents

- [ML_PIPELINE.md](../02-technical/ML_PIPELINE.md) - Updated pipeline architecture
- [ARCHITECTURE.md](../02-technical/ARCHITECTURE.md) - Updated system diagrams
- [ROADMAP.md](../01-business/ROADMAP.md) - Sprint 1.6 sentiment collection
- [UI_WIREFRAMES.md](../03-functional/UI_WIREFRAMES.md) - Sentiment panel design

## References

- Freqtrade FreqAI: Does not include sentiment by default
- QuantMuse: Includes LLM sentiment but as separate layer
- Academic research: Mixed results on sentiment prediction value

## Decision Makers

- Main Architect (AI)
- Product Owner (User)

## Date

2026-01-25
