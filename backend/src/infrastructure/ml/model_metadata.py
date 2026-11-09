"""
Model Metadata and Bundle Dataclasses.

Contains data structures for model versioning and storage.
Extracted from model_storage.py for better modularity.

@see docs/02-technical/ML_PIPELINE.md - Model Versioning
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.shared.constants.confidence import DEFAULT_MIN_SIGNAL_CONFIDENCE_THRESHOLD
from src.shared.constants.trading import DEFAULT_EXCHANGE


class ModelMetadata(BaseModel):
    """
    Metadata for a trained model.

    WHY Pydantic:
    - Validates field types at construction
    - model_dump(mode='json') auto-serializes datetime → ISO
    - model_validate() auto-parses datetime from ISO strings
    - Replaces manual to_dict/from_dict boilerplate

    Fields:
        version: Model version number (auto-incremented)
        symbol: Trading pair (e.g., "BTC/USDT")
        timeframe: Candle interval (e.g., "1h", "4h")
        created_at: Training timestamp
        training_samples: Number of samples used for training
        validation_folds: Number of walk-forward validation folds
        best_params: Optuna-optimized hyperparameters
        metrics: Training/validation/backtest metrics
        feature_columns: Feature names used by model
        notes: Optional notes about this version
        is_production: Whether this is the active production model
        feature_importance: SHAP feature importance scores
        confusion_matrix: 3x3 matrix for SELL/HOLD/BUY predictions
        deleted_at: Soft deletion timestamp (ADR-011)
        deleted_by: User ID who deleted
        was_ever_production: Compliance flag - set when promoted, never unset
        model_type: Model architecture (e.g., xgboost_3class)
        confidence_threshold: Minimum confidence for signals (0.0-1.0)
        test_start_date: Test set start date (for reproducible backtesting)
        test_end_date: Test set end date (for reproducible backtesting)
        generation: Semantic generation label (e.g., "gen1", "gen2") — auto-detected
        generation_notes: Human-readable description of this generation
        tags: Flexible labels for filtering (e.g., ["production", "best-sharpe"])
        optimization_objective: Training objective (e.g., "trading_performance", "accuracy")
    """

    model_config = ConfigDict(from_attributes=True)

    version: int
    symbol: str
    timeframe: str
    created_at: datetime
    training_samples: int
    validation_folds: int
    best_params: dict[str, Any]
    # Metrics can be nested (training, validation, backtest, per_class)
    metrics: dict[str, Any]
    feature_columns: list[str]
    notes: str = ""
    is_production: bool = False
    # SHAP feature importance scores
    feature_importance: dict[str, float] | None = None
    # Confusion matrix (3x3 for SELL/HOLD/BUY)
    confusion_matrix: list[list[int]] | None = None
    # Soft deletion fields (ADR-011)
    deleted_at: datetime | None = None
    deleted_by: str | None = None  # user_id who deleted
    was_ever_production: bool = False  # Set when promoted, never unset
    # Model type (e.g., xgboost_3class, xgboost_2class_buy)
    model_type: str | None = None
    # Confidence threshold used during training (0.0-1.0)
    # WHY store: Backtest page / admin display; platform floor is settings.signal_min_confidence_percent
    # Default SoT: shared.constants.confidence (same as GET /config/public limits)
    confidence_threshold: float = DEFAULT_MIN_SIGNAL_CONFIDENCE_THRESHOLD
    # Test set date range for reproducible backtesting
    # WHY store (2026-02-05): Training backtest uses 20% test split, but
    # backtest endpoint uses user-specified dates. Without tracking the exact
    # dates used in training, impossible to verify metrics match.
    # @see docs/02-technical/ML_PIPELINE.md - Test Set Date Tracking
    test_start_date: datetime | None = None
    test_end_date: datetime | None = None
    # ── Generation & Tags (Sprint 2.9c) ──────────────────────────
    # WHY: v1-v72 is meaningless. Generations group versions by fundamental
    # config changes (model_type, objective, target). Auto-detected on save.
    # @see docs/01-business/ROADMAP.md - Sprint 2.9c
    generation: str = ""  # "gen1", "gen2" — auto-detected or manual
    generation_notes: str = ""  # "3-class XGBoost, trading_performance objective"
    tags: list[str] = []  # ["production", "best-sharpe", "experimental"]
    # WHY store optimization_objective in metadata (not just TrainingJobConfig)?
    # 1. GenerationDetector needs it to detect generation bumps
    # 2. Admin can see what objective each model optimized for
    # 3. TrainingJobConfig lives in DB; metadata.json is self-contained
    optimization_objective: str | None = None
    holding_periods: int | None = None
    # Stable retrain config snapshot for future manual/scheduled retrains.
    # WHY store on the model artifact:
    # - Retrain flows must follow the production model's own contract
    # - Querying "latest completed job" by model_name is unstable and can drift
    #   away from what is actually running in production
    # - This excludes request-scoped flags such as batch_id/reset_optuna_study
    training_config: dict[str, Any] | None = None
    # Feature selection results (Sprint 2.0k Phase 2)
    # WHY store: At inference time, the model must use the SAME features it was
    # trained on. If selection reduced 71→25 features, inference must load these
    # exact 25 — feature_columns alone tells you WHICH features, but this field
    # records HOW they were selected (stages, removed features) for debugging.
    # None = old model or feature selection was not enabled.
    feature_selection: dict[str, Any] | None = None
    # ── Campaign tagging (Sprint 2.Xc) ───────────────────────────
    # WHY batch_id: Batch training creates N models for the same symbol/timeframe.
    # Arena previously filtered by (symbol, timeframe) which showed ALL models.
    # With batch_id in metadata, Arena filters to exact campaign models.
    batch_id: str | None = None
    # WHY target_type: Generation notes only had model_type + objective + features.
    # Adding target_type makes notes like "xgboost_3class, volatility, trading_performance, 25 features"
    # so admins can distinguish models at a glance without opening metadata.
    target_type: str | None = None
    # Vol/range overlay promotion evidence (nonprice_vol_fwd lane).
    promotion_probe: dict[str, Any] | None = None
    # Which chart bundle is authoritative (training vs overlay gate).
    chart_provenance: dict[str, Any] | None = None
    # ── Directional / class-count provenance (2-class fix) ───────
    # WHY: a model trained with `--direction buy` is a 2-class model (labels
    # {0,1}). The CLI maps `--model-type xgboost --direction buy` to
    # ModelType.XGBOOST (string "xgboost"), so model_type alone carries NO
    # direction hint and inference mis-maps class 1 → 3-class HOLD → 0 trades.
    # Persisting the direction the pipeline KNEW at train time lets the hub /
    # live inference map class 1 → BUY correctly. None = 3-class OR a legacy
    # model where direction was never persisted (backward compatible — callers
    # fall back to the model_type string).
    model_direction: str | None = None
    # Number of output classes (2 for directional, 3 for SELL/HOLD/BUY).
    # None = legacy model where the count was not persisted.
    num_classes: int | None = None
    # ── Model-exchange provenance (Phase 1b, latency-fix plan 8d8170ab) ──
    # WHY: the Phase 2 WebSocket supervisor MUST refuse to serve a model trained
    # on exchange X with live bars from exchange Y (no silent cross-exchange
    # failover). That barrier requires every bundle to declare which exchange
    # it was trained on. Historically all production models were trained via
    # DEFAULT_EXCHANGE = Exchange.BINANCE.value — see
    # `src/shared/constants/trading.py`. The default here matches that reality
    # so pre-Phase-1b metadata.json files remain loadable AND are correctly
    # attributed to Binance (not marked as "unknown", which would surface as a
    # runtime barrier trip for models that in fact ARE Binance-trained).
    # Value MUST equal a CCXT exchange id — enforce by passing an Exchange enum
    # value at the call site (see `src/domain/enums.py::Exchange`).
    exchange: str = DEFAULT_EXCHANGE
    # ── Meta-labeling (Slice 2b-ii) ──────────────────────────────
    # WHY: a meta-gate is a binary act/pass model that gates a PRIMARY model's
    # signals. is_meta_model distinguishes it from a primary (model_type alone is
    # the binary engine, e.g. xgboost_2class_buy, which is ambiguous); primary_model_id
    # records which primary it gates. Optional + default-off → pre-2b-ii metadata.json
    # files load unchanged (gate OFF).
    is_meta_model: bool = False
    primary_model_id: str | None = None
    # The gate's suppression threshold (P(act) below this → HOLD). Only meaningful for a
    # meta-gate; None for primaries (omitted by exclude_none). Inference falls back to
    # DEFAULT_META_GATE_THRESHOLD when absent.
    meta_gate_threshold: float | None = None
    # ── Leverage-governance decouple (item 87, owner 2026-07-23) ──────────
    # WHY: a served CANDIDATE (fails the OOS edge bar but shown on-chart + offered as an opt-in
    # live signal) must carry its honest tier + risk disclosure with every signal so it never
    # reaches a user as a bare BUY/SELL. Structured block {tier, is_edge, served, serve_mode,
    # label, oos_gate, spot_vs_buyhold, leverage_profile, ...} — see
    # application/services/model_governance_view.resolve_model_governance. Previously DROPPED by
    # from_dict (undeclared → pydantic ignore); declaring it preserves it for every consumer
    # (signals API, admin registry). None = validated edge or legacy model (nothing to disclose).
    honest_verdict: dict[str, Any] | None = None
    # ── Training-environment provenance ──────────────────────────
    # WHY: scikit-learn embeds `_sklearn_version` in each pickle and warns on mismatch at LOAD time
    # ("Trying to unpickle estimator Ridge from version 1.8.0 when using version 1.9.0. This might
    # lead to breaking code or invalid results."). Measured 2026-08-26: 6 of 148 model.joblib files
    # were pickled by 1.8.0 against an installed 1.9.0, and **1 of 106** metadata.json files
    # recorded any library version. So the only signal was a warning in a log, after the model had
    # already been used — and for the 59 native LightGBM/XGBoost/CatBoost artifacts there is no
    # embedded version to recover at all, making this the only possible record.
    # Stamped in ModelStorage.save (see capture_training_library_versions), not by call sites.
    # None = artifact predates this field.
    library_versions: dict[str, str] | None = None
    # ── Pre-committed confirm levers (select/confirm cert) ───────
    # WHY: a served signal says WHICH model predicted, never HOW that model's money was made. The
    # confirm run freezes one cell -- lane, exit, holding, sizing, DCA depth, confidence floor --
    # and every capital number published for the model is that cell's. Without it on the artifact a
    # user reads "1d lightgbm v42, BUY 72%" and cannot tell a spot book from an 8x book, which is
    # the difference between a 6% loss and a liquidation on the same model (see
    # `.claude/rules/ml-gate-leverage-capital-cert.md`).
    # Stamped by `research_loop_model_cert.stamp_precommitted_levers_into_metadata` on each confirm
    # run. DECLARED here, not merely written: this model's config is `from_attributes=True` with
    # pydantic's default `extra="ignore"`, so an undeclared key is silently DROPPED at load -- the
    # exact defect `honest_verdict` above records. Measured: 24 artifacts carried the key on disk
    # and 0 of them survived `model_validate`.
    # None = a model whose confirm run has not been recorded (189 of 213 at time of writing).
    precommitted_levers: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        WHY Pydantic model_dump:
        - Auto-converts datetime → ISO string
        - exclude_none removes None fields (matches previous behavior)
        - DRY: No manual field enumeration
        """
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelMetadata:
        """
        Create ModelMetadata from dictionary.

        WHY Pydantic model_validate:
        - Auto-parses datetime from ISO strings
        - Validates all field types
        - Handles optional fields with defaults
        """
        return cls.model_validate(data)


