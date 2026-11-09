"""
Training scalar defaults (SoT for SQLAlchemy column defaults and TrainingConfig).

WHY:
- `src/domain/models/training_job.py` must not depend on `infrastructure.config.training`
  (layering). Values stay aligned with `infrastructure/config/training.py` by importing
  **from here** in both places.
"""

DEFAULT_TRAINING_DAYS = 365
DEFAULT_OPTUNA_TRIALS = 100
# P2.3: signal-quality (rank-IC) is the honest hyperparameter-selection objective. `trading_performance`
# selected on backtest net, which the edge-hunt program proved picks multiple-testing LUCK (inflated
# coin-flips like btc v8, buried real 1d signal). Tradability/costs are gated DOWNSTREAM (honest
# exit-grid eval -> rolling-origin -> forward tape), not in the training objective.
DEFAULT_OPTIMIZATION_OBJECTIVE = "rank_ic"
DEFAULT_OPTIMIZATION_MODE = "standard"
DEFAULT_EXIT_STRATEGY = "fixed_holding"
DEFAULT_MODEL_TYPE = "xgboost_3class"

# Meta-labeling (López de Prado): a secondary binary model gates the primary
# signal. The gate threshold is a probability — suppress the signal to HOLD when
# P(profitable) < threshold. 0.5 = act only when the meta-model is net-positive.
DEFAULT_META_GATE_THRESHOLD = 0.5

# Number of cross-validation folds used when validating a meta-gate model.
# 0 = no fold-based validation (use the full training set for gate calibration).
# WHY 0: meta-gate training data is already limited (meta-labels on a subset of
# the primary model's signals); adding CV folds reduces the effective training
# size further and is not the default constraint for the gate.
META_GATE_VALIDATION_FOLDS: int = 0
