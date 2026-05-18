import { api } from './client'
import type { ApiResponse } from '@/types/api'
import type { User } from '@/types/models'

export async function listUsers() {
  return api.get<ApiResponse<User[]>>('/auth/users')
}

export async function updateUserRole(userId: string, role: string) {
  return api.put<ApiResponse<User>>(`/auth/users/${userId}/role`, { role })
}

export async function createUser(data: { email: string; password: string; full_name: string; role: string }) {
  return api.post<ApiResponse<User>>('/auth/users', data)
}

export async function updateUser(userId: string, data: { email?: string; password?: string; full_name?: string; cashbook_access?: string }) {
  return api.put<ApiResponse<User>>(`/auth/users/${userId}`, data)
}

export async function deactivateUser(userId: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/auth/users/${userId}`)
}

export async function updateProfile(data: {
  full_name?: string
  password?: string
  fallback_phone?: string
  booking_link?: string
  conversation_reply_enabled?: boolean
  conversation_template?: string
  conversation_ai_instructions?: string
  identity_capture_enabled?: boolean
}) {
  return api.put<ApiResponse<User>>('/auth/me', data)
}

export type VoicemailMode = 'cell_then_voicemail' | 'voicemail_only' | 'cell_only'

export async function updateVoicemailMode(mode: VoicemailMode) {
  return api.put<ApiResponse<User>>('/auth/me', { voicemail_mode: mode })
}

export type VoicemailGreetingPreview = {
  type: 'audio' | 'text' | null
  text?: string | null
  storage_key?: string | null
}

export async function getVoicemailGreeting() {
  return api.get<ApiResponse<VoicemailGreetingPreview>>('/auth/me/voicemail-greeting')
}

export async function uploadVoicemailGreeting(formData: FormData) {
  // Raw fetch — the api helper assumes JSON body
  const token = localStorage.getItem('access_token')
  const res = await fetch('/api/auth/me/voicemail-greeting', {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = (json as any)?.error?.message || (json as any)?.detail || `HTTP ${res.status}`
    throw new Error(detail)
  }
  return json
}

export async function deleteVoicemailGreeting() {
  return api.delete<ApiResponse<{ type: null }>>('/auth/me/voicemail-greeting')
}

// ─── Onboarding Checklist ───

export interface OnboardingItem {
  key: string
  label: string
  description: string
  completed: boolean
  action_link: string | null
  can_dismiss: boolean
  dismissed_at: string | null
}

export interface OnboardingPayload {
  items: OnboardingItem[]
  overall_progress: number
}

export async function getOnboarding() {
  return api.get<ApiResponse<OnboardingPayload>>('/auth/me/onboarding')
}

export async function dismissOnboardingItem(itemKey: string) {
  return api.post<ApiResponse<{ onboarding_state: Record<string, any> }>>(
    `/auth/me/onboarding/${itemKey}/dismiss`,
    {},
  )
}

// ─── Conversation engine preview ───

export interface ConversationPreviewResult {
  generated_reply: string
  classification: 'respond' | 'close_out' | 'silent'
  sample_inbound_used: string
}

export async function previewConversationReply(data: {
  template: string
  ai_instructions?: string
  sample_inbound?: string
}) {
  return api.post<ApiResponse<ConversationPreviewResult>>(
    '/auth/me/conversation-preview',
    data,
  )
}

// ─── Admin team management ───

export interface AdminTeamMember {
  id: string
  email: string
  full_name: string
  role: string | null
  assigned_phone_number: string | null
  fallback_phone: string | null
  voicemail_greeting_set: boolean
  voicemail_mode: string
  conversation_reply_enabled: boolean
  onboarding_progress: number
  onboarding_done_count: number
  onboarding_total_count: number
}

export async function listAdminTeam() {
  return api.get<ApiResponse<AdminTeamMember[]>>('/auth/admin/team')
}

export async function getTeamMemberOnboarding(userId: string) {
  return api.get<ApiResponse<OnboardingPayload & { user_id: string; email: string; full_name: string }>>(
    `/auth/admin/team/${userId}/onboarding`,
  )
}

export async function overrideTeamMember(userId: string, data: {
  fallback_phone?: string
  voicemail_mode?: string
}) {
  return api.put<ApiResponse<{ id: string; fallback_phone: string | null; voicemail_mode: string }>>(
    `/auth/admin/team/${userId}/override`,
    data,
  )
}

export async function sendTeamMemberReminder(userId: string) {
  return api.post<ApiResponse<{ sent: boolean; reason?: string; incomplete_count?: number }>>(
    `/auth/admin/team/${userId}/remind`,
    {},
  )
}

export async function getSystemStats() {
  return api.get<ApiResponse<{
    document_count: number
    storage_used: number
    user_count: number
    pending_approvals: number
  }>>('/system/stats')
}
