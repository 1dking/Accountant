import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type { RecurringRule } from '@/types/models'

export interface RecurringRuleCreateData {
  type: string
  name: string
  frequency: string
  next_run_date: string
  end_date?: string
  template_data: Record<string, unknown>
}

export interface RecurringRuleUpdateData {
  name?: string
  frequency?: string
  next_run_date?: string
  end_date?: string
  is_active?: boolean
  template_data?: Record<string, unknown>
}

export async function listRules(filters: { page?: number; page_size?: number } = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined) params.set(key, String(val))
  })
  const query = params.toString()
  return api.get<ApiListResponse<RecurringRule>>(`/recurring${query ? `?${query}` : ''}`)
}

export async function getRule(id: string) {
  return api.get<ApiResponse<RecurringRule>>(`/recurring/${id}`)
}

export async function createRule(data: RecurringRuleCreateData) {
  return api.post<ApiResponse<RecurringRule>>('/recurring', data)
}

export async function updateRule(id: string, data: RecurringRuleUpdateData) {
  return api.put<ApiResponse<RecurringRule>>(`/recurring/${id}`, data)
}

export async function deleteRule(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/recurring/${id}`)
}

export async function toggleRule(id: string) {
  return api.post<ApiResponse<RecurringRule>>(`/recurring/${id}/toggle`)
}

export async function processRules() {
  return api.post<ApiResponse<{ processed: number }>>('/recurring/process')
}

export async function getUpcomingRules() {
  return api.get<ApiResponse<RecurringRule[]>>('/recurring/upcoming')
}
