"""
BacktestRun Domain Model (ADR-012)

SQLAlchemy model for persisted backtest runs.

WHY PERSIST BACKTESTS?
- Audit trail: Know what was tested and when
- Comparison: Compare runs without re-running
- Export: Download historical results
- History: View past backtest performance

Strategy Types:
- MODEL: Single ML model backtest
- CLASSIC: Classic signals backtest (RSI, MACD, BB)
- HYBRID: ML + Classic confirmation
- COMPARISON: Side-by-side strategy comparison
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Double, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, query_expression
from sqlalchemy.schema import Computed

from src.infrastructure.persistence.sqlalchemy_base import Base
from src.shared.utils.datetime_utils import utc_now

# The only keys any LIST view reads out of the `metrics` blob. The list queries extract
# exactly these server-side (see `_metrics_summary_expression`) so the blob -- measured at
# 169 kB average and 1.1 MB peak on the real table -- never leaves Postgres for a list.
# `backtest_to_summary` is held to this tuple by an AST parity test, so adding a key there
# without adding it here fails rather than silently returning None on every row.
SUMMARY_METRIC_KEYS: tuple[str, ...] = (
    "total_return",
    "sharpe_ratio",
    "win_rate",
    "num_trades",
    "benchmark_buy_hold_return",
)


class BacktestStatus(StrEnum):
    """
    Backtest run status.

    PENDING: Queued but not started
    RUNNING: Currently executing
    COMPLETED: Finished successfully
    FAILED: Execution error occurred
    CANCELLED: User cancelled
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StrategyType(StrEnum):
    """
    Backtest strategy type.

    MODEL: Single ML model backtest
    CLASSIC: Classic signals (RSI divergence, MACD crossover, BB squeeze)
    HYBRID: ML + Classic confirmation (higher confidence when both agree)
    COMPARISON: Side-by-side comparison of two strategies
    """

    MODEL = "model"
    CLASSIC = "classic"
    HYBRID = "hybrid"
    COMPARISON = "comparison"


