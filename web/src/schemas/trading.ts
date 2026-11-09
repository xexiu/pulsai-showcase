/**
 * Valibot schema for POST /trading/orders request body — mirrors BE contract in
 * `apps/api/src/api/v1/endpoints/trading_schemas.py::TradingOrderRequest`.
 *
 * Enforces the same cross-field invariants so demo+swap, paper/live spot sell+SLTP,
 * demo+limit+SLTP, and symbol > 32 chars are caught client-side before the
 * network round trip (slice B7).
 */

import * as v from 'valibot';

import { MARKET_TYPE, ORDER_TYPE, SLTP_MODE, TRADING_MODE } from '@/utils/constants/trading';

const SYMBOL_MAX_LENGTH = 32;

const modeLiteral = v.picklist([TRADING_MODE.DEMO, TRADING_MODE.PAPER, TRADING_MODE.LIVE]);
const sideLiteral = v.picklist(['buy', 'sell']);
const marketTypeLiteral = v.picklist([MARKET_TYPE.SPOT, MARKET_TYPE.SWAP]);
const orderExecutionLiteral = v.picklist([ORDER_TYPE.MARKET, ORDER_TYPE.LIMIT]);
const sltpModeLiteral = v.picklist([SLTP_MODE.ABSOLUTE, SLTP_MODE.PERCENTAGE]);

const optionalNullableString = v.optional(v.nullable(v.string()));

const bodyShape = v.object({
  mode: modeLiteral,
  exchange_connection_id: optionalNullableString,
  side: sideLiteral,
  symbol: v.pipe(v.string(), v.maxLength(SYMBOL_MAX_LENGTH)),
  order_execution: v.optional(orderExecutionLiteral),
  price: v.string(),
  amount_usd: optionalNullableString,
  amount_btc: optionalNullableString,
  stop_loss_price: optionalNullableString,
  take_profit_price: optionalNullableString,
  sltp_mode: v.optional(sltpModeLiteral),
  sl_percentage: optionalNullableString,
  tp_percentage: optionalNullableString,
  market_type: v.optional(marketTypeLiteral),
  leverage: v.optional(v.number()),
  max_compound_trades: v.optional(v.number()),
  min_compound_step_pct: v.optional(v.number()),
  reduce_only: v.optional(v.boolean()),
  // BE `TradingOrderRequest.exit_strategy` — optional audit/SoT tag used by
  // paper-order persistence (e.g. "fixed_holding", "raw_signal"). BE caps it
  // at 32 chars; we mirror that so long free-form strings are caught before
  // the network round-trip. P3-LOW-7 parity guard pins this field's presence.
  exit_strategy: v.optional(v.nullable(v.pipe(v.string(), v.maxLength(SYMBOL_MAX_LENGTH)))),
});

function hasBracket(input: v.InferOutput<typeof bodyShape>): boolean {
  return (
    (input.stop_loss_price != null && input.stop_loss_price !== '') ||
    (input.take_profit_price != null && input.take_profit_price !== '')
  );
}

type PlaceOrderBody = v.InferOutput<typeof bodyShape>;

function isCcxtTradingMode(mode: PlaceOrderBody['mode']): boolean {
  return mode === TRADING_MODE.PAPER || mode === TRADING_MODE.LIVE;
}

function validateReduceOnlyContract(input: PlaceOrderBody, isCcxt: boolean): boolean {
  if (input.reduce_only !== true) {
    return true;
  }

  if (!isCcxt) {
    return false;
  }

  if ((input.market_type ?? MARKET_TYPE.SPOT) !== MARKET_TYPE.SWAP) {
    return false;
  }

  return (input.order_execution ?? ORDER_TYPE.MARKET) === ORDER_TYPE.MARKET;
}

function validatePlaceOrderInvariants(input: PlaceOrderBody): boolean {
  if (input.mode === TRADING_MODE.DEMO) {
    if (input.market_type === MARKET_TYPE.SWAP) return false;
    if (input.leverage != null) return false;
    if (input.order_execution === ORDER_TYPE.LIMIT && hasBracket(input)) return false;
  }

  const isCcxt = isCcxtTradingMode(input.mode);

  if (isCcxt && hasBracket(input)) {
    const mt = input.market_type ?? MARKET_TYPE.SPOT;

    if (mt === MARKET_TYPE.SPOT && input.side === 'sell') {
      return false;
    }
  }

  return validateReduceOnlyContract(input, isCcxt);
}

export const placeOrderRequestSchema = v.pipe(
  bodyShape,
  v.check(validatePlaceOrderInvariants, 'trading.schema.invalidOrderContract')
);

/**
 * The accepted-field names for the POST /trading/orders public HTTP surface.
 *
 * Used by the FE/BE contract-parity test
 * (`tests/unit/schemas/trading-order-request-contract-parity.test.ts`) to assert
 * this Valibot schema stays in lockstep with the BE Pydantic model
 * (`TradingOrderRequest`) and with the committed SOT JSON at
 * `/contracts/trading_order_request.contract.json`.
 *
 * Exporting the derived list — rather than the full schema internals — keeps
 * the public surface minimal while still giving a runtime-checkable shape for
 * drift detection. (P3-LOW-7)
 */
export const PLACE_ORDER_REQUEST_ACCEPTED_FIELDS = Object.keys(
  bodyShape.entries
) as readonly string[]; /**
 * Compile-time guard: valibot output should be assignable to the shared
 * `PlaceOrderRequest` type. Runtime callers continue to use `PlaceOrderRequest`.
 */
