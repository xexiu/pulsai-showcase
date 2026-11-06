// =============================================================================
// Auth Types - Matching Backend API Schemas
// =============================================================================
//
// ARCHITECT NOTES:
// - Types match backend Pydantic schemas exactly
// - Enables type-safe API communication
// - Single source of truth for auth data shapes
// =============================================================================

// =============================================================================
// Request Types
// =============================================================================

export type LoginCredentials = {
  email: string;
  password: string;
  /**
   * When true (default), API sets a long-lived refresh cookie. When false, refresh token is a
   * browser session cookie (cleared when the browser session ends).
   */
  remember_me?: boolean;
};

export type RegisterData = {
  email: string;
  password: string;
  name?: string;
  /** Next-intl locale segment (`en` | `es`); stored on user for emails and UI. */
  locale?: string;
  /** VIP launch / invitation code (optional; must match email on backend). */
  invitation_code?: string;
  terms_consent: boolean;
  data_processing_consent: boolean;
  marketing_consent?: boolean;
};

export type RefreshTokenData = {
  refresh_token: string;
};

// =============================================================================
// Response Data Types
// =============================================================================

type TokenData = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number; // Seconds until access token expires
};

export type UserData = {
  id: string;
  email: string;
  name: string | null;
  role: string;
  subscription_tier: string;
  is_active: boolean;
  is_verified: boolean;
  locale: string;
  created_at: string;
  required_legal_bundle_version: number;
  legal_bundle_version_accepted: number;
  pending_legal_consent: boolean;
  /** True when user has completed Stripe Checkout at least once (Customer Portal available). */
  has_stripe_customer?: boolean;
  /** ISO time when user accepted ADR-009 full-auto safeguards; absent or null until consent. */
  full_auto_trading_consent_at?: string | null;
};

/** Matches GET/PATCH /api/v1/auth/me/settings (notification + billing prefs). */
export type AuthMeSettingsPayload = {
  email_notifications: boolean;
  signal_alerts: boolean;
  weekly_summary: boolean;
  email_signal_alerts_entitled?: boolean;
  theme: string;
  timezone: string;
  /** Cross-device chart IANA; null/absent = use localStorage or Intl until user picks a zone. */
  chart_timezone?: string | null;
  billing_currency: 'eur' | 'usd';
  chart_symbol?: string | null;
  chart_timeframe?: string | null;
  chart_viewport?: Record<string, number> | null;
};

type RegisteredUserData = {
  id: string;
  email: string;
  name: string | null;
  subscription_tier: string;
  // GDPR Consent Fields
  terms_consent: boolean;
  data_processing_consent: boolean;
  marketing_consent: boolean | null;
  // Audit Trail Timestamps (ISO format strings)
  terms_consent_at: string | null;
  data_processing_consent_at: string | null;
  marketing_consent_at: string | null;
};

// =============================================================================
// API Response Wrappers
// =============================================================================

type ResponseMeta = {
  timestamp: string;
};

type ApiResponse<T> = {
  data: T;
  meta: ResponseMeta;
};

type ErrorDetail = {
  code: string;
  message: string;
  details?: Record<string, unknown>;
};

export type ErrorResponse = {
  error: ErrorDetail;
  meta: ResponseMeta;
};

// =============================================================================
// Concrete Response Types
// =============================================================================

export type TokenResponse = ApiResponse<TokenData>;
export type UserResponse = ApiResponse<UserData>;
export type RegisterResponse = ApiResponse<RegisteredUserData>;
