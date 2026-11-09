/**
 * Sum ledger fees per `order_id` for the open-orders table fallback column.
 *
 * Includes **all** trade sides (swap/open can be `sell` vs `buy` depending on venue mapping).
 * Spot FIFO helpers that need buy-only behavior live elsewhere (see `open-long-btc-by-order-id-after-fifo`).
 */

import type { TradeRow } from '@/types/tradingBarrel';

function formatFeePlain(n: number): string {
  if (!Number.isFinite(n) || n < 0) {
    return '0';
  }

  return n.toLocaleString(undefined, { maximumFractionDigits: 8 });
}

/** order_id → summed fee string from all trades referencing that order. */
export function sumBuyFeesQuoteByOrderId(trades: TradeRow[]): Map<string, string> {
  const acc = new Map<string, number>();

  for (const t of trades) {
    const oid = t.order_id?.trim();

    if (!oid) {
      continue;
    }

    const f = Number.parseFloat(t.fee);

    if (!Number.isFinite(f) || f < 0) {
      continue;
    }

    acc.set(oid, (acc.get(oid) ?? 0) + f);
  }

  const out = new Map<string, string>();

  for (const [k, v] of acc) {
    out.set(k, formatFeePlain(v));
  }

  return out;
}
