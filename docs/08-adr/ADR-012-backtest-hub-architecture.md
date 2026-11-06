# ADR-012: Backtest Hub Architecture

## Status: APPROVED (Updated 2026-02-02)

## Date: 2026-01-30

## Last Updated: 2026-04-24 (Community public backtests + promote to trade)

## Context

PulsAI needs a centralized backtesting system that allows users to:

1. Run backtests on ML models
2. Run backtests on classic signals (RSI, MACD, BB)
3. Compare different strategies (Model vs Model, Model vs Classic, Hybrid)
4. Export results for further analysis
5. View historical backtest runs

Currently, backtesting is scattered:

- Model backtests happen during training
- No classic signal backtesting
- No comparison framework
- No backtest history/persistence

## Decision

Implement a **Backtest Hub** with phased delivery:

### Phase 2.1a: Foundation (COMPLETED)

- ~~Dedicated `/admin/backtests` page with sidebar link~~ **REMOVED in Sprint 2.3b**
- BacktestRun entity for persistence
- Single model backtest (refactor existing)
- CSV/JSON export functionality
- Backtest history table

### Phase 2.1b: Classic Signals + Comparison (COMPLETED)

- Classic signal backtester (RSI divergence, MACD crossover, BB squeeze)
- Model vs Classic comparison view
- Side-by-side metrics table

### Phase 2.1c: Advanced Comparison (DEFERRED to Phase 3)

- Model vs Model (A/B testing)
- Hybrid mode (Model + Signals confirmation)
- Equity curve overlay chart

### Phase 2.2+: AI Analysis (Future)

- AI analysis of backtest results
- Automated strategy recommendations

---

## Sprint 2.3b Update: Admin Backtests Removed

### Decision

Remove separate admin backtest pages/endpoints for MVP. Users access backtests via `/dashboard/backtest` (user-scoped).

### Rationale

1. **DRY Principle**: Admin and user backtest endpoints were ~80% identical code
2. **YAGNI**: Admin-only backtest view not needed for MVP
3. **Focus**: Prioritize user-facing features over admin features
4. **Simplicity**: Less code = fewer bugs = faster delivery

### What Was Removed

- `/apps/web/src/app/[locale]/admin/backtests/` (frontend pages)
- `/apps/api/src/api/routes/admin/backtests.py` (backend API)
- Admin sidebar link to backtests

### What Remains

- `/dashboard/backtest` - User runs and views their own backtests
- `/api/v1/backtest/run` - Execute backtests (with optional save to history)
- `/api/v1/backtests` - User-scoped backtest history CRUD
- BacktestRun entity with user_id for multi-tenancy
- BacktestService, BacktestRepository (shared infrastructure)
- Shared backtest_mappers.py (DRY compliant)

### Phase 3 Plan: Admin Backtest Features

When admin backtest features are needed, implement with:

1. **Audit logging**: Track who viewed/exported what
2. **Role-based filtering**: Admin can view all users' backtests
3. **Separate concerns**: Admin routes under `/api/v1/admin/backtests`
4. **Proper authorization**: AdminUser dependency with audit trail

```
# Phase 3 Admin Endpoints (NOT IMPLEMENTED YET)
GET    /api/v1/admin/backtests              # List ALL users' backtests
GET    /api/v1/admin/backtests/{id}         # View any backtest (with audit log)
GET    /api/v1/admin/backtests/user/{uid}   # List specific user's backtests
```

## Data Model

