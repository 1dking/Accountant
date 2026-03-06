import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type {
  TwilioPhoneNumber,
  CallLogEntry,
  SmsMessageEntry,
  ChatSession,
  ChatMessage,
} from '@/types/models'

// Phone Numbers
export async function listPhoneNumbers() {
  return api.get<ApiResponse<TwilioPhoneNumber[]>>('/communication/phone-numbers')
}

export async function addPhoneNumber(data: { phone_number: string; friendly_name?: string }) {
  return api.post<ApiResponse<TwilioPhoneNumber>>('/communication/phone-numbers', data)
}

export async function assignPhoneNumber(id: string, userId: string | null) {
  return api.put<ApiResponse<TwilioPhoneNumber>>(`/communication/phone-numbers/${id}`, {
    assigned_user_id: userId,
  })
}

export async function deletePhoneNumber(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/communication/phone-numbers/${id}`)
}

// Call Log
export interface CallLogFilters {
  direction?: string
  contact_id?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

export async function logCall(data: {
  contact_id?: string
  direction: string
  from_number: string
  to_number: string
  duration_seconds?: number
  notes?: string
  outcome?: string
}) {
  return api.post<ApiResponse<CallLogEntry>>('/communication/calls', data)
}

export async function listCalls(filters: CallLogFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== '' && val !== null) params.set(key, String(val))
  })
  const query = params.toString()
  return api.get<ApiListResponse<CallLogEntry>>(
    `/communication/calls${query ? `?${query}` : ''}`
  )
}

export async function getCapabilityToken() {
  return api.get<ApiResponse<{ token: string }>>('/communication/calls/capability-token')
}

// SMS
export interface SmsFilters {
  direction?: string
  contact_id?: string
  page?: number
  page_size?: number
}

export async function sendSms(data: { to_number: string; body: string; contact_id?: string }) {
  return api.post<ApiResponse<SmsMessageEntry>>('/communication/sms', data)
}

export async function listSms(filters: SmsFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== '' && val !== null) params.set(key, String(val))
  })
  const query = params.toString()
  return api.get<ApiListResponse<SmsMessageEntry>>(
    `/communication/sms${query ? `?${query}` : ''}`
  )
}

// Live Chat
export async function createChatSession(data: {
  visitor_name?: string
  visitor_email?: string
  contact_id?: string
}) {
  return api.post<ApiResponse<ChatSession>>('/communication/chat/sessions', data)
}

export async function listChatSessions(status?: string, page = 1) {
  const params = new URLSearchParams({ page: String(page) })
  if (status) params.set('status', status)
  return api.get<ApiListResponse<ChatSession>>(
    `/communication/chat/sessions?${params.toString()}`
  )
}

export async function sendChatMessage(sessionId: string, message: string) {
  return api.post<ApiResponse<ChatMessage>>(
    `/communication/chat/sessions/${sessionId}/messages`,
    { message }
  )
}

export async function getChatMessages(sessionId: string) {
  return api.get<ApiResponse<ChatMessage[]>>(
    `/communication/chat/sessions/${sessionId}/messages`
  )
}

export async function closeChatSession(sessionId: string) {
  return api.put<ApiResponse<ChatSession>>(
    `/communication/chat/sessions/${sessionId}/close`,
    {}
  )
}
