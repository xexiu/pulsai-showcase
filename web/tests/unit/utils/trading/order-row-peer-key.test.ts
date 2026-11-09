// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { orderRowPeerKey } from '@/utils/trading/order-row-peer-key';

describe('orderRowPeerKey', () => {
  it('prefers trimmed venue_client_order_id', () => {
    expect(
      orderRowPeerKey({
        venue_client_order_id: '  vc-1  ',
        ccxt_order_id: 'cx-1',
      })
    ).toBe('vc-1');
  });

  it('falls back to ccxt_order_id when venue id missing', () => {
    expect(
      orderRowPeerKey({
        venue_client_order_id: '   ',
        ccxt_order_id: 'cx-2',
      })
    ).toBe('cx-2');
  });

  it('returns null when both ids are empty', () => {
    expect(
      orderRowPeerKey({
        venue_client_order_id: null,
        ccxt_order_id: null,
      })
    ).toBeNull();
  });
});
