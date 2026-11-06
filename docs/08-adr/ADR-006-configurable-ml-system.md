# ADR-006: Configurable ML Training System

## Status

**ACCEPTED** - 2026-01-26
**UPDATED** - 2026-01-30 (Reflects actual implementation)

## Context

After implementing Sprint 1.5 (first XGBoost model), we analyzed reference projects (`trading_bots/backend/core/models/`) and identified patterns that significantly improve model performance:

1. **Target Type Flexibility**: Different market conditions require different target definitions
2. **Model Type Variety**: 3-class (BUY/HOLD/SELL) vs 2-class (BUY vs NOT-BUY) have different use cases
3. **Feature Selection**: Auto-pruning low-contributing features improves generalization
4. **Admin Configurability**: Non-technical admins need UI to configure training without code changes

### Current Implementation (Sprint 1.5)

```python
# Single target type - Fixed threshold
class TargetCreator:
    def __init__(self, threshold_pct: float = 1.0):
        self.threshold_pct = threshold_pct

    # Creates BUY/HOLD/SELL based on future_return >= threshold
```

### Problem

1. Fixed 1% threshold doesn't adapt to market volatility
2. 3-class model results in 80%+ HOLD predictions (class imbalance)
3. No way to experiment with different approaches without code changes
4. Feature importance not visible during training decisions

## Decision

Implement a **Configurable ML Training System** for Sprint 2.0 with:

### 1. Factory Pattern for Target Types

```python
# src/domain/services/targets/base.py (factory integrated with base)
class TargetFactory:
    """Factory for creating target creators."""

    def __init__(self) -> None:
        self._creators: dict[TargetType, type[BaseTargetCreator]] = {}

    def register(self, target_type: TargetType, creator_class: type[BaseTargetCreator]) -> None:
        self._creators[target_type] = creator_class

    def create(self, config: TargetConfig) -> BaseTargetCreator:
        return self._creatorsconfig.target_type

# Global factory with helper functions
_target_factory: TargetFactory | None = None

def get_target_factory() -> TargetFactory:
    """Get the global target factory."""
    ...

def register_target(target_type: TargetType, creator_class: type[BaseTargetCreator]) -> None:
    """Register a target type in the global factory."""
    ...
```

### 2. Safe Dynamic Target Types

| Target Type          | Description           | Formula                            | Data Leakage Risk |
| -------------------- | --------------------- | ---------------------------------- | ----------------- |
| `fixed_threshold`    | Fixed % price change  | `future_return >= 1%`              | SAFE ✅           |
| `volatility_scaled`  | 2-sigma moves         | `future_return >= 2 * rolling_vol` | SAFE ✅           |
| `atr_based`          | ATR-scaled threshold  | `future_return >= 1.5 * ATR`       | SAFE ✅           |
| `max_returns`        | Best exit in window   | `max(returns[1:12]) >= threshold`  | SAFE ✅           |
| `technical_filtered` | Returns + RSI/Support | `return >= threshold AND rsi < 30` | SAFE ✅           |

All safe because they use:

- **Future PRICES** for target calculation ✅
- **Current INDICATORS** for filtering ✅

### 3. Factory Pattern for Model Types

```python
# src/infrastructure/ml/models/factory.py
class ModelFactory:
    _models: dict[str, type[BaseModel]] = {}

    @classmethod
    def create(cls, model_type: str, **config) -> BaseModel:
        return cls._modelsmodel_type
```

### 4. Model Types

| Model Type            | Classes          | Use Case                    |
| --------------------- | ---------------- | --------------------------- |
| `xgboost_3class`      | BUY/HOLD/SELL    | Current default             |
| `xgboost_2class_buy`  | BUY vs NOT-BUY   | High-precision buy signals  |
| `xgboost_2class_sell` | SELL vs NOT-SELL | High-precision sell signals |
| `voting_ensemble`     | Configurable     | Combines multiple models    |

### 5. Admin Training UI

```
┌─────────────────────────────────────────────────────┐
│  Train New Model                                     │
├─────────────────────────────────────────────────────┤
│  Symbol:        [BTC/USDT ▼]                        │
│  Timeframe:     [1h ▼]                              │
│                                                      │
│  Model Type:    [XGBoost 3-class (BUY/HOLD/SELL) ▼] │
│                  - XGBoost 3-class (BUY/HOLD/SELL)  │
│                  - XGBoost 2-class (BUY vs NOT-BUY) │
│                  - XGBoost 2-class (SELL vs NOT)    │
│                  - Voting Ensemble                   │
│                                                      │
│  Target Type:   [Volatility-Scaled ▼]               │
│                  - Fixed Threshold (1%)             │
│                  - Volatility-Scaled (2σ)           │
│                  - ATR-Based (1.5x ATR)             │
│                  - Max Returns Window               │
│                  - Technical-Filtered               │
│                                                      │
│  [Start Training]                                   │
└─────────────────────────────────────────────────────┘
```

### 6. Feature Importance Display

After training, show SHAP feature importance with low-contributor warnings:

