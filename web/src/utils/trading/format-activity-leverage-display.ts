import type { MarketType } from '@/types/tradingBarrel';

/**
 * Activity table leverage cell: only meaningful for swap; otherwise callers show em dash.
 */
export function formatActivityLeverageDisplay(
  marketType: MarketType | null | undefined,
  leverage: number | null | undefined
): string | null {
  // See `resolve-trade-activity-side-i18n-key.ts` — avoid importing `trading` here (cycles with `@/types/tradingBarrel`).
  if (marketType !== 'swap') {
    return null;
  }

  if (leverage == null || !Number.isFinite(leverage)) {
    return null;
  }

  return `${leverage}x`;
}
