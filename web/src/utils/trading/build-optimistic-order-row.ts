import type { OrderRow, PlaceOrderRequest } from '@/types/tradingBarrel';
import { PAPER_ORDER_STATUS } from '@/utils/constants/trading';

/** Prefix used to recognize an optimistic (not-yet-server-confirmed) row. */
export const OPTIMISTIC_ORDER_ID_PREFIX = 'optimistic-' as const;

export function isOptimisticOrderRow(row: Pick<OrderRow, 'id'>): boolean {
  return row.id.startsWith(OPTIMISTIC_ORDER_ID_PREFIX);
}

const BASE36 = 36;
const FALLBACK_ID_SUFFIX_START = 2;
const FALLBACK_ID_SUFFIX_END = 10;

function generateOptimisticOrderId(): string {
  const cryptoApi: Crypto | undefined =
    typeof globalThis.crypto !== 'undefined' ? globalThis.crypto : undefined;
  const uuid =
    cryptoApi?.randomUUID?.() ??
    `${Date.now().toString(BASE36)}-${Math.random().toString(BASE36).slice(FALLBACK_ID_SUFFIX_START, FALLBACK_ID_SUFFIX_END)}`;

  return `${OPTIMISTIC_ORDER_ID_PREFIX}${uuid}`;
}

/**
 * Synthesize an open-resting OrderRow from the submitted PlaceOrderRequest so the
 * Órdenes tab can render the new order instantly. The row is replaced (or removed
 * for filled market orders) once the server response / WS reconcile fires.
 */
export function buildOptimisticOrderRow(body: PlaceOrderRequest): OrderRow {
  const now = new Date().toISOString();
  const orderType: 'market' | 'limit' = body.order_execution ?? 'market';

  return {
    id: generateOptimisticOrderId(),
    symbol: body.symbol,
    side: body.side,
    order_type: orderType,
    status: PAPER_ORDER_STATUS.PENDING,
    amount_usd: body.amount_usd ?? null,
    amount_btc: body.amount_btc ?? null,
    limit_price: orderType === 'limit' ? body.price : null,
    stop_loss_price: body.stop_loss_price ?? null,
    take_profit_price: body.take_profit_price ?? null,
    created_at: now,
    updated_at: now,
    market_type: body.market_type ?? null,
    leverage: body.leverage ?? null,
    paper_order_intent: body.paper_order_intent ?? null,
    exit_strategy: body.exit_strategy ?? null,
  };
}
