/**
 * Admin AI – Pure helpers for provider display and status (CODING_STANDARDS §2: no reinvention).
 *
 * WHY this file:
 * - Centralizes AI provider display logic used by admin AI page
 * - Testable without React; constants live in utils/constants.ts
 *
 * @see apps/web/src/app/[locale]/admin/ai/page.tsx
 * @see utils/constants.ts AI_PROVIDER_DISPLAY_NAMES, AI_PROVIDER_STRATEGY
 */

import { AI_PROVIDER_DISPLAY_NAMES } from '@/utils/constants';

/**
 * Resolve display name for a provider ID (uses centralized AI_PROVIDER_DISPLAY_NAMES).
 */
export function getProviderDisplayName(providerId: string, fallbackName: string): string {
  const label = AI_PROVIDER_DISPLAY_NAMES[providerId];

  if (label) {
    return label;
  }

  return fallbackName;
}

/**
 * Resolve current_provider for display (groq → "Groq (Llama 3)" for consistency).
 */
export function getCurrentProviderLabel(providerId: string): string {
  if (providerId === 'groq') {
    return 'Groq (Llama 3)';
  }

  return providerId;
}

/** Translation function type for use-case labels (admin.ai keys). */
export type AdminAiTranslator = (key: string) => string;

/**
 * Resolve use-case label for a provider ID (mock/groq/claude → i18n key).
 */
export function getProviderUseCaseLabel(providerId: string, t: AdminAiTranslator): string {
  const map: Record<string, string> = {
    mock: t('development'),
    groq: t('freeUsers'),
    claude: t('proUsers'),
  };

  const label = map[providerId];

  if (label) {
    return label;
  }

  return '-';
}

/**
 * Badge variant for configured (ready = success, not configured = danger).
 */
export type ConfiguredVariant = 'success' | 'danger';

export function getConfiguredVariant(configured: boolean): ConfiguredVariant {
  if (configured) {
    return 'success';
  }

  return 'danger';
}

/**
 * Translated label for configured status (ready / notConfigured).
 */
export function getConfiguredLabel(configured: boolean, t: AdminAiTranslator): string {
  if (configured) {
    return t('ready');
  }

  return t('notConfigured');
}
