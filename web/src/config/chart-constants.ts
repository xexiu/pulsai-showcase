/**
 * Chart-related constants — SoT for DOM events, pane layout, and chart config literals.
 *
 * WHY CENTRALIZED (CODING_STANDARDS §12)?
 * - No magic strings in useChartInit / chart-series / chart-pane-heights
 * - Single place to change event names or pane counts
 * - Type-safe; testable in isolation
 *
 * @see docs/04-structural/CODING_STANDARDS.md §12 (Constants and Magic Numbers)
 */

// =============================================================================
// Pane resize persistence (useChartInit, chart-series)
// =============================================================================

/**
 * DOM event fired when user releases pointer after dragging pane separator.
 * Used to persist stretch factors to localStorage (LWC has no pane-resize event).
 */
export const CHART_PANE_RESIZE_EVENT = 'pointerup' as const;

/**
 * Minimum panes to read/persist stretch (main + at least one indicator slot).
 * Full five-pane layout is legacy; compact sync mounts only visible slots.
 */
export const CHART_PANE_COUNT_FOR_STRETCH = 2;

// =============================================================================
// Chart tooltip (floating hover)
// =============================================================================

/** Horizontal offset from cursor to tooltip (px). */
export const CHART_TOOLTIP_OFFSET_X = 12;

/** Vertical offset from cursor to tooltip (px). */
export const CHART_TOOLTIP_OFFSET_Y = 12;

/** Tooltip z-index above chart canvas. */
export const CHART_TOOLTIP_Z_INDEX = 1000;

/** Min width for tooltip content (px). */
export const CHART_TOOLTIP_MIN_WIDTH = 160;

/** Max BE indicator columns shown in full-chart tooltip (perf guard). */
export const CHART_TOOLTIP_MAX_COLUMNS = 12;

// =============================================================================
// Chart gap investigation (dev-only logs; §12 SoT for log prefix)
// =============================================================================

/**
 * Log prefix for opt-in chart gap debug (`DEBUG_CHART_GAP` / `?debugChartGap=1`).
 * @see apps/web/src/utils/chart-gap-debug.ts
 */
export const CHART_GAP_DEBUG_LOG_PREFIX = '[chart-gap]';

// =============================================================================
// Chart viewport persistence (localStorage — useChartVisibleRangePersistence)
// =============================================================================

/** Debounce before writing viewport JSON (ms). Reduces localStorage writes during drag. */
export const CHART_VIEWPORT_PERSIST_SAVE_DEBOUNCE_MS = 400;

/**
 * After restore, ignore saves so async `fitContent` / settle does not overwrite stored zoom.
 */
export const CHART_VIEWPORT_PERSIST_IGNORE_SAVE_AFTER_RESTORE_MS = 2800;

const CHART_VIEWPORT_RESTORE_DELAY_MS_0 = 0;
const CHART_VIEWPORT_RESTORE_DELAY_MS_50 = 50;
const CHART_VIEWPORT_RESTORE_DELAY_MS_150 = 150;
const CHART_VIEWPORT_RESTORE_DELAY_MS_300 = 300;

/**
 * Retry applying stored viewport after `requestAnimationFrame` (async LWC layout).
 */
export const CHART_VIEWPORT_RESTORE_ATTEMPT_DELAYS_MS: readonly number[] = [
  CHART_VIEWPORT_RESTORE_DELAY_MS_0,
  CHART_VIEWPORT_RESTORE_DELAY_MS_50,
  CHART_VIEWPORT_RESTORE_DELAY_MS_150,
  CHART_VIEWPORT_RESTORE_DELAY_MS_300,
];
