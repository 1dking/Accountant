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

// ---------------------------------------------------------------------------
// Journal entries (Phase 1.2 — manual double-entry posting)
// ---------------------------------------------------------------------------

export type JournalStatus = 'posted' | 'void'

export interface JournalLine {
  id: string
  account_id: string
  account_code: string | null
  account_name: string | null
  debit: string
  credit: string
  description: string | null
}

export interface JournalLineInput {
  account_id: string
  debit: string
  credit: string
  description?: string | null
}

export interface JournalEntry {
  id: string
  entry_number: number
  date: string
  memo: string | null
  source: string
  source_id: string | null
  status: JournalStatus
  created_by: string
  created_at: string
  lines: JournalLine[]
  total: string
}

export interface JournalEntryInput {
  date: string
  memo?: string | null
  lines: JournalLineInput[]
}

export async function listJournalEntries(params: { date_from?: string; date_to?: string; include_void?: boolean } = {}) {
  const q = new URLSearchParams()
  if (params.date_from) q.set('date_from', params.date_from)
  if (params.date_to) q.set('date_to', params.date_to)
  if (params.include_void === false) q.set('include_void', 'false')
  const query = q.toString()
  return api.get<ApiResponse<JournalEntry[]>>(`/accounting/journal${query ? `?${query}` : ''}`)
}

export async function createJournalEntry(data: JournalEntryInput) {
  return api.post<ApiResponse<JournalEntry>>('/accounting/journal', data)
}

export async function getJournalEntry(id: string) {
  return api.get<ApiResponse<JournalEntry>>(`/accounting/journal/${id}`)
}

export async function voidJournalEntry(id: string) {
  return api.post<ApiResponse<JournalEntry>>(`/accounting/journal/${id}/void`)
}

// ---------------------------------------------------------------------------
// Ledger reports (Phase 1.3 — Trial Balance + General Ledger)
// ---------------------------------------------------------------------------

export interface TrialBalanceRow {
  code: string
  name: string
  account_type: CoaAccountType
  debit: string
  credit: string
}

export interface TrialBalance {
  rows: TrialBalanceRow[]
  total_debit: string
  total_credit: string
  balanced: boolean
}

export interface GeneralLedgerPosting {
  date: string
  ref: string
  source: string
  memo: string | null
  debit: string
  credit: string
  balance: string
}

export interface GeneralLedgerAccount {
  code: string
  name: string
  account_type: CoaAccountType
  normal_balance: 'debit' | 'credit'
  postings: GeneralLedgerPosting[]
  total_debit: string
  total_credit: string
  closing_balance: string
}

function reportQuery(params: { date_from?: string; date_to?: string }): string {
  const q = new URLSearchParams()
  if (params.date_from) q.set('date_from', params.date_from)
  if (params.date_to) q.set('date_to', params.date_to)
  const s = q.toString()
  return s ? `?${s}` : ''
}

export async function getTrialBalance(params: { date_from?: string; date_to?: string } = {}) {
  return api.get<ApiResponse<TrialBalance>>(`/accounting/reports/trial-balance${reportQuery(params)}`)
}

export async function getGeneralLedger(params: { date_from?: string; date_to?: string } = {}) {
  return api.get<ApiResponse<{ accounts: GeneralLedgerAccount[] }>>(
    `/accounting/reports/general-ledger${reportQuery(params)}`,
  )
}

export interface StatementLine {
  code: string
  name: string
  amount: string
}

export interface ProfitLoss {
  income: StatementLine[]
  expenses: StatementLine[]
  total_income: string
  total_expenses: string
  net_profit: string
}

export interface BalanceSheet {
  assets: StatementLine[]
  liabilities: StatementLine[]
  equity: StatementLine[]
  total_assets: string
  total_liabilities: string
  total_equity: string
  total_liabilities_equity: string
  balanced: boolean
  as_of: string
}

export async function getProfitLoss(params: { date_from?: string; date_to?: string } = {}) {
  return api.get<ApiResponse<ProfitLoss>>(`/accounting/reports/profit-loss${reportQuery(params)}`)
}

export async function getBalanceSheet(as_of?: string) {
  const q = as_of ? `?as_of=${encodeURIComponent(as_of)}` : ''
  return api.get<ApiResponse<BalanceSheet>>(`/accounting/reports/balance-sheet${q}`)
}

// ---------------------------------------------------------------------------
// Accounts Payable / vendor bills (Phase 1.4)
// ---------------------------------------------------------------------------

export type BillStatus = 'draft' | 'pending' | 'approved' | 'paid' | 'void'

export interface VendorBillLine {
  id: string
  account_id: string
  account_code: string | null
  account_name: string | null
  description: string | null
  amount: string
}

export interface VendorBillLineInput {
  account_id: string
  description?: string | null
  amount: string
}

export interface VendorBill {
  id: string
  bill_number: string
  vendor_name: string
  vendor_contact_id: string | null
  bill_date: string
  due_date: string | null
  memo: string | null
  total_amount: string
  status: BillStatus
  approval_journal_id: string | null
  payment_journal_id: string | null
  scheduled_payment_date: string | null
  paid_at: string | null
  created_at: string
  lines: VendorBillLine[]
}

export interface VendorBillInput {
  vendor_name: string
  vendor_contact_id?: string | null
  bill_number?: string | null
  bill_date: string
  due_date?: string | null
  memo?: string | null
  status?: BillStatus | null
  lines: VendorBillLineInput[]
}

export async function listBills(status?: BillStatus) {
  const q = status ? `?status=${status}` : ''
  return api.get<ApiResponse<VendorBill[]>>(`/accounting/bills${q}`)
}

export async function getApprovalQueue() {
  return api.get<ApiResponse<VendorBill[]>>('/accounting/bills/approval-queue')
}

export async function createBill(data: VendorBillInput) {
  return api.post<ApiResponse<VendorBill>>('/accounting/bills', data)
}

export async function approveBill(id: string) {
  return api.post<ApiResponse<VendorBill>>(`/accounting/bills/${id}/approve`)
}

export async function payBill(id: string, cash_account_id: string, payment_date: string) {
  return api.post<ApiResponse<VendorBill>>(`/accounting/bills/${id}/pay`, { cash_account_id, payment_date })
}

export async function voidBill(id: string) {
  return api.post<ApiResponse<VendorBill>>(`/accounting/bills/${id}/void`)
}

// ---------------------------------------------------------------------------
// 1099 / contractor tracking (Phase 1.5)
// ---------------------------------------------------------------------------

export interface Vendor1099Row {
  contact_id: string
  name: string
  contact_name: string | null
  tax_id: string | null
  is_1099_vendor: boolean
  bills_total: string
  cashbook_total: string
  total_paid: string
  meets_threshold: boolean
}

export interface Report1099 {
  year: number
  threshold: string
  vendors: Vendor1099Row[]
  candidates: Vendor1099Row[]
}

export async function get1099Report(year: number) {
  return api.get<ApiResponse<Report1099>>(`/accounting/1099/report?year=${year}`)
}

export async function set1099Flag(contactId: string, is_1099_vendor: boolean) {
  return api.post<ApiResponse<{ contact_id: string; is_1099_vendor: boolean }>>(
    `/accounting/1099/vendors/${contactId}`,
    { is_1099_vendor },
  )
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
