// Auth
export interface User {
  id: string
  email: string
  full_name: string
  role: 'admin' | 'accountant' | 'viewer'
  is_active: boolean
  created_at: string
}

// Documents
export type DocumentType = 'invoice' | 'receipt' | 'contract' | 'tax_form' | 'report' | 'statement' | 'other'
export type DocumentStatus = 'draft' | 'pending_review' | 'approved' | 'filed' | 'archived'

export interface Document {
  id: string
  filename: string
  original_filename: string
  mime_type: string
  file_size: number
  file_hash: string
  storage_path: string
  folder_id: string | null
  document_type: DocumentType
  status: DocumentStatus
  title: string | null
  description: string | null
  extracted_text: string | null
  extracted_metadata: Record<string, unknown> | null
  uploaded_by: string
  uploaded_by_user?: User
  folder?: Folder | null
  tags: Tag[]
  created_at: string
  updated_at: string
}

export interface DocumentListItem {
  id: string
  filename: string
  original_filename: string
  mime_type: string
  file_size: number
  document_type: DocumentType
  status: DocumentStatus
  title: string | null
  folder_id: string | null
  uploaded_by: string
  tags: Tag[]
  created_at: string
  updated_at: string
}

export interface DocumentVersion {
  id: string
  document_id: string
  version_number: number
  filename: string
  file_size: number
  uploaded_by: string
  created_at: string
}

// Folders
export interface Folder {
  id: string
  name: string
  parent_id: string | null
  description: string | null
  created_by: string
  created_at: string
  updated_at: string
  children?: Folder[]
}

// Tags
export interface Tag {
  id: string
  name: string
  color: string | null
}

// Comments
export interface Comment {
  id: string
  document_id: string
  user_id: string
  user_name: string
  user_email: string
  parent_id: string | null
  content: string
  is_edited: boolean
  created_at: string
  updated_at: string
}

// Activity
export interface ActivityLogEntry {
  id: string
  user_id: string
  user_name?: string
  action: string
  resource_type: string
  resource_id: string | null
  details: Record<string, unknown> | null
  created_at: string
}

// Approvals
export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'cancelled'

export interface Approval {
  id: string
  document_id: string
  document_title?: string
  requested_by: string
  requester_name?: string
  assigned_to: string
  assignee_name?: string
  status: ApprovalStatus
  comment: string | null
  created_at: string
  resolved_at: string | null
}

// Notifications
export interface Notification {
  id: string
  user_id: string
  type: string
  title: string
  message: string
  resource_type: string | null
  resource_id: string | null
  is_read: boolean
  created_at: string
}

// Calendar
export type EventType = 'deadline' | 'reminder' | 'tax_date' | 'contract_expiry' | 'custom'
export type Recurrence = 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly'

export interface CalendarEvent {
  id: string
  title: string
  description: string | null
  event_type: EventType
  date: string
  recurrence: Recurrence
  document_id: string | null
  created_by: string
  is_completed: boolean
  created_at: string
  updated_at: string
}

// Contacts
export type ContactType = 'client' | 'vendor' | 'both'

export interface Contact {
  id: string
  type: ContactType
  company_name: string
  contact_name: string | null
  email: string | null
  phone: string | null
  address_line1: string | null
  address_line2: string | null
  city: string | null
  state: string | null
  zip_code: string | null
  country: string
  tax_id: string | null
  notes: string | null
  is_active: boolean
  created_by: string
  created_at: string
  updated_at: string
}

export interface ContactListItem {
  id: string
  type: ContactType
  company_name: string
  contact_name: string | null
  email: string | null
  phone: string | null
  city: string | null
  state: string | null
  is_active: boolean
  created_at: string
}

// Invoicing
export type InvoiceStatus = 'draft' | 'sent' | 'viewed' | 'paid' | 'overdue' | 'cancelled' | 'partially_paid'

export interface InvoiceLineItem {
  id: string
  invoice_id: string
  description: string
  quantity: number
  unit_price: number
  tax_rate: number | null
  total: number
}

export interface InvoicePayment {
  id: string
  invoice_id: string
  amount: number
  date: string
  payment_method: string | null
  reference: string | null
  notes: string | null
  recorded_by: string
  created_at: string
  updated_at: string
}

