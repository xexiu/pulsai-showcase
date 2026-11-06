# ADR-016: ML prediction marker anchor (LWC vs Plotly parity)

**Status:** Accepted  
**Date:** 2026-04-21  
**Scope:** `apps/web` — TradingChart (dashboard, full chart, paper-trade). Plotly backtest unchanged.

## Context

- Backend `Signal.timestamp` / OHLCV row key = **bar open** (UTC).
- **Legacy LWC** drew ML prediction markers at **open + 1×timeframe** so the dot sat at the **close instant** on the axis (documented in `chart-converters/markers.ts` tests).
- **Plotly** backtest traces use **bar open** x directly → two UIs could disagree for the same logical prediction.

## Decision

1. Introduce a **single resolver** (`resolveMlPredictionChartBarOpenUtc`) used by:
   - `getSignalMarkerTimeUtc` / `convertSignalsToMarkers`
   - `signalToChartBarTime` and ML tooltip lookup (`chart-tooltip-signals.ts`) so **markers and hover stay aligned**.

2. **Env (build-time)** — `NEXT_PUBLIC_CHART_ML_PREDICTION_MARKER_USE_BAR_OPEN_ONLY`
   - **unset** or `true` → **bar open** anchor (Plotly / row-key parity); this is the product default.
   - `false` → **legacy** (`open + period`) for rare debugging or comparison.

3. **Legacy:** kept as an explicit opt-out only; no timed rollout.

## Consequences

- Trade **execution** markers (entry/exit/fills) remain governed by backtester / venue semantics — **not** this flag.
- Changing anchor affects **only** ML prediction placement + tooltip matching for those markers.

## Verification

- `cd apps/web && pnpm exec vitest run tests/unit/utils/chart-converters.test.ts tests/unit/utils/chart-tooltip-helpers.test.ts tests/unit/config/chart-ml-prediction-marker-anchor.test.ts`
