/**
 * Paper / demo trading — UI presets, tabs, query tuning, and Tailwind helpers (SoT).
 */

/* eslint-disable @typescript-eslint/no-magic-numbers -- Canonical numeric literals live here as the single source of truth. */

import type { ExchangePermissionKey } from '@/types/tradingBarrel';
import { TRADING_MODE, type TradingModeKind } from '@/utils/constants/trading/trading-modes';
import { ORDER_SIDE } from '@/utils/constants/trading/trading-order';

/** USD amount quick-fill presets (% of buying power for current side). */
export const TRADING_USD_AMOUNT_PRESET_PERCENTS = [25, 50, 75, 100] as const;

/** Stop-loss / take-profit distance presets (% from reference price). */
export const TRADING_SL_TP_PRESET_PERCENTS = [1, 5, 10] as const;

/**
 * Shared Tailwind for small % preset buttons (amount + SL/TP rows).
 * Single class string — avoids copy-paste drift between components.
 */
export const TRADING_PRESET_PERCENT_BUTTON_CLASS =
  'flex-1 rounded-lg border border-border/40 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40' as const;

/** Dim and block interaction when demo is exhausted or section is locked. */
export const TRADING_SECTION_OVERLAY_DISABLED_CLASS = 'pointer-events-none opacity-50' as const;

/** Right-column tabs (labels from `dashboard.trade.overviewTab.<key>`). */
export const TRADING_OVERVIEW_TAB_KEYS = ['orders', 'history', 'stats'] as const;

/**
 * Legacy key for chart-as-tab UX. Chart is no longer a tab; kept for active-tab fallback tests
 * and any stored selection edge cases.
 */
export const TRADING_CHART_OVERVIEW_TAB_KEY = 'chart' as const;

export type PaperTradingOverviewTabKey =
  | (typeof TRADING_OVERVIEW_TAB_KEYS)[number]
  | typeof TRADING_CHART_OVERVIEW_TAB_KEY;

/**
 * Overview tab keys for the trade dashboard right column (Órdenes / Historial / Estadísticas).
 * Chart is not a tab — when the feature flag is on, `TradeDashboardGrid` renders the chart above this bar.
 */
export function resolveTradeOverviewTabKeys(): PaperTradingOverviewTabKey[] {
  return [...TRADING_OVERVIEW_TAB_KEYS] as PaperTradingOverviewTabKey[];
}

/** Height (px) for the optional trade OHLCV panel (`TradeChartPanel`). */

export const TRADING_OVERVIEW_TAB_DEFAULT_KEY: PaperTradingOverviewTabKey = 'orders';

/**
 * Demo portfolio USD shown / used for presets before GET /trading/portfolio resolves.
 * Align with backend `DEFAULT_DEMO_BALANCE_USD` (apps/api `exchanges.py`).
 */
export const TRADING_DEMO_FALLBACK_BALANCE_USD_STRING = '10000' as const;

/**
 * Demo taker fee as fraction of notional (0.001 = 0.1%).
 * SoT: `DEFAULT_FEE_RATE` in `apps/api/src/shared/constants/exchanges.py`.
 */
export const TRADING_DEMO_FEE_RATE_FRACTION = 0.001 as const;

/**
 * When GET /exchanges/supported has not loaded, assume catalog size matches API `SUPPORTED_EXCHANGES` length.
 */
export const TRADING_SUPPORTED_EXCHANGE_COUNT_FALLBACK = 6 as const;

/** Display precision for base balance line in the trade balances card. */

/** Balance line when portfolio GET failed (same glyph as `emptyFallback` i18n). */
export const TRADING_BALANCE_UNAVAILABLE_MARK = '\u2014' as const;

/** GET /trading/modes — changes rarely; 30s stale reduces chatter. */
export const TRADING_QUERY_STALE_MODES_MS = 30_000;

/** Portfolio snapshot — refresh after orders; 15s balances UX vs load. */
export const TRADING_QUERY_STALE_PORTFOLIO_MS = 10_000;

/**
 * TanStack `refetchInterval` for GET /trading/portfolio: paper/live re-fetch on a timer so
 * open orders / fills stay aligned with the venue when a WebSocket lifecycle event is missed
 * (e.g. user cancels on the exchange site). Demo is `false` — synthetic portfolio, no CCXT poll.
 */
export function tradePortfolioRefetchIntervalMs(mode: TradingModeKind): number | false {
  if (mode === TRADING_MODE.PAPER || mode === TRADING_MODE.LIVE) {
    return TRADING_QUERY_STALE_PORTFOLIO_MS;
  }

  return false;
}

/** Row cap for GET /trading/trades and GET /trading/orders (demo lists). */
export const TRADING_ACTIVITY_FETCH_LIMIT = 100;

/**
 * Estadísticas tab — default rolling UTC window used by the stats panel when no
 * explicit start/end is provided. Aligned with the Performance & Review hub's
 * common "last 30 days" view; bounded by backend
 * ``TRADING_PERFORMANCE_MAX_RANGE_DAYS`` (366).
 */
