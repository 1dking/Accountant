import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type { Estimate, EstimateListItem, Invoice } from '@/types/models'

export interface EstimateFilters {
  search?: string
  status?: string
  contact_id?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

export interface EstimateLineItemData {
  description: string
  quantity: number
  unit_price: number
  tax_rate?: number
}

export interface EstimateCreateData {
  contact_id: string
  issue_date: string
  expiry_date: string
  tax_rate?: number
  discount_amount?: number
  currency?: string
  notes?: string
  line_items: EstimateLineItemData[]
}

export interface EstimateUpdateData {
  contact_id?: string
  issue_date?: string
  expiry_date?: string
  status?: string
  tax_rate?: number
  discount_amount?: number
  currency?: string
  notes?: string
  line_items?: EstimateLineItemData[]
}

export async function listEstimates(filters: EstimateFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== '' && val !== null) params.set(key, String(val))
  })
  const query = params.toString()
  return api.get<ApiListResponse<EstimateListItem>>(`/estimates${query ? `?${query}` : ''}`)
}

export async function getEstimate(id: string) {
  return api.get<ApiResponse<Estimate>>(`/estimates/${id}`)
}

export async function createEstimate(data: EstimateCreateData) {
  return api.post<ApiResponse<Estimate>>('/estimates', data)
}

export async function updateEstimate(id: string, data: EstimateUpdateData) {
  return api.put<ApiResponse<Estimate>>(`/estimates/${id}`, data)
}

export async function deleteEstimate(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/estimates/${id}`)
}

export async function convertEstimateToInvoice(id: string) {
  return api.post<ApiResponse<Invoice>>(`/estimates/${id}/convert-to-invoice`)
}
