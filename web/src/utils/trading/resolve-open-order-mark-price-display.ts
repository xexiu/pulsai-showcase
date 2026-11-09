import type { MarketType } from '@/types/tradingBarrel';
import { MARKET_TYPE, TRADING_BALANCE_UNAVAILABLE_MARK } from '@/utils/constants/trading';
import { formatVenueUsdPriceDisplay } from '@/utils/trading/format-venue-usd-price-display';

function formatPageMarkUsd(pageMarkUsd: number | null): string {
  if (pageMarkUsd == null || !Number.isFinite(pageMarkUsd)) {
    return TRADING_BALANCE_UNAVAILABLE_MARK;
  }

  return pageMarkUsd.toLocaleString(undefined, {
    maximumFractionDigits: 2,
  });
}

/**
 * Órdenes "Mark" column: prefer venue position mark for swap (exchange SoT), else page ticker.
 */
export function resolvePaperOpenOrderMarkPriceDisplay(opts: {
  marketType: MarketType | null | undefined;
  venueMarkPrice: string | null | undefined;
  pageMarkUsd: number | null;
}): string {
  const { marketType, venueMarkPrice, pageMarkUsd } = opts;

  if (marketType === MARKET_TYPE.SWAP) {
    const venueFormatted = formatVenueUsdPriceDisplay(venueMarkPrice);

    if (venueFormatted !== TRADING_BALANCE_UNAVAILABLE_MARK) {
      return venueFormatted;
    }
  }

  return formatPageMarkUsd(pageMarkUsd);
}
