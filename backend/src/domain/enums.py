"""
Domain Enumerations - Single Source of Truth

This module contains ALL domain enums used across the codebase.
Using these enums instead of hardcoded strings provides:
- Type safety (IDE autocomplete, compile-time errors)
- Single source of truth (change in one place)
- Refactor safety (rename propagates everywhere)
- No typos (typo in "BUY" = money lost!)

USAGE:
    from src.domain.enums import SignalAction, Timeframe, Exchange

    # Instead of: if action == "BUY":
    if action == SignalAction.BUY:
        execute_buy()

@see docs/04-structural/CODING_STANDARDS.md
"""

from enum import StrEnum

# =============================================================================
# Constants
# =============================================================================

MINUTES_PER_DAY = 1440
"""Minutes in a day (24 hours * 60 minutes)."""

# Signal class mapping (for ML model predictions)
# WHY 2: In 3-class models, BUY is class 2 (SELL=0, HOLD=1, BUY=2)
BUY_SIGNAL_CLASS = 2

# RSI indicator thresholds
# WHY 30/70: Standard RSI thresholds for oversold/overbought conditions
RSI_OVERSOLD_THRESHOLD = 30
RSI_OVERBOUGHT_THRESHOLD = 70

# Stochastic K level "pop" (StochasticCrossoverDetector + signal_stochastic_crossover)
# WHY 20/80: Standard slow-stochastic zones; @see momentum_detectors.StochasticCrossoverDetector
STOCHASTIC_OVERSOLD_LEVEL = 20
STOCHASTIC_OVERBOUGHT_LEVEL = 80

# ADX trend breakout (ADXTrendBreakoutDetector + signal_adx_trend_breakout)
# WHY 25: trend strength floor (Wilder); WHY 0.5: % dead zone around EMA21 vs price
ADX_STRONG_TREND_THRESHOLD = 25
ADX_PRICE_VS_EMA_DEAD_ZONE_PCT = 0.5

# Signal confluence thresholds
# WHY 2: Need at least 2 signals to confirm a trade (reduces false positives)
MIN_SIGNALS_FOR_CONFLUENCE = 2

# Roles that count as STAFF for domain policy decisions.
#
# WHY here and not beside the role enum: ``UserRole`` lives in
# ``infrastructure.persistence.user_model``, which domain policies must not import. With no
# domain-side definition, each policy re-spelled the strings, and "who is staff" had drifted
# into three backend definitions -- ``UserRole.is_admin()``, a private ``_STAFF_ROLES`` in the
# email policy, and a bare ``("admin", "super_admin")`` tuple inside the LIVE-TRADING gate.
# Adding a role would have reached some and silently missed the rest, the money gate included.
#
# No new vocabulary: both values already exist on both sides of the wire (the web app has
# ``USER_ROLES.ADMIN`` / ``.SUPER_ADMIN`` and types ``role`` as a free string, so nothing
# switches on a closed union). ``tests/domain/test_staff_roles_sot.py`` reads the
# infrastructure enum and fails when the two disagree -- a checked derivation, not a comment
# promising that someone will keep them in sync.
STAFF_ROLES: frozenset[str] = frozenset({"admin", "super_admin"})
"""Roles granted staff-level policy access. Mirrors ``UserRole.is_admin()``, pinned by a test."""

# =============================================================================
# Trading Enums - HIGH PRIORITY (113+ occurrences)
# =============================================================================


class SignalAction(StrEnum):
    """
    Trading signal actions.

    WHY this enum:
    - 113 occurrences across 23 files
    - Typo in "BUY" = wrong trade = MONEY LOST
    - Core trading logic must be type-safe

    VALUES match existing code exactly - DO NOT CHANGE without migration!
    """

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

    def is_bullish(self) -> bool:
        """Check if this is a bullish (buy) signal."""
        return self == SignalAction.BUY

    def is_bearish(self) -> bool:
        """Check if this is a bearish (sell) signal."""
        return self == SignalAction.SELL

    def is_neutral(self) -> bool:
        """Check if this is a neutral (hold) signal."""
        return self == SignalAction.HOLD

    @classmethod
    def actionable(cls) -> frozenset["SignalAction"]:
        """The actions that become TRADES (SoT for "does this signal cost money?").

        HOLD is a prediction, but it is never a position, so it has no capital consequence.
        Anything measuring TRADING skill — accuracy for retraining triggers and rollback —
        must be computed over these actions only.

        WHY this is a constant: the tuple ``("BUY", "SELL")`` was inlined in
        ``Signal.is_actionable`` and re-derived ad hoc elsewhere. Measured 2026-08-06, the
        cost of not having it: signal accuracy counted HOLD, which was 48% of all evaluated
        signals and (through a separate bug) always "correct", reporting 98.7% where real
        trading skill was 46.9%.
        """
        return frozenset({cls.BUY, cls.SELL})

    def to_emoji(self) -> str:
        """
        Display emoji for Telegram/email (SoT for signal action → emoji).

        CODING_STANDARDS: Explicit if/else, no ternary chain.
        Used by: telegram_formatters, handlers, email_service.
        """
        if self == SignalAction.BUY:
            return "🟢"
        if self == SignalAction.SELL:
            return "🔴"
        return "⚪"

    def to_hex_color(self) -> str:
        """Hex color for email HTML (SoT for signal action → color)."""
        if self == SignalAction.BUY:
            return "#22c55e"
        if self == SignalAction.SELL:
            return "#ef4444"
        return "#6b7280"