```
┌──────────────────────────────────────────────────┐
│ Feature Importance (SHAP):                       │
│ ┌──────────────────────────────────────────────┐ │
│ │ atr_14         ████████████████  0.137       │ │
│ │ bb_width       ██████████████    0.101       │ │
│ │ volume_ratio   ████████████      0.088       │ │
│ │ rsi_14         ██████████        0.049       │ │
│ │ macd           ████              0.028       │ │
│ │ stoch_k        ███               0.022  ⚠️    │ │
│ │ obv_slope      ██                0.015  ⚠️    │ │
│ └──────────────────────────────────────────────┘ │
│                                                  │
│ ⚠️ Low-contributing features: stoch_k, obv_slope │
│ [Remove & Retrain]  [Keep All]                  │
└──────────────────────────────────────────────────┘
```

## Architecture

### Backend Structure (Actual Implementation)

> **NOTE (2026-01-30):** Final implementation differs slightly from original proposal.
> Factory pattern is in `base.py` for targets (cleaner), and 2-class models share one file.

```
src/domain/services/targets/
├── __init__.py                # Exports all + registers targets
├── base.py                    # BaseTargetCreator + TargetFactory + TargetConfig
├── target_creator.py          # FixedThreshold (kept original name for compatibility)
├── volatility_target.py       # VolatilityScaledTarget
├── atr_target.py              # ATRBasedTarget
├── returns_target.py          # MaxReturnsTarget
└── filtered_target.py         # TechnicalFilteredTarget

src/infrastructure/ml/models/
├── __init__.py                # Exports all models
├── base.py                    # BaseModel
├── factory.py                 # ModelFactory
├── xgboost_model.py           # XGBoostModel (3-class BUY/HOLD/SELL)
├── xgboost_2class.py          # XGBoost2ClassBuyModel + XGBoost2ClassSellModel (both in one file)
└── voting_ensemble.py         # VotingEnsemble
```

**Design Decisions (vs original proposal):**

| Original Plan                     | Actual Implementation       | Why                               |
| --------------------------------- | --------------------------- | --------------------------------- |
| Separate `factory.py` for targets | Factory in `base.py`        | Cleaner - base + factory together |
| Rename to `xgboost_3class.py`     | Kept `xgboost_model.py`     | Avoid breaking imports            |
| Separate buy/sell files           | Both in `xgboost_2class.py` | DRY - shared logic together       |

### Database Schema

```sql
-- Training configurations stored for reproducibility
CREATE TABLE training_configs (
    id UUID PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    model_type VARCHAR(50) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_config JSONB,
    model_config JSONB,
    optuna_trials INTEGER DEFAULT 100,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);
```

## Implementation Priority

### Phase 1: Target Types (Sprint 2.0a) ✅ COMPLETE

1. ✅ Keep `TargetCreator` (FixedThreshold) - works as-is
2. ✅ Implement `TargetFactory` in `base.py`
3. ✅ Add `VolatilityScaledTarget`
4. ✅ Add `ATRBasedTarget`
5. ✅ Add `MaxReturnsTarget`
6. ✅ Add `TechnicalFilteredTarget`
7. ✅ Unit tests for all target types (24 tests)

### Phase 2: Model Types (Sprint 2.0b) ✅ COMPLETE

1. ✅ Keep `XGBoostModel` as 3-class model
2. ✅ Implement `ModelFactory`
3. ✅ Add `XGBoost2ClassBuyModel`
4. ✅ Add `XGBoost2ClassSellModel`
5. ✅ Add `VotingEnsemble`
6. ✅ Unit tests for all model types (12 tests for ensemble)

### Phase 3: Admin UI (Sprint 2.0c) 🔄 IN PROGRESS

1. ✅ TrainingJob domain model
2. ✅ TrainingJobRepository
3. ✅ TrainingValidationService (pre-training checks)
4. ✅ TrainingJobService (orchestration)
5. 🔄 Admin training page UI
6. ⏳ Feature importance display component
7. ⏳ Low-contributor warnings
8. ⏳ "Remove & Retrain" functionality

## Consequences

### Positive

- Admins can experiment without code changes
- Different strategies for different market conditions
- Better model transparency (feature importance)
- Reduced class imbalance with 2-class models
- Faster iteration on ML improvements

### Negative

- More complexity in training pipeline
- Need to document when to use each target/model type
- Training UI requires more backend endpoints
- More combinations to test

### Risks

- Users might not understand when to use which configuration
- More configurations = more potential for misconfiguration

### Mitigations

- Provide sensible defaults (volatility-scaled + 3-class for beginners)
- Add tooltips explaining each option
- Show recommended configuration based on symbol volatility
- Log all training configurations for audit

## References

- `trading_bots/backend/core/models/trend_detection/voting_bottom_signals_v11/` - Volatility-scaled targets
- `docs/02-technical/ML_PIPELINE.md` - Current pipeline documentation
- `docs/03-functional/ADMIN_DASHBOARD.md` - Admin UI specifications

## Decision Date

2026-01-26

## Decision Makers

- Main Architect (PulsAI)
