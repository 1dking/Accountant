import { api } from './client'
import type { ApiResponse } from '@/types/api'

export interface PersonalAccount {
  id: string
  name: string
  account_type: string
  currency: string
  opening_balance: string
  opening_balance_date: string
  is_active: boolean
  current_balance?: string | null
}

export interface PersonalTransaction {
  id: string
  account_id: string
  date: string
  direction: 'in' | 'out'
  amount: string
  description: string
  category_id: string | null
  category_name: string | null
  notes: string | null
}

export interface PersonalCategory {
  id: string
  name: string
  direction: string
}

export interface CategoryCashflow {
  category_id: string | null
  category_name: string
  direction: string
  total: string
  count: number
}

export interface PersonalCashflow {
  period_start: string | null
  period_end: string | null
  total_in: string
  total_out: string
  net: string
  by_category: CategoryCashflow[]
}

export async function listPersonalCategories() {
  return api.get<ApiResponse<PersonalCategory[]>>('/personal/categories')
}

export async function listPersonalAccounts() {
  return api.get<ApiResponse<PersonalAccount[]>>('/personal/accounts')
}

export async function createPersonalAccount(data: {
  name: string; account_type?: string; currency?: string
  opening_balance?: string; opening_balance_date: string
}) {
  return api.post<ApiResponse<PersonalAccount>>('/personal/accounts', data)
}

export async function deletePersonalAccount(id: string) {
  return api.delete<ApiResponse<{ detail: string }>>(`/personal/accounts/${id}`)
}

export async function listPersonalTransactions(params: {
  account_id?: string; date_from?: string; date_to?: string; limit?: number
} = {}) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') qs.set(k, String(v)) })
  const q = qs.toString()
  return api.get<ApiResponse<PersonalTransaction[]>>(`/personal/transactions${q ? `?${q}` : ''}`)
}

export async function createPersonalTransaction(data: {
  account_id: string; date: string; direction: 'in' | 'out'
  amount: string; description: string; category_id?: string | null; notes?: string
}) {
  return api.post<ApiResponse<PersonalTransaction>>('/personal/transactions', data)
}

export async function deletePersonalTransaction(id: string) {
  return api.delete<ApiResponse<{ detail: string }>>(`/personal/transactions/${id}`)
}

export async function getPersonalCashflow(params: { date_from?: string; date_to?: string } = {}) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v) qs.set(k, String(v)) })
  const q = qs.toString()
  return api.get<ApiResponse<PersonalCashflow>>(`/personal/cashflow${q ? `?${q}` : ''}`)
}
