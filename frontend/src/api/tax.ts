import { api } from './client'
import type { ApiResponse } from '@/types/api'

export type TaxType = 'gst' | 'hst' | 'pst' | 'rst' | 'qst' | 'other'

export interface TaxRate {
  id: string
  name: string
  rate: number
  description: string | null
  is_default: boolean
  is_active: boolean
  region: string | null
  /** Canadian tax matrix — null on legacy user-created rates. */
  tax_type: TaxType | null
  /** ISO-3166-2:CA code; null = federal (GST) or not province-bound. */
  province: string | null
  /** Eligible as an input tax credit on the GST34. PST is not. */
  is_recoverable: boolean
  /** Seeded system rate — not editable or deletable. */
  is_system: boolean
  effective_from: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface ProvinceInfo {
  code: string
  name: string
  /** Human summary — "HST 13%", "GST 5% + PST 7%". */
  regime: string
  combined_rate: number
}

export interface ProvinceRates {
  province: string
  primary: TaxRate | null
  secondary: TaxRate | null
  combined_rate: number
}

export interface TaxLiabilityReport {
  date_from: string
  date_to: string
  total_tax_collected: number
  total_tax_paid: number
  net_tax_liability: number
}

export async function listTaxRates() {
  return api.get<{ data: TaxRate[] }>('/accounting/tax-rates')
}

export async function listProvinces() {
  return api.get<{ data: ProvinceInfo[] }>('/accounting/tax/provinces')
}

export async function getProvinceRates(code: string) {
  return api.get<ApiResponse<ProvinceRates>>(`/accounting/tax/provinces/${code}/rates`)
}

export async function createTaxRate(data: {
  name: string
  rate: number
  description?: string
  is_default?: boolean
  region?: string
  tax_type?: TaxType
  province?: string
  is_recoverable?: boolean
}) {
  return api.post<ApiResponse<TaxRate>>('/accounting/tax-rates', data)
}

export async function updateTaxRate(
  id: string,
  data: Partial<{
    name: string
    rate: number
    description: string
    is_default: boolean
    is_active: boolean
    region: string
    tax_type: TaxType
    province: string
    is_recoverable: boolean
  }>
) {
  return api.put<ApiResponse<TaxRate>>(`/accounting/tax-rates/${id}`, data)
}

export async function deleteTaxRate(id: string) {
  return api.delete<ApiResponse<{ detail: string }>>(`/accounting/tax-rates/${id}`)
}

export async function getTaxLiability(dateFrom?: string, dateTo?: string) {
  const params = new URLSearchParams()
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo) params.set('date_to', dateTo)
  const query = params.toString()
  return api.get<ApiResponse<TaxLiabilityReport>>(
    `/accounting/tax-liability${query ? `?${query}` : ''}`
  )
}
