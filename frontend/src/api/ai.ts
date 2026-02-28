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

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export async function streamHelpChat(
  messages: ChatMessage[],
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
): Promise<void> {
  const token = localStorage.getItem('access_token')
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  try {
    const response = await fetch('/api/ai/chat', {
      method: 'POST',
      headers,
      body: JSON.stringify({ messages }),
    })

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.error?.message || `Request failed (${response.status})`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('No response body')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') {
            onDone()
            return
          }
          onChunk(data)
        }
      }
    }
    onDone()
  } catch (err) {
    onError(err instanceof Error ? err.message : 'Chat request failed')
  }
}
