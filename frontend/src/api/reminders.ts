import { api } from './client'
import type { ApiResponse } from '@/types/api'
import type { ReminderRule, PaymentReminder } from '@/types/models'

// ---------------------------------------------------------------------------
// Reminder Rules
// ---------------------------------------------------------------------------

export async function listReminderRules() {
  return api.get<{ data: ReminderRule[] }>('/invoices/reminder-rules')
}

export async function createReminderRule(data: {
  name: string
  days_offset: number
  channel: 'email' | 'sms' | 'both'
  email_subject?: string
  email_body?: string
  sms_body?: string
  is_active?: boolean
}) {
  return api.post<ApiResponse<ReminderRule>>('/invoices/reminder-rules', data)
}

export async function updateReminderRule(
  ruleId: string,
  data: Partial<{
    name: string
    days_offset: number
    channel: 'email' | 'sms' | 'both'
    email_subject: string
    email_body: string
    sms_body: string
    is_active: boolean
  }>
) {
  return api.put<ApiResponse<ReminderRule>>(`/invoices/reminder-rules/${ruleId}`, data)
}

export async function deleteReminderRule(ruleId: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/invoices/reminder-rules/${ruleId}`)
}

// ---------------------------------------------------------------------------
// Reminder History
// ---------------------------------------------------------------------------

export async function getReminderHistory(invoiceId: string) {
  return api.get<{ data: PaymentReminder[] }>(`/invoices/${invoiceId}/reminders`)
}

// ---------------------------------------------------------------------------
// Manual Send
// ---------------------------------------------------------------------------

export async function sendManualReminder(
  invoiceId: string,
  data: {
    channel: 'email' | 'sms' | 'both'
    email_subject?: string
    email_body?: string
    sms_body?: string
  }
) {
  return api.post<ApiResponse<PaymentReminder>>(`/invoices/${invoiceId}/send-reminder`, data)
}
