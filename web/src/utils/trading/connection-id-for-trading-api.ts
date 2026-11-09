import { TRADING_MODE, type TradingModeKind } from '@/utils/constants/trading';

/**
 * Resolves `exchange_connection_id` for GET /trading/* calls.
 * Demo mode never sends a connection; paper/live use the selected connection when present.
 */
export function connectionIdForTradingApi(
  mode: TradingModeKind,
  connectionId: string | null | undefined
): string | null {
  if (mode === TRADING_MODE.DEMO) {
    return null;
  }

  return connectionId ?? null;
}
