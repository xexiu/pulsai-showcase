# ADR-013: Backtesting Architecture Decisions

**Status**: Approved
**Date**: 2026-02-02
**Author**: Architect
**Sprint**: 2.1b / 2.3

## Context

The backtesting system needed several architectural decisions regarding:

1. Exit strategy for trades (fixed holding vs SL/TP)
2. Compound entries (pyramiding)
3. Leverage support (SPOT vs Futures)
4. Classic signals architecture

## Decision 1: Fixed Holding Periods for MVP Backtesting

### Decision

Use fixed holding periods (N candles) instead of Stop Loss/Take Profit for MVP backtesting.

### Rationale

| Approach       | Purpose                   | Risk                   |
| -------------- | ------------------------- | ---------------------- |
| Fixed Holding  | Isolate ML signal quality | None                   |
| SL/TP/Trailing | Realistic trading         | **Curve fitting risk** |

**Why fixed holding is better for model evaluation:**

- When testing if ML model produces good BUY/SELL signals, we want to isolate signal quality
- Adding SL/TP parameters introduces noise - users will over-optimize exit parameters
- Results that look good in backtest won't generalize to live trading

**Future consideration:**

- Add "Strategy Testing" mode with SL/TP in Phase 3+
- Separate from "Model Evaluation" mode (current)

### Consequences

- ✅ Simpler implementation
- ✅ Clear signal quality metrics
- ✅ No parameter over-fitting
- ❌ Less realistic trading simulation

## Decision 1b: Holding Periods vs Live/Autopilot Trading

### Context

Users may be confused about the relationship between the backtester's "Holding Period"
parameter and how live/autopilot trading will work.

### Key Distinction

| Mode                          | Exit Trigger           | Holding Period Used? |
| ----------------------------- | ---------------------- | -------------------- |
| **Backtesting**               | Fixed time (N candles) | ✅ Yes               |
| **Autopilot (3-class model)** | SELL signal from model | ❌ No                |
| **Autopilot (2-class model)** | Fixed time OR SL/TP    | ✅ Yes               |

### Rationale

**For Backtesting (Current):**

- Fixed holding is for **signal quality validation**
- "If I trust every BUY signal, what return do I get holding for N candles?"
- Controlled experiment with single variable (holding period)

**For Live/Autopilot (Phase 4):**

```
┌────────────────────────────────────────────────────────────────────┐
│           AUTOPILOT EXIT STRATEGY OPTIONS                          │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  OPTION A: Signal-Driven (3-class models)                          │
│  ─────────────────────────────────────────                         │
│  - BUY signal  → Open LONG position                                │
│  - HOLD signal → Do nothing                                        │
│  - SELL signal → Close position                                    │
│  - Model handles timing, no fixed holding needed                   │
│                                                                    │
│  OPTION B: Hybrid (RECOMMENDED for production)                     │
│  ──────────────────────────────────────────                        │
│  - BUY signal  → Open LONG position                                │
│  - Exit when: SELL signal OR stop-loss OR take-profit              │
│  - Better risk management than pure signal-driven                  │
│                                                                    │
│  OPTION C: Time-Based (like backtest)                              │
│  ─────────────────────────────────────                             │
│  - BUY signal  → Open LONG, close after N candles                  │
│  - Ignores SELL signals (not recommended)                          │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Recommendation

| Phase             | Mode          | Exit Strategy                 |
| ----------------- | ------------- | ----------------------------- |
| **Phase 2 (MVP)** | Backtest      | Fixed holding (current)       |
| **Phase 3**       | Paper Trading | Add signal-driven exit option |
| **Phase 4**       | Autopilot     | Hybrid (signal + SL/TP)       |

**Why Hybrid for Autopilot?**

1. **Safety**: SL/TP protects against bad signals
2. **Flexibility**: User configures risk tolerance
3. **Model trust**: SELL signal closes, but SL catches missed SELLs

### Implementation Notes

For Phase 4 Autopilot, the bot will:

```python
# Simplified autopilot logic
def on_signal(signal: Signal):
    if signal.type == "BUY" and not has_open_position():
        open_position(direction="LONG", sl=calculated_sl, tp=calculated_tp)

    elif signal.type == "SELL" and has_open_position():
        close_position(reason="SELL_SIGNAL")

    # SL/TP also auto-close via exchange order types