export const TRADING_STATS_DEFAULT_WINDOW_DAYS = 30;

/**
 * Estadísticas tab — TanStack `staleTime` for ``GET /trading/performance/summary``.
 *
 * KPIs are server-side aggregates; no need to refetch on every focus. Same
 * cadence as portfolio polling so the user sees coherent numbers across panels.
 */
export const TRADING_QUERY_STALE_STATS_MS = 30_000;

/**
 * Estadísticas tab — equity curve (`PaperEquityCurveSection` → `SingleEquityCurve`) fixed
 * height in CSS pixels. Kept here so layout tweaks don’t scatter magic numbers in molecules.
 */
export const TRADING_STATS_EQUITY_CURVE_HEIGHT_PX = 220;

/**
 * `SingleEquityCurve` still expects a timeframe label prop; the stats read-model has no
 * chart timeframe axis — pass this sentinel instead of an inline empty string.
 */
export const TRADING_STATS_EQUITY_CHART_TIMEFRAME_NONE = '' as const;

/** Min table width (px) for demo fills grid — horizontal scroll on narrow viewports. */
export const TRADING_ACTIVITY_FILLS_TABLE_MIN_WIDTH_PX = 720;

/** Min table width (px) for demo open-orders grid. */
export const TRADING_ACTIVITY_ORDERS_TABLE_MIN_WIDTH_PX = 1360;

/** Min table width (px) for paper open-positions table inside `PortfolioTable` (§12 SoT, G1). */
export const PORTFOLIO_TABLE_MIN_WIDTH_PX = 640;

/**
 * Shared bordered panel for trade activity (status lines, empty states).
 * Text color applied per variant in `TradeActivityPanelStatus`.
 */
export const TRADING_ACTIVITY_MESSAGE_PANEL_CLASS =
  'rounded-lg border border-border/40 bg-card/40 px-4 py-6 text-left text-sm' as const;

/** Table wrapper: scroll + border (matches `PortfolioTable` / stats patterns). `touch-pan-x` helps iOS horizontal swipe. */
export const TRADING_ACTIVITY_TABLE_SCROLL_CLASS =
  'overflow-x-auto touch-pan-x rounded-lg border border-border/40' as const;

/** Table header row styling — reused by demo activity tables. */
export const TRADING_ACTIVITY_TABLE_HEAD_CLASS =
  'border-b border-border/40 bg-muted/30 text-xs uppercase tracking-wide text-muted-foreground' as const;

/** Body row divider — demo activity tables. */
export const TRADING_ACTIVITY_TABLE_ROW_CLASS = 'border-b border-border/20 last:border-0' as const;

/** GET /exchanges/supported — static catalog; 60s is enough. */
export const TRADING_QUERY_STALE_SUPPORTED_EXCHANGES_MS = 60_000;

/** User connections list — moderate freshness. */
export const TRADING_QUERY_STALE_CONNECTIONS_MS = 30_000;

/** Permission keys we display in the connections list (subset of CCXT flags). */
export const EXCHANGE_PERMISSION_KEYS: ExchangePermissionKey[] = ['read', 'trade', 'withdraw'];

/**
 * Shared Tailwind classes for two-option segmented toggle buttons (Market Type, Order Type).
 * Single source of truth — avoids copy-paste drift between toggle components.
 */
const SEGMENTED_TOGGLE_BTN_BASE =
  'flex-1 rounded-md px-4 py-2 text-sm font-medium transition-colors';

export const SEGMENTED_TOGGLE_BTN_ACTIVE = `${SEGMENTED_TOGGLE_BTN_BASE} bg-muted text-foreground`;
export const SEGMENTED_TOGGLE_BTN_INACTIVE = `${SEGMENTED_TOGGLE_BTN_BASE} text-muted-foreground hover:text-foreground`;

/** Live price refresh — 10s balances freshness vs rate limit overhead. */
export const TRADING_LIVE_PRICE_REFETCH_MS = 10_000;

const MODE_BTN_BASE = 'rounded-lg border px-3 py-1.5 text-sm transition-colors ';

/** Tailwind class string for the active/inactive mode selection button. */
export function getModeButtonClass(isSelected: boolean): string {
  if (isSelected) {
    return `${MODE_BTN_BASE}border-primary bg-primary/10 text-primary`;
  }

  return `${MODE_BTN_BASE}border-border text-muted-foreground hover:bg-muted/50`;
}

const SIDE_BTN_BASE = 'flex-1 rounded-lg py-2 text-sm font-medium transition-colors ';

/** Tailwind class string for buy/sell toggle button. */
export function getSideButtonClass(isActive: boolean, variant: 'buy' | 'sell'): string {
  if (!isActive) {
    return `${SIDE_BTN_BASE}border border-border text-muted-foreground hover:bg-muted/50`;
  }

  if (variant === ORDER_SIDE.BUY) {
    return `${SIDE_BTN_BASE}bg-green-600 text-white`;
  }

  return `${SIDE_BTN_BASE}bg-red-600 text-white`;
}
