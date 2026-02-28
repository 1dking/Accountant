import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type { IncomeEntry, IncomeSummary } from '@/types/models'

export interface IncomeFilters {
  search?: string
  category?: string
  contact_id?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

export interface IncomeCreateData {
  contact_id?: string
  invoice_id?: string
  category?: string
  description: string
  amount: number
  currency?: string
  date: string
  payment_method?: string
  reference?: string
  notes?: string
}

export interface IncomeUpdateData {
  contact_id?: string
  invoice_id?: string
  category?: string
  description?: string
  amount?: number
  currency?: string
  date?: string
  payment_method?: string
  reference?: string
  notes?: string
}

export async function listIncome(filters: IncomeFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== '' && val !== null) params.set(key, String(val))
  })
  const query = params.toString()
  return api.get<ApiListResponse<IncomeEntry>>(`/income${query ? `?${query}` : ''}`)
}

export async function getIncome(id: string) {
  return api.get<ApiResponse<IncomeEntry>>(`/income/${id}`)
}

export async function createIncome(data: IncomeCreateData) {
  return api.post<ApiResponse<IncomeEntry>>('/income', data)
}

export async function updateIncome(id: string, data: IncomeUpdateData) {
  return api.put<ApiResponse<IncomeEntry>>(`/income/${id}`, data)
}

export async function deleteIncome(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/income/${id}`)
}

export async function createIncomeFromDocument(documentId: string) {
  return api.post<ApiResponse<IncomeEntry>>(`/income/from-document/${documentId}`)
}

export async function getIncomeSummary(params: { date_from?: string; date_to?: string } = {}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, val]) => {
    if (val) searchParams.set(key, val)
  })
  const query = searchParams.toString()
  return api.get<ApiResponse<IncomeSummary>>(`/income/summary${query ? `?${query}` : ''}`)
}
