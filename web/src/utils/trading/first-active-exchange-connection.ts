import type { ExchangeConnection } from '@/types/tradingBarrel';

/**
 * Returns the first connection that can be used for trading UI (verified keys).
 * Disconnected rows remain in the list for reconnect but must not drive exchange branding.
 */
export function firstActiveExchangeConnection(
  connections: ExchangeConnection[] | undefined
): ExchangeConnection | undefined {
  if (!connections?.length) {
    return undefined;
  }

  return connections.find((c) => c.status === 'active');
}
