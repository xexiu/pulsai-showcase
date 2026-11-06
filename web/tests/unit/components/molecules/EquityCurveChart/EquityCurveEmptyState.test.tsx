/**
 * EquityCurveEmptyState — user-visible empty state when no equity data.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('next-intl', () => ({
  useTranslations: (namespace: string) => (key: string) => `${namespace}.${key}`,
}));

import { EquityCurveEmptyState } from '@/components/molecules/EquityCurveChart/EquityCurveEmptyState';

describe('EquityCurveEmptyState', () => {
  it('renders message and applies height style for layout stability', () => {
    render(<EquityCurveEmptyState height={240} />);

    const root = screen.getByText('admin.training.noEquityData');

    expect(root).toBeInTheDocument();
    expect(root).toHaveStyle({ height: '240px' });
  });
});
