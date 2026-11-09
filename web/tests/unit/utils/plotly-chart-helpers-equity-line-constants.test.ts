// @vitest-environment node
/**
 * Locks Plotly equity stroke constants to `globals.css` `--chart-equity-line` HSL triples
 * (documented in both places — change both when adjusting brand purple).
 */

import { describe, expect, it } from 'vitest';

import {
  PLOTLY_EQUITY_CURVE_LINE_DARK,
  PLOTLY_EQUITY_CURVE_LINE_LIGHT,
} from '@/utils/plotly-chart-helpers/constants';
import { getThemeColors } from '@/utils/plotly-chart-helpers/theme';

describe('plotly equity curve line SoT', () => {
  it('exports hsl() strings aligned with getThemeColors', () => {
    expect(PLOTLY_EQUITY_CURVE_LINE_LIGHT).toBe('hsl(271 91% 55%)');
    expect(PLOTLY_EQUITY_CURVE_LINE_DARK).toBe('hsl(271 91% 65%)');
    expect(getThemeColors(false).equityCurveLine).toBe(PLOTLY_EQUITY_CURVE_LINE_LIGHT);
    expect(getThemeColors(true).equityCurveLine).toBe(PLOTLY_EQUITY_CURVE_LINE_DARK);
  });
});
