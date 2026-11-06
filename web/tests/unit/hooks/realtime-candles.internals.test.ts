/**
 * Pure Binance URL + kline parsing — behavior matches live chart contract.
 *
 * WHY test URL builders?
 * - Wrong stream name = silent empty chart; regression guard for symbol/timeframe formatting.
 */

import { describe, expect, it } from 'vitest';

import {
  buildConnectedFromPrevious,
  buildConnectingState,
  buildReconnectingState,
  buildWebSocketUrl,
  formatSymbolForBinance,
  parseKlineEvent,
} from '@/hooks/realtime-candles.internals';

describe('realtime-candles.internals', () => {
  it('buildConnectingState does not hydrate stale cached candles (hard-refresh guard)', () => {
    const state = buildConnectingState('5m');

    expect(state.liveCandle).toBeNull();
    expect(state.klineStreamTimeframe).toBe('5m');
    expect(state.connectionState).toBe('connecting');
  });

  it('formatSymbolForBinance strips slash and lowercases (BTC/USDT → btcusdt)', () => {
    expect(formatSymbolForBinance('BTC/USDT')).toBe('btcusdt');
  });

  it('buildWebSocketUrl uses kline stream for timeframe', () => {
    const url = buildWebSocketUrl('ETH/USDT', '4h');

    expect(url).toBe('wss://stream.binance.com:9443/ws/ethusdt@kline_4h');
  });

  it('parseKlineEvent returns null when k.t is invalid', () => {
    expect(
      parseKlineEvent({
        e: 'kline',
        k: { t: Number.NaN, o: '1', h: '2', l: '0.5', c: '1.5', x: false },
      })
    ).toBeNull();
  });

  it('buildReconnectingState keeps badge connected when a live candle is preserved', () => {
    const previous = {
      liveCandle: { time: 1, open: 1, high: 2, low: 0.5, close: 1.5 },
      klineStreamTimeframe: '5m' as const,
      connectionState: 'connected' as const,
      badgeState: 'connected' as const,
      isConnected: true,
      lastUpdate: 99,
      isCandleClosed: false,
      lastBarCloseOpenTimeSec: null,
    };

    const next = buildReconnectingState(previous);

    expect(next.badgeState).toBe('connected');
  });

  it('buildConnectedFromPrevious preserves the last live candle on socket open', () => {
    const previous = {
      liveCandle: { time: 1, open: 1, high: 2, low: 0.5, close: 1.5 },
      klineStreamTimeframe: null,
      connectionState: 'connecting' as const,
      badgeState: 'connected' as const,
      isConnected: false,
      lastUpdate: 99,
      isCandleClosed: false,
      lastBarCloseOpenTimeSec: null,
    };

    const next = buildConnectedFromPrevious(previous);

    expect(next.liveCandle).toEqual(previous.liveCandle);
    expect(next.connectionState).toBe('connected');
    expect(next.isConnected).toBe(true);
  });

  it('buildReconnectingState preserves the last live candle while reconnecting', () => {
    const previous = {
      liveCandle: { time: 1, open: 1, high: 2, low: 0.5, close: 1.5 },
      klineStreamTimeframe: '5m' as const,
      connectionState: 'connected' as const,
      badgeState: 'connected' as const,
      isConnected: true,
      lastUpdate: 99,
      isCandleClosed: false,
      lastBarCloseOpenTimeSec: null,
    };

    const next = buildReconnectingState(previous);

    expect(next.liveCandle).toEqual(previous.liveCandle);
    expect(next.lastUpdate).toBe(99);
    expect(next.connectionState).toBe('connecting');
    expect(next.isConnected).toBe(false);
  });

  it('parseKlineEvent converts ms to seconds and parses OHLC', () => {
    const candle = parseKlineEvent({
      e: 'kline',
      k: { t: 1_700_000_000_000, o: '10', h: '12', l: '9', c: '11', x: true },
    });

    expect(candle).not.toBeNull();
    expect(candle?.time).toBe(1_700_000_000);
    expect(candle?.open).toBe(10);
    expect(candle?.high).toBe(12);
    expect(candle?.low).toBe(9);
    expect(candle?.close).toBe(11);
  });
});
