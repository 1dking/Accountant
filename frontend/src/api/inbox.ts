import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type { UnifiedMessage, UnreadCount } from '@/types/models'

export async function listMessages(params: {
  message_type?: string
  direction?: string
  contact_id?: string
  is_read?: boolean
  search?: string
  page?: number
  page_size?: number
} = {}) {
  const qs = new URLSearchParams()
  if (params.message_type) qs.set('message_type', params.message_type)
  if (params.direction) qs.set('direction', params.direction)
  if (params.contact_id) qs.set('contact_id', params.contact_id)
  if (params.is_read !== undefined) qs.set('is_read', String(params.is_read))
  if (params.search) qs.set('search', params.search)
  qs.set('page', String(params.page ?? 1))
  qs.set('page_size', String(params.page_size ?? 50))
  return api.get<ApiListResponse<UnifiedMessage>>(`/inbox/messages?${qs}`)
}

export interface ThreadItem {
  message: UnifiedMessage
  message_count: number
  unread_count: number
}

export async function listThreads(page = 1, pageSize = 50) {
  return api.get<ApiListResponse<ThreadItem>>(
    `/inbox/threads?page=${page}&page_size=${pageSize}`,
  )
}

export async function getThreadMessages(threadId: string) {
  return api.get<ApiResponse<UnifiedMessage[]>>(`/inbox/threads/${encodeURIComponent(threadId)}`)
}

export async function replyToThread(threadId: string, body: string, subject?: string, smtpConfigId?: string) {
  return api.post<ApiResponse<UnifiedMessage>>(`/inbox/threads/${encodeURIComponent(threadId)}/reply`, {
    body,
    subject: subject || null,
    smtp_config_id: smtpConfigId || null,
  })
}

export async function markMessageRead(messageId: string) {
  return api.post<ApiResponse<{ message: string }>>(`/inbox/messages/${messageId}/read`)
}

export async function markThreadRead(threadId: string) {
  return api.post<ApiResponse<{ message: string }>>(`/inbox/threads/${encodeURIComponent(threadId)}/read`)
}

export async function getUnreadCount() {
  return api.get<ApiResponse<UnreadCount>>('/inbox/unread-count')
}

export async function syncMessages() {
  return api.post<ApiResponse<{ message: string; created: number }>>('/inbox/sync')
}