export interface Invoice {
  id: string
  invoice_number: string
  contact_id: string
  issue_date: string
  due_date: string
  status: InvoiceStatus
  subtotal: number
  tax_rate: number | null
  tax_amount: number | null
  discount_amount: number
  total: number
  currency: string
  notes: string | null
  payment_terms: string | null
  created_by: string
  contact: Contact | null
  line_items: InvoiceLineItem[]
  payments: InvoicePayment[]
  created_at: string
  updated_at: string
}

export interface InvoiceListItem {
  id: string
  invoice_number: string
  contact_id: string
  issue_date: string
  due_date: string
  status: InvoiceStatus
  total: number
  currency: string
  contact: Contact | null
  created_at: string
}

// Income
export type IncomeCategory = 'invoice_payment' | 'service' | 'product' | 'interest' | 'refund' | 'other'

export interface IncomeEntry {
  id: string
  contact_id: string | null
  invoice_id: string | null
  category: IncomeCategory
  description: string
  amount: number
  currency: string
  date: string
  payment_method: string | null
  reference: string | null
  notes: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface IncomeCategorySummary {
  category: string
  total: number
  count: number
}

export interface IncomeMonthSummary {
  year: number
  month: number
  total: number
  count: number
}

export interface IncomeSummary {
  total_amount: number
  income_count: number
  by_category: IncomeCategorySummary[]
  by_month: IncomeMonthSummary[]
}

// Recurring Transactions
export type RecurringType = 'expense' | 'income' | 'invoice'
export type Frequency = 'weekly' | 'biweekly' | 'monthly' | 'quarterly' | 'yearly'

export interface RecurringRule {
  id: string
  type: RecurringType
  name: string
  frequency: Frequency
  next_run_date: string
  end_date: string | null
  is_active: boolean
  template_data: Record<string, unknown>
  last_run_date: string | null
  run_count: number
  created_by: string
  created_at: string
  updated_at: string
}

// Budget Management
export type PeriodType = 'monthly' | 'quarterly' | 'yearly'

export interface Budget {
  id: string
  name: string
  category_id: string | null
  amount: number
  period_type: PeriodType
  year: number
  month: number | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface BudgetVsActual {
  budget_id: string
  budget_name: string
  category_id: string | null
  category_name: string
  budgeted_amount: number
  actual_amount: number
  remaining: number
  percentage_used: number
}

// Financial Reports
export interface CategoryAmount {
  category: string
  amount: number
}

export interface ProfitLossReport {
  date_from: string
  date_to: string
  total_income: number
  total_expenses: number
  net_profit: number
  income_by_category: CategoryAmount[]
  expenses_by_category: CategoryAmount[]
}

export interface TaxSummary {
  year: number
  taxable_income: number
  deductible_expenses: number
  tax_collected: number
  net_taxable: number
}

export interface CashFlowPeriod {
  period_label: string
  income: number
  expenses: number
  net: number
}

export interface CashFlowReport {
  date_from: string
  date_to: string
  periods: CashFlowPeriod[]
}

export interface AccountsSummary {
  total_receivable: number
  total_payable: number
  overdue_receivable: number
  net_position: number
}

// Accounting - Expenses
export type PaymentMethod = 'cash' | 'credit_card' | 'debit_card' | 'bank_transfer' | 'check' | 'other'
export type ExpenseStatus = 'draft' | 'pending_review' | 'approved' | 'rejected' | 'reimbursed'

export interface ExpenseCategory {
  id: string
  name: string
  color: string | null
  icon: string | null
  is_system: boolean
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface ExpenseLineItem {
  id: string
  expense_id: string
  description: string
  quantity: number | null
  unit_price: number | null
  total: number
}

export interface Expense {
  id: string
  document_id: string | null
  category_id: string | null
  user_id: string
  vendor_name: string | null
  description: string | null
  amount: number
  currency: string
  tax_amount: number | null
  date: string
  payment_method: PaymentMethod | null
  status: ExpenseStatus
  notes: string | null
  is_recurring: boolean
  ai_category_suggestion: string | null
  ai_confidence: number | null
  category: ExpenseCategory | null
  line_items: ExpenseLineItem[]
  created_at: string
  updated_at: string
}

export interface ExpenseListItem {
  id: string
  document_id: string | null
  category_id: string | null
  user_id: string
  vendor_name: string | null
  description: string | null
  amount: number
  currency: string
  date: string
  payment_method: PaymentMethod | null
  status: ExpenseStatus
  is_recurring: boolean
  category: ExpenseCategory | null
  created_at: string
}

export interface ExpenseCreate {
  vendor_name?: string
  description?: string
  amount: number
  currency?: string
  tax_amount?: number
  date: string
  payment_method?: PaymentMethod
  category_id?: string
  document_id?: string
  notes?: string
  is_recurring?: boolean
  line_items?: { description: string; quantity?: number; unit_price?: number; total: number }[]
}

export interface ExpenseUpdate {
  vendor_name?: string
  description?: string
  amount?: number
  currency?: string
  tax_amount?: number
  date?: string
  payment_method?: PaymentMethod
  status?: ExpenseStatus
  category_id?: string
  notes?: string
  is_recurring?: boolean
  line_items?: { description: string; quantity?: number; unit_price?: number; total: number }[]
}

export interface ExpenseFilters {
  search?: string
  category_id?: string
  status?: string
  payment_method?: string
  date_from?: string
  date_to?: string
  min_amount?: number
  max_amount?: number
  user_id?: string
  page?: number
  page_size?: number
}

export interface CategorySpend {
  category_id: string | null
  category_name: string
  category_color: string | null
  total: number
  count: number
}

export interface MonthlySpend {
  year: number
  month: number
  total: number
  count: number
}

export interface VendorSpend {
  vendor_name: string
  total: number
  count: number
}

export interface ExpenseSummary {
  total_amount: number
  expense_count: number
  average_amount: number
  by_category: CategorySpend[]
  by_month: MonthlySpend[]
  top_vendors: VendorSpend[]
}

export type ExpenseApprovalStatus = 'pending' | 'approved' | 'rejected'

export interface ExpenseApproval {
  id: string
  expense_id: string
  requested_by: string
  assigned_to: string
  status: ExpenseApprovalStatus
  comment: string | null
  created_at: string
  resolved_at: string | null
}

// SMTP Email Config
export interface SmtpConfig {
  id: string
  name: string
  host: string
  port: number
  username: string
  from_email: string
  from_name: string
  use_tls: boolean
  is_default: boolean
  created_at: string
  updated_at: string
}

// Gmail Integration
export interface GmailAccount {
  id: string
  email: string
  is_active: boolean
  last_sync_at: string | null
  created_at: string
}

export interface GmailScanResult {
  id: string
  message_id: string
  subject: string | null
  sender: string | null
  date: string | null
  snippet: string | null
  has_attachments: boolean
  is_processed: boolean
  matched_invoice_id: string | null
  matched_document_id: string | null
  created_at: string
}

// Plaid Banking
export interface PlaidConnection {
  id: string
  institution_name: string
  institution_id: string
  is_active: boolean
  last_sync_at: string | null
  accounts: { account_id: string; name: string; type: string; subtype: string; mask: string | null }[] | null
  created_at: string
}

export interface PlaidTransaction {
  id: string
  plaid_connection_id: string
  plaid_transaction_id: string
  account_id: string
  amount: number
  date: string
  name: string
  merchant_name: string | null
  category: string | null
  pending: boolean
  is_income: boolean
  matched_expense_id: string | null
  matched_income_id: string | null
  matched_invoice_id: string | null
  is_categorized: boolean
  created_at: string
}

// Stripe Payments
export type PaymentLinkStatus = 'pending' | 'completed' | 'expired' | 'cancelled'
export type SubscriptionInterval = 'monthly' | 'quarterly' | 'yearly'
export type SubscriptionStatus = 'active' | 'cancelled' | 'past_due' | 'incomplete'

export interface StripePaymentLink {
  id: string
  invoice_id: string
  checkout_session_id: string | null
  payment_intent_id: string | null
  payment_url: string
  amount: number
  currency: string
  status: PaymentLinkStatus
  expires_at: string | null
  paid_at: string | null
  created_at: string
}

export interface StripeSubscription {
  id: string
  contact_id: string
  stripe_subscription_id: string
  stripe_customer_id: string
  name: string
  amount: number
  currency: string
  interval: SubscriptionInterval
  status: SubscriptionStatus
  current_period_end: string | null
  created_at: string
}

export interface StripeConfig {
  is_configured: boolean
  publishable_key: string | null
}

// Twilio SMS
export interface SmsLog {
  id: string
  recipient: string
  message: string
  status: 'sent' | 'failed' | 'delivered'
  direction: string
  related_invoice_id: string | null
  twilio_sid: string | null
  created_at: string
}
