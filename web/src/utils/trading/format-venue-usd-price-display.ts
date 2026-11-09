import { TRADING_BALANCE_UNAVAILABLE_MARK } from '@/utils/constants/trading';

/**
 * Format venue-provided USD price strings from GET /trading/orders (`venue_*` fields).
 * Values are already normalized plain decimals on the API; we locale-format for display.
 */
export function formatVenueUsdPriceDisplay(raw: string | null | undefined): string {
  if (raw == null || String(raw).trim() === '') {
    return TRADING_BALANCE_UNAVAILABLE_MARK;
  }

  const n = Number.parseFloat(String(raw).trim());

  if (!Number.isFinite(n)) {
    return TRADING_BALANCE_UNAVAILABLE_MARK;
  }

  return n.toLocaleString(undefined, { maximumFractionDigits: 8 });
}
