import { api } from './client'
import type { ApiResponse } from '@/types/api'

export interface Subscription {
  plan_key: string
  status: string
  billing_period: string | null
  current_period_end: string | null
  has_stripe_customer: boolean
}

/** `limit: null` means unlimited on this plan. */
export interface UsageMetric {
  used: number
  limit: number | null
}

export interface Usage {
  plan_key: string
  pages: UsageMetric
  storage: UsageMetric
  ai_messages: UsageMetric
}

/** Prepaid telephony balance + auto top-up settings (sell price only). */
export interface TelephonyCreditSummary {
  balance_usd: number
  is_low: boolean
  is_empty: boolean
  lifetime_purchased_usd: number
  lifetime_spent_usd: number
  auto_topup_enabled: boolean
  auto_topup_threshold_usd: number
  auto_topup_amount_usd: number
  has_payment_method: boolean
}

/** What THIS tenant pays per unit — never our cost. */
export interface TelephonyRateItem {
  unit: string
  label: string
  price_usd: number
  is_enabled: boolean
}

export interface TelephonyLedgerItem {
  id: string
  type: string
  unit: string | null
  quantity: number
  /** Negative = money in (top-up/refund); positive = money out (usage). */
  amount_usd: number
  balance_after_usd: number
  description: string | null
  created_at: string
}

export interface AutoTopupInput {
  enabled?: boolean
  threshold_usd?: number
  amount_usd?: number
}

export const billingApi = {
  getSubscription: () => api.get<ApiResponse<Subscription>>('/billing/subscription'),

  getUsage: () => api.get<ApiResponse<Usage>>('/billing/usage'),

  createCheckout: (planKey: string, period: 'monthly' | 'annual' = 'monthly') =>
    api.post<ApiResponse<{ checkout_url?: string; free?: boolean; plan_key?: string }>>(
      '/billing/checkout',
      { plan_key: planKey, period }
    ),

  verify: (sessionId: string) =>
    api.get<ApiResponse<Subscription>>(`/billing/verify?session_id=${encodeURIComponent(sessionId)}`),

  openPortal: () => api.post<ApiResponse<{ url: string }>>('/billing/portal', {}),

  // --- Prepaid telephony credit ---
  getTelephonyCredit: () =>
    api.get<ApiResponse<TelephonyCreditSummary>>('/billing/telephony/credit'),

  getTelephonyRates: () =>
    api.get<ApiResponse<TelephonyRateItem[]>>('/billing/telephony/rates'),

  getTelephonyLedger: (limit = 25) =>
    api.get<ApiResponse<TelephonyLedgerItem[]>>(`/billing/telephony/ledger?limit=${limit}`),

  telephonyTopup: (amountUsd: number) =>
    api.post<ApiResponse<{ checkout_url: string; session_id: string }>>(
      '/billing/telephony/topup',
      { amount_usd: amountUsd }
    ),

  verifyTelephonyTopup: (sessionId: string) =>
    api.get<ApiResponse<TelephonyCreditSummary>>(
      `/billing/telephony/topup/verify?session_id=${encodeURIComponent(sessionId)}`
    ),

  setTelephonyAutoTopup: (input: AutoTopupInput) =>
    api.put<ApiResponse<TelephonyCreditSummary>>('/billing/telephony/auto-topup', input),
}
