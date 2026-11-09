import type { OrderRow } from '@/types/tradingBarrel';

/**
 * True when the order is still working on the book (demo + paper/live).
 *
 * - Demo: pending limits, etc.
 * - Paper/live persisted orders: `pending`, `partially_filled` (see API `paper_order.status`).
 * - CCXT-normalized strings often use `open` or `new` for working orders.
 */
export function isOpenRestingOrderStatus(status: string): boolean {
  const s = status.trim().toLowerCase();

  return s === 'pending' || s === 'open' || s === 'new' || s === 'partially_filled';
}

/** Órdenes tab: same open-only rule for demo, paper, and live (exchange-style; History holds fills). */
export function filterOrderRowsToOpenResting<T extends Pick<OrderRow, 'status'>>(rows: T[]): T[] {
  return rows.filter((r) => isOpenRestingOrderStatus(r.status));
}
