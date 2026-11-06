import {
  PLOTLY_EQUITY_CURVE_LINE_DARK,
  PLOTLY_EQUITY_CURVE_LINE_LIGHT,
} from '@/utils/plotly-chart-helpers/constants';
import type { ThemeColors } from '@/utils/plotly-chart-helpers/types';

/**
 * Get theme-aware colors for Plotly charts.
 *
 * WHY: Consistent color scheme across all chart components,
 * respecting user's dark/light mode preference.
 */
export function getThemeColors(isDark: boolean): ThemeColors {
  if (isDark) {
    return {
      paper: '#1f2937',
      plot: '#111827',
      grid: '#374151',
      line: '#4b5563',
      text: '#e5e7eb',
      textMuted: '#9ca3af',
      bullish: '#26a69a',
      bearish: '#ef5350',
      signal: '#7c4dff',
      equityCurveLine: PLOTLY_EQUITY_CURVE_LINE_DARK,
    };
  }

  return {
    paper: '#ffffff',
    plot: '#f9fafb',
    grid: '#e5e7eb',
    line: '#d1d5db',
    text: '#111827',
    textMuted: '#6b7280',
    bullish: '#16a34a',
    bearish: '#dc2626',
    signal: '#7c3aed',
    equityCurveLine: PLOTLY_EQUITY_CURVE_LINE_LIGHT,
  };
}
