// @vitest-environment node
/**
 * SoT regression: stats-tab equity layout tokens live in `trading.ts`;
 * stroke color follows `getThemeColors().equityCurveLine` + `--chart-equity-line`
 * (CODING_STANDARDS §12 — no duplicate hex in dashboard constants).
 */

import { describe, expect, it } from 'vitest';

import {
  TRADING_STATS_EQUITY_CHART_TIMEFRAME_NONE,
  TRADING_STATS_EQUITY_CURVE_HEIGHT_PX,
} from '@/utils/constants/trading';

describe('trading stats equity chart constants', () => {
  it('exports stable layout tokens for SingleEquityCurve', () => {
    expect(TRADING_STATS_EQUITY_CURVE_HEIGHT_PX).toBe(220);
    expect(TRADING_STATS_EQUITY_CHART_TIMEFRAME_NONE).toBe('');
  });
});
