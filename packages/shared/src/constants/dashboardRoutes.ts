/**
 * Locale-agnostic dashboard URL path segments (browser paths; next-intl prepends `/{locale}`).
 *
 * SoT for FE nav, active-route checks, and BE email deep links. Mirrors:
 * - `apps/api/src/shared/constants/frontend_dashboard_paths.py` (`DASHBOARD_TRADE_PATH`)
 * - `apps/web/next.config.mjs` redirect `destination` (same string; config cannot import this package)
 */
export const DASHBOARD_TRADE_PATH = '/dashboard/trade' as const;

/**
 * True when `pathname` is the trade dashboard section (e.g. `/en/dashboard/trade`, optional query).
 * False for unrelated paths such as `/dashboard/trades`.
 */
export function isPathnameDashboardTradeSection(pathname: string): boolean {
  const escaped = DASHBOARD_TRADE_PATH.replace(/\//g, '\\/');

  return new RegExp(`${escaped}(?:\\/|$|\\?)`).test(pathname);
}
