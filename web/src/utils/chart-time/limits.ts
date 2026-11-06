import { getPivotPeriodForTimeframe } from '@/utils/chart-time/timeframes';
import type { SubscriptionTier } from '@/utils/constants';
import {
  CHART_MIN_HISTORY_DAYS,
  MARKET_OHLCV_API_MAX_CANDLES,
  SIGNAL_FETCH_HISTORICAL_LIMIT_FALLBACK,
  SIGNAL_MAX_HISTORY_FALLBACK,
  SIGNAL_MAX_WEEK_CAP,
  TIMEFRAME_HISTORY_DAYS_OVERRIDES,
} from '@/utils/constants';
import { isReducedSignalTier } from '@/utils/signals/signal-tier-policy';

/**
 * A count of CANDLES.
 *
 * Branded so it cannot be passed where a row count is expected. On 2026-09-02 the same number
 * (`7`, "one week of daily candles") was produced here and consumed as a ROW limit in two
 * places — the API query and the in-memory merge cap. A bar carries one row PER MODEL, and
 * BTC/USDT 1d runs 8 model versions, so both consumers silently kept an eighth of one bar and
 * the chart drew markers on a single candle. Nothing in the type system objected.
 *
 * Grouping these into a class would not have helped: the ambiguity was in the VALUE, not in
 * where it lived. Making the unit part of the type is what makes the mistake unrepresentable.
 */
export type Bars = number & { readonly __unit: 'bars' };

/** A count of signal ROWS. rows = bars x models, so on the HTF band rows >> bars. */
export type SignalRows = number & { readonly __unit: 'signal-rows' };

const MIN_TIER_SIGNAL_LIMIT = 20;
/** Legacy flat default for coarse TFs (still below 2 days on 5m/15m if used alone). */
const OHLCV_DASHBOARD_CANDLE_FLOOR = 200;
/** Previous full-chart batch size; keep as floor so 1h+ still fetch generous history. */
const FULL_CHART_CANDLE_FLOOR = 500;

/** Per-TF override falls back to the global floor when no override is registered. */
function getMinHistoryDaysForTimeframe(timeframe: string): number {
  return TIMEFRAME_HISTORY_DAYS_OVERRIDES[timeframe] ?? CHART_MIN_HISTORY_DAYS;
}

/**
 * Candle limit for full chart: last CHART_MAX_DAYS, capped so 5m doesn't request 100k+.
 * Uses getPivotPeriodForTimeframe (SoT for candles-per-day). For GET chart-indicators / OHLCV.
 */

/**
 * Resolves the candle limit the SERVER publishes for a timeframe.
 *
 * Declared in this layer, not in `@/hooks/`, so that pure helpers (the peer-timeframe prefetch)
 * can depend on the CONTRACT without depending on React. `useChartCandleLimitResolver` supplies
 * the implementation; anything that cannot call a hook takes one of these as a parameter.
 */
export type ChartCandleLimitResolver = (timeframe: string) => number;

/**
 * Shared OHLCV bar count for chart-indicators (dashboard, trade, full chart).
 * Uses the deeper full-chart floor so every surface reads the same REST tail.
 */
export function getChartOhlcvSharedCandleLimit(
  timeframe: string,
  servedCandleLimit?: number | null
): number {
  // A NUMBER, not the served option object: this module has no business knowing the shape of a
  // config DTO, and every caller that has the option already has the field. It also gives the
  // signal marker window below the same one-line way to consume the served value.
  //
  // A non-positive served value is REJECTED rather than honoured — a `0` would otherwise sail
  // through as "served" and ask the API for an empty chart.
  return typeof servedCandleLimit === 'number' && servedCandleLimit > 0
    ? servedCandleLimit
    : getFullChartCandleFetchLimit(timeframe);
}

/**
 * GET /market/ohlcv (dashboard, paper trade, etc.): at least {@link CHART_MIN_HISTORY_DAYS}
 * of bars for the TF, never below the legacy 200-candle floor for coarse TFs, capped at API max.
 */
export function getOhlcvDashboardCandleLimit(timeframe: string): number {
  const perDay = getPivotPeriodForTimeframe(timeframe);
  const minForHistoryDays = perDay * getMinHistoryDaysForTimeframe(timeframe);

  return Math.min(
    Math.max(OHLCV_DASHBOARD_CANDLE_FLOOR, minForHistoryDays),
    MARKET_OHLCV_API_MAX_CANDLES
  );
}

/**
 * GET /market/chart-indicators (full chart): same minimum history rule as dashboard OHLCV,
 * with a higher floor so hourly charts still load a deep window.
 */
export function getFullChartCandleFetchLimit(timeframe: string): number {
  const perDay = getPivotPeriodForTimeframe(timeframe);
  const minForHistoryDays = perDay * getMinHistoryDaysForTimeframe(timeframe);

  return Math.min(
    Math.max(FULL_CHART_CANDLE_FLOOR, minForHistoryDays),
    MARKET_OHLCV_API_MAX_CANDLES
  );
}