class Timeframe(StrEnum):
    """
    OHLCV candle timeframes.

    WHY this enum:
    - 154 occurrences across 45 files
    - Wrong timeframe = wrong data = bad predictions
    - Must match CCXT/exchange format exactly

    SoT ALIGNMENT: Member values MUST match shared/constants/timeframes.TIMEFRAME_REGISTRY
    keys. VALID_TIMEFRAMES_SIGNAL_AND_TRAINING is a subset of the registry; each of its
    values must have a corresponding Timeframe member (e.g. Timeframe("1h")).

    NAMING CONVENTION:
    - M = minutes (M1, M5, M15)
    - H = hours (H1, H4)
    - D = days (D1)
    """

    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    # H2 closes the LTF band and H6 the HTF band (`shared/constants/timeframe_bands.py`).
    # Members here MUST match TIMEFRAME_REGISTRY keys — a test enforces it, and the alternative
    # is the crash that took production down today: `Timeframe.D3` referenced by deployed code
    # while the member existed only in an uncommitted file.
    H2 = "2h"
    H4 = "4h"
    H6 = "6h"
    H8 = "8h"
    H12 = "12h"
    D1 = "1d"
    D3 = "3d"
    W1 = "1w"

    def to_minutes(self) -> int:
        """
        Convert timeframe to minutes.

        Useful for calculations like:
        - How many candles in a period
        - Sleep duration between fetches
        """
        from src.shared.constants.timeframes import get_timeframe_delta

        delta = get_timeframe_delta(self.value)
        return int(delta.total_seconds() // 60)

    def to_seconds(self) -> int:
        """Convert timeframe to seconds."""
        return self.to_minutes() * 60

    def is_intraday(self) -> bool:
        """Check if timeframe is intraday (strictly less than one UTC day)."""
        from src.shared.constants.timeframes import is_intraday_timeframe

        return is_intraday_timeframe(self.value)


# =============================================================================
# Exchange Enums - MEDIUM PRIORITY
# =============================================================================


class Exchange(StrEnum):
    """
    Supported cryptocurrency exchanges — typed schema layer.

    Values must match the canonical SoT in
    ``packages/shared/src/constants/exchanges.ts`` (``EXCHANGE_IDS``) and
    ``src/shared/constants/exchanges.py`` (``SUPPORTED_EXCHANGES``). This
    enum is the narrower subset used by Pydantic schemas + domain-typed
    code paths (backtest configs, ML pipelines, fee tables); the broader
    ``SUPPORTED_EXCHANGES`` tuple is used by the user-connection flow.

    WHY this enum (in addition to ``SUPPORTED_EXCHANGES``):
    - Pydantic ``Field`` defaults: ``Field(default=Exchange.BINANCE)``
    - StrEnum gives static type safety + autocomplete
    - Values are CCXT exchange IDs (lowercase) — typo = API error

    @see docs/04-structural/EPIC_A_EXCHANGE_SOT_AUDIT.md
    @see https://docs.ccxt.com/en/latest/exchange-markets.html
    """

    BINANCE = "binance"
    BITGET = "bitget"
    BYBIT = "bybit"

    def get_fee_rate(self) -> float:
        """
        Default trading fee rate for this exchange.

        Note: Actual fees depend on user's VIP level. These are standard
        maker/taker fees. Defensive ``0.001`` fallback for any future
        venue added without an explicit row.
        """
        fees = {
            Exchange.BINANCE: 0.001,  # 0.1%
            Exchange.BITGET: 0.001,  # 0.1%
            Exchange.BYBIT: 0.001,  # 0.1% taker (mainnet); demo uses same
        }
        return fees.get(self, 0.001)


# =============================================================================
# ML Model Enums - NOTE: ModelType lives in src/infrastructure/ml/base.py
# This is intentional - it's tightly coupled to the ML infrastructure.
# Do NOT duplicate it here to avoid type conflicts.
# =============================================================================


# =============================================================================
# User/Billing Enums - LOW PRIORITY
# =============================================================================


class RegistrationSource(StrEnum):
    """
    How the user signed up (SoT for User.registration_source and campaigns).

    WHY this enum:
    - Analytics: know which campaign (VIP launch, invitation, Google, etc.) brought the user
    - One place to add new campaigns (christmas_campaign, black_friday, …)
    - Default for normal signups: direct. VIP launch code at register → vip_launch

    @see .cursor/plans/landing_full_page_merged.plan.md (RegistrationSource enum)
    """

    DIRECT = "direct"
    VIP_LAUNCH = "vip_launch"
    INVITATION = "invitation"
    GOOGLE_CAMPAIGN = "google_campaign"
    X_CAMPAIGN = "x_campaign"
    CHRISTMAS_CAMPAIGN = "christmas_campaign"
    BLACK_FRIDAY = "black_friday"


class SubscriptionTier(StrEnum):
    """
    User subscription tiers.

    WHY this enum:
    - Feature gating based on tier
    - Values must match database SqlEnum
    - Typo = wrong features enabled

    HIERARCHY: FREE < STARTER < PRO < ELITE
    """

    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ELITE = "elite"

    def _tier_level(self) -> int:
        """Get numeric level for comparison."""
        levels = {
            SubscriptionTier.FREE: 0,
            SubscriptionTier.STARTER: 1,
            SubscriptionTier.PRO: 2,
            SubscriptionTier.ELITE: 3,
        }
        return levels[self]

    def can_access(self, required_tier: "SubscriptionTier") -> bool:
        """
        Check if this tier can access features requiring the specified tier.

        Example:
            user_tier = SubscriptionTier.PRO
            user_tier.can_access(SubscriptionTier.FREE)  # True
            user_tier.can_access(SubscriptionTier.PRO)   # True

            user_tier = SubscriptionTier.FREE
            user_tier.can_access(SubscriptionTier.PRO)   # False
        """
        return self._tier_level() >= required_tier._tier_level()

    @classmethod
    def coerce(cls, value: "SubscriptionTier | str | None") -> "SubscriptionTier | None":
        """SoT coercion from the str-or-enum boundary into the enum (or ``None``).

        SQLAlchemy's ``UserModel.subscription_tier`` is ``Mapped[str]`` —
        i.e. the ORM hands back a plain string ("free", "pro", ...) rather
        than a :class:`SubscriptionTier` instance. Downstream tier-gating
        code (``.can_access``, ``._tier_level``) only exists on the enum,
        so consumers across infrastructure/application either had to
        coerce themselves (parallel implementations) or crash with
        ``AttributeError: 'str' object has no attribute 'can_access'``.

        This classmethod is the SoT. Both
        ``AIExplainConfigService.get_enabled_section_keys`` and
        ``rag_section_registry.iter_effective`` delegate to it so the
        coercion logic lives in exactly one place.

        Returns ``None`` for:
        - ``None`` input (sentinel for "unauthenticated / no tier")
        - unknown string values (defensive: a misspelled tier must NOT
          crash a request — downstream treats ``None`` as "lowest tier,
          no access")
        - non-string / non-enum types (defensive against future bugs)
        """
        if value is None:
            return None
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError, TypeError:
            return None


class OAuthProvider(StrEnum):
    """
    Supported OAuth authentication providers.

    WHY this enum:
    - Stored in user.oauth_provider column
    - Used to route to correct OAuth flow
    - Typo = auth fails

    @see src/application/auth/oauth.py
    """

    GOOGLE = "google"
    # Future providers:
    # GITHUB = "github"  # noqa: ERA001
    # DISCORD = "discord"  # noqa: ERA001


# =============================================================================
# Notification Enums - LOW PRIORITY
# =============================================================================


class NotificationChannel(StrEnum):
    """
    Notification delivery channels.

    WHY this enum:
    - User preferences for notification routing
    - Feature gating (some channels are paid)
    """

    EMAIL = "email"
    TELEGRAM = "telegram"
    # Future channels:
    # PUSH = "push"  # noqa: ERA001
    # SMS = "sms"  # noqa: ERA001


class AdminAnnouncementKind(StrEnum):
    """Audience contract shared by admin announcement API and delivery layers."""

    SERVICE = "service"
    MARKETING = "marketing"