```

### Consequences

- ✅ Backtest stays simple for model validation
- ✅ Autopilot will be more sophisticated with multiple exit triggers
- ✅ Users understand the difference between testing and trading
- ❌ Backtest results may differ from live autopilot results

## Decision 1c: Realistic Execution Model (Sprint 2.1b Enhancement)

### Decision

Use NEXT candle's OPEN price for trade entry/exit, not the signal candle's CLOSE.

### Rationale

**The Problem with Close Price Entry:**

```
Signal detected at candle i close (price = 96)
→ Enter position at 96? NO! You can't time travel!
→ First opportunity to trade is next candle's open
```

**Implementation:**

```python
# BEFORE (Unrealistic - can time travel):
entry_price = close_prices[i]           # Signal candle's close
exit_price = close_prices[i + holding]  # Close after holding

# AFTER (Realistic - Sprint 2.1b):
entry_price = open_prices[i + 1]                    # NEXT candle's open
exit_price = open_prices[i + 1 + holding_periods]  # Open after holding
```

### Impact

| Metric      | Before             | After             | Real-World Accuracy                 |
| ----------- | ------------------ | ----------------- | ----------------------------------- |
| Entry Price | Close (optimistic) | Next Open         | ✅ Realistic                        |
| Exit Price  | Close              | Next Open         | ✅ Realistic                        |
| Timestamp   | Signal time        | Actual entry time | ✅ Accurate                         |
| Max Trades  | N                  | N-1               | ✅ Correct (last signal can't exit) |

### Consequences

- ✅ Backtest results closer to live trading
- ✅ No "look-ahead bias" in execution
- ✅ Conservative estimates (slightly worse than optimistic)
- ❌ Slightly fewer trades (last signal can't complete)

## Decision 2: No Compound Entries

### Decision

Do not implement compound entries (pyramiding/DCA) in backtester.

### Rationale

**What compound entries are:**

- Adding to winning positions (pyramiding)
- Averaging down on losing positions (DCA)

**Why NOT for PulsAI:**

1. **Signal Evaluation Problem**: If backtest shows 200% return, was it good signals or good pyramiding? Cannot isolate.

2. **Dangerous for users**: Averaging down is how retail traders blow accounts.

3. **Not our core value**: PulsAI is about ML signals, not capital management.

### Consequences

- ✅ Clear signal attribution
- ✅ Safer for users
- ✅ Simpler capital management
- ❌ May underperform strategies that use pyramiding

## Decision 3: SPOT Only (No Leverage) for MVP

### Decision

Support only SPOT trading (1x) in MVP. Defer futures/leverage to Phase 3+.

### Rationale

| Factor          | SPOT  | Futures/Leverage                    |
| --------------- | ----- | ----------------------------------- |
| Complexity      | Low   | High (liquidation, margin, funding) |
| Risk            | Low   | Very High                           |
| Regulatory      | Clear | Restricted in many jurisdictions    |
| User Protection | Safe  | Beginners can lose > deposited      |

**When to add futures:**

- Phase 3+ after MVP stable
- With user verification (experienced trader)
- Educational content about risks
- Maximum leverage caps (e.g., 5x, not 100x)

### Consequences

- ✅ Safer MVP launch
- ✅ Simpler implementation
- ✅ No regulatory concerns
- ❌ Lower potential returns in backtest

## Decision 4: Strategy Pattern for Classic Signals

### Decision

Refactor ClassicSignalGenerator to use Strategy Pattern with a detector registry.

### Rationale

**Before (Junior Code):**

```python
# To add new signal:
# 1. Edit enum
# 2. Edit CONFIDENCE_LEVELS dict
# 3. Edit generate() method (copy-paste logic)
# 4. Edit generate_predictions_for_backtest() method (duplicate!)
# 5. Maybe edit _calculate_action_and_confidence()
```

**After (Architect Code):**

```python
# To add new signal:
# 1. Create class implementing BaseSignalDetector
# 2. register_detector(MyNewDetector())
# Done!
```

**SOLID Compliance:**

- **S**ingle Responsibility: Each detector handles ONE signal
- **O**pen/Closed: Add signals without modifying existing code
- **L**iskov Substitution: All detectors interchangeable
- **I**nterface Segregation: Minimal detect() interface
- **D**ependency Inversion: Generator depends on abstraction

### Consequences

- ✅ Easy to add new signals
- ✅ Config-driven thresholds
- ✅ No DRY violations
- ✅ Testable in isolation
- ❌ Slightly more files

## Decision 5: Exit Strategy Framework (Sprint 2.5+)

### Context

The MVP backtester uses only fixed holding periods. Users need more realistic exit strategies
for strategy testing (separate from model evaluation).

### Decision

Implement configurable exit strategies via an `ExitStrategy` enum:

| #   | Strategy                    | Parameters                           | Use Case                       |
| --- | --------------------------- | ------------------------------------ | ------------------------------ |
| 1   | **Fixed Holding** (current) | `holding_periods`                    | Model signal quality testing   |
| 2   | **Raw Signal Exit**         | (none)                               | 3-class model exit timing test |
| 3   | **Fixed TP/SL**             | `sl_pct`, `tp_pct`                   | Basic risk management          |
| 4   | **R:R Based**               | `sl_pct`, `rr_ratio`                 | Standardized risk testing      |
| 5   | **ATR-Based**               | `atr_period`, `atr_mult`, `rr_ratio` | Volatility-adaptive exits      |
| 6   | **Trailing Stop**           | `initial_sl_pct`, `trail_pct`        | Profit-locking strategy        |

### Architecture

```python
class ExitStrategy(Enum):
    """Exit strategy options for backtesting."""
    FIXED_HOLDING = "fixed_holding"   # Exit after N candles (MVP)
    RAW_SIGNAL = "raw_signal"         # Exit on opposite signal (3-class)
    FIXED_TPSL = "fixed_tpsl"         # Fixed % stop-loss/take-profit
    RISK_REWARD = "risk_reward"       # SL + R:R ratio for TP
    ATR_BASED = "atr_based"           # Volatility-adaptive SL/TP
    TRAILING_STOP = "trailing_stop"   # Trail profits, lock gains

