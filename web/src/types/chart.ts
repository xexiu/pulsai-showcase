// =============================================================================
// Chart Types - TradingView Lightweight Charts
// =============================================================================

import type { ClassicIndicatorConfig } from '@/types/classic-indicator-config';

/**
 * OHLCV candlestick data structure.
 *
 * WHY THIS FORMAT?
 * - Matches Binance API response format
 * - Compatible with lightweight-charts library
 * - Time is Unix timestamp in seconds (not milliseconds)
 */
export type CandlestickData = {
  time: number; // Unix timestamp in seconds
  open: number;
  high: number;
  low: number;
  close: number;
};

/**
 * Volume bar data for the volume histogram.
 */
export type VolumeData = {
  time: number;
  value: number;
  color: string;
};

/**
 * OHLCV fetcher result shape (queryFetchers.fetchOHLCV).
 * Shared by fetcher and useOHLCVData; lives in @/types per CODING_STANDARDS.
 */
export type OHLCVFetcherResult = {
  candles: CandlestickData[];
  volumes: VolumeData[];
  /** Per-TF periods from GET /market/ohlcv (BE TIMEFRAME_CONFIGS SoT). */
  classicIndicatorConfig?: ClassicIndicatorConfig;
};

/**
 * Chart configuration options.
 */
export type ChartConfig = {
  /** Symbol to display (e.g., "BTC/USDT") */
  symbol: string;
  /** Timeframe for candles (e.g., "1h", "4h", "1d") */
  timeframe: Timeframe;
  /** Show volume histogram below chart */
  showVolume?: boolean;
  /** Enable crosshair */
  showCrosshair?: boolean;
  /** Height of the chart in pixels */
  height?: number;
};

/**
 * Supported timeframes.
 *
 * WHY THESE?
 * - 15m, 30m: Day traders (intraday positions)
 * - 1h: Most popular for swing entries
 * - 4h: Swing traders (multi-day positions)
 * - 1d: Position traders (weekly/monthly)
 * - 1w: Long-term trend analysis
 *
 * Sprint 2.2: Added 5m for scalpers/day traders
 */
/**
 * Chart timeframes. MUST mirror the backend `TIMEFRAME_REGISTRY` keys.
 *
 * `2h` closes the lower training band and `6h` the higher one — see
 * `apps/api/src/shared/constants/timeframe_bands.py`. Adding a member here without the backend
 * (or vice versa) is what broke both runtimes on 2026-08-12: `confluence.ts` referenced `'3d'`
 * while this union lacked it, and the API crash-looped on `Timeframe.D3` for the mirror reason.
 */
export type Timeframe =
  | '5m'
  | '15m'
  | '30m'
  | '1h'
  | '2h'
  | '4h'
  | '6h'
  | '8h'
  | '12h'
  | '1d'
  | '3d'
  | '1w';

/**
 * Binance API interval mapping.
 */

/**
 * Binance kline (candlestick) API response.
 *
 * Array format: [
 *   openTime, open, high, low, close, volume,
 *   closeTime, quoteVolume, trades, takerBuyBase, takerBuyQuote, ignore
 * ]
 */

/**
 * Parse Binance kline data to chart format.
 *
 * WHY SEPARATE FUNCTION?
 * - Single responsibility
 * - Easy to test
 * - Reusable for WebSocket data
 */

/**
 * Parse Binance kline to volume data.
 */
