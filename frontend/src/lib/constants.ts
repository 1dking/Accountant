import i18n from '@/i18n'

export const DOCUMENT_TYPES = [
  { value: 'invoice', label: i18n.t('ui:constants.invoice') },
  { value: 'receipt', label: i18n.t('ui:constants.receipt') },
  { value: 'contract', label: i18n.t('ui:constants.contract') },
  { value: 'tax_form', label: i18n.t('ui:constants.taxForm') },
  { value: 'report', label: i18n.t('ui:constants.report') },
  { value: 'statement', label: i18n.t('ui:constants.statement') },
  { value: 'other', label: i18n.t('ui:constants.other') },
] as const

export const DOCUMENT_STATUSES = [
  { value: 'draft', label: i18n.t('ui:constants.draft'), color: 'bg-gray-100 text-gray-700' },
  { value: 'pending_review', label: i18n.t('ui:constants.pendingReview'), color: 'bg-yellow-100 text-yellow-700' },
  { value: 'approved', label: i18n.t('ui:constants.approved'), color: 'bg-green-100 text-green-700' },
  { value: 'filed', label: i18n.t('ui:constants.filed'), color: 'bg-blue-100 text-blue-700' },
  { value: 'archived', label: i18n.t('ui:constants.archived'), color: 'bg-gray-200 text-gray-500' },
] as const

export const EVENT_TYPES = [
  { value: 'deadline', label: i18n.t('ui:constants.deadline'), color: '#ef4444' },
  { value: 'reminder', label: i18n.t('ui:constants.reminder'), color: '#3b82f6' },
  { value: 'tax_date', label: i18n.t('ui:constants.taxDate'), color: '#f59e0b' },
  { value: 'contract_expiry', label: i18n.t('ui:constants.contractExpiry'), color: '#8b5cf6' },
  { value: 'meeting', label: i18n.t('ui:constants.meeting'), color: '#2563eb' },
  { value: 'custom', label: i18n.t('ui:constants.custom'), color: '#6b7280' },
] as const

export const ROLES = [
  { value: 'admin', label: i18n.t('ui:constants.admin'), description: i18n.t('ui:constants.fullAccessToAllFeatures') },
  { value: 'accountant', label: i18n.t('ui:constants.accountant'), description: i18n.t('ui:constants.canUploadEditAndManage') },
  { value: 'viewer', label: i18n.t('ui:constants.viewer'), description: i18n.t('ui:constants.readOnlyAccessToDocuments') },
] as const