```python
class BacktestRun(Base):
    """
    Persisted backtest run for history and comparison.

    WHY PERSIST?
    - Audit trail: Know what was tested and when
    - Comparison: Compare runs without re-running
    - Export: Download historical results
    """
    __tablename__ = "backtest_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))

    # Strategy configuration
    strategy_type: Mapped[str]  # "model", "classic", "hybrid", "comparison"
    config: Mapped[dict] = mapped_column(JSONB)
    # For model: {"symbol": "BTC/USDT", "timeframe": "1h", "version": 5}
    # For classic: {"symbol": "BTC/USDT", "timeframe": "1h", "signals": ["rsi_divergence"]}
    # For comparison: {"model_a": {...}, "model_b": {...}}

    # Time range
    symbol: Mapped[str]
    timeframe: Mapped[str]
    start_date: Mapped[datetime]
    end_date: Mapped[datetime]

    # Results (stored as JSONB for flexibility)
    metrics: Mapped[dict] = mapped_column(JSONB)
    # {
    #   "sharpe_ratio": 1.5,
    #   "win_rate": 0.62,
    #   "max_drawdown": 0.15,
    #   "total_return": 0.45,
    #   "total_trades": 120,
    #   "profit_factor": 1.8
    # }

    trades: Mapped[list] = mapped_column(JSONB, default=list)
    # [{"entry_time": "...", "exit_time": "...", "pnl": 0.02, "side": "BUY"}, ...]

    equity_curve: Mapped[list] = mapped_column(JSONB, default=list)
    # [1.0, 1.02, 1.01, 1.05, ...] (normalized starting at 1.0)

    # Status
    status: Mapped[str] = mapped_column(default="pending")
    # "pending", "running", "completed", "failed"
    error_message: Mapped[str | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
```

## API Endpoints

### Current (Sprint 2.3b - User-Scoped)

```
# Backtest Execution
POST   /api/v1/backtest/run                 # Run backtest (ML or Classic)
                                            # Optional: save_to_history=true

# User Backtest History (user-scoped, requires auth)
GET    /api/v1/backtests                    # List user's backtests (paginated)
GET    /api/v1/backtests/recent             # Get recent backtests
GET    /api/v1/backtests/stats              # Get backtest counts by status
GET    /api/v1/backtests/{id}               # Get backtest details
PATCH  /api/v1/backtests/{id}               # Update backtest name
DELETE /api/v1/backtests/{id}               # Delete backtest
GET    /api/v1/backtests/{id}/export        # Download CSV/JSON
POST   /api/v1/backtests/check-duplicate    # Check for duplicate config
```

### Phase 3 (Admin - NOT IMPLEMENTED)

```
# Admin Backtest Management (requires AdminUser, with audit logging)
GET    /api/v1/admin/backtests              # List ALL backtests (all users)
GET    /api/v1/admin/backtests/{id}         # View any backtest (audit logged)
GET    /api/v1/admin/backtests/user/{uid}   # List specific user's backtests
```

## UI Structure

### Current (Sprint 2.3b)

```
/dashboard/backtest                         # User backtest page
├── BacktestConfig (form to configure & run)
│   ├── SymbolSelector
│   ├── TimeframeSelector
│   ├── DateRangePicker
│   ├── SignalSourceSelector (ML/Classic)
│   ├── ConfidenceSlider (ML only)
│   └── HoldingPeriodInput
├── BacktestResults (after running)
│   ├── MetricsSummary (key metrics cards)
│   ├── BacktestChart (signals + OHLCV)
│   └── TradesTable
└── BacktestHistory (list of saved runs)
    ├── HistoryTable (paginated)
    ├── LoadConfigButton
    ├── DeleteButton
    └── ExportButton (CSV/JSON)
```

### Phase 3 (Admin - NOT IMPLEMENTED)

```
/admin/backtests                            # Admin backtest oversight
├── BacktestList (all users, with filters)
├── UserFilter (filter by user)
├── AuditLog (who viewed what)
└── ExportAllButton (bulk export)
```

## Consequences

### Positive

- Centralized backtest management
- Persistent history for audit and comparison
- Export capability for external analysis
- Foundation for advanced comparison features
- **Sprint 2.3b**: Simplified architecture (no admin duplication)
- **Sprint 2.3b**: DRY compliant with shared mappers

### Negative

