# ADR-010: AI Provider Strategy

## Status

**ACCEPTED** (2026-01-29)

## Context

PulsAI needs AI capabilities for:

1. **Signal explanations** - "Why did the model generate this BUY signal?"
2. **Chart analysis** - Visual pattern recognition (Sprint 2.7)
3. **Quick explanations** - Pre-built prompts for market context

AI API costs can be significant at scale. We need a strategy that:

- Keeps free tier viable (no AI costs for free users)
- Provides premium value for paid users
- Allows development/testing without API costs

## Decision

### Multi-Provider Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  AI PROVIDER STRATEGY                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Tier          │ Provider      │ Model            │ Cost        │ Why   │
│  ──────────────┼───────────────┼──────────────────┼─────────────┼────── │
│  Development   │ Mock          │ Templates        │ FREE        │ Testing│
│  Free Users    │ Groq          │ Llama 3 70B      │ FREE tier   │ Good quality, no cost │
│  Paid Users    │ Claude        │ claude-sonnet-4  │ ~$3/1M tok  │ Best quality │
│  Vision (2.7)  │ Claude        │ claude-sonnet-4  │ ~$5/1M tok  │ Only Claude has vision │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Provider Capabilities

| Provider | Text Explain | Chart Vision | Speed     | Quality   | Cost      |
| -------- | ------------ | ------------ | --------- | --------- | --------- |
| Mock     | ✅ Templates | ✅ Mock      | Instant   | N/A       | FREE      |
| Groq     | ✅ Llama 3   | ❌ No vision | Very fast | Good      | FREE tier |
| Claude   | ✅ Best      | ✅ Vision    | Medium    | Excellent | $$$ Paid  |

### Implementation

**Implemented in Sprint 1.7** (`src/infrastructure/ai/providers.py`):

```python
# Abstract base class for all providers
class AIProvider(ABC):
    @abstractmethod
    async def explain_signal(self, context: str) -> str: ...
    @abstractmethod
    async def analyze_chart(self, image_base64: str, context: str) -> str: ...
    @abstractmethod
    def is_configured(self) -> bool: ...
    @abstractmethod
    def get_provider_name(self) -> str: ...

# Concrete implementations
class MockAIProvider(AIProvider): ...   # Development
class GroqAIProvider(AIProvider): ...   # Free tier
class ClaudeAIProvider(AIProvider): ... # Premium
```

**Pricing Tier Integration (Sprint 3.4)**:

```python
def get_ai_provider_for_user(user: User) -> AIProvider:
    """
    Select AI provider based on user's subscription tier.

    BUSINESS LOGIC:
    - Free/Starter tier → Groq (Llama 3)
    - Pro/Elite tier → Claude (Anthropic)
    """
    if user.subscription_tier in ['pro', 'elite']:
        return ClaudeAIProvider()
    return GroqAIProvider()
```

### Cost Estimation

| Tier      | Users | Requests/month | Provider | Cost/month      |
| --------- | ----- | -------------- | -------- | --------------- |
| Free      | 1000  | 5,000          | Groq     | $0 (free tier)  |
| Starter   | 200   | 4,000          | Groq     | $0 (free tier)  |
| Pro       | 100   | 10,000         | Claude   | ~$30            |
| Elite     | 50    | 25,000         | Claude   | ~$75            |
| **Total** | 1350  | 44,000         |          | **~$105/month** |

### Fallback Strategy

```
Claude → Groq → Mock

1. If Claude fails/unconfigured → Fall back to Groq
2. If Groq fails/unconfigured → Fall back to Mock
3. Mock always works (no external dependencies)
```

### Admin Controls

- **Mock Mode Toggle**: Admin can enable mock mode globally (for demos, testing)
- **Provider Override**: Admin can force a specific provider for debugging
- **Usage Dashboard**: Track AI requests per provider, per tier

## Consequences

### Positive

1. **Free tier remains free** - No AI costs for free users (Groq free tier)
2. **Premium differentiation** - Claude's superior quality justifies paid tiers
3. **Development efficiency** - Mock mode for testing without API costs
4. **Graceful degradation** - System works even if AI providers are down
5. **Easy to add providers** - Just implement `AIProvider` interface

### Negative

1. **Groq rate limits** - Free tier has limits (~30 req/min)
2. **Quality difference** - Free users get "good" not "excellent" explanations
3. **Vision locked to premium** - Chart analysis requires Claude (paid)

### Risks

| Risk                               | Mitigation                                        |
| ---------------------------------- | ------------------------------------------------- |
| Groq removes free tier             | Claude becomes fallback, adjust pricing           |
| Claude price increase              | Negotiate volume discount, or switch to Groq paid |
| Quality complaints from free users | Set expectations clearly in UI                    |

### Telegram vs web (routing parity)

When a Telegram chat is **linked** to a PulsAI account (`/link`), `/explain` uses the same **tier-based** AI client selection as the web app (resolved via the linked `User`, e.g. `get_ai_client_for_user` in `src/infrastructure/ai/providers.py` — not a single global client). **Signal-specific** explanations use the alert inline action or `/explain <signal-uuid>` so the bot targets the correct signal; plain `/explain` uses the latest signal for the default or requested symbol.

**Code:** `apps/api/src/infrastructure/telegram/handlers.py`, `telegram_inline_markup.py`, `telegram_account_linking.py`.

## Related

- **Sprint 1.7**: Initial AI implementation (current)
- **Sprint 2.7**: Visual Pattern Recognition (requires Claude Vision)
- **Sprint 3.4**: Stripe Payments (tier enforcement)
- `src/infrastructure/ai/providers.py` - Implementation
- `src/infrastructure/config/settings.py` - Configuration

## Configuration

```env
# .env configuration
AI_PROVIDER=groq           # Default: groq (free), options: claude, groq, mock
AI_MOCK_MODE=false         # Force mock mode (for testing)
GROQ_API_KEY=gsk_xxx       # Get from console.groq.com (FREE)
ANTHROPIC_API_KEY=sk-ant-xxx  # Get from console.anthropic.com (PAID)
```

## Notes

- Groq free tier: ~30 req/min, ~6000 tokens/min (sufficient for free tier)
- Claude pricing: ~$3-15/1M tokens depending on model
- Mock responses are realistic but templated (good for UI testing)
