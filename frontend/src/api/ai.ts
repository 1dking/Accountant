import { api } from './client'
import type { ApiResponse } from '@/types/api'

export interface LineItem {
  description: string
  quantity: number | null
  unit_price: number | null
  total: number | null
}

export interface ReceiptExtraction {
  vendor_name: string | null
  vendor_address: string | null
  date: string | null
  currency: string
  subtotal: number | null
  tax_amount: number | null
  tax_rate: number | null
  total_amount: number | null
  tip_amount: number | null
  payment_method: string | null
  line_items: LineItem[]
  category: string | null
  receipt_number: string | null
  full_text: string
}

export interface AIProcessResponse {
  document_id: string
  extraction: ReceiptExtraction
  processing_time_ms: number
}

export interface AIExtractionStatus {
  document_id: string
  has_extraction: boolean
  extraction: ReceiptExtraction | null
}

export async function triggerExtraction(documentId: string) {
  return api.post<ApiResponse<AIProcessResponse>>(`/ai/extract/${documentId}`)
}

export async function getExtraction(documentId: string) {
  return api.get<ApiResponse<AIExtractionStatus>>(`/ai/extraction/${documentId}`)
}