class SaveModelParams(BaseModel):
    """
    Caller-facing parameters for saving a trained model.

    WHY this schema (Sprint 2.9c refactor):
    - ModelStorage.save() had 16+ kwargs — Long Parameter List smell
    - Every new field meant touching 3+ call sites (persistence, pipeline, tests)
    - This schema groups all caller-provided metadata into a validated object
    - Binary artifacts (model, scaler) stay as separate args — they're not metadata

    WHAT GOES HERE vs ModelMetadata:
    - SaveModelParams: what the CALLER provides (training output)
    - ModelMetadata: what gets PERSISTED (adds version, created_at, generation, etc.)
    - save() creates ModelMetadata FROM SaveModelParams + auto-generated fields

    Usage:
        params = SaveModelParams(
            symbol="BTC/USDT",
            timeframe="1h",
            training_samples=10000,
            ...
        )
        version = storage.save(model=xgb_model, params=params, scaler=scaler)
    """

    model_config = ConfigDict(from_attributes=True)

    # ── Identity ──────────────────────────────────────────────────
    symbol: str  # Trading pair (e.g., "BTC/USDT")
    timeframe: str  # Candle interval (e.g., "1h", "4h")
    # ── Training results ──────────────────────────────────────────
    training_samples: int
    validation_folds: int
    best_params: dict[str, Any]
    metrics: dict[str, Any]  # Nested: training, validation, backtest, per_class
    feature_columns: list[str]
    # ── Optional metadata ─────────────────────────────────────────
    notes: str = ""
    set_as_production: bool = False
    feature_importance: dict[str, float] | None = None
    confusion_matrix: list[list[int]] | None = None
    model_type: str | None = None
    test_start_date: datetime | None = None
    test_end_date: datetime | None = None
    optimization_objective: str | None = None
    holding_periods: int | None = None
    training_config: dict[str, Any] | None = None
    # Feature selection results — persisted to metadata.json for debugging
    feature_selection: dict[str, Any] | None = None
    # Campaign tagging — propagated from TrainingConfig.batch_id
    batch_id: str | None = None
    # Target labeling strategy — propagated for richer generation notes
    target_type: str | None = None
    # ── Directional / class-count provenance (2-class fix) ───────
    # WHY mirror ModelMetadata here: SaveModelParams is the caller-facing save()
    # contract. The training pipeline KNOWS model_direction ("buy"/"sell"/None)
    # and the detected class count; without these fields that knowledge is
    # dropped before reaching metadata.json, and a CLI-trained directional model
    # gets backtested as 3-class. Defaults None so existing callers are unchanged.
    model_direction: str | None = None
    num_classes: int | None = None
    # ── Model-exchange provenance (Phase 1b) ─────────────────────
    # WHY mirror ModelMetadata.exchange here: SaveModelParams is the caller-
    # facing save() contract. Without this field, training code has no way to
    # declare which exchange the bundle was trained on, and the persistence
    # layer would have to guess — defeating the whole point of Phase 1b.
    # Default is DEFAULT_EXCHANGE so existing callers (tests, scripts that
    # never passed an exchange) keep their previous Binance-only behaviour.
    exchange: str = DEFAULT_EXCHANGE
    # ── Meta-labeling (Slice 2b-ii) ──────────────────────────────
    # Mirrors ModelMetadata: the caller (meta-model save path) declares the gate's
    # primary linkage. Default-off keeps every existing save() call unchanged.
    is_meta_model: bool = False
    primary_model_id: str | None = None
    meta_gate_threshold: float | None = None
    # ── Governance (GOV-1) ───────────────────────────────────────
    # The block `ModelMetadata.honest_verdict` stores and `model_governance_view` reads. OPTIONAL
    # because callers rarely have a real one: `ModelStorage.save` auto-stamps an `ungraded` verdict
    # when this is None, so coverage does not depend on every call site remembering. Supply it only
    # when a REAL verdict exists (the lifecycle gate graded the model) — a supplied verdict is never
    # overwritten by the auto-stamp.
    #
    # Before this field, `ModelMetadata` could HOLD a verdict and `SaveModelParams` had no way to
    # pass one, so 0 of 70 metadata files carried the block and every read fell through to
    # `_UNGRADED_PRODUCTION_GOVERNANCE` — the substitute working as designed on a corpus where the
    # field was never populated.
    honest_verdict: dict[str, Any] | None = None


class ModelBundle(BaseModel):
    """
    Bundle containing model and its metadata.

    WHY bundle: Groups related artifacts for loading/saving.
    Model + metadata always travel together.

    WHY Pydantic with arbitrary_types_allowed:
    - model (XGBClassifier) and scaler (RobustScaler) are complex objects
    - Cannot be validated by Pydantic, but bundling them is useful
    - Consistent with other Pydantic models in infrastructure

    Fields:
        model: Trained XGBClassifier instance
        metadata: Associated ModelMetadata
        scaler: Optional RobustScaler for feature normalization
    """

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    model: Any  # XGBClassifier
    metadata: ModelMetadata
    scaler: Any | None = None  # Optional RobustScaler
