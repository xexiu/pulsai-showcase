// @vitest-environment node

import { describe, expect, it } from 'vitest';

import { resolveChartContainerResizeDimensions } from '@/utils/chart-container-resize';
import { FULL_CHART_MIN_HEIGHT_PX } from '@/utils/constants';

describe('resolveChartContainerResizeDimensions', () => {
  it('uses fallback height when not fitting to container', () => {
    expect(
      resolveChartContainerResizeDimensions({
        clientWidth: 400,
        clientHeight: 200,
        fallbackHeight: 500,
        fitHeightToContainer: false,
      })
    ).toEqual({ width: 400, height: 500 });
  });

  it('uses measured clientHeight when fitting to container', () => {
    expect(
      resolveChartContainerResizeDimensions({
        clientWidth: 390,
        clientHeight: 420,
        fallbackHeight: 500,
        fitHeightToContainer: true,
      })
    ).toEqual({ width: 390, height: 420 });
  });

  it('falls back to prop height when container height is zero', () => {
    expect(
      resolveChartContainerResizeDimensions({
        clientWidth: 300,
        clientHeight: 0,
        fallbackHeight: 480,
        fitHeightToContainer: true,
      })
    ).toEqual({ width: 300, height: 480 });
  });

  it('clamps to minimum chart height', () => {
    expect(
      resolveChartContainerResizeDimensions({
        clientWidth: 300,
        clientHeight: 100,
        fallbackHeight: 100,
        fitHeightToContainer: true,
      })
    ).toEqual({ width: 300, height: FULL_CHART_MIN_HEIGHT_PX });
  });
});
