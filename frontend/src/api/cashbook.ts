import { api } from './client'
import type {
  CashbookEntry,
  CashbookEntryCreate,
  CashbookEntryFilters,
  CashbookEntryUpdate,
  CashbookSummary,
  ImportPreview,
  PaymentAccount,
  TransactionCategory,
} from '../types/models'

interface ApiResponse<T> {
  data: T
  meta?: { page: number; page_size: number; total_count: number; total_pages: number }
}

// Payment Accounts
export function listAccounts() {
  return api.get<ApiResponse<PaymentAccount[]>>('/cashbook/accounts')
}

export function createAccount(data: {
  name: string
  account_type: 'bank' | 'credit_card'
  opening_balance: number
  opening_balance_date: string
  default_tax_rate_id?: string
}) {
  return api.post<ApiResponse<PaymentAccount>>('/cashbook/accounts', data)
}

export function getAccount(id: string) {
  return api.get<ApiResponse<PaymentAccount>>(`/cashbook/accounts/${id}`)
}

export function updateAccount(id: string, data: Record<string, unknown>) {
  return api.put<ApiResponse<PaymentAccount>>(`/cashbook/accounts/${id}`, data)
}

export function deleteAccount(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/cashbook/accounts/${id}`)
}

// Cashbook Entries
export function listEntries(filters: CashbookEntryFilters = {}) {
  const params = new URLSearchParams()
  if (filters.account_id) params.set('account_id', filters.account_id)
  if (filters.entry_type) params.set('entry_type', filters.entry_type)
  if (filters.category_id) params.set('category_id', filters.category_id)
  if (filters.date_from) params.set('date_from', filters.date_from)
  if (filters.date_to) params.set('date_to', filters.date_to)
  if (filters.search) params.set('search', filters.search)
  if (filters.page) params.set('page', String(filters.page))
  if (filters.page_size) params.set('page_size', String(filters.page_size))
  const qs = params.toString()
  return api.get<ApiResponse<CashbookEntry[]>>(`/cashbook/entries${qs ? `?${qs}` : ''}`)
}

export function createEntry(data: CashbookEntryCreate) {
  return api.post<ApiResponse<CashbookEntry>>('/cashbook/entries', data)
}

export function getEntry(id: string) {
  return api.get<ApiResponse<CashbookEntry>>(`/cashbook/entries/${id}`)
}

export function updateEntry(id: string, data: CashbookEntryUpdate) {
  return api.put<ApiResponse<CashbookEntry>>(`/cashbook/entries/${id}`, data)
}

export function deleteEntry(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/cashbook/entries/${id}`)
}

// Summary
export function getSummary(accountId: string, dateFrom: string, dateTo: string) {
  return api.get<ApiResponse<CashbookSummary>>(
    `/cashbook/summary?account_id=${accountId}&date_from=${dateFrom}&date_to=${dateTo}`
  )
}

// Categories
export function listCategories(categoryType?: 'income' | 'expense') {
  const params = categoryType ? `?category_type=${categoryType}` : ''
  return api.get<ApiResponse<TransactionCategory[]>>(`/cashbook/categories${params}`)
}

export function createCategory(data: {
  name: string
  category_type: 'income' | 'expense' | 'both'
  color?: string
  icon?: string
}) {
  return api.post<ApiResponse<TransactionCategory>>('/cashbook/categories', data)
}

// Excel Import
export function importExcelPreview(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.upload<ApiResponse<ImportPreview>>('/cashbook/import/excel', formData)
}

export function importExcelConfirm(data: { account_id: string; rows: unknown[] }) {
  return api.post<ApiResponse<{ imported_count: number; message: string }>>(
    '/cashbook/import/excel/confirm',
    data
  )
}
