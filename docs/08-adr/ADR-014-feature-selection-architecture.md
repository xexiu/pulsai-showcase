# ADR-014: Feature Selection Architecture

**Status**: Approved → **Implemented**
**Date**: 2026-02-09
**Author**: Architect
**Sprint**: 2.0k-fix (Part A + Part B both COMPLETE)

## Context

Sprint 2.0k (January 2026) was marked as "COMPLETE" for feature selection but delivered only:

- `FeatureSelectionConfig` and `FeatureSelectionResult` Pydantic schemas
- `PostTrainingAnalysisService` (analyzes feature importance AFTER training)
- `SHAPExplainerService` (SHAP values for explainability)

The actual feature selection pipeline -- correlation removal, Lasso filtering, RF importance ranking -- was **never wired into the training flow**. `_resolve_feature_columns()` in `train_model_data.py` returns ALL features from `FastFeatureCalculator` with zero selection.

**Evidence of the problem**: Model v14 (BTC/USDT 1h, XGBoost 3-class) trained on all 65 features and produced Sharpe ratio -5.99 with -3.12% net return.

Additionally, `LookaheadBiasDetector` and `DataLeakageDetector` (implemented in Sprint 2.0n) were fully functional but never called during training. The training flow used `validate_all()` (basic checks) instead of `validate_all_enhanced()` (includes lookahead + leakage detection).

## Decision

### Part 1: Multi-Stage Feature Selection

Implement a 4-stage selection pipeline adapted from `trading_bots/backend/core/helpers/feature_selection.py` and `trading_bots/backend/core/models/AbstractPredictor.py` (lines 313-419):

1. **Correlation removal** (threshold 0.85): Upper-triangle correlation matrix, drop one feature from each pair exceeding threshold. Adapted to Polars.
2. **Lasso filter**: `LassoCV` from sklearn, keep features with non-zero coefficients. Requires converting Polars DataFrame to numpy for sklearn.
3. **RF importance filter**: `RandomForestClassifier` importance scores, keep top N features.
4. **Cap at `max_features`** (default 25): Hard limit on final feature count.

Pipeline is **config-driven** via existing `FeatureSelectionConfig` and **toggled** by `use_feature_engineering` in `TrainingConfigRequest`.

Selected features are **persisted** in model metadata for inference consistency.

### Part 2: Feature Safety Gate

**Original plan:** Activate `validate_all_enhanced()` (replacing `validate_all()`) in `training_job_service.py`.

**Actual implementation (DRY refactor):**

1. **Merged** `validate_all_enhanced()` INTO `validate_all()` — one method, one code path.
   Having two methods caused `training_job_service.py` to call the "basic" one, silently
   skipping all enhanced checks. Now `validate_all()` always runs all 7 checks.

2. **Added `_run_safety_gate()`** directly in the training pipeline (`train_model.py`).
   Runs after `create_targets()`, before `_split_data()`. Uses `LookaheadBiasDetector` and
   `DataLeakageDetector` on Polars directly (no pandas conversion). Raises `SafetyGateError`
   if any critical issue found — training stops immediately.

Validators as **blocking gates**:

- `LookaheadBiasDetector`: blocks training if any feature correlates with future target beyond threshold
- `DataLeakageDetector`: blocks training if any feature nearly equals the target
- `FeatureDeterminismValidator`: blocks training if any feature gives different values across dataset sizes

This is a prerequisite for Sprint 2.Xf (Feature Enrichment) which adds complex indicators from `trading_bots` that have high lookahead risk.

## Alternatives Considered

### Single-method selection (Lasso only)

- **Pro**: Simpler, one sklearn call
- **Con**: Doesn't catch multicollinearity. Two highly correlated features could both have non-zero Lasso coefficients.
- **Rejected**: Correlation removal is necessary as a pre-filter.

### Qlib-style shuffling-based ablation

- **Pro**: More sophisticated, feature-model interaction aware
- **Con**: Already implemented inside `DoubleEnsemble` (Sprint 2.13). Applying it to all models is redundant and computationally expensive.
- **Rejected for standard models**: DoubleEnsemble already has its own internal feature selection.

### PCA (Principal Component Analysis)

- **Pro**: Mathematically optimal dimensionality reduction
- **Con**: Destroys interpretability. SHAP requires original feature names. PCA components are uninterpretable linear combinations.
- **Rejected**: Interpretability is critical for trading decisions.

### No selection (current state)

- **Pro**: No implementation effort
- **Con**: Proven unprofitable (Sharpe -5.99). All reference projects (`trading_bots`, Qlib) use 10-50 features, not 65+.
- **Rejected**: Status quo is actively harmful.

### Warning-only safety gate (no blocking)

- **Pro**: Doesn't interrupt training
- **Con**: Warnings get ignored. Sprint 2.Xf adds complex indicators with high lookahead risk. A bad feature in production means wrong trading signals and real money lost.
- **Rejected**: Safety gates must block, not warn.

## Consequences

### Positive

- Models train on 20-30 selected features instead of 65 unfiltered
- Reduced overfitting and improved generalization
- Backward compatible: `use_feature_engineering=False` (default) skips selection
- Bad features blocked before training starts
- Safe foundation for Sprint 2.Xf (Feature Enrichment)

### Negative

- Feature selection adds ~10-20 seconds to training time (correlation matrix + Lasso + RF)
- Requires Polars -> numpy conversion for sklearn methods (minor overhead)
- Blocking gates may reject training jobs that previously succeeded (intentional -- those jobs were training on bad data)

### Risks

- Default `max_features=25` may be too aggressive for some model types. Mitigation: configurable per training job.
- Lasso may behave differently on different target types (classification vs regression). Mitigation: use `LassoCV` with auto-tuned alpha.

## References

- `trading_bots/backend/core/helpers/feature_selection.py` (609 lines): VIF, correlation, Lasso, RF, MI, RFE, SHAP, stationarity, tsfresh
- `trading_bots/backend/core/models/AbstractPredictor.py` (lines 313-419): `combined_feature_selection()`, `remove_highly_correlated_features()`
- `trading_bots/backend/core/models/test_indicators_diff_datasets.py`: Determinism test (PulsAI equivalent: `FeatureDeterminismValidator`)
- Microsoft Qlib `double_ensemble.py`: Shuffling-based ablation (already in PulsAI's DoubleEnsemble)
- Sprint 2.0k documentation: `docs/01-business/ROADMAP.md` (Sprint 2.0k section)
- Sprint 2.0n: Enhanced Validation (implemented `LookaheadBiasDetector`, `DataLeakageDetector`)
