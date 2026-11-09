// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  resolveChartMlPredictionMarkerAnchorMode,
  resolveChartMlPredictionMarkerUseBarOpenOnly,
  resolveMlPredictionChartBarOpenUtc,
} from '@/config/chart-ml-prediction-marker-anchor';

describe('chart-ml-prediction-marker-anchor (ADR-016)', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('env true forces bar_open', () => {
    vi.stubEnv('NEXT_PUBLIC_CHART_ML_PREDICTION_MARKER_USE_BAR_OPEN_ONLY', 'true');
    expect(resolveChartMlPredictionMarkerAnchorMode()).toBe('bar_open');
    expect(resolveMlPredictionChartBarOpenUtc(1000, '1h')).toBe(1000);
  });

  it('env false forces legacy (+period)', () => {
    vi.stubEnv('NEXT_PUBLIC_CHART_ML_PREDICTION_MARKER_USE_BAR_OPEN_ONLY', 'false');
    expect(resolveChartMlPredictionMarkerAnchorMode()).toBe('legacy_close_instant');
    expect(resolveMlPredictionChartBarOpenUtc(1000, '1h')).toBe(4600);
  });

  it('unset defaults to bar_open', () => {
    vi.unstubAllEnvs();
    expect(resolveChartMlPredictionMarkerUseBarOpenOnly()).toBe(true);
    expect(resolveMlPredictionChartBarOpenUtc(1000, '1h')).toBe(1000);
  });
});