- Database storage for backtest results
- Additional API complexity
- Migration needed for new table

### Mitigations

- Auto-cleanup old backtests (>90 days, configurable)
- Paginated results to handle large datasets
- Background job for long-running backtests

## Community public backtests (2026-04)

### Decision

- **`backtest_runs.is_public`** (default false) + **`publicized_at`**: owner can POST-hoc toggle visibility via `PATCH /api/v1/backtests/{id}/visibility` (with **consent text version** for audit when making public; tier gating for publish).
- **In-app catalog**: `GET /api/v1/backtests/public` and `GET /api/v1/backtests/public/{id}` for **completed** public runs matching **symbol** (optional `timeframe` filter; omit = all TFs so form default TF does not hide other-TF publics) (rate-limited, authenticated). Default includes the viewer’s own public runs (`is_own` on each row; `exclude_own=true` still available). Each row includes `owner_label` from the author’s profile **name** (never email/`user_id`; fallback “Community member” for missing/anonymized accounts).
- **Promote to `TradingAutomation` (User Y)**: `POST /api/v1/trading/automations/promote-from-public-backtest` allows any authenticated user to create **their** draft automation from a **public** run’s snapshot (not only the owner’s `promote-from-backtest` path). `promoted_from_backtest_id` still points at the source run; **Y’s** row is `user_id = Y`. If the author later sets `is_public=false`, Y’s automation keeps the stored **strategy_snapshot**.
- **UI**: `/dashboard/backtest` shows a **Community** block (same symbol/TF as the form; own public rows labeled **Yours** plus `by {owner_label}` attribution) and **history** of the user’s runs (not auto-filtered by form symbol). History actions change visibility with **modals**; “Use on trade” uses the public promote endpoint, then users continue on **`/dashboard/trade`** to connect an exchange.

### Rationale

- Reuses existing `TradingAutomation` + promote snapshot pipeline; separate route avoids conflating **owner** vs **community** authorization.
- **404** for private runs in community promote and public detail (no existence leak).

## List query performance: admin and user backtest history (2026-04)

### Decision

- **ORM projection:** List-style repository methods (`list_backtests`, `list_community_public_backtests`, `get_recent_completed`) use `defer(BacktestRun.trades, BacktestRun.equity_curve)` so large JSONB is not read for summary rows; detail (`get_by_id`) remains full.
- **Pagination:** `list_backtests` (and community list) use `count() OVER()` in one round trip via `fetch_scalars_page_with_window` in `async_pagination.py`, with a subquery count fallback when the paged result is empty.
- **Positive return / Sharpe filter:** `only_positive_total_return_or_sharpe` uses generated stored columns `m_coalesce_tr` and `m_coalesce_sharpe` (mirroring `coalesce((metrics->>'...')::double precision, -1.0)`) with btree indexes for planner-friendly `OR` predicates, instead of ad hoc `text()` on `metrics` JSON.

## Alternatives Considered

### A: Keep backtests ephemeral (no persistence)

- Rejected: Loses history, can't compare without re-running

### B: Store only metrics, not trades

- Rejected: Trades needed for detailed analysis and export

### C: External backtesting service

- Rejected: Over-engineering for current scale, adds latency

### D: Separate admin and user backtest endpoints (Sprint 2.1a original)

- **Rejected in Sprint 2.3b**: DRY violation (~80% code duplication)
- User-scoped endpoints sufficient for MVP
- Admin features deferred to Phase 3 with proper audit logging

## References

- Sprint 2.3b in `ROADMAP.md`
- ADR-013 for backtesting architecture decisions
- Backtest execution: `apps/api/src/api/v1/endpoints/backtest.py`
- User backtest history: `apps/api/src/api/v1/endpoints/user_backtests.py`
- Shared mappers: `apps/api/src/application/services/backtest_mappers.py`
- Classic signals: `apps/api/src/domain/services/signals/classic/`
