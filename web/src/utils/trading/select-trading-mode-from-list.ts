import type { TradingMode } from '@/types/tradingBarrel';
import { TRADING_MODE } from '@/utils/constants/trading';

/** First demo entry from GET /trading/modes (there is at most one). */
export function findDemoMode(modes: TradingMode[]): TradingMode | undefined {
  return modes.find((m) => m.kind === TRADING_MODE.DEMO);
}

/** First paper entry — retained for legacy callers that read auto-mode partition values. */
export function findFirstPaperMode(modes: TradingMode[]): TradingMode | undefined {
  return modes.find((m) => m.kind === TRADING_MODE.PAPER);
}

/** First live entry — Phase 5 mode list emits one live entry per active exchange connection. */
export function findFirstLiveMode(modes: TradingMode[]): TradingMode | undefined {
  return modes.find((m) => m.kind === TRADING_MODE.LIVE);
}
