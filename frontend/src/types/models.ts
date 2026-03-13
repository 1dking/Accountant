// Auth
export interface User {
  id: string
  email: string
  full_name: string
  role: 'admin' | 'accountant' | 'viewer'
  is_active: boolean
  created_at: string
  cashbook_access?: 'personal' | 'org'
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
  is_starred: boolean
  is_trashed: boolean
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
export type EventType = 'deadline' | 'reminder' | 'tax_date' | 'contract_expiry' | 'meeting' | 'custom'
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
  assigned_user_id: string | null
  dnd_enabled: boolean
  lead_source: string | null
  job_title: string | null
  custom_fields_data: Record<string, unknown> | null
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
  assigned_user_id: string | null
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

// Estimates
export type EstimateStatus = 'draft' | 'sent' | 'accepted' | 'rejected' | 'expired' | 'converted'

export interface EstimateLineItem {
  id: string
  estimate_id: string
  description: string
  quantity: number
  unit_price: number
  tax_rate: number | null
  total: number
}

export interface Estimate {
  id: string
  estimate_number: string
  contact_id: string
  issue_date: string
  expiry_date: string
  status: EstimateStatus
  subtotal: number
  tax_rate: number | null
  tax_amount: number | null
  discount_amount: number
  total: number
  currency: string
  notes: string | null
  converted_invoice_id: string | null
  created_by: string
  contact: Contact | null
  line_items: EstimateLineItem[]
  created_at: string
  updated_at: string
}

export interface EstimateListItem {
  id: string
  estimate_number: string
  contact_id: string
  issue_date: string
  expiry_date: string
  status: EstimateStatus
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

export interface AgingBucketTotals {
  current: number
  days_1_30: number
  days_31_60: number
  days_61_90: number
  days_90_plus: number
  total: number
}

export interface AgingBucket extends AgingBucketTotals {
  name: string
}

export interface AgingReport {
  as_of_date: string
  buckets: AgingBucket[]
  grand_totals: AgingBucketTotals
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
  body_text: string | null
  has_attachments: boolean
  is_processed: boolean
  is_skipped: boolean
  matched_invoice_id: string | null
  matched_document_id: string | null
  matched_expense_id: string | null
  matched_income_id: string | null
  created_at: string
}

export interface EmailParsedData {
  vendor_name: string | null
  amount: string | null
  currency: string
  date: string | null
  description: string | null
  category_suggestion: string | null
  record_type: 'expense' | 'income'
  attachments: { filename: string; mimeType: string; size: number }[]
  body_html: string | null
  body_text: string | null
}

export interface EmailImportRequest {
  record_type: 'expense' | 'income'
  vendor_name?: string | null
  description?: string | null
  amount?: number | null
  currency?: string
  date?: string | null
  category_id?: string | null
  income_category?: string | null
  notes?: string | null
  account_id?: string | null
  is_recurring?: boolean
  recurring_frequency?: string | null
  recurring_next_date?: string | null
}

// Categorization Rules
export type CategorizationMatchField = 'name' | 'merchant_name' | 'category'
export type CategorizationMatchType = 'contains' | 'exact' | 'starts_with' | 'regex'

export interface CategorizationRule {
  id: string
  name: string
  match_field: CategorizationMatchField
  match_type: CategorizationMatchType
  match_value: string
  assign_category_id: string
  priority: number
  is_active: boolean
  created_by: string
  created_at: string
  updated_at: string
}

export interface CategorizationRuleCreate {
  name: string
  match_field: CategorizationMatchField
  match_type: CategorizationMatchType
  match_value: string
  assign_category_id: string
  priority?: number
  is_active?: boolean
}

export interface CategorizationRuleUpdate {
  name?: string
  match_field?: CategorizationMatchField
  match_type?: CategorizationMatchType
  match_value?: string
  assign_category_id?: string
  priority?: number
  is_active?: boolean
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

// Payment Reminders
export type ReminderChannel = 'email' | 'sms' | 'both'
export type ReminderStatus = 'sent' | 'failed' | 'skipped'

export interface ReminderRule {
  id: string
  name: string
  days_offset: number
  channel: ReminderChannel
  email_subject: string | null
  email_body: string | null
  sms_body: string | null
  is_active: boolean
  created_by: string
  created_at: string
  updated_at: string
}

export interface PaymentReminder {
  id: string
  invoice_id: string
  contact_id: string
  reminder_rule_id: string | null
  reminder_type: string
  channel: ReminderChannel
  status: ReminderStatus
  sent_at: string | null
  error_message: string | null
  created_at: string
}

// Accounting Periods
export type PeriodStatus = 'open' | 'closed'

export interface AccountingPeriod {
  id: string
  year: number
  month: number
  status: PeriodStatus
  closed_by: string | null
  closed_at: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

// Credit Notes
export type CreditNoteStatus = 'draft' | 'issued' | 'applied'

export interface CreditNote {
  id: string
  credit_note_number: string
  invoice_id: string
  contact_id: string
  amount: number
  reason: string | null
  status: CreditNoteStatus
  issue_date: string
  applied_at: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface CreditNoteListItem {
  id: string
  credit_note_number: string
  invoice_id: string
  contact_id: string
  amount: number
  reason: string | null
  status: CreditNoteStatus
  issue_date: string
  created_at: string
}

export interface ContactCreditBalance {
  contact_id: string
  total_issued: number
  total_applied: number
  available_balance: number
}

// Cashbook
export type AccountType = 'bank' | 'credit_card' | 'cash' | 'savings' | 'loan' | 'paypal' | 'other'
export type EntryType = 'income' | 'expense'
export type CategoryTypeEnum = 'income' | 'expense' | 'both'

export interface TransactionCategory {
  id: string
  name: string
  category_type: CategoryTypeEnum
  color: string | null
  icon: string | null
  is_system: boolean
  display_order: number
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface PaymentAccount {
  id: string
  user_id: string
  name: string
  account_type: AccountType
  currency: string
  opening_balance: number
  opening_balance_date: string
  default_tax_rate_id: string | null
  is_active: boolean
  current_balance: number | null
  created_at: string
  updated_at: string
}

export type EntryStatusType = 'pending' | 'cleared' | 'reconciled' | 'voided'

export interface CashbookEntry {
  id: string
  account_id: string
  entry_type: EntryType
  date: string
  description: string
  total_amount: number
  tax_amount: number | null
  tax_rate_used: number | null
  tax_override: boolean
  category_id: string | null
  contact_id: string | null
  document_id: string | null
  source: string | null
  source_id: string | null
  notes: string | null
  user_id: string
  status: EntryStatusType
  is_deleted: boolean
  split_parent_id: string | null
  bank_balance: number | null
  category: TransactionCategory | null
  account_name: string | null
  created_at: string
  updated_at: string
}

export interface CashbookEntryCreate {
  account_id: string
  entry_type: EntryType
  date: string
  description: string
  total_amount: number
  tax_amount?: number
  tax_override?: boolean
  category_id?: string
  contact_id?: string
  document_id?: string
  notes?: string
}

export interface CashbookEntryUpdate {
  account_id?: string
  entry_type?: EntryType
  date?: string
  description?: string
  total_amount?: number
  tax_amount?: number
  tax_override?: boolean
  category_id?: string
  contact_id?: string
  document_id?: string
  notes?: string
  status?: EntryStatusType
}

export interface CashbookEntryFilters {
  account_id?: string
  entry_type?: EntryType
  category_id?: string
  status?: EntryStatusType
  date_from?: string
  date_to?: string
  search?: string
  include_deleted?: boolean
  page?: number
  page_size?: number
}

export interface CashbookCategoryTotal {
  category_id: string | null
  category_name: string
  category_type: CategoryTypeEnum | null
  entry_type: EntryType
  total_amount: number
  total_tax: number
  count: number
}

export interface CashbookSummary {
  opening_balance: number
  closing_balance: number
  total_income: number
  total_expenses: number
  net_change: number
  total_tax_collected: number
  total_tax_paid: number
  category_totals: CashbookCategoryTotal[]
  period_start: string
  period_end: string
}

export interface ParsedExcelRow {
  row_number: number
  sheet_name: string
  date: string | null
  description: string
  total_amount: number
  category_name: string | null
  entry_type: EntryType
  tax_amount: number | null
  errors: string[]
}

export interface ImportPreview {
  rows: ParsedExcelRow[]
  total_rows: number
  valid_rows: number
  error_rows: number
  sheets_found: string[]
}

// Meetings
export type MeetingStatus = 'scheduled' | 'in_progress' | 'completed' | 'cancelled'
export type ParticipantRole = 'host' | 'participant'
export type RecordingStatus = 'recording' | 'processing' | 'available' | 'failed'

export interface MeetingParticipant {
  id: string
  meeting_id: string
  user_id: string | null
  contact_id: string | null
  guest_name: string | null
  guest_email: string | null
  role: ParticipantRole
  join_token: string | null
  joined_at: string | null
  left_at: string | null
}

export interface MeetingRecording {
  id: string
  meeting_id: string
  status: RecordingStatus
  duration_seconds: number | null
  file_size: number | null
  storage_path: string | null
  mime_type: string
  started_by: string
  created_at: string
}

export interface Meeting {
  id: string
  title: string
  description: string | null
  status: MeetingStatus
  scheduled_start: string
  scheduled_end: string | null
  actual_start: string | null
  actual_end: string | null
  livekit_room_name: string
  record_meeting: boolean
  created_by: string
  contact_id: string | null
  calendar_event_id: string | null
  participants: MeetingParticipant[]
  recordings: MeetingRecording[]
  created_at: string
  updated_at: string
}

export interface MeetingListItem {
  id: string
  title: string
  status: MeetingStatus
  scheduled_start: string
  scheduled_end: string | null
  contact_id: string | null
  record_meeting: boolean
  participant_count: number
  created_at: string
}

// Office Suite
export type DocType = 'document' | 'spreadsheet' | 'presentation'
export type OfficePermission = 'view' | 'comment' | 'edit'

export interface OfficeDocument {
  id: string
  title: string
  doc_type: DocType
  created_by: string
  folder_id: string | null
  content_preview: string | null
  thumbnail_path: string | null
  is_starred: boolean
  is_trashed: boolean
  content_json: Record<string, unknown> | null
  last_accessed_at: string | null
  collaborators: OfficeCollaborator[]
  created_at: string
  updated_at: string
}

export interface OfficeDocListItem {
  id: string
  title: string
  doc_type: DocType
  created_by: string
  folder_id: string | null
  is_starred: boolean
  last_accessed_at: string | null
  updated_at: string
}

export interface OfficeCollaborator {
  id: string
  user_id: string
  user_email: string
  user_name: string
  permission: OfficePermission
}

// Reconciliation
export type MatchStatus = 'pending' | 'confirmed' | 'rejected'

export interface MatchResponse {
  id: string
  receipt_id: string
  transaction_id: string
  match_confidence: number
  match_reason: string | null
  status: MatchStatus
  confirmed_by: string | null
  confirmed_at: string | null
  receipt_vendor: string | null
  receipt_amount: number
  receipt_date: string
  transaction_description: string
  transaction_amount: number
  transaction_date: string
  created_at: string
  updated_at: string
}

export interface ReconciliationSummary {
  pending_matches: number
  confirmed_matches: number
  unmatched_receipts: number
  unmatched_transactions: number
  total_matched_amount: number
}

// Unified Inbox
export type MessageType = 'email' | 'sms'
export type MessageDirection = 'inbound' | 'outbound'

export interface UnifiedMessage {
  id: string
  user_id: string
  contact_id: string | null
  message_type: MessageType
  direction: MessageDirection
  subject: string | null
  body: string | null
  recipient: string | null
  sender: string | null
  is_read: boolean
  thread_id: string | null
  source_type: string | null
  source_id: string | null
  created_at: string
  updated_at: string
}

export interface UnreadCount {
  total: number
  email: number
  sms: number
}

// Quarterly Tax Reports
export interface QuarterlyBreakdown {
  quarter: number
  quarter_label: string
  income: number
  expenses: number
  net: number
  tax_collected: number
  estimated_tax: number
  deadline: string
  is_overdue: boolean
}

export interface QuarterlyTaxReport {
  year: number
  tax_rate: number
  quarters: QuarterlyBreakdown[]
  annual_total_income: number
  annual_total_expenses: number
  annual_net: number
  annual_tax_collected: number
  annual_estimated_tax: number
  income_by_category: CategoryAmount[]
  expenses_by_category: CategoryAmount[]
}

export interface YearOverYearComparison {
  current_year: number
  previous_year: number
  current_income: number
  previous_income: number
  income_change_pct: number | null
  current_expenses: number
  previous_expenses: number
  expenses_change_pct: number | null
  current_net: number
  previous_net: number
}

export interface TaxDeadline {
  quarter: number
  quarter_label: string
  deadline_date: string
  description: string
  is_past: boolean
  days_until: number | null
}

// Contact Tags
export interface ContactTag {
  id: string
  contact_id: string
  tag_name: string
  created_by: string
  created_at: string
}

// Contact Activities
export interface ContactActivity {
  id: string
  contact_id: string
  activity_type: string
  title: string
  description: string | null
  reference_type: string | null
  reference_id: string | null
  created_by: string | null
  created_at: string
}

// File Share
export interface FileShareItem {
  id: string
  file_id: string
  contact_id: string
  permission: 'view' | 'download'
  shared_by: string
  shared_at: string
}

// User Invitation
export interface UserInvitation {
  id: string
  email: string
  role: string
  status: 'pending' | 'accepted' | 'expired'
  invited_by: string
  contact_id: string | null
  expires_at: string
  accepted_at: string | null
  created_at: string
}

// Duplicate Group
export interface DuplicateGroup {
  field: string
  value: string
  contact_ids: string[]
}

// Workflows
export interface Workflow {
  id: string
  name: string
  description?: string
  trigger_type: string
  trigger_config_json?: string
  is_active: boolean
  created_by: string
  created_at: string
  updated_at: string
  steps?: WorkflowStep[]
}

export interface WorkflowStep {
  id: string
  workflow_id: string
  step_order: number
  action_type: string
  action_config_json?: string
  condition_json?: string
  wait_duration_seconds?: number
}

export interface WorkflowExecution {
  id: string
  workflow_id: string
  contact_id?: string
  status: string
  started_at: string
  completed_at?: string
  error_message?: string
  steps?: WorkflowExecutionStep[]
}

export interface WorkflowExecutionStep {
  id: string
  execution_id: string
  step_id?: string
  status: string
  started_at: string
  completed_at?: string
  result_json?: string
  error_message?: string
}

export interface WorkflowListItem {
  id: string
  name: string
  trigger_type: string
  is_active: boolean
  created_at: string
  execution_count: number
  last_run_at?: string
}

export interface WorkflowTemplate {
  name: string
  description: string
  trigger_type: string
  trigger_config_json: string
  steps: Omit<WorkflowStep, 'id' | 'workflow_id'>[]
}

// Forms
export interface FormDef {
  id: string
  name: string
  description?: string
  fields_json: string
  thank_you_type: string
  thank_you_config_json?: string
  style_json?: string
  is_active: boolean
  created_by: string
  created_at: string
}

export interface FormListItem {
  id: string
  name: string
  is_active: boolean
  submission_count: number
  last_submission_at?: string
  created_at: string
}

export interface FormSubmission {
  id: string
  form_id: string
  contact_id?: string
  data_json: string
  submitted_at: string
}

// Communication
export interface TwilioPhoneNumber {
  id: string
  phone_number: string
  assigned_user_id?: string
  friendly_name?: string
  capabilities_json?: string
}

export interface CallLogEntry {
  id: string
  user_id?: string
  contact_id?: string
  direction: string
  from_number: string
  to_number: string
  duration_seconds: number
  recording_url?: string
  status: string
  notes?: string
  outcome?: string
  created_at: string
}

export interface SmsMessageEntry {
  id: string
  user_id?: string
  contact_id?: string
  direction: string
  from_number: string
  to_number: string
  body: string
  status: string
  created_at: string
}

export interface ChatSession {
  id: string
  contact_id?: string
  visitor_name?: string
  visitor_email?: string
  status: string
  assigned_user_id?: string
  created_at: string
}

export interface ChatMessage {
  id: string
  session_id: string
  direction: string
  message: string
  created_at: string
}

// Pages (AI Web Builder)
export interface PageItem {
  id: string
  title: string
  slug: string
  status: string
  is_homepage: boolean
  custom_domain?: string
  created_at: string
  updated_at: string
}

export interface PageDetail {
  id: string
  title: string
  slug: string
  description?: string
  status: string
  html_content?: string
  css_content?: string
  js_content?: string
  sections_json?: string
  meta_title?: string
  meta_description?: string
  og_image_url?: string
  custom_domain?: string
  is_homepage: boolean
  favicon_url?: string
  custom_head_html?: string
  style_preset?: string
  primary_color?: string
  font_family?: string
  created_by: string
  created_at: string
  updated_at: string
}

export interface PageVersion {
  id: string
  page_id: string
  version_number: number
  change_summary?: string
  created_by: string
  created_at: string
}

export interface PageAnalyticsSummary {
  total_views: number
  unique_visitors: number
  total_submissions: number
  conversion_rate: number
  views_by_day: Record<string, unknown>[]
}

export interface StylePreset {
  id: string
  name: string
  description: string
  preview_colors: { primary: string; bg: string; text: string }
}

export interface SectionTemplate {
  id: string
  type: string
  name: string
  description: string
  default_html: string
}

// Scheduling
export interface SchedulingCalendar {
  id: string
  name: string
  slug: string
  description?: string
  calendar_type: string
  duration_minutes: number
  buffer_minutes: number
  max_advance_days: number
  min_notice_hours: number
  availability_json?: string
  timezone: string
  is_active: boolean
  confirmation_message?: string
  reminder_enabled: boolean
  google_calendar_id?: string
  google_sync_enabled: boolean
  created_by: string
  created_at: string
  updated_at: string
}

export interface CalendarMember {
  id: string
  calendar_id: string
  user_id: string
  is_active: boolean
  priority: number
  created_at: string
}

export interface CalendarBooking {
  id: string
  calendar_id: string
  contact_id?: string
  assigned_user_id?: string
  guest_name: string
  guest_email: string
  guest_phone?: string
  guest_notes?: string
  start_time: string
  end_time: string
  status: string
  cancellation_reason?: string
  meeting_type?: string
  meeting_location?: string
  reschedule_token?: string
  cancel_token?: string
  google_event_id?: string
  confirmation_sent: boolean
  created_at: string
  updated_at: string
}

export interface AvailableSlot {
  start: string
  end: string
}

// Branding
export interface BrandingSettings {
  id: string
  logo_url?: string
  logo_dark_url?: string
  favicon_url?: string
  primary_color: string
  secondary_color: string
  accent_color: string
  font_heading: string
  font_body: string
  border_radius: string
  custom_css?: string
  email_header_html?: string
  email_footer_html?: string
  portal_welcome_message?: string
  booking_page_header?: string
  org_slug?: string
  updated_by: string
  created_at: string
  updated_at: string
}
