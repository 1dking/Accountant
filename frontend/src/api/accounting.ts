import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type {
  Expense,
  ExpenseListItem,
  ExpenseCategory,
  ExpenseSummary,
  ExpenseCreate,
  ExpenseUpdate,
  ExpenseFilters,
  ExpenseApproval,
  AccountingPeriod,
} from '@/types/models'

// Categories
export async function listCategories() {
  return api.get<ApiResponse<ExpenseCategory[]>>('/accounting/categories')
}

export async function createCategory(data: { name: string; color?: string; icon?: string }) {
  return api.post<ApiResponse<ExpenseCategory>>('/accounting/categories', data)
}

export async function updateCategory(id: string, data: { name?: string; color?: string; icon?: string }) {
  return api.put<ApiResponse<ExpenseCategory>>(`/accounting/categories/${id}`, data)
}

export async function deleteCategory(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/accounting/categories/${id}`)
}

// Expenses
export async function listExpenses(filters: ExpenseFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== '' && val !== null) params.set(key, String(val))
  })
  const query = params.toString()
  return api.get<ApiListResponse<ExpenseListItem>>(`/accounting/expenses${query ? `?${query}` : ''}`)
}

export async function createExpense(data: ExpenseCreate) {
  return api.post<ApiResponse<Expense>>('/accounting/expenses', data)
}

export async function createExpenseFromDocument(documentId: string) {
  return api.post<ApiResponse<Expense>>(`/accounting/expenses/from-document/${documentId}`)
}

export async function getExpense(id: string) {
  return api.get<ApiResponse<Expense>>(`/accounting/expenses/${id}`)
}

export async function updateExpense(id: string, data: ExpenseUpdate) {
  return api.put<ApiResponse<Expense>>(`/accounting/expenses/${id}`, data)
}

export async function deleteExpense(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/accounting/expenses/${id}`)
}

// Summary
export async function getExpenseSummary(params: {
  date_from?: string
  date_to?: string
  user_id?: string
  year?: number
} = {}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null) searchParams.set(key, String(val))
  })
  const query = searchParams.toString()
  return api.get<ApiResponse<ExpenseSummary>>(`/accounting/summary${query ? `?${query}` : ''}`)
}

// Approvals
export async function getExpenseApproval(expenseId: string) {
  return api.get<ApiResponse<ExpenseApproval | null>>(`/accounting/expenses/${expenseId}/approval`)
}

export async function requestExpenseApproval(expenseId: string, assignedTo: string) {
  return api.post<ApiResponse<ExpenseApproval>>(
    `/accounting/expenses/${expenseId}/request-approval`,
    { assigned_to: assignedTo },
  )
}

export async function approveExpense(expenseId: string, comment?: string) {
  return api.post<ApiResponse<ExpenseApproval>>(
    `/accounting/expenses/${expenseId}/approve`,
    { comment: comment || null },
  )
}

export async function rejectExpense(expenseId: string, comment?: string) {
  return api.post<ApiResponse<ExpenseApproval>>(
    `/accounting/expenses/${expenseId}/reject`,
    { comment: comment || null },
  )
}

export async function listPendingApprovals() {
  return api.get<ApiResponse<ExpenseApproval[]>>('/accounting/expenses/pending-approvals')
}

// ---------------------------------------------------------------------------
// Chart of Accounts (Phase 1 — double-entry spine)
// ---------------------------------------------------------------------------

export type CoaAccountType = 'asset' | 'liability' | 'equity' | 'income' | 'expense'

export interface ChartAccount {
  id: string
  code: string
  name: string
  account_type: CoaAccountType
  normal_balance: 'debit' | 'credit'
  description: string | null
  parent_id: string | null
  is_active: boolean
  is_system: boolean
  created_at: string
  updated_at: string
}

export interface ChartAccountInput {
  code: string
  name: string
  account_type: CoaAccountType
  description?: string | null
  parent_id?: string | null
  is_active?: boolean
}

export interface CoaSeedResult {
  accounts_created: number
  categories_mapped: number
  payment_accounts_mapped: number
  already_seeded: boolean
}

export async function listChartAccounts(params: { account_type?: CoaAccountType; include_inactive?: boolean } = {}) {
  const q = new URLSearchParams()
  if (params.account_type) q.set('account_type', params.account_type)
  if (params.include_inactive) q.set('include_inactive', 'true')
  const query = q.toString()
  return api.get<ApiResponse<ChartAccount[]>>(`/accounting/accounts${query ? `?${query}` : ''}`)
}

export async function seedChartOfAccounts(migrate = true) {
  return api.post<ApiResponse<CoaSeedResult>>(`/accounting/accounts/seed?migrate=${migrate}`)
}

export async function createChartAccount(data: ChartAccountInput) {
  return api.post<ApiResponse<ChartAccount>>('/accounting/accounts', data)
}

export async function updateChartAccount(id: string, data: Partial<ChartAccountInput>) {
  return api.patch<ApiResponse<ChartAccount>>(`/accounting/accounts/${id}`, data)
}

export async function deactivateChartAccount(id: string) {
  return api.delete<ApiResponse<ChartAccount>>(`/accounting/accounts/${id}`)
}

// Accounting Periods
export async function listPeriods() {
  return api.get<ApiResponse<AccountingPeriod[]>>('/accounting/periods')
}

export async function closePeriod(data: { year: number; month: number; notes?: string }) {
  return api.post<ApiResponse<AccountingPeriod>>('/accounting/periods/close', data)
}

export async function reopenPeriod(periodId: string, data: { notes?: string }) {
  return api.post<ApiResponse<AccountingPeriod>>(`/accounting/periods/${periodId}/reopen`, data)
}
