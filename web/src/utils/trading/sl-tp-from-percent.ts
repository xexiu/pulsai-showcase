/**
 * Derive stop-loss / take-profit prices from entry and distance (%) for trade UI.
 *
 * Long (buy): SL below entry, TP above entry.
 * Short (sell): SL above entry, TP below entry.
 *
 * Preset percentages live in `@/utils/constants/trading` (§12 SoT).
 */

import { TRADING_NUMERIC_EPSILON } from '@/utils/constants/trading';
import { DECIMAL_PLACES } from '@/utils/formatters/constants';

/** Format a positive USD price for HTML number inputs (trim trailing zeros). */
export function formatOrderPriceUsd(value: number): string {
  if (!Number.isFinite(value) || value < TRADING_NUMERIC_EPSILON) {
    return '';
  }

  const s = value.toFixed(DECIMAL_PLACES.CRYPTO_PRECISE).replace(/\.?0+$/, '');

  return s === '' ? '' : s;
}

export function stopLossPriceFromPercent(
  side: 'buy' | 'sell',
  entryPriceUsd: number,
  percentDistance: number
): number {
  if (!Number.isFinite(entryPriceUsd) || entryPriceUsd < TRADING_NUMERIC_EPSILON) {
    return Number.NaN;
  }

  if (!Number.isFinite(percentDistance) || percentDistance <= 0) {
    return Number.NaN;
  }

  const factor = percentDistance / 100;

  if (side === 'buy') {
    return entryPriceUsd * (1 - factor);
  }

  return entryPriceUsd * (1 + factor);
}

export function takeProfitPriceFromPercent(
  side: 'buy' | 'sell',
  entryPriceUsd: number,
  percentDistance: number
): number {
  if (!Number.isFinite(entryPriceUsd) || entryPriceUsd < TRADING_NUMERIC_EPSILON) {
    return Number.NaN;
  }

  if (!Number.isFinite(percentDistance) || percentDistance <= 0) {
    return Number.NaN;
  }

  const factor = percentDistance / 100;

  if (side === 'buy') {
    return entryPriceUsd * (1 + factor);
  }

  return entryPriceUsd * (1 - factor);
}
