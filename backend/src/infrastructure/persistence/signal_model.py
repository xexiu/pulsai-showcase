"""
Signal Domain Model

SQLAlchemy model for trading signals (ML, Classic, Hybrid).

Signal Types (Sprint 2.0g):
- ML: XGBoost/ensemble prediction
- CLASSIC: Rule-based (RSI divergence, MACD crossover, etc.)
- HYBRID: ML + Classic agreement (+15% confidence boost)

Outcome Tracking (Sprint 2.0e):
- outcome: PENDING -> CORRECT/INCORRECT after evaluation
- outcome_price: Price at evaluation time
- outcome_evaluated_at: When outcome was determined

WHY outcome tracking:
- Calculate accuracy for retraining triggers
- Backtesting validation
- Model performance monitoring
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.persistence.sqlalchemy_base import Base
from src.shared.utils.datetime_utils import utc_now

#: Name of the unique index enforcing one signal row per (model, bar).
#:
#: Shared so `SignalRepository.save` can recognise THIS violation specifically and treat it as the
#: no-op it is, while a duplicate PRIMARY KEY — a genuine bug — still raises. Catching
#: `IntegrityError` broadly silenced both, which a pre-existing test caught immediately.
SIGNAL_ONE_ROW_PER_BAR_INDEX = "uq_signals_symbol_tf_model_version_bar"


class SignalType(StrEnum):
    """
    Signal generation method (Sprint 2.0g).

    ML: XGBoost/ensemble ML model prediction
    CLASSIC: Rule-based signals (divergences, crossovers, overbought/oversold)
    HYBRID: ML + Classic agreement (higher confidence when both agree)

    WHY distinguish signal types:
    - Compare ML vs Classic vs Hybrid performance in backtesting
    - Users can filter by signal type preference
    - Hybrid signals get +15% confidence boost when ML and Classic agree
    """

    ML = "ml"
    CLASSIC = "classic"
    HYBRID = "hybrid"


class SignalOutcome(StrEnum):
    """
    Signal prediction outcome status.

    PENDING: Not yet evaluated (signal too recent)
    CORRECT: Prediction matched actual price movement
    INCORRECT: Prediction did not match
    UNKNOWN: Unable to evaluate (missing data)
    """

    PENDING = "pending"
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNKNOWN = "unknown"


class Signal(Base):
    """Trading signal (ML, Classic, or Hybrid)."""

    __tablename__ = "signals"

    # DB-perf D2 (architect review): composite supporting
    # ``SignalRepository.get_latest_batch`` which does
    # ``DISTINCT ON (symbol, timeframe) ... ORDER BY symbol, timeframe, created_at DESC``.
    # Without a matching composite the planner sorts every symbol-filtered row
    # in memory, which becomes the dashboard's bottleneck as the hypertable
    # grows. Mirrored by migration 20260510_db_perf_indexes_d1_d3.
    #
    # The legacy auto-generated ``ix_signals_symbol`` (from ``index=True`` on
    # the symbol column) is dropped in migration 20260511 because the leading
    # ``symbol`` column of this composite already satisfies every standalone
    # ``WHERE symbol = ?`` query the old index served. Do NOT re-add
    # ``index=True`` to ``symbol`` — the integration test
    # ``test_d2_redundant_ix_signals_symbol_dropped`` will fail.
    __table_args__ = (
        Index(
            "ix_signals_symbol_tf_created_desc",
            "symbol",
            "timeframe",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        # ONE row per model per bar. Declared HERE as well as in migration
        # 20260827_signals_one_row_per_model_bar because a database built by ``create_all`` (the
        # test suite, a fresh dev box) never runs migrations — the constraint would then exist in
        # production and nowhere else, which is how a test suite comes to pass against a schema
        # nobody ships. Caught exactly that way: the idempotency tests wrote two rows because the
        # index was migration-only.
        #
        # ``created_at`` is the BAR OPEN for all four writers, so this is a real identity, not a
        # write timestamp. See SIGNAL_ONE_ROW_PER_BAR_INDEX for why the NAME is shared.
        #
        # THE FAMILY IS PART OF THE KEY (migration 20260917_signals_bar_key_includes_model_type): a
        # version label is shared across families, so two production members holding ``v2`` must
        # each record the bar. ``COALESCE`` keeps rows with no recorded family deduplicated -- a
        # bare nullable column would make every NULL distinct and reopen the August duplicate loop.
        Index(
            SIGNAL_ONE_ROW_PER_BAR_INDEX,
            "symbol",
            "timeframe",
            "model_version",
            text("COALESCE(model_type, '')"),
            "created_at",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        # No index=True: see __table_args__ comment — the composite
        # ix_signals_symbol_tf_created_desc covers ``WHERE symbol = ?`` as
        # well, and we dropped the redundant standalone index in 20260511.
    )
    timeframe: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    #: ML-only action/confidence **before** use-case final HOLD clamp (same bar as infer/ensemble).
    #: Parity with ML backtest live-step; nullable on legacy rows.
    ml_action: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )
    ml_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    price: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    #: WHICH model produced this signal, written at generation time from ``primary.metadata``.
    #:
    #: WHY ON THE ROW rather than looked up: answering "which model was this?" from the version
    #: alone means opening the bundle's ``metadata.json`` per request — measured at 784ms cold
    #: against a 200ms API budget. The serving path already holds these values; not writing them
    #: down is what forced the re-read, and the detail page filled the gap with a hardcoded
    #: "XGBoost" that is wrong for five of the six model types actually serving BTC/USDT.
    #:
    #: Nullable: every signal written before this column existed has no answer, and inventing one
    #: from the version number would be a guess presented as provenance.
    model_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Model architecture that produced this signal (lightgbm, gradient_boosting_clf, ...)",
    )
    #: What the model was trained to PREDICT (forward_return, triple_barrier, adaptive_quantile…).
    #: Not derivable from ``model_type``: the same estimator family serves several targets.
    target_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Training target the model was fitted on",
    )
    #: 2 (directional buy-only / sell-only book) vs 3 (BUY/HOLD/SELL). Without it a 2-class book
    #: and a 3-class one read identically in the UI while meaning different things.
    num_classes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of classes the classifier was trained on; null for regressors and legacy rows",
    )
    indicators: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    #: Inference input passed to the model (feature name -> value), same row as predict_proba
    model_input_features: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    #: display_timezone, candle_open_local_iso, candle_close_local_iso (IANA local labels; UTC = created_at)
    candle_time_display: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    feature_importance: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    meta_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    model_votes: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    inference_time_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: utc_now(),
        nullable=False,
        index=True,
    )

    # Signal type (Sprint 2.0g)
    # WHY: Distinguish ML vs Classic vs Hybrid for comparison and filtering
    # No index=True: the auto-named ``ix_signals_signal_type`` was dropped in
    # ``20260610_db_hygiene_dead_indexes_ohlcv_chunk_interval`` — signal_type is
    # low-selectivity (prod ~90% hybrid) so the planner never used it; it only
    # added write amplification. Keep create_all aligned with the migrated DB.
    signal_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SignalType.ML.value,
        comment="Signal generation method: ml, classic, hybrid",
    )

    # Classic signal sources (Sprint 2.0g)
    # WHY: Track which classic rules triggered the signal for transparency
    # Format: JSON with rule names as keys and boolean values
    classic_sources: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Which classic rules triggered (for CLASSIC/HYBRID signals)",
    )

    # Outcome tracking (Sprint 2.0e)
    # WHY: Needed for accuracy calculation in retraining triggers
    outcome: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SignalOutcome.PENDING.value,
        index=True,
    )
    outcome_price: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Price at outcome evaluation time",
    )
    outcome_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When outcome was determined",
    )

    def __repr__(self) -> str:
        return f"<Signal {self.symbol} {self.action} {self.signal_type} {self.confidence:.0f}%>"
