/**
 * CCXT exchange id for the active paper/live connection, from GET /trading/modes
 * ``label_params`` (BE: ``UnifiedTradingService.list_modes``).
 */

import type { TradingMode } from '@/types/tradingDomain';
import { TRADING_MODE_LABEL_PARAM_EXCHANGE } from '@/utils/constants/trading';

export function resolveVenueExchangeIdFromTradingMode(
  mode: TradingMode | null | undefined
): string | undefined {
  if (mode == null) {
    return undefined;
  }
  const raw = mode.label_params[TRADING_MODE_LABEL_PARAM_EXCHANGE];

  if (typeof raw !== 'string') {
    return undefined;
  }
  const trimmed = raw.trim();

  if (trimmed === '') {
    return undefined;
  }

  return trimmed.toLowerCase();
}
