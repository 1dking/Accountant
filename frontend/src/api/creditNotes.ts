import { api } from './client'
import type { ApiResponse } from '@/types/api'
import type { CreditNote, CreditNoteListItem, ContactCreditBalance } from '@/types/models'

export interface CreditNoteCreateData {
  amount: number
  reason?: string
  issue_date: string
}

export async function listCreditNotes(params: { invoice_id?: string; contact_id?: string } = {}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null) searchParams.set(key, String(val))
  })
  const query = searchParams.toString()
  return api.get<ApiResponse<CreditNoteListItem[]>>(`/invoices/credit-notes${query ? `?${query}` : ''}`)
}

export async function createCreditNote(invoiceId: string, data: CreditNoteCreateData) {
  return api.post<ApiResponse<CreditNote>>(`/invoices/${invoiceId}/credit-note`, data)
}

export async function getCreditNote(creditNoteId: string) {
  return api.get<ApiResponse<CreditNote>>(`/invoices/credit-notes/${creditNoteId}`)
}

export async function applyCreditNote(creditNoteId: string) {
  return api.post<ApiResponse<CreditNote>>(`/invoices/credit-notes/${creditNoteId}/apply`)
}

export async function getContactCreditBalance(contactId: string) {
  return api.get<ApiResponse<ContactCreditBalance>>(`/invoices/credit-notes/contact/${contactId}/balance`)
}
