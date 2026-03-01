import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type { Invoice, InvoiceListItem } from '@/types/models'

export interface InvoiceFilters {
  search?: string
  status?: string
  contact_id?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

export interface InvoiceLineItemData {
  description: string
  quantity: number
  unit_price: number
  tax_rate?: number
}

export interface InvoiceCreateData {
  contact_id: string
  issue_date: string
  due_date: string
  tax_rate?: number
  discount_amount?: number
  currency?: string
  notes?: string
  payment_terms?: string
  line_items: InvoiceLineItemData[]
}

export interface InvoiceUpdateData {
  contact_id?: string
  issue_date?: string
  due_date?: string
  status?: string
  tax_rate?: number
  discount_amount?: number
  currency?: string
  notes?: string
  payment_terms?: string
  line_items?: InvoiceLineItemData[]
}

export interface PaymentData {
  amount: number
  date: string
  payment_method?: string
  reference?: string
  notes?: string
}

export async function listInvoices(filters: InvoiceFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== '' && val !== null) params.set(key, String(val))
  })
  const query = params.toString()
  return api.get<ApiListResponse<InvoiceListItem>>(`/invoices${query ? `?${query}` : ''}`)
}

export async function getInvoice(id: string) {
  return api.get<ApiResponse<Invoice>>(`/invoices/${id}`)
}

export async function createInvoice(data: InvoiceCreateData) {
  return api.post<ApiResponse<Invoice>>('/invoices', data)
}

export async function updateInvoice(id: string, data: InvoiceUpdateData) {
  return api.put<ApiResponse<Invoice>>(`/invoices/${id}`, data)
}

export async function deleteInvoice(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/invoices/${id}`)
}

export async function sendInvoice(id: string) {
  return api.post<ApiResponse<Invoice>>(`/invoices/${id}/send`)
}

export async function recordPayment(invoiceId: string, data: PaymentData) {
  return api.post<ApiResponse<any>>(`/invoices/${invoiceId}/payments`, data)
}

export async function getInvoiceStats() {
  return api.get<ApiResponse<{
    total_outstanding: number
    total_overdue: number
    total_paid_this_month: number
    invoice_count: number
  }>>('/invoices/stats')
}

export function getInvoicePdfUrl(id: string) {
  return `/api/invoices/${id}/pdf`
}

export async function downloadInvoicePdf(id: string, invoiceNumber?: string) {
  const token = localStorage.getItem('access_token')
  const res = await fetch(`/api/invoices/${id}/pdf`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error('Failed to download PDF')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = invoiceNumber ? `Invoice-${invoiceNumber}.pdf` : 'invoice.pdf'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
