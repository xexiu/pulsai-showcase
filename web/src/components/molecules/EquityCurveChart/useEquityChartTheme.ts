import { useMemo } from 'react';

import { useTheme } from 'next-themes';

import { getThemeColors, type ThemeColors } from '@/utils/plotly-chart-helpers';

export interface EquityChartTheme {
  colors: ThemeColors;
  isDark: boolean;
}

/**
 * Theme for Plotly equity charts (same SoT as BacktestChart / plotly-chart-helpers).
 */
export function useEquityChartTheme(): EquityChartTheme {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const colors = useMemo(() => getThemeColors(isDark), [isDark]);

  return { colors, isDark };
}
