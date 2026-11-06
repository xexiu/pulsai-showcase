// =============================================================================
// Signal Validators - Valibot schemas for signal validation
// =============================================================================

import * as v from 'valibot';

import { DEFAULT_SUPPORTED_SYMBOLS } from '../constants/symbol-registry';
import { TIMEFRAME_REGISTRY_MS, type RegistryTimeframe } from '../constants/timeframe-registry';

/**
 * Trading symbol validation — derived from the shared symbol registry, never re-typed.
 */
export const TradingSymbolSchema = v.picklist(DEFAULT_SUPPORTED_SYMBOLS);

/**
 * Timeframe validation — DERIVED from the registry, never re-typed.
 *
 * This was the literal `['1m', '5m', '15m', '1h', '4h', '1d']`, which had fallen SEVEN timeframes
 * behind the backend: it rejected 30m, 2h, 6h, 8h, 12h, 3d and 1w, every one of them a real
 * registry member that signals are generated on. A validator that rejects valid production data
 * is worse than no validator, because the failure looks like bad input.
 *
 * Deriving from `TIMEFRAME_REGISTRY_MS` (itself parity-checked against the backend
 * `TIMEFRAME_REGISTRY` by a test) means adding a timeframe can never leave this behind again.
 */
export const TimeframeSchema = v.picklist(
  Object.keys(TIMEFRAME_REGISTRY_MS) as [RegistryTimeframe, ...RegistryTimeframe[]]
);

/**
 * Signal action validation
 */
export const SignalActionSchema = v.picklist(['BUY', 'SELL', 'HOLD']);

/**
 * MACD indicator validation
 */
export const MacdIndicatorSchema = v.object({
  value: v.number(),
  signal: v.number(),
  histogram: v.number(),
});

/**
 * Bollinger Bands validation
 */
export const BollingerBandsSchema = v.object({
  upper: v.number(),
  middle: v.number(),
  lower: v.number(),
});

/**
 * Signal indicators validation
 */
export const SignalIndicatorsSchema = v.object({
  rsi: v.pipe(v.number(), v.minValue(0), v.maxValue(100)),
  macd: MacdIndicatorSchema,
  bollingerBands: BollingerBandsSchema,
  ema20: v.number(),
  ema50: v.number(),
  volume24h: v.pipe(v.number(), v.minValue(0)),
  volumeChange: v.number(),
});

/**
 * Full signal validation
 */
export const SignalSchema = v.object({
  id: v.pipe(v.string(), v.uuid()),
  symbol: TradingSymbolSchema,
  timeframe: TimeframeSchema,
  action: SignalActionSchema,
  confidence: v.pipe(v.number(), v.minValue(0), v.maxValue(100)),
  price: v.pipe(v.number(), v.minValue(0)),
  timestamp: v.pipe(v.string(), v.isoTimestamp()),
  indicators: SignalIndicatorsSchema,
  modelVersion: v.string(),
});

/**
 * Sentiment score validation (-1 to 1)
 */
export const SentimentScoreSchema = v.pipe(v.number(), v.minValue(-1), v.maxValue(1));

/**
 * Sentiment label validation
 */
export const SentimentLabelSchema = v.picklist(['bearish', 'neutral', 'bullish']);

/**
 * Validate a signal object
 */
export function validateSignal(data: unknown) {
  return v.safeParse(SignalSchema, data);
}
