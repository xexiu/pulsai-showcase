/**
 * Human-readable label for the AI provider that served an explain request.
 *
 * Reuses admin AI provider display names (SoT: AI_PROVIDER_DISPLAY_NAMES).
 */

import { getProviderDisplayName } from '@/utils/admin-ai';

export type ExplainPoweredByTranslator = (key: string, values?: { provider?: string }) => string;

function buildProviderLabel(providerId: string, llmModel?: string | null): string {
  const display = getProviderDisplayName(providerId, providerId);
  const modelId = llmModel?.trim();

  if (modelId && modelId !== providerId) {
    return `${display} (${modelId})`;
  }

  return display;
}

export type ExplainProviderPoweredByOptions = {
  llmModel?: string | null;
  /** When false, never reveal provider/model (regular users). */
  canViewProvider?: boolean;
};

/** Footer line under an explanation (e.g. "Powered by Mock (Development)"). */
export function formatExplainProviderPoweredBy(
  providerId: string | null | undefined,
  t: ExplainPoweredByTranslator,
  options?: ExplainProviderPoweredByOptions
): string {
  if (options?.canViewProvider === false) {
    return t('poweredByPublic');
  }

  if (!providerId?.trim()) {
    return t('poweredByUnknown');
  }

  return t('poweredByProvider', {
    provider: buildProviderLabel(providerId.trim(), options?.llmModel),
  });
}