class BacktestRun(Base):
    """
    Persisted backtest run for history and comparison.

    WHY THIS STRUCTURE?
    - config: Flexible JSONB to store strategy-specific parameters
    - metrics: Standard performance metrics for all strategies
    - trades: Individual trades for detailed analysis
    - equity_curve: For charting performance over time
    """

    __tablename__ = "backtest_runs"

    # DB-perf D1 (architect review): partial expression index supporting
    # ``BacktestRepository.find_latest_by_request_fingerprint``. Without it the
    # JSONB ``config ->> 'request_fingerprint'`` predicate degrades to a per-row
    # extraction over the user's full run history. The predicate is partial on
    # ``config ? 'request_fingerprint'`` because only programmatically-launched
    # runs carry a fingerprint — most UI-launched runs do not, so we keep the
    # index small. Mirrored by migration 20260510_db_perf_indexes_d1_d3.
    # Plan D-7: a promoted model is published as a PAIR of backtests at the cert cell's exact
    # levers -- TEST (`window_role: select`) and UNSEEN (`window_role: confirm`) -- and Q4 settles
    # that there is ONE pair per symbol/timeframe, a challenger REPLACING it rather than adding a
    # third row. Hence the key is (symbol, timeframe, role) and NOT (..., model_version, role),
    # which would allow one pair per version.
    #
    # Measured on the live DB 2026-09-20 before writing this: the table's only constraint was
    # `backtest_runs_pkey PRIMARY KEY (id)`. Two writers reach this table (the admin endpoint and
    # the research CLI), so an application-side check passes twice under a race -- the rule has to
    # live in the database.
    #
    # Partial on BOTH predicates, each load-bearing: `is_public` because a private run is the
    # user's own history and re-running a book is not a public claim; `config ? 'window_role'`
    # because every public row that exists predates the role (LOCAL 6 rows / 0 public; PROD 8
    # public rows measured 2026-09-12, none roled) and without it they would collapse onto one key
    # per book. Mirrored by migration 20260920_public_backtest_one_pair_per_book.
    __table_args__ = (
        Index(
            "ix_backtest_runs_user_request_fingerprint",
            "user_id",
            text("(config ->> 'request_fingerprint')"),
            text("created_at DESC"),
            postgresql_where=text("config ? 'request_fingerprint'"),
        ),
        Index(
            "uq_backtest_runs_public_book_window_role",
            "symbol",
            "timeframe",
            text("(config ->> 'window_role')"),
            unique=True,
            postgresql_where=text("is_public AND config ? 'window_role'"),
        ),
    )

    # Primary key
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # User who ran the backtest
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        index=True,
        comment="User who initiated the backtest",
    )

    # Strategy configuration
    strategy_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Strategy type: model, classic, hybrid, comparison",
    )

    # Strategy-specific config (flexible JSONB)
    # For MODEL: {"symbol": "BTC/USDT", "timeframe": "1h", "version": 5}
    # For CLASSIC: {"symbol": "BTC/USDT", "signals": ["rsi_divergence", "macd_crossover"]}
    # For COMPARISON: {"strategy_a": {...}, "strategy_b": {...}}
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Strategy-specific configuration",
    )

    # Trading pair and timeframe
    symbol: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    timeframe: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    # Date range for backtest
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Backtest start date",
    )
    end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Backtest end date",
    )

    # Performance metrics (stored as JSONB for flexibility)
    # Keys: sharpe_ratio, win_rate, max_drawdown, total_return, total_trades, profit_factor
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Performance metrics",
    )

    # Set ONLY by list queries, through with_expression(): the SUMMARY_METRIC_KEYS scalars
    # pulled out server-side. It is None on detail loads (which select the whole row and
    # already have `metrics`), and `backtest_to_summary` falls back to the blob then.
    # Not a column: query_expression() is a load-time slot, so it adds no DDL.
    metrics_summary: Mapped[dict[str, Any] | None] = query_expression()

    # DB-generated; mirrors coalesce on metrics for indexed admin list filter.
    # Each column has a standalone btree index from migration 20260442 — these
    # are sufficient for the ``list_backtests`` OR predicate (PG's BitmapOr
    # planner node unions both index scans). See the D4 closure note in that
    # migration's docstring for why we do not add partial duplicates.
    m_coalesce_tr: Mapped[float | None] = mapped_column(
        Double,
        Computed("coalesce((metrics->>'total_return')::double precision, -1.0)", persisted=True),
        nullable=True,
        comment="PG generated: coalesce total_return; listed until refresh",
    )
    m_coalesce_sharpe: Mapped[float | None] = mapped_column(
        Double,
        Computed("coalesce((metrics->>'sharpe_ratio')::double precision, -1.0)", persisted=True),
        nullable=True,
        comment="PG generated: coalesce sharpe_ratio; listed until refresh",
    )

    # Individual trades for detailed analysis and export
    # Each trade: entry_time, exit_time, pnl, side, entry_price, exit_price
    trades: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Individual trades executed",
    )

    # Equity curve for charting (normalized starting at 1.0)
    equity_curve: Mapped[list[float]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="Equity curve for charting (normalized to 1.0)",
    )

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=BacktestStatus.PENDING.value,
        index=True,
        comment="Backtest status",
    )

    # Error message (if failed)
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if backtest failed",
    )

    # Progress tracking (for long-running backtests)
    progress_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Progress percentage (0-100)",
    )

    # Timing
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: utc_now(),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When backtest started running",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When backtest completed",
    )

    # Optional name/description for user reference
    name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="User-provided name for the backtest",
    )

    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="If true, eligible for community list on /backtest (symbol+timeframe match)",
    )
    publicized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the run was first made public",
    )

    def __repr__(self) -> str:
        return f"<BacktestRun {self.id[:8]} {self.strategy_type} {self.symbol} {self.status}>"

    @property
    def duration_seconds(self) -> float | None:
        """Calculate backtest duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_running(self) -> bool:
        """Check if backtest is currently running."""
        return self.status == BacktestStatus.RUNNING.value

    @property
    def is_completed(self) -> bool:
        """Check if backtest completed successfully."""
        return self.status == BacktestStatus.COMPLETED.value

    @property
    def is_failed(self) -> bool:
        """Check if backtest failed."""
        return self.status == BacktestStatus.FAILED.value
