// @vitest-environment node
import { describe, expect, it, vi } from 'vitest';

import { formatExplainProviderPoweredBy } from '@/utils/ai-explain-provider-label';

describe('formatExplainProviderPoweredBy', () => {
  const t = vi.fn((key: string, values?: { provider?: string }) => {
    if (key === 'poweredByProvider' && values?.provider) {
      return `Powered by ${values.provider}`;
    }
    if (key === 'poweredByPublic') {
      return 'Powered by AI';
    }
    if (key === 'poweredByUnknown') {
      return 'AI provider';
    }

    return key;
  });

  it('maps mock provider id to display name for admins', () => {
    expect(formatExplainProviderPoweredBy('mock', t, { canViewProvider: true })).toBe(
      'Powered by Mock (Development)'
    );
  });

  it('maps groq provider id to display name for admins', () => {
    expect(formatExplainProviderPoweredBy('groq', t, { canViewProvider: true })).toBe(
      'Powered by Groq (Llama 3)'
    );
  });

  it('appends llm model id when different from provider slug', () => {
    expect(
      formatExplainProviderPoweredBy('claude', t, {
        canViewProvider: true,
        llmModel: 'claude-3-5-sonnet',
      })
    ).toBe('Powered by Claude (Anthropic) (claude-3-5-sonnet)');
  });

  it('returns unknown label when provider missing for admins', () => {
    expect(formatExplainProviderPoweredBy(null, t, { canViewProvider: true })).toBe('AI provider');
  });

  it('returns public label for non-admins even when provider is present', () => {
    expect(
      formatExplainProviderPoweredBy('mock', t, { canViewProvider: false, llmModel: 'mock-dev' })
    ).toBe('Powered by AI');
    expect(t).toHaveBeenCalledWith('poweredByPublic');
    expect(t).not.toHaveBeenCalledWith('poweredByProvider', expect.anything());
  });
});
