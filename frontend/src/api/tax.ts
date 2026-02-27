import { api } from './client'
import type { ApiResponse } from '@/types/api'

export interface TaxRate {
  id: string
  name: string
  rate: number
  description: string | null
  is_default: boolean
  is_active: boolean
  region: string | null
  created_by: string
  created_at: string
  updated_at: string
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

export async function createTaxRate(data: {
  name: string
  rate: number
  description?: string
  is_default?: boolean
  region?: string
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
