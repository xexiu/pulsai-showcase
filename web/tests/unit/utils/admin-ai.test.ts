// @vitest-environment node
/**
 * utils/admin-ai – Pure helpers for AI provider display (CODING_STANDARDS: test behavior).
 */

import { describe, expect, it } from 'vitest';

import {
  getConfiguredLabel,
  getConfiguredVariant,
  getCurrentProviderLabel,
  getProviderDisplayName,
  getProviderUseCaseLabel,
} from '@/utils/admin-ai';

const mockT = (key: string): string => key;

describe('admin-ai utils', () => {
  describe('getProviderDisplayName', () => {
    it('returns centralized label for known provider id', () => {
      expect(getProviderDisplayName('groq', 'Fallback')).toBe('Groq (Llama 3)');
      expect(getProviderDisplayName('mock', 'Fallback')).toBe('Mock (Development)');
      expect(getProviderDisplayName('claude', 'Fallback')).toBe('Claude (Anthropic)');
    });

    it('returns fallback for unknown provider id', () => {
      expect(getProviderDisplayName('unknown', 'Custom Name')).toBe('Custom Name');
    });
  });

  describe('getCurrentProviderLabel', () => {
    it('returns Groq (Llama 3) for groq', () => {
      expect(getCurrentProviderLabel('groq')).toBe('Groq (Llama 3)');
    });

    it('returns providerId as-is for others', () => {
      expect(getCurrentProviderLabel('claude')).toBe('claude');
      expect(getCurrentProviderLabel('mock')).toBe('mock');
    });
  });

  describe('getProviderUseCaseLabel', () => {
    it('returns translated key for mock, groq, claude', () => {
      expect(getProviderUseCaseLabel('mock', mockT)).toBe('development');
      expect(getProviderUseCaseLabel('groq', mockT)).toBe('freeUsers');
      expect(getProviderUseCaseLabel('claude', mockT)).toBe('proUsers');
    });

    it('returns - for unknown provider', () => {
      expect(getProviderUseCaseLabel('other', mockT)).toBe('-');
    });
  });

  describe('getConfiguredVariant', () => {
    it('returns success when configured', () => {
      expect(getConfiguredVariant(true)).toBe('success');
    });

    it('returns danger when not configured', () => {
      expect(getConfiguredVariant(false)).toBe('danger');
    });
  });

  describe('getConfiguredLabel', () => {
    it('returns translated ready when configured', () => {
      expect(getConfiguredLabel(true, mockT)).toBe('ready');
    });

    it('returns translated notConfigured when not configured', () => {
      expect(getConfiguredLabel(false, mockT)).toBe('notConfigured');
    });
  });
});
