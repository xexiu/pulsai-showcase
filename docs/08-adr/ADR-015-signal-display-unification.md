# ADR-015: Signal Display Unification (EXIT vs SELL)

**Status**: Approved
**Date**: 2026-02-09
**Author**: Architect
**Depends on**: Centralize OHLCV Data Pipeline, ADR-013

## Context

The same model (e.g., BTC-USDT/1h/v21) showed different signals on two pages:

- **Model detail page**: Trade-derived markers (BUY at entry, SELL at exit)
- **Backtest page**: Raw model predictions (BUY/SELL/HOLD per candle)

For 2-class BUY models, trade exits were incorrectly labeled "SELL" — the model cannot predict SELL. A position close (holding period, SL, TP) is an **EXIT**, not a model prediction.

## Decision

### 1. EXIT vs SELL Semantics

| Type     | Meaning                            | When Used                                                      |
| -------- | ---------------------------------- | -------------------------------------------------------------- |
| **BUY**  | Model prediction or long entry     | 3-class prediction; 2-class BUY prediction; long trade entry   |
| **SELL** | Model prediction or short entry    | 3-class prediction; 2-class SELL prediction; short trade entry |
| **EXIT** | Position close (backtester action) | Closing long or short — NOT a model prediction                 |

**WHY EXIT is distinct:**

- 2-class BUY model: Predicts BUY or HOLD only. When backtester closes a long (timeout, SL, TP), that's EXIT.
- 2-class SELL model: Predicts SELL or HOLD only. When backtester closes a short, that's EXIT.
- 3-class model: Can predict SELL to close long (RAW_SIGNAL exit). But time-based/SL/TP exits are still EXIT.

### 2. EXIT Marker Coloring (PnL-Based with Fallback)

**Primary (when net_pnl present):**

| net_pnl | Color | Meaning    |
| ------- | ----- | ---------- |
| > 0     | Green | Profitable |
| < 0     | Red   | Losing     |
| = 0     | Grey  | Break-even |

**Fallback (when net_pnl missing):** Side-based (ADR-015 original):

| side    | Color | Meaning                 |
| ------- | ----- | ----------------------- |
| long    | Red   | Sell-to-close (bearish) |
| short   | Green | Buy-to-close (bullish)  |
| missing | Red   | Backward compatibility  |

**WHY PnL-based:** Outcome is more useful for backtest review than trade direction.

### 3. Signal Type Cheat Sheet (Per Model Type)

| Model Type       | Prediction Markers       | Trade Markers                               |
| ---------------- | ------------------------ | ------------------------------------------- |
| **2-class BUY**  | BUY (green), HOLD (gray) | ENTRY (green), EXIT (PnL or side-based)     |
| **2-class SELL** | SELL (red), HOLD (gray)  | ENTRY (red), EXIT (PnL or side-based)       |
| **3-class**      | BUY, HOLD, SELL          | ENTRY (green/red), EXIT (PnL or side-based) |
| **Regression**   | N/A (422 error)          | N/A                                         |

### 4. Dual-Layer Chart Display

Both model detail and backtest pages show:

- **Prediction markers**: Small dots (what the model THINKS per candle)
- **Trade markers**: Large triangles (what the backtester DID — entries + exits)

## Consequences

- ✅ No misleading "SELL" on 2-class BUY charts
- ✅ Consistent semantics across model detail and backtest pages
- ✅ Future-proof for futures (EXIT = close position, long or short)
- ✅ Same pattern for Phase 3+ futures: EXIT remains position-close action
- ✅ EXIT markers show outcome at a glance (green=profit, red=loss, grey=break-even) when net_pnl present

## Futures Trading (Phase 3+)

When futures/leverage is added (ADR-013 Decision 3):

- **SPOT**: BUY=long entry, EXIT=close long (sell to close)
- **FUTURES**: BUY=open long, SELL=open short, EXIT=close either position
- EXIT type unchanged — it always means "position close"

## Related Documents

- `docs/02-technical/BACKTESTING_GUIDE.md` — EXIT semantics in execution model
- `docs/08-adr/ADR-013-backtesting-architecture.md` — SPOT vs Futures
- `docs/01-business/ROADMAP.md` — Phase 3+ futures
