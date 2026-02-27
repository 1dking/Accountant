import { api } from './client'
import type { ApiResponse } from '@/types/api'
import type {
  SmtpConfig,
  GmailAccount,
  GmailScanResult,
  PlaidConnection,
  PlaidTransaction,
  CategorizationRule,
  CategorizationRuleCreate,
  CategorizationRuleUpdate,
  StripePaymentLink,
  StripeSubscription,
  StripeConfig,
  SmsLog,
} from '@/types/models'

// ---------------------------------------------------------------------------
// SMTP Email
// ---------------------------------------------------------------------------

export async function listSmtpConfigs() {
  return api.get<{ data: SmtpConfig[] }>('/email/configs')
}

export async function createSmtpConfig(data: {
  name: string
  host: string
  port: number
  username: string
  password: string
  from_email: string
  from_name: string
  use_tls?: boolean
  is_default?: boolean
}) {
  return api.post<ApiResponse<SmtpConfig>>('/email/configs', data)
}

export async function updateSmtpConfig(id: string, data: Partial<{
  name: string
  host: string
  port: number
  username: string
  password: string
  from_email: string
  from_name: string
  use_tls: boolean
  is_default: boolean
}>) {
  return api.put<ApiResponse<SmtpConfig>>(`/email/configs/${id}`, data)
}

export async function deleteSmtpConfig(id: string) {
  return api.delete<ApiResponse<{ detail: string }>>(`/email/configs/${id}`)
}

export async function sendTestEmail(smtp_config_id: string, to_email: string) {
  return api.post<ApiResponse<{ detail: string }>>('/email/test', { smtp_config_id, to_email })
}

export async function sendInvoiceEmail(data: {
  invoice_id: string
  smtp_config_id?: string
  recipient_email?: string
  subject?: string
  message?: string
}) {
  return api.post<ApiResponse<{ detail: string }>>('/email/send-invoice', data)
}

export async function sendPaymentReminderEmail(data: {
  invoice_id: string
  smtp_config_id?: string
}) {
  return api.post<ApiResponse<{ detail: string }>>('/email/send-reminder', data)
}

// ---------------------------------------------------------------------------
// Gmail
// ---------------------------------------------------------------------------

export async function connectGmail() {
  return api.get<ApiResponse<{ auth_url: string }>>('/integrations/gmail/connect')
}

export async function listGmailAccounts() {
  return api.get<{ data: GmailAccount[] }>('/integrations/gmail/accounts')
}

export async function disconnectGmailAccount(accountId: string) {
  return api.delete<ApiResponse<{ detail: string }>>(`/integrations/gmail/accounts/${accountId}`)
}

export async function scanGmailEmails(data: {
  gmail_account_id: string
  query?: string
  max_results?: number
}) {
  return api.post<{ data: GmailScanResult[] }>('/integrations/gmail/scan', data)
}

export async function listGmailScanResults(gmailAccountId?: string) {
  const query = gmailAccountId ? `?gmail_account_id=${gmailAccountId}` : ''
  return api.get<{ data: GmailScanResult[] }>(`/integrations/gmail/results${query}`)
}

export async function importGmailAttachment(resultId: string) {
  return api.post<ApiResponse<{ document_id: string }>>(`/integrations/gmail/results/${resultId}/import`)
}

export async function sendEmailViaGmail(data: {
  gmail_account_id: string
  to: string
  subject: string
  body_html: string
}) {
  return api.post<ApiResponse<{ detail: string }>>('/integrations/gmail/send', data)
}

// ---------------------------------------------------------------------------
// Plaid Banking
// ---------------------------------------------------------------------------

export async function createPlaidLinkToken() {
  return api.post<ApiResponse<{ link_token: string }>>('/integrations/plaid/link-token')
}

export async function exchangePlaidToken(data: {
  public_token: string
  institution_name: string
  institution_id: string
}) {
  return api.post<ApiResponse<PlaidConnection>>('/integrations/plaid/exchange-token', data)
}

export async function listPlaidConnections() {
  return api.get<{ data: PlaidConnection[] }>('/integrations/plaid/connections')
}

export async function deletePlaidConnection(connectionId: string) {
  return api.delete<ApiResponse<{ detail: string }>>(`/integrations/plaid/connections/${connectionId}`)
}

export async function syncPlaidTransactions(connectionId: string) {
  return api.post<ApiResponse<{ detail: string }>>(`/integrations/plaid/connections/${connectionId}/sync`)
}

export async function listPlaidTransactions(filters: {
  connection_id?: string
  is_categorized?: boolean
  is_income?: boolean
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
} = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== null) params.set(key, String(val))
  })
  const query = params.toString()
  return api.get<{ data: PlaidTransaction[]; meta: { total: number; page: number; page_size: number } }>(
    `/integrations/plaid/transactions${query ? `?${query}` : ''}`
  )
}

