# ADR-018: Three SL/TP execution paths (swap preset, spot plan, demo managed)

## Context

Paper and live orders can attach SL/TP in three different ways. Mixing them causes subtle bugs (e.g. sending swap `presetStopLossPrice` on Bitget spot plain `create_order`).

## Decision

1. **Swap (USDT-M perpetual):** native preset brackets on the same CCXT `create_order` call (`SLTP_STRATEGY_EXCHANGE_NATIVE`). Bitget/Binance swap adapters own preset field names.
2. **Spot (supported venues, v1 Bitget):** primary spot order has **no** preset brackets; SL/TP are **Bitget spot plan orders** placed after an authoritative fill (`SLTP_STRATEGY_EXCHANGE_SPOT_PLAN`), via CCXT trigger params + `place-bitget-spot-plan-orders` helper. Registry: `SpotBracketAttachmentRegistry` + `default_registry.py`.
3. **Demo spot:** simulator-side managed brackets (`SLTP_STRATEGY_PULSAI_MANAGED`); no CCXT plan orders.

## Consequences

- New exchanges add a `SpotBracketAttachmentStrategy` + registry entry; do not reuse swap bracket modules for spot.
- Partial spot fills defer plan placement until lifecycle sees a full fill (see `OrderReconciliationService._maybe_place_spot_bracket_plans_on_fill`).

## References

- `apps/api/src/application/services/unified_trading/order_preflight.py`
- `apps/api/src/infrastructure/exchange/adapters/bitget_spot.py`
- `apps/api/src/infrastructure/exchange/spot_brackets/`
