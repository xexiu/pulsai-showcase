/**
 * Aligns with backend ``paper_order_peer_key``: outbound ``venue_client_order_id`` (SoT),
 * else ``ccxt_order_id``.
 */

import type { OrderRow } from '@/types/tradingBarrel';

export function orderRowPeerKey(
  o: Pick<OrderRow, 'venue_client_order_id' | 'ccxt_order_id'>
): string | null {
  const vc = o.venue_client_order_id?.trim();

  if (vc) {
    return vc;
  }

  const cx = o.ccxt_order_id?.trim();

  if (cx) {
    return cx;
  }

  return null;
}