export async function categorizePlaidTransaction(txnId: string, data: {
  as_type: 'expense' | 'income' | 'ignore'
  expense_category_id?: string
  description?: string
}) {
  return api.post<ApiResponse<PlaidTransaction>>(`/integrations/plaid/transactions/${txnId}/categorize`, data)
}

// ---------------------------------------------------------------------------
// Categorization Rules
// ---------------------------------------------------------------------------

export async function listCategorizationRules() {
  return api.get<{ data: CategorizationRule[] }>('/integrations/plaid/categorization-rules')
}

export async function createCategorizationRule(data: CategorizationRuleCreate) {
  return api.post<ApiResponse<CategorizationRule>>('/integrations/plaid/categorization-rules', data)
}

export async function updateCategorizationRule(ruleId: string, data: CategorizationRuleUpdate) {
  return api.put<ApiResponse<CategorizationRule>>(`/integrations/plaid/categorization-rules/${ruleId}`, data)
}

export async function deleteCategorizationRule(ruleId: string) {
  return api.delete<ApiResponse<{ detail: string }>>(`/integrations/plaid/categorization-rules/${ruleId}`)
}

export async function applyCategorizationRules() {
  return api.post<ApiResponse<{ detail: string }>>('/integrations/plaid/apply-rules')
}

export async function aiCategorizeTransactions() {
  return api.post<ApiResponse<{ detail: string }>>('/integrations/plaid/ai-categorize')
}

// ---------------------------------------------------------------------------
// Stripe Payments
// ---------------------------------------------------------------------------

export async function getStripeConfig() {
  return api.get<ApiResponse<StripeConfig>>('/integrations/stripe/config')
}

export async function createPaymentLink(invoiceId: string) {
  return api.post<ApiResponse<StripePaymentLink>>('/integrations/stripe/payment-links', { invoice_id: invoiceId })
}

export async function getPaymentLink(invoiceId: string) {
  return api.get<ApiResponse<StripePaymentLink | null>>(`/integrations/stripe/payment-links/${invoiceId}`)
}

export async function createStripeSubscription(data: {
  contact_id: string
  name: string
  amount: number
  currency?: string
  interval: 'monthly' | 'quarterly' | 'yearly'
}) {
  return api.post<ApiResponse<StripeSubscription>>('/integrations/stripe/subscriptions', data)
}

export async function listStripeSubscriptions() {
  return api.get<{ data: StripeSubscription[] }>('/integrations/stripe/subscriptions')
}

export async function cancelStripeSubscription(subId: string) {
  return api.delete<ApiResponse<StripeSubscription>>(`/integrations/stripe/subscriptions/${subId}`)
}

// ---------------------------------------------------------------------------
// Twilio SMS
// ---------------------------------------------------------------------------

export async function sendSms(to: string, message: string) {
  return api.post<ApiResponse<SmsLog>>('/integrations/sms/send', { to, message })
}

export async function sendInvoiceSms(data: { invoice_id: string; to?: string }) {
  return api.post<ApiResponse<SmsLog>>('/integrations/sms/send-invoice-sms', data)
}

export async function sendReminderSms(data: { invoice_id: string; to?: string }) {
  return api.post<ApiResponse<SmsLog>>('/integrations/sms/send-reminder-sms', data)
}

export async function listSmsLogs() {
  return api.get<{ data: SmsLog[] }>('/integrations/sms/logs')
}

// ---------------------------------------------------------------------------
// Integration Settings (admin config for Twilio, Stripe, Plaid)
// ---------------------------------------------------------------------------

export async function getIntegrationSettings(type: string) {
  return api.get<{ data: Record<string, string>; meta: { is_configured: boolean } }>(
    `/integrations/settings/${type}`
  )
}

export async function saveIntegrationSettings(type: string, config: Record<string, string>) {
  return api.put<ApiResponse<{ message: string }>>(`/integrations/settings/${type}`, { config })
}

// ---------------------------------------------------------------------------
// QuickBooks Export
// ---------------------------------------------------------------------------

export function getExportUrl(_format: 'csv' | 'iif', _include: string, _dateFrom?: string, _dateTo?: string) {
  return `/api/export/quickbooks`
}

export async function exportQuickBooks(data: {
  format: 'csv' | 'iif'
  date_from?: string
  date_to?: string
  include: 'expenses' | 'income' | 'invoices' | 'all'
}) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = localStorage.getItem('access_token')
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch('/api/export/quickbooks', {
    method: 'POST',
    headers,
    body: JSON.stringify(data),
  })

  if (!response.ok) throw new Error('Export failed')

  const blob = await response.blob()
  const ext = data.format === 'iif' ? 'iif' : 'csv'
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `export.${ext}`
  a.click()
  window.URL.revokeObjectURL(url)
}

export async function exportChartOfAccounts() {
  const headers: Record<string, string> = {}
  const token = localStorage.getItem('access_token')
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch('/api/export/chart-of-accounts', { headers })
  if (!response.ok) throw new Error('Export failed')

  const blob = await response.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'chart_of_accounts.csv'
  a.click()
  window.URL.revokeObjectURL(url)
}