/**
 * Signal marker window for a timeframe: the candles the chart ACTUALLY DRAWS, capped.
 *
 * WHY IT IS NOT "ONE WEEK". The old rule was `perDay * 7`, one week of candles, which is 2016
 * bars on 5m and **7 bars on 1d**. The chart does not draw one week — it draws
 * `getChartOhlcvSharedCandleLimit(tf)` candles, floor 500. So a daily chart rendered ~500
 * candles and asked for markers on the last seven; 493 could not carry a marker however many
 * signals existed. The error scaled with the timeframe, which is why it looked fine on 5m
 * (2016 >= 576 drawn) and near-empty on the HTF band.
 *
 * MEASURED against prod 2026-09-04, BTC/USDT: the 1d table holds 87 signal rows across 45
 * distinct bars and the chart requested 7. Coverage was 1.4% on 1d, 8.4% on 4h, 34% on 1h.
 *
 * Widening is cheap because rows are not bars: measured rows-per-bar is 1.93 (1d), 2.00 (4h/6h),
 * 2.80 (8h), 4.00 (12h), 1.00 (1h/5m). The ENTIRE 1d signal history is 87 rows, so asking for
 * 500 bars returns all of it.
 *
 * THIS SYMPTOM HAS RECURRED THREE TIMES and each earlier fix corrected a CONSUMER of the number
 * rather than the number: `FETCH_HISTORICAL_LIMIT = 20` (raised to a bigger constant), then
 * `limit=7` read as rows when the caller meant bars (fixed at the API), then this — a window
 * that was never tied to what the chart draws. Deriving it from the candle-limit SoT is what
 * stops "what is drawn" and "what is asked for" drifting apart a fourth time.
 *
 * AND THE FOURTH WAY IT COULD RECUR, closed here: once the SERVER began publishing the candle
 * limit, "the candle-limit SoT" stopped being a local function. This window derived the local
 * rule while the chart requested the served value, so the two were one config change away from
 * disagreeing again — with markers landing on a subset of the drawn candles, exactly the
 * reported bug. Pass `servedCandleLimit` (from `useChartCandleLimitResolver`) and they cannot.
 */
export function getSignalLimitForTimeframe(
  timeframe: string,
  servedCandleLimit?: number | null
): Bars {
  if (timeframe === '1w') {
    return Math.min(2, SIGNAL_MAX_WEEK_CAP) as Bars;
  }

  return Math.min(
    getChartOhlcvSharedCandleLimit(timeframe, servedCandleLimit),
    SIGNAL_MAX_WEEK_CAP
  ) as Bars;
}

/**
 * Primary fetch limit and max in-memory history for signal events (same value per TF).
 * Use when timeframe may be missing; fallbacks avoid requesting too many signals.
 */
function getSignalLimits(
  timeframe: string | undefined,
  servedCandleLimit?: number | null
): {
  maxRealtimeRows: SignalRows;
  historyBars: Bars;
} {
  const limit = timeframe ? getSignalLimitForTimeframe(timeframe, servedCandleLimit) : null;

  return {
    historyBars: limit ?? (SIGNAL_FETCH_HISTORICAL_LIMIT_FALLBACK as Bars),
    // Deliberately the same magnitude, but a DIFFERENT unit, and now named as one. It bounds the
    // unbounded real-time stream only; `mergeAndDedupeSignals` floors it at whatever the server
    // returned for the requested bar window, so it can never truncate history again.
    // The ONE deliberate crossing, and the compiler made me write it down: the real-time cap is
    // seeded from the same magnitude as the bar count. That is a sizing choice, not an identity —
    // it bounds a live stream, it does not describe the history window. Every other place the two
    // units met silently is now a type error.
    maxRealtimeRows: (limit ?? SIGNAL_MAX_HISTORY_FALLBACK) as number as SignalRows,
  };
}

/**
 * Tier-aware signal limits for chart marker history.
 *
 * Free/starter users keep half of baseline marker depth to match delayed-tier UX and
 * reduce noisy marker density. Pro/elite retain full baseline depth.
 */
export function getSignalLimitsForTier(
  timeframe: string | undefined,
  subscriptionTier: SubscriptionTier | string | undefined,
  servedCandleLimit?: number | null
): {
  maxRealtimeRows: SignalRows;
  historyBars: Bars;
} {
  const base = getSignalLimits(timeframe, servedCandleLimit);

  if (subscriptionTier == null) {
    return base;
  }
  const isReduced = isReducedSignalTier(subscriptionTier);

  if (!isReduced) {
    return base;
  }

  const reduced = Math.max(MIN_TIER_SIGNAL_LIMIT, Math.floor(base.historyBars / 2));

  return {
    historyBars: reduced as Bars,
    maxRealtimeRows: reduced as SignalRows,
  };
}
