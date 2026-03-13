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
  account_type: string
  currency?: string
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

export function deleteAccountWithEntries(id: string, action: 'move' | 'delete', targetAccountId?: string) {
  return api.post<ApiResponse<{ message: string; entries_moved: number; entries_deleted: number }>>(
    `/cashbook/accounts/${id}/delete`,
    { action, target_account_id: targetAccountId || null }
  )
}

// Cashbook Entries
export function listEntries(filters: CashbookEntryFilters = {}) {
  const params = new URLSearchParams()
  if (filters.account_id) params.set('account_id', filters.account_id)
  if (filters.entry_type) params.set('entry_type', filters.entry_type)
  if (filters.category_id) params.set('category_id', filters.category_id)
  if (filters.status) params.set('status', filters.status)
  if (filters.date_from) params.set('date_from', filters.date_from)
  if (filters.date_to) params.set('date_to', filters.date_to)
  if (filters.search) params.set('search', filters.search)
  if (filters.include_deleted) params.set('include_deleted', 'true')
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
export function getSummary(accountId: string | null, dateFrom: string, dateTo: string) {
  const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo })
  if (accountId) params.set('account_id', accountId)
  return api.get<ApiResponse<CashbookSummary>>(
    `/cashbook/summary?${params.toString()}`
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

// Capture (upload-and-book)
export interface CashbookCaptureResult {
  document_id: string
  document_title: string
  entry_id: string | null
  entry_type: string | null
  entry_amount: number | null
  entry_description: string | null
  entry_date: string | null
  category_name: string | null
  extraction: Record<string, unknown> | null
  processing_time_ms: number
}

export function cashbookCapture(
  file: File,
  entryType: 'income' | 'expense',
  accountId: string,
  folderId?: string
) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('entry_type', entryType)
  formData.append('account_id', accountId)
  if (folderId) formData.append('folder_id', folderId)
  return api.upload<ApiResponse<CashbookCaptureResult>>('/cashbook/capture', formData)
}

// Restore soft-deleted entry
export function restoreEntry(id: string) {
  return api.post<ApiResponse<CashbookEntry>>(`/cashbook/entries/${id}/restore`, {})
}

// Split transaction
export function splitEntry(id: string, lines: { description: string; amount: number; category_id?: string; notes?: string }[]) {
  return api.post<ApiResponse<CashbookEntry[]>>(`/cashbook/entries/${id}/split`, { lines })
}

// Bulk actions
export function bulkDeleteEntries(entry_ids: string[]) {
  return api.post<ApiResponse<{ deleted: number }>>('/cashbook/entries/bulk-delete', { entry_ids })
}

export function bulkCategorizeEntries(entry_ids: string[], category_id: string) {
  return api.post<ApiResponse<{ updated: number }>>('/cashbook/entries/bulk-categorize', { entry_ids, category_id })
}

export function bulkMoveEntries(entry_ids: string[], account_id: string) {
  return api.post<ApiResponse<{ moved: number }>>('/cashbook/entries/bulk-move', { entry_ids, account_id })
}

export function bulkUpdateStatus(entry_ids: string[], status: string) {
  return api.post<ApiResponse<{ updated: number }>>('/cashbook/entries/bulk-status', { entry_ids, status })
}

export function fixOrphanEntries() {
  return api.post<ApiResponse<{ reassigned: number }>>('/cashbook/entries/fix-orphans')
}

// Trash
export function listTrash(page = 1, pageSize = 50) {
  return api.get<ApiResponse<{ entries: CashbookEntry[]; accounts: PaymentAccount[] }>>(
    `/cashbook/trash?page=${page}&page_size=${pageSize}`
  )
}

export function getTrashCount() {
  return api.get<ApiResponse<{ entries: number; accounts: number; total: number }>>('/cashbook/trash/count')
}

export function emptyTrash() {
  return api.post<ApiResponse<{ deleted_entries: number; deleted_accounts: number }>>('/cashbook/trash/empty')
}

export function restoreAllTrash() {
  return api.post<ApiResponse<{ restored_entries: number; restored_accounts: number }>>('/cashbook/trash/restore-all')
}

export function permanentDeleteEntry(id: string) {
  return api.post<ApiResponse<{ message: string }>>(`/cashbook/entries/${id}/permanent-delete`)
}

export function restoreAccount(id: string) {
  return api.post<ApiResponse<PaymentAccount>>(`/cashbook/accounts/${id}/restore`)
}

export function permanentDeleteAccount(id: string) {
  return api.post<ApiResponse<{ message: string }>>(`/cashbook/accounts/${id}/permanent-delete`)
}
