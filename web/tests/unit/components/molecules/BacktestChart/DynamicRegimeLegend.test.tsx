import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { DynamicRegimeLegend } from '@/components/molecules/BacktestChart/DynamicRegimeLegend';

describe('DynamicRegimeLegend', () => {
  it('renders legend chips when enabled with active regimes', () => {
    render(
      <DynamicRegimeLegend
        show
        activeRegimes={['low', 'high']}
        label="Dynamic regime hints:"
        regimeLabels={{ low: 'Low', mid: 'Mid', high: 'High' }}
      />
    );

    expect(screen.getByText('Dynamic regime hints:')).toBeInTheDocument();
    expect(screen.getByText('Low')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
  });

  it('does not render when disabled', () => {
    const { container } = render(
      <DynamicRegimeLegend show={false} activeRegimes={['mid']} label="Dynamic regime hints:" />
    );

    expect(container).toBeEmptyDOMElement();
  });
});
