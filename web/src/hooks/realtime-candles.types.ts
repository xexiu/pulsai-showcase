/**
 * Realtime Binance kline WebSocket types (co-located with realtime-candles modules).
 */

import type { CandlestickData, Timeframe } from '@/types/chart';
import type {
  RealtimeCandlesBadgeState,
  RealtimeCandlesConnectionState,
} from '@/types/realtime-candles';

export type {
  RealtimeCandlesBadgeState,
  RealtimeCandlesConnectionState,
} from '@/types/realtime-candles';

export type BinanceKlineEvent = {
  e: string;
  /** Event time (ms epoch). Used to drop stale / out-of-order frames on reconnect. */
  E?: number;
  k: { t: number; o: string; c: string; h: string; l: string; x: boolean; v?: string };
};

export type WebSocketState = {
  liveCandle: CandlestickData | null;
  /** Binance `kline_*` stream that produced `liveCandle`; null while connecting or after TF/symbol change. */
  klineStreamTimeframe: Timeframe | null;
  connectionState: RealtimeCandlesConnectionState;
  badgeState: RealtimeCandlesBadgeState;
  isConnected: boolean;
  lastUpdate: number | null;
  isCandleClosed: boolean;
  /** Latched open time (seconds) of the last finalized bar; survives the next forming tick. */
  lastBarCloseOpenTimeSec: number | null;
};

/** Public hook result — identical to internal socket state (no duplicate fields). */
export type UseRealtimeCandlesResult = WebSocketState;
