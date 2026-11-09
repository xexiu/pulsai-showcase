import type { OrderRow } from '@/types/tradingBarrel';
import { isOptimisticOrderRow } from '@/utils/trading/build-optimistic-order-row';
import { isOpenRestingOrderStatus } from '@/utils/trading/is-open-resting-order-status';

/**
 * Open / working orders that can be cancelled on the book (demo or paper/live).
 *
 * Optimistic rows are excluded: their synthetic `optimistic-…` id would 404
 * on the cancel endpoint until the server-confirmed row replaces them.
 */
export function isTradingOrderCancellable(row: OrderRow): boolean {
  if (isOptimisticOrderRow(row)) return false;

  return isOpenRestingOrderStatus(row.status);
}
