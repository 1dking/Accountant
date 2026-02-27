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
