/// <reference types="vitest" />
import path from 'path';
import { fileURLToPath } from 'url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/helpers/setup.ts'],
    include: ['tests/**/*.{test,spec}.{ts,tsx}'],
    globals: true,
    testTimeout: 10000,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**'],
      // Same scope as the monorepo (docs/05-testing/COVERAGE_REQUIREMENTS.md): components are covered by
      // component / E2E tests, Plotly glue by chart QA, and barrels hold no logic.
      exclude: ['src/components/**', 'src/utils/plotly-chart-helpers/**', '**/index.ts'],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@/components': path.resolve(__dirname, './src/components'),
      '@/hooks': path.resolve(__dirname, './src/hooks'),
      '@/lib': path.resolve(__dirname, './src/lib'),
      '@/providers': path.resolve(__dirname, './src/providers'),
      '@/types': path.resolve(__dirname, './src/types'),
    },
  },
});