export const ACCEPTED_FILE_TYPES = {
  // Documents
  'application/pdf': ['.pdf'],
  'application/msword': ['.doc'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/rtf': ['.rtf'],
  // Spreadsheets
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
  // Presentations
  'application/vnd.ms-powerpoint': ['.ppt'],
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
  // Images
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/png': ['.png'],
  'image/gif': ['.gif'],
  'image/webp': ['.webp'],
  'image/tiff': ['.tiff', '.tif'],
  'image/svg+xml': ['.svg'],
  'image/bmp': ['.bmp'],
  'image/heic': ['.heic'],
  'image/heif': ['.heif'],
  // Text / data
  'text/plain': ['.txt'],
  'text/csv': ['.csv'],
  'application/json': ['.json'],
  'application/xml': ['.xml'],
  'text/xml': ['.xml'],
  // Archives
  'application/zip': ['.zip'],
  'application/x-zip-compressed': ['.zip'],
  'application/gzip': ['.gz'],
  'application/x-rar-compressed': ['.rar'],
  'application/x-7z-compressed': ['.7z'],
  // Video
  'video/mp4': ['.mp4'],
  'video/webm': ['.webm'],
  'video/quicktime': ['.mov'],
  'video/x-msvideo': ['.avi'],
  // Audio
  'audio/mpeg': ['.mp3'],
  'audio/wav': ['.wav'],
  'audio/ogg': ['.ogg'],
  'audio/webm': ['.weba'],
  'audio/mp4': ['.m4a'],
}

export const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB

export const EXPENSE_STATUSES = [
  { value: 'draft', label: i18n.t('ui:constants.draft'), color: 'bg-gray-100 text-gray-700' },
  { value: 'pending_review', label: i18n.t('ui:constants.pendingReview'), color: 'bg-yellow-100 text-yellow-700' },
  { value: 'approved', label: i18n.t('ui:constants.approved'), color: 'bg-green-100 text-green-700' },
  { value: 'rejected', label: i18n.t('ui:constants.rejected'), color: 'bg-red-100 text-red-700' },
  { value: 'reimbursed', label: i18n.t('ui:constants.reimbursed'), color: 'bg-blue-100 text-blue-700' },
] as const

export const PAYMENT_METHODS = [
  { value: 'cash', label: i18n.t('ui:constants.cash') },
  { value: 'credit_card', label: i18n.t('ui:constants.creditCard') },
  { value: 'debit_card', label: i18n.t('ui:constants.debitCard') },
  { value: 'bank_transfer', label: i18n.t('ui:constants.bankTransfer') },
  { value: 'check', label: i18n.t('ui:constants.check') },
  { value: 'other', label: i18n.t('ui:constants.other') },
] as const

export const INVOICE_STATUSES = [
  { value: 'draft', label: i18n.t('ui:constants.draft'), color: 'bg-gray-100 text-gray-700' },
  { value: 'sent', label: i18n.t('ui:constants.sent'), color: 'bg-blue-100 text-blue-700' },
  { value: 'viewed', label: i18n.t('ui:constants.viewed'), color: 'bg-cyan-100 text-cyan-700' },
  { value: 'partially_paid', label: i18n.t('ui:constants.partiallyPaid'), color: 'bg-yellow-100 text-yellow-700' },
  { value: 'paid', label: i18n.t('ui:constants.paid'), color: 'bg-green-100 text-green-700' },
  { value: 'overdue', label: i18n.t('ui:constants.overdue'), color: 'bg-red-100 text-red-700' },
  { value: 'cancelled', label: i18n.t('ui:constants.cancelled'), color: 'bg-gray-200 text-gray-500' },
] as const

export const ESTIMATE_STATUSES = [
  { value: 'draft', label: i18n.t('ui:constants.draft'), color: 'bg-gray-100 text-gray-700' },
  { value: 'sent', label: i18n.t('ui:constants.sent'), color: 'bg-blue-100 text-blue-700' },
  { value: 'accepted', label: i18n.t('ui:constants.accepted'), color: 'bg-green-100 text-green-700' },
  { value: 'rejected', label: i18n.t('ui:constants.rejected'), color: 'bg-red-100 text-red-700' },
  { value: 'expired', label: i18n.t('ui:constants.expired'), color: 'bg-yellow-100 text-yellow-700' },
  { value: 'converted', label: i18n.t('ui:constants.converted'), color: 'bg-purple-100 text-purple-700' },
] as const

export const INCOME_CATEGORIES = [
  { value: 'invoice_payment', label: i18n.t('ui:constants.invoicePayment') },
  { value: 'service', label: i18n.t('ui:constants.service') },
  { value: 'product', label: i18n.t('ui:constants.product') },
  { value: 'interest', label: i18n.t('ui:constants.interest') },
  { value: 'refund', label: i18n.t('ui:constants.refund') },
  { value: 'other', label: i18n.t('ui:constants.other') },
] as const

export const RECURRING_TYPES = [
  { value: 'expense', label: i18n.t('ui:constants.expense') },
  { value: 'income', label: i18n.t('ui:constants.income') },
  { value: 'invoice', label: i18n.t('ui:constants.invoice') },
] as const

export const FREQUENCIES = [
  { value: 'weekly', label: i18n.t('ui:constants.weekly') },
  { value: 'biweekly', label: i18n.t('ui:constants.biWeekly') },
  { value: 'monthly', label: i18n.t('ui:constants.monthly') },
  { value: 'quarterly', label: i18n.t('ui:constants.quarterly') },
  { value: 'yearly', label: i18n.t('ui:constants.yearly') },
] as const

export const PERIOD_TYPES = [
  { value: 'monthly', label: i18n.t('ui:constants.monthly') },
  { value: 'quarterly', label: i18n.t('ui:constants.quarterly') },
  { value: 'yearly', label: i18n.t('ui:constants.yearly') },
] as const

export const ACCOUNT_TYPES = [
  { value: 'bank', label: i18n.t('ui:constants.checking') },
  { value: 'savings', label: i18n.t('ui:constants.savings') },
  { value: 'credit_card', label: i18n.t('ui:constants.creditCard') },
  { value: 'cash', label: i18n.t('ui:constants.cash') },
  { value: 'paypal', label: 'PayPal' },
  { value: 'loan', label: i18n.t('ui:constants.loan') },
  { value: 'other', label: i18n.t('ui:constants.other') },
] as const

export const ENTRY_TYPES = [
  { value: 'income', label: i18n.t('ui:constants.income'), color: 'bg-green-100 text-green-700' },
  { value: 'expense', label: i18n.t('ui:constants.expense'), color: 'bg-red-100 text-red-700' },
] as const
