import { api } from './client'

interface ApiResponse<T> {
  data: T
}

export interface PublicDocument {
  resource_type: string
  document: {
    id: string
    type: string
    number: string
    status: string
    issue_date: string
    expiry_date?: string
    due_date?: string
    subtotal: number
    tax_rate: number | null
    tax_amount: number | null
    discount_amount: number
    total: number
    currency: string
    notes: string | null
    payment_terms?: string | null
    signed_by_name?: string | null
    signed_at?: string | null
    contact: {
      company_name: string | null
      contact_name: string | null
      email: string | null
    } | null
    line_items: {
      description: string
      quantity: number
      unit_price: number
      tax_rate: number | null
      total: number
    }[]
    payments?: {
      amount: number
      date: string
      payment_method: string | null
    }[]
  }
  company: {
    company_name: string | null
    company_email: string | null
    company_phone: string | null
    company_website: string | null
    address_line1: string | null
    city: string | null
    state: string | null
    zip_code: string | null
    country: string | null
    has_logo: boolean
  } | null
  actions: string[]
  is_signed: boolean
  stripe_configured: boolean
  stripe_publishable_key: string | null
}

export interface PublicTokenInfo {
  id: string
  token: string
  resource_type: string
  resource_id: string
  expires_at: string | null
  is_active: boolean
  view_count: number
  shareable_url: string
}

export function getPublicDocument(token: string) {
  return api.get<ApiResponse<PublicDocument>>(`/public/view/${token}`)
}

export function acceptEstimate(token: string, data: { signature_data: string; signer_name: string }) {
  return api.post<ApiResponse<{ status: string; signed_at: string }>>(`/public/view/${token}/accept`, data)
}

export function createShareLink(resourceType: 'estimate' | 'invoice', resourceId: string, expiresInDays?: number) {
  const endpoint = resourceType === 'estimate'
    ? `/estimates/${resourceId}/share`
    : `/invoices/${resourceId}/share`
  return api.post<ApiResponse<PublicTokenInfo>>(endpoint, expiresInDays ? { expires_in_days: expiresInDays } : {})
}

export interface PaymentIntentResponse {
  client_secret: string
  publishable_key: string
  amount: number
  currency: string
}

export function payPublicDocument(token: string) {
  return api.post<ApiResponse<PaymentIntentResponse>>(`/public/view/${token}/pay`)
}
