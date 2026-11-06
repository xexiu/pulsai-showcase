// =============================================================================
// User Types - User and authentication data structures
// =============================================================================

import type { SubscriptionTier, UserRole } from './common';

/**
 * User profile data
 */
export interface User {
  id: string;
  email: string;
  name: string | null;
  avatarUrl: string | null;
  role: UserRole;
  subscription: UserSubscription;
  preferences: UserPreferences;
  createdAt: string;
  updatedAt: string;
}

/**
 * User subscription details
 */
export interface UserSubscription {
  tier: SubscriptionTier;
  status: 'active' | 'cancelled' | 'expired' | 'trialing';
  currentPeriodStart: string;
  currentPeriodEnd: string;
  cancelAtPeriodEnd: boolean;
  stripeCustomerId: string | null;
  stripeSubscriptionId: string | null;
}

/**
 * User preferences for signals and notifications
 */
export interface UserPreferences {
  locale: 'es' | 'en';
  theme: 'light' | 'dark' | 'system';
  notifications: NotificationPreferences;
  watchlist: string[]; // Symbol IDs
  defaultTimeframe: '1h' | '4h' | '1d';
}

/**
 * Notification preferences
 */
export interface NotificationPreferences {
  email: boolean;
  push: boolean;
  signalAlerts: boolean;
  priceAlerts: boolean;
  weeklyDigest: boolean;
}

/**
 * Authentication tokens
 */
export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
}

/**
 * Login request payload
 */
export interface LoginRequest {
  email: string;
  password: string;
}

/**
 * Registration request payload
 */
export interface RegisterRequest {
  email: string;
  password: string;
  name?: string;
  locale?: 'es' | 'en';
}
