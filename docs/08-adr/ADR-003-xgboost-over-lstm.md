# ADR-003: XGBoost Over LSTM/Deep Learning

## Status

**Accepted** - 2026-01-25

## Context

We need to choose a machine learning approach for trading signal generation. Options include:

- Traditional ML (XGBoost, Random Forest)
- Deep Learning (LSTM, Transformer)
- Reinforcement Learning (FinRL)

## Decision Drivers

1. **Data type**: Financial data is TABULAR (rows = timestamps, columns = indicators)
2. **Inference speed**: Must be < 50ms for signal generation
3. **Interpretability**: Need to explain signals to users (SHAP values)
4. **Training time**: Want to retrain weekly without expensive GPUs
5. **Historical performance**: What works in practice for financial prediction

## Considered Options

### Option A: XGBoost (Gradient Boosting) - Chosen

**Description**: Ensemble of decision trees optimized with gradient boosting.

**Pros**:

- **Designed for tabular data** - exactly what financial indicators are
- Fast inference: 1-5ms per prediction
- Interpretable: SHAP values explain feature importance
- No GPU required for training
- Handles missing data gracefully
- Works well with small datasets (1 year of hourly data = 8,760 samples)

**Cons**:

- Cannot capture long-term sequential dependencies
- May underfit on very complex patterns

### Option B: LSTM (Long Short-Term Memory) - Rejected

**Description**: Recurrent neural network designed for sequential data.

**Pros**:

- Can learn long-term dependencies
- Good for sequential patterns

**Cons**:

- **Wrong fit for tabular data** - designed for sequences, not features
- Slow inference: 20-50ms per prediction
- Requires GPU for efficient training
- Black box - hard to explain predictions
- Needs more data to train effectively
- Prone to overfitting on financial data

### Option C: Transformer - Rejected

**Description**: Attention-based architecture (like GPT).

**Pros**:

- State-of-the-art for many tasks
- Can handle long sequences

**Cons**:

- **Massive overkill for tabular data**
- Inference: 50-200ms
- Requires significant GPU resources
- Even less interpretable than LSTM
- Research shows no benefit over XGBoost for tabular data

### Option D: Reinforcement Learning (FinRL) - Deferred to Phase 2+

**Description**: Agent learns trading strategy through environment interaction.

**Pros**:

- Can learn complex trading strategies
- Adapts to market conditions

**Cons**:

- Very complex to implement correctly
- Requires extensive backtesting framework
- High risk of overfitting
- Computationally expensive
- Overkill for MVP

## Decision

**Choose Option A: XGBoost** for the following reasons:

### 1. Data Type Match

```
Financial Data Structure:
┌──────────┬───────┬──────┬──────┬─────┬────────┬──────────┐
│ timestamp│  RSI  │ MACD │ EMA  │ ATR │ Volume │ Returns  │
├──────────┼───────┼──────┼──────┼─────┼────────┼──────────┤
│ row 1    │ 28.5  │ 125  │ 44500│ 850 │ 1.2M   │ 0.02     │
│ row 2    │ 32.1  │ 130  │ 44600│ 820 │ 1.1M   │ 0.01     │
└──────────┴───────┴──────┴──────┴─────┴────────┴──────────┘

This is TABULAR DATA, not sequential.
XGBoost is designed for tabular data.
LSTM is designed for sequences like text/audio.

Using LSTM for tabular data is like using a hammer for screws.
```

### 2. Performance Comparison

| Model       | Inference Time | GPU Required   | Interpretability |
| ----------- | -------------- | -------------- | ---------------- |
| **XGBoost** | **1-5ms**      | No             | SHAP values      |
| LSTM        | 20-50ms        | Yes (training) | Black box        |
| Transformer | 50-200ms       | Yes            | Black box        |

### 3. Research Evidence

Academic research consistently shows:

- XGBoost/LightGBM outperform deep learning on tabular data
- [TabNet paper](https://arxiv.org/abs/1908.07442) - Google's attempt to beat XGBoost with DL
- [Why do tree-based models still outperform deep learning on tabular data?](https://arxiv.org/abs/2207.08815)

## Implementation

```python
# Our XGBoost setup (adapted from trading_bots project)
model = XGBClassifier(
    n_estimators=500,
    max_depth=6,
    learning_rate=0.01,
    subsample=0.8,
    colsample_bytree=0.8,
    eval_metric="mlogloss",
)

# Features: Technical indicators (tabular)
features = [
    "rsi_14", "macd", "macd_signal",
    "bb_width", "atr", "volume_ratio",
    "returns", "returns_5", "returns_20",
]
```

## Consequences

### Positive

- Inference < 5ms (well under 50ms requirement)
- Can explain predictions with SHAP
- Weekly retraining on CPU
- Leverage existing code from trading_bots
- Works well with available data volume

### Negative

- Cannot capture very long-term patterns
- May miss complex non-linear relationships

### Mitigations

- Use multiple timeframes (1h, 4h, 1d) to capture longer patterns
- Combine with sentiment analysis (LLM) for additional signals
- Consider RL in Phase 2 after validating XGBoost performance

## Classification vs Regression for Signal Generation

This ADR chose XGBoost (model family). A related design question is **task type**: classification or regression?

**Decision: Classification is the primary signal task.**

- **Classification** asks "will price go UP or DOWN?" — maps directly to BUY/SELL/HOLD actions, tolerates market noise, and outputs calibrated probabilities for confidence scores.
- **Regression** asks "what will the exact price be?" — small prediction errors can produce entirely wrong trade direction. Useful for **auxiliary** outputs (return magnitude, TP/SL levels) but not primary direction.

Research consensus (Dec 2025): XGBoost achieved **55.9% classification accuracy** for BTC direction, highest among 7 models tested (including LSTM, GRU, SVM, RF). In trading, ~53%+ accuracy with sound risk management is profitable at scale. See `ML_PIPELINE.md` § "Why Classifiers for Primary Signal Generation" for full rationale and citations.

PulsAI implements both: classification for core signals (2-class and 3-class targets), regression (Sprint 2.9b) for TP/SL prediction and return magnitude estimation.

## Future Considerations

- **Phase 2**: Add LightGBM for comparison (even faster)
- **Phase 3**: Evaluate FinRL if XGBoost performance plateaus
- **Core signals**: LSTM/Transformer are **not** used for primary BUY/SELL signal generation (wrong tool for tabular data).
- **Phase 3+ optional (Sprint 3.1b)**: LSTM/Transformer may be introduced for **non-core** use cases only: e.g. price time-series forecasting, TP/SL prediction, or research/experiments. When: after 2.12; why: sequence-based forecasting, not replacement for XGBoost. See master plan and ROADMAP 3.1b.
- **Multi-agent architecture**: Research (arXiv:2412.20138, ScienceDirect 2025) shows specialized agents outperform generic LLMs for trading. PulsAI's architecture — ML models for signals, LLM for explanation only — aligns with this. See `RD_TRADING_STRATEGIES_RESEARCH.md` § 24.

## References

- trading_bots/backend/core/models/xgboost_classifier_v1.py
- [XGBoost Documentation](https://xgboost.readthedocs.io/)
- [SHAP Values](https://shap.readthedocs.io/)
- [Why Tree-Based Models Beat Deep Learning on Tabular Data](https://arxiv.org/abs/2207.08815)
