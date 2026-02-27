export const DOCUMENT_TYPES = [
  { value: 'invoice', label: 'Invoice' },
  { value: 'receipt', label: 'Receipt' },
  { value: 'contract', label: 'Contract' },
  { value: 'tax_form', label: 'Tax Form' },
  { value: 'report', label: 'Report' },
  { value: 'statement', label: 'Statement' },
  { value: 'other', label: 'Other' },
] as const

export const DOCUMENT_STATUSES = [
  { value: 'draft', label: 'Draft', color: 'bg-gray-100 text-gray-700' },
  { value: 'pending_review', label: 'Pending Review', color: 'bg-yellow-100 text-yellow-700' },
  { value: 'approved', label: 'Approved', color: 'bg-green-100 text-green-700' },
  { value: 'filed', label: 'Filed', color: 'bg-blue-100 text-blue-700' },
  { value: 'archived', label: 'Archived', color: 'bg-gray-200 text-gray-500' },
] as const

export const EVENT_TYPES = [
  { value: 'deadline', label: 'Deadline', color: '#ef4444' },
  { value: 'reminder', label: 'Reminder', color: '#3b82f6' },
  { value: 'tax_date', label: 'Tax Date', color: '#f59e0b' },
  { value: 'contract_expiry', label: 'Contract Expiry', color: '#8b5cf6' },
  { value: 'custom', label: 'Custom', color: '#6b7280' },
] as const

export const ROLES = [
  { value: 'admin', label: 'Admin', description: 'Full access to all features' },
  { value: 'accountant', label: 'Accountant', description: 'Can upload, edit, and manage documents' },
  { value: 'viewer', label: 'Viewer', description: 'Read-only access to documents' },
] as const

export const ACCEPTED_FILE_TYPES = {
  'application/pdf': ['.pdf'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/webp': ['.webp'],
  'application/msword': ['.doc'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  'text/csv': ['.csv'],
  'text/plain': ['.txt'],
}

export const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB

export const EXPENSE_STATUSES = [
  { value: 'draft', label: 'Draft', color: 'bg-gray-100 text-gray-700' },
  { value: 'pending_review', label: 'Pending Review', color: 'bg-yellow-100 text-yellow-700' },
  { value: 'approved', label: 'Approved', color: 'bg-green-100 text-green-700' },
  { value: 'rejected', label: 'Rejected', color: 'bg-red-100 text-red-700' },
  { value: 'reimbursed', label: 'Reimbursed', color: 'bg-blue-100 text-blue-700' },
] as const

export const PAYMENT_METHODS = [
  { value: 'cash', label: 'Cash' },
  { value: 'credit_card', label: 'Credit Card' },
  { value: 'debit_card', label: 'Debit Card' },
  { value: 'bank_transfer', label: 'Bank Transfer' },
  { value: 'check', label: 'Check' },
  { value: 'other', label: 'Other' },
] as const

export const INVOICE_STATUSES = [
  { value: 'draft', label: 'Draft', color: 'bg-gray-100 text-gray-700' },
  { value: 'sent', label: 'Sent', color: 'bg-blue-100 text-blue-700' },
  { value: 'viewed', label: 'Viewed', color: 'bg-cyan-100 text-cyan-700' },
  { value: 'partially_paid', label: 'Partially Paid', color: 'bg-yellow-100 text-yellow-700' },
  { value: 'paid', label: 'Paid', color: 'bg-green-100 text-green-700' },
  { value: 'overdue', label: 'Overdue', color: 'bg-red-100 text-red-700' },
  { value: 'cancelled', label: 'Cancelled', color: 'bg-gray-200 text-gray-500' },
] as const

export const INCOME_CATEGORIES = [
  { value: 'invoice_payment', label: 'Invoice Payment' },
  { value: 'service', label: 'Service' },
  { value: 'product', label: 'Product' },
  { value: 'interest', label: 'Interest' },
  { value: 'refund', label: 'Refund' },
  { value: 'other', label: 'Other' },
] as const

export const RECURRING_TYPES = [
  { value: 'expense', label: 'Expense' },
  { value: 'income', label: 'Income' },
  { value: 'invoice', label: 'Invoice' },
] as const

export const FREQUENCIES = [
  { value: 'weekly', label: 'Weekly' },
  { value: 'biweekly', label: 'Bi-Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'yearly', label: 'Yearly' },
] as const

export const PERIOD_TYPES = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'yearly', label: 'Yearly' },
] as const
