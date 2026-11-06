/**
 * Paper / demo trading — mode kinds, labels, and mode-scoped defaults (SoT).
 */

import type { TradingMode } from '@/types/tradingBarrel';

/** Demo vs paper trading mode — matches GET /trading/modes `kind`. `LIVE` is UI-only until live trading ships. */
export const TRADING_MODE = { DEMO: 'demo', PAPER: 'paper', LIVE: 'live' } as const;

/** API `mode` query / `TradingMode.kind` — value union derived from TRADING_MODE (§12 SoT). */
export type TradingModeKind = (typeof TRADING_MODE)[keyof typeof TRADING_MODE];

/**
 * i18n label keys mirrored from BE SoT
 * (``src/shared/constants/trading_mode_label_keys.py``). Resolve via
 * ``useTranslations`` against the exact key string.
 *
 * Kept on the FE side too so fixtures + the synthetic demo fallback can
 * populate ``TradingMode.label_key`` without repeating the string literal.
 */
export const TRADING_MODE_LABEL_KEY = {
  DEMO: 'dashboard.trade.modeSwitcher.demo',
  PAPER: 'dashboard.trade.modeSwitcher.paper',
  LIVE: 'dashboard.trade.modeSwitcher.live',
} as const;

/** ``label_params`` key carrying the exchange id — see BE SoT. */
export const TRADING_MODE_LABEL_PARAM_EXCHANGE = 'exchange';

/**
 * JSON field on each GET /trading/modes item — USDT-M swap support (paper + live; false for demo).
 * Paired with BE ``TRADING_MODES_JSON_KEY_FUTURES_SUPPORTED``; do not rename without an API version bump.
 */
export const TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED = 'futures_paper_supported' as const;

/**
 * Synthetic mode when GET /trading/modes fails but the user is logged in — keeps portfolio fetch enabled.
 * Mirrors API list_modes demo entry.
 */
export const TRADING_DEFAULT_DEMO_MODE: TradingMode = {
  id: TRADING_MODE.DEMO,
  label: 'Demo',
  label_key: TRADING_MODE_LABEL_KEY.DEMO,
  label_params: {},
  kind: TRADING_MODE.DEMO,
  exchange_connection_id: null,
  fallback_simulated: false,
  [TRADING_MODES_WIRE_KEY_FUTURES_SUPPORTED]: false,
};

/**
 * Epsilon for positive USD/BTC comparisons across trade math utils (§12 SoT).
 * Import from here — do not duplicate `1e-12` in feature modules.
 */
export const TRADING_NUMERIC_EPSILON = 1e-12;

/**
 * Futures margin headroom — safety buffer applied to the naive
 * ``notional / leverage`` initial-margin estimate.
 *
 * Mirrors BE SoT: ``FUTURES_MARGIN_HEADROOM = Decimal("1.02")`` in
 * ``apps/api/src/domain/services/ccxt_futures_preflight.py``. BE uses this to
 * reject orders that cannot fund a 2% cushion before calling CCXT; the FE
 * preview must use the same factor so the user's "margin required" hint
 * matches what preflight will actually check (P3-HIGH-1, audit G1).
 *
 * Keep in lockstep: a drift between FE and BE here shows up as a user
 * entering an amount that looks fundable in the UI but fails preflight with
 * ``PAPER_PREFLIGHT_INSUFFICIENT_MARGIN``.
 */
export const TRADING_FUTURES_MARGIN_HEADROOM = 1.02;

/**
 * Órdenes tab: treat FIFO remainder at or below this BTC as closed (legacy USD-sized demo sells
 * could leave a few satoshis vs the buy lot). §12 SoT — do not duplicate in feature modules.
 */
export const ORDENES_TAB_FIFO_REMAINDER_IGNORE_BTC = 1e-7;

/**
 * Badge variant for trading mode kind — header + trade ModeSelector (SoT).
 * - demo: warning (amber) — simulated
 * - paper: info (blue) — testnet / paper
 * - live: success (green) — real funds when Live ships (distinct from paper)
 */
export function getTradingModeBadgeVariant(kind: string): 'info' | 'success' | 'warning' {
  if (kind === TRADING_MODE.PAPER) {
    return 'info';
  }

  if (kind === TRADING_MODE.LIVE) {
    return 'success';
  }

  return 'warning';
}
