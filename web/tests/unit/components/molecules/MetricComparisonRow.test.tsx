/**
 * MetricComparisonRow Molecule Tests
 *
 * Tests for the MetricComparisonRow component that compares model metrics.
 * Following: TESTING_STRATEGY.md - Tests formatting and delta display.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { MetricComparisonRow } from '@/components/molecules/MetricComparisonRow/MetricComparisonRow';

describe('MetricComparisonRow', () => {
  describe('rendering', () => {
    it('renders metric name with proper formatting', () => {
      render(
        <MetricComparisonRow
          metric="validation_accuracy"
          valueA={0.85}
          valueB={0.87}
          delta={0.02}
          versionA={1}
          versionB={2}
        />
      );
      expect(screen.getByText('validation accuracy')).toBeInTheDocument();
    });

    it('renders version labels', () => {
      render(
        <MetricComparisonRow
          metric="accuracy"
          valueA={0.85}
          valueB={0.87}
          delta={0.02}
          versionA={1}
          versionB={2}
        />
      );
      expect(screen.getByText('v1')).toBeInTheDocument();
      expect(screen.getByText('v2')).toBeInTheDocument();
    });
  });

  describe('percentage formatting', () => {
    it('formats accuracy metrics as percentages', () => {
      render(
        <MetricComparisonRow
          metric="validation_accuracy"
          valueA={0.85}
          valueB={0.87}
          delta={0.02}
          versionA={1}
          versionB={2}
        />
      );
      expect(screen.getByText('85.00%')).toBeInTheDocument();
      expect(screen.getByText('87.00%')).toBeInTheDocument();
      expect(screen.getByText('+2.00%')).toBeInTheDocument();
    });

    it('formats score metrics as percentages', () => {
      render(
        <MetricComparisonRow
          metric="training_score"
          valueA={0.9}
          valueB={0.92}
          delta={0.02}
          versionA={1}
          versionB={2}
        />
      );
      expect(screen.getByText('90.00%')).toBeInTheDocument();
    });
  });

  describe('non-percentage formatting', () => {
    it('formats non-percentage metrics with 4 decimals', () => {
      render(
        <MetricComparisonRow
          metric="sharpe_ratio"
          valueA={1.5}
          valueB={1.8}
          delta={0.3}
          versionA={1}
          versionB={2}
        />
      );
      expect(screen.getByText('1.5000')).toBeInTheDocument();
      expect(screen.getByText('1.8000')).toBeInTheDocument();
      expect(screen.getByText('+0.3000')).toBeInTheDocument();
    });
  });

  describe('delta colors', () => {
    it('applies green color for positive delta', () => {
      const { container } = render(
        <MetricComparisonRow
          metric="accuracy"
          valueA={0.85}
          valueB={0.87}
          delta={0.02}
          versionA={1}
          versionB={2}
        />
      );
      const deltaElement = container.querySelector('.text-green-600');

      expect(deltaElement).toBeInTheDocument();
    });

    it('applies red color for negative delta', () => {
      const { container } = render(
        <MetricComparisonRow
          metric="accuracy"
          valueA={0.87}
          valueB={0.85}
          delta={-0.02}
          versionA={1}
          versionB={2}
        />
      );
      const deltaElement = container.querySelector('.text-red-600');

      expect(deltaElement).toBeInTheDocument();
    });

    it('applies gray color for zero delta', () => {
      const { container } = render(
        <MetricComparisonRow
          metric="accuracy"
          valueA={0.85}
          valueB={0.85}
          delta={0}
          versionA={1}
          versionB={2}
        />
      );
      const deltaElement = container.querySelector('.text-gray-500');

      expect(deltaElement).toBeInTheDocument();
    });
  });

  describe('null/undefined handling', () => {
    it('displays N/A for null values', () => {
      render(
        <MetricComparisonRow
          metric="accuracy"
          valueA={null}
          valueB={0.85}
          delta={null}
          versionA={1}
          versionB={2}
        />
      );
      expect(screen.getAllByText('N/A')).toHaveLength(2);
    });

    it('displays N/A for undefined values', () => {
      render(
        <MetricComparisonRow
          metric="accuracy"
          valueA={undefined}
          valueB={undefined}
          delta={undefined}
          versionA={1}
          versionB={2}
        />
      );
      expect(screen.getAllByText('N/A')).toHaveLength(3);
    });
  });
});
