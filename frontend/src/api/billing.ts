import { api } from './client'
import type { ApiResponse } from '@/types/api'

export interface Subscription {
  plan_key: string
  status: string
  billing_period: string | null
  current_period_end: string | null
  has_stripe_customer: boolean
}

export const billingApi = {
  getSubscription: () => api.get<ApiResponse<Subscription>>('/billing/subscription'),

  createCheckout: (planKey: string, period: 'monthly' | 'annual' = 'monthly') =>
    api.post<ApiResponse<{ checkout_url?: string; free?: boolean; plan_key?: string }>>(
      '/billing/checkout',
      { plan_key: planKey, period }
    ),

  verify: (sessionId: string) =>
    api.get<ApiResponse<Subscription>>(`/billing/verify?session_id=${encodeURIComponent(sessionId)}`),

  openPortal: () => api.post<ApiResponse<{ url: string }>>('/billing/portal', {}),
}
