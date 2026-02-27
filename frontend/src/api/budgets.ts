import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type { Budget, BudgetVsActual } from '@/types/models'

export interface BudgetCreateData {
  name: string
  category_id?: string
  amount: number
  period_type: string
  year: number
  month?: number
}

export interface BudgetUpdateData {
  name?: string
  amount?: number
}

export async function listBudgets(params: { year?: number; period_type?: string; page?: number; page_size?: number } = {}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined) searchParams.set(key, String(val))
  })
  const query = searchParams.toString()
  return api.get<ApiListResponse<Budget>>(`/budgets${query ? `?${query}` : ''}`)
}

export async function createBudget(data: BudgetCreateData) {
  return api.post<ApiResponse<Budget>>('/budgets', data)
}

export async function updateBudget(id: string, data: BudgetUpdateData) {
  return api.put<ApiResponse<Budget>>(`/budgets/${id}`, data)
}

export async function deleteBudget(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/budgets/${id}`)
}

export async function getBudgetVsActual(year: number, month?: number) {
  const params = new URLSearchParams({ year: String(year) })
  if (month) params.set('month', String(month))
  return api.get<ApiResponse<BudgetVsActual[]>>(`/budgets/vs-actual?${params.toString()}`)
}

export async function getBudgetAlerts() {
  return api.get<ApiResponse<BudgetVsActual[]>>('/budgets/alerts')
}