class CryptoBacktester:
    def __init__(
        self,
        exit_strategy: ExitStrategy = ExitStrategy.FIXED_HOLDING,
        # Fixed Holding
        holding_periods: int = 4,
        # TP/SL strategies
        stop_loss_pct: float | None = None,
        take_profit_pct: float | None = None,
        # R:R strategies
        risk_reward_ratio: float = 2.0,
        # ATR-Based
        atr_period: int = 14,
        atr_multiplier: float = 2.0,
        # Trailing Stop
        trail_pct: float = 0.5,
        trail_activation_pct: float = 1.0,
        # Position management (Sprint 2.4)
        max_open_positions: int | None = 1,
        ...
    ):
```

### Phased Implementation

| Phase           | Exit Strategies                      | Purpose                               | Status               |
| --------------- | ------------------------------------ | ------------------------------------- | -------------------- |
| **Sprint 2.4**  | Fixed Holding + max_positions        | Model evaluation (current)            | ✅ Done              |
| **Sprint 2.5**  | + Fixed TP/SL + R:R + ATR + Trailing | Strategy testing                      | ✅ Done              |
| **Sprint 2.5b** | + Raw Signal                         | Model-driven exits (SELL closes LONG) | ✅ Done (2026-02-08) |

### UI Wireframe

See `docs/03-functional/UI_WIREFRAMES.md` section "Backtest Configuration Form".

### Consequences

- ✅ Users can test different exit strategies
- ✅ Clear separation: Model Evaluation vs Strategy Testing
- ✅ Extensible architecture (add more strategies)
- ❌ More parameters = more curve fitting risk (mitigated with warnings)

---

## Implementation

### Files Changed/Created

**Backend:**

- `apps/api/src/api/v1/endpoints/backtest.py` - Added `signal_source` (ml/classic)
- `apps/api/src/domain/services/classic_signal_generator.py` - Added backtest support
- `apps/api/src/domain/services/signals/classic/` - New Strategy Pattern architecture:
  - `base.py` - BaseSignalDetector abstract class
  - `detectors.py` - 6 concrete detector implementations
  - `registry.py` - SIGNAL_REGISTRY with register/get functions

**Documentation:**

- This ADR

### API Changes

```python
# BacktestRequest now supports:
{
    "signal_source": "ml" | "classic",
    "model_version": 9,           # Required for ML mode
    "classic_signals": [          # Optional for Classic mode
        "rsi_divergence",
        "macd_crossover"
    ],
    ...
}
```

## §6 Linear perp simulation (leverage) — 2026-04 initiative

**Canonical implementation plan:** `.cursor/plans/backtest_linear_perp_leverage.plan.md` (repo).

### Decision (supersedes Decision 3 “SPOT only” for the dashboard product)

| State                                                      | Behavior                                                                                                                                                    |
| ---------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `leverage == 0` (default)                                  | **Spot** fixed-stake backtest — identical semantics and regression contract to pre-perp code paths.                                                         |
| `leverage >= MIN_LEVERAGE` (app SoT, same as paper: 3–100) | **Isolated USDT-linear futures simulation**: margin = notional / leverage; shorts allowed; simplified liquidation vs bar **low** (long) / **high** (short). |

Values `1..MIN_LEVERAGE-1` are **rejected** (aligns with live paper minimum).

### Leveraged compound DCA — phased user unlock (2026-07)

| State                           | Behavior                                                                                                                                   |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Default                         | `leverage > 0` + `max_compound_trades > 0` → **422** (unchanged safety default).                                                           |
| `allow_leveraged_compound=true` | Explicit advanced opt-in on `POST /backtest/run`; mandatory FE liquidation/ruin copy.                                                      |
| Caps (CERT-aligned)             | `max_compound_trades <= 4`, `leverage <= 6` when both are on.                                                                              |
| Promote-to-live                 | **Blocked** when saved config has both `leverage > 0` and `max_compound_trades > 0` until backtest vs live `compound_v2` parity is proven. |
| Research / CERT                 | Unchanged — scripts pass `allow_leveraged_compound=True` directly on `CryptoBacktester`.                                                   |
| Compare / Hub (parity)          | Same `allow_leveraged_compound` field + caps as `POST /backtest/run` (no silent 422 asymmetry).                                            |

### Phase 3 follow-up — promote lift (status: **blocked**, 2026-07)

Promote-to-live for leveraged compound **stays blocked**. Characterization tests:
`apps/api/tests/unit/domain/services/test_compound_backtest_vs_v2_parity_phase3.py`.

| Gap             | Evidence                                                                                                                                                                                      |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Step geometry   | Paper/backtest `validate_compound_min_step` = **last-fill** relative; live `compute_compound_v2_leg_limit_prices` = **anchor × (1 ± step×k)** linear — diverge after the first follow-on leg. |
| Executor wiring | `AutomationExecutorRunService` validates `compound_leg_schedule_v2` for swap-only, then places a **single** signal order — ladder legs are not placed on the tick.                            |

**Lift criteria (all required):** multi-leg executor placement E2E green; geometry SoT chosen + parity tests green; then remove `validate_promotion_leveraged_compound_blocked` with an ADR amendment.

Optional explicit `market_mode` on the API must **not** contradict `leverage` (`spot` + high leverage, or `linear_perp` + zero leverage → 422).

### Non-goals (documented; not hidden “out of scope” language)

- No **funding** rate time series; no **cross** margin; no exchange-identical liquidation engine.
- **Fees:** v1 reuses **spot** fee table from `FeeConfigService` / `EXCHANGE_FEES` (same as before); not a separate futures fee tier.
- **Mark / liq (amended 2026-10-18, LIQ-ONE):** the intrabar check reads OHLC **low/high** against the
  **liquidation** price (the bankruptcy price moved toward entry by the maintenance margin rate) and FILLS at the
  **bankruptcy** price, so a liquidated isolated position loses exactly its margin -- the venue closes it there and
  keeps any surplus for its insurance fund. Until this amendment the engine filled at the liquidation price (minus
  slippage), keeping the maintenance part: measured, a 50x liquidation booked -$8,000 of a $10,000 margin, while the
  risk-sized grade (`risk_sized_book`) and the lab (`money_paths`) booked -$10,000. A resting stop that filled before
  the liquidation price on its own bar closed the position first: that bar is read at the stop's fill (the thin-stop
  ladder carries it as `PlannedExit.stop_fill`); measured on SOL 5m v2 CONFIRM, the engine had flagged 1 such trade at
  40x and 4 at 50x as liquidations, and now liquidates exactly the grade's set on every lane. Formulas:
  `src/shared/math/linear_isolated_perp.py`.
- **Perp MMR mode (v1.1):** optional `perp_maintenance_margin_mode` = `flat` (default) or `tiered`; tiered uses constants (`0.004` / `0.025` split at `150_000` USD notional) and can be globally coerced to `flat` by `settings.backtest_perp_tiered_mmr_allowed`.
- **Kelly / sizing:** deployable equity for sizing remains **`available_balance + sum(locked_collateral)`** (margin only counts toward “committed” under perp), same Kelly code path as spot — ADR-consistent, tested under perp in Initiative tests.

### §Gate0Log (mandatory design gate — `/grill-me`)

1. **Decision log (chosen vs rejected)**
   - **Leverage-only FE wire** for v1; optional `market_mode` for strict clients only.
   - **Compare:** single shared `leverage` for both strategies (same economics surface).
   - **Async `run-async`:** no Redis response cache parity in v1 (documented UX asymmetry vs sync); no job dedupe unless a future ADR funds it.
   - **Cache stampede:** fail-open Redis unchanged; no singleflight in v1.

2. **Risks + mitigations**
   - Sync vs async / cache: ADR §6 + FE copy; `save_to_history` forces fresh on sync path per existing API.
   - Reproducibility: results depend on model artifact + OHLC snapshot, not only form fields.
   - Legal: user-visible “simulation / not live execution” strings via i18n (`backtest` namespace).

3. **FE / BE impact map**
   - BE: `BacktestRequest`, `build_backtest_history_config_and_strategy`, `RunBacktestRequest`, `BacktestExecutionRequest`, `_run_backtester`, `CryptoBacktester` + `backtester_trade_math` / `backtester_capital`, worker `_build_execution_request`, `CompareBacktestRequest` / routes / `CompareBacktestsRequest`, `user_backtest_comparisons` mismatch tuple, Hub optimize schemas.
   - FE: `BacktestConfig`, `buildBacktestRequestBody`, `BacktestConfigForm`, compare `CompareConfig` / `configToCompareRequest`, types `backtest-compare.ts`.

4. **Test strategy**
   - Domain golden: liquidation prices (long/short).
   - API: leverage validation + cache key includes `leverage`.
   - Worker: persisted `config` includes `leverage`.
   - Regression: `leverage=0` matches prior golden / characterization suites.

5. **Verification**
   - `cd apps/api && ./scripts/verify.sh`
   - `cd apps/web && pnpm verify` when FE touched.

## Related Documents

- `docs/01-business/ROADMAP.md` - Sprint 2.1b, 2.3
- `docs/02-technical/ML_PIPELINE.md` - Model architecture (cross-link: linear perp backtest = **simulation** only; see ADR-013 §6)
- `docs/04-structural/DDD_PATTERNS.md` - Strategy Pattern reference
- `.cursor/plans/backtest_linear_perp_leverage.plan.md` - Initiative plan + compliance gate

## References

- trading_bots/backend/core/models/backtest2.py - Reference implementation
- Cambridge ML Trading Study (2025) - Simple factors outperform complex models
- Bulkowski Pattern Research - Visual pattern success rates
