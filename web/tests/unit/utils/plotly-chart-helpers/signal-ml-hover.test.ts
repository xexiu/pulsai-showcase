// @vitest-environment node
import { describe, expect, it } from 'vitest';

import { FEATURE_CATEGORY_ORDER } from '@/utils/plotly-chart-helpers/constants';
import { buildSignalMlHoverText } from '@/utils/plotly-chart-helpers/traces';

describe('FEATURE_CATEGORY_ORDER', () => {
  it('has at least 5 categories covering the main feature groups', () => {
    expect(FEATURE_CATEGORY_ORDER.length).toBeGreaterThanOrEqual(5);

    const labels = FEATURE_CATEGORY_ORDER.map((c) => c.label);

    expect(labels).toContain('Momentum');
    expect(labels).toContain('Volatility');
    expect(labels).toContain('Pattern');
  });

  it('every category has at least one prefix', () => {
    for (const cat of FEATURE_CATEGORY_ORDER) {
      expect(cat.prefixes.length).toBeGreaterThan(0);
    }
  });
});

describe('buildSignalMlHoverText', () => {
  const baseBuySignal = {
    timestamp: '2024-01-01T00:00:00Z',
    type: 'BUY' as const,
    price: 50_000,
    confidence: 72.5,
  };

  it('includes signal type, price, and confidence in header', () => {
    const html = buildSignalMlHoverText(baseBuySignal, { rsi_14: 45 });

    expect(html).toContain('BUY');
    expect(html).toContain('50,000');
    expect(html).toContain('72.5');
  });

  it('groups features under category headers', () => {
    const features = {
      rsi_14: 55.3,
      atr_14: 120.5,
      double_bottom: 0.85,
    };
    const html = buildSignalMlHoverText(baseBuySignal, features);

    expect(html).toContain('<b>Momentum');
    expect(html).toContain('rsi_14');
    expect(html).toContain('<b>Volatility');
    expect(html).toContain('atr_14');
    expect(html).toContain('<b>Pattern');
    expect(html).toContain('double_bottom');
  });

  it('filters out zero and near-zero values', () => {
    const features = {
      rsi_14: 55.3,
      macd: 0,
      stoch_k: 1e-10,
      atr_14: 0.0,
    };
    const html = buildSignalMlHoverText(baseBuySignal, features);

    expect(html).toContain('rsi_14');
    expect(html).not.toContain('macd');
    expect(html).not.toContain('stoch_k');
    expect(html).not.toContain('atr_14');
  });

  it('places unmatched features into an "Other" category', () => {
    const features = {
      rsi_14: 55.3,
      some_unknown_feature: 42.0,
    };
    const html = buildSignalMlHoverText(baseBuySignal, features);

    expect(html).toContain('<b>Other');
    expect(html).toContain('some_unknown_feature');
  });

  it('omits empty categories entirely', () => {
    const features = { rsi_14: 55.3 };
    const html = buildSignalMlHoverText(baseBuySignal, features);

    expect(html).toContain('<b>Momentum');
    expect(html).not.toContain('<b>Volatility');
    expect(html).not.toContain('<b>Pattern');
  });

  it('falls back to basic hover when features are null', () => {
    const html = buildSignalMlHoverText(baseBuySignal, null);

    expect(html).toContain('BUY');
    expect(html).toContain('72.5');
    expect(html).not.toContain('<b>Momentum');
  });

  it('falls back to basic hover when features are empty', () => {
    const html = buildSignalMlHoverText(baseBuySignal, {});

    expect(html).toContain('BUY');
    expect(html).not.toContain('<b>Momentum');
  });

  it('sorts features alphabetically within each category', () => {
    const features = {
      rsi_14: 55.3,
      macd_histogram: 2.1,
      macd: 1.5,
      macd_signal: 0.8,
    };
    const html = buildSignalMlHoverText(baseBuySignal, features);

    const macdIdx = html.indexOf('macd:');
    const macdHistIdx = html.indexOf('macd_histogram:');
    const macdSigIdx = html.indexOf('macd_signal:');

    expect(macdIdx).toBeLessThan(macdHistIdx);
    expect(macdHistIdx).toBeLessThan(macdSigIdx);
  });

  it('renders categories in FEATURE_CATEGORY_ORDER sequence', () => {
    const features = {
      double_bottom: 0.9,
      rsi_14: 55.3,
      atr_14: 120.5,
    };
    const html = buildSignalMlHoverText(baseBuySignal, features);

    const momentumIdx = html.indexOf('<b>Momentum');
    const volatilityIdx = html.indexOf('<b>Volatility');
    const patternIdx = html.indexOf('<b>Pattern');

    expect(momentumIdx).toBeLessThan(volatilityIdx);
    expect(volatilityIdx).toBeLessThan(patternIdx);
  });

  it('works with SELL signal type', () => {
    const sellSignal = { ...baseBuySignal, type: 'SELL' as const };
    const html = buildSignalMlHoverText(sellSignal, { rsi_14: 80 });

    expect(html).toContain('SELL');
  });
});
