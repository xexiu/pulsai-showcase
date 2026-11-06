/**
 * Internal timeframe type for chart utilities.
 *
 * NOTE: This is a SUPERSET of the app's Timeframe type (@/types/chart).
 * We support more timeframes internally for calculations (countdown, etc.)
 * but the UI only exposes a subset. See TIMEFRAME_MS for all supported values.
 */
export type ChartTimeframe =
  | '1m'
  | '3m'
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

export interface ChangeResult {
  /** Absolute percentage value */
  value: number;
  /** Whether change is positive or zero */
  isPositive: boolean;
}
