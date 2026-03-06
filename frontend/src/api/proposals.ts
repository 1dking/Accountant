import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'

// Types
export interface ProposalRecipient {
  id: string
  proposal_id: string
  email: string
  name: string
  role: string
  signing_order: number
  signed_at: string | null
  signature_type: string | null
  document_hash: string | null
  ip_address: string | null
}

export interface ProposalActivity {
  id: string
  proposal_id: string
  action: string
  actor_email: string | null
  actor_name: string | null
  ip_address: string | null
  metadata_json: string | null
  created_at: string
}

export interface Proposal {
  id: string
  proposal_number: string
  contact_id: string
  title: string
  content_json: string
  status: ProposalStatus
  value: number
  currency: string
  template_id: string | null
  collect_payment: boolean
  payment_mode: string | null
  payment_frequency: string | null
  payment_status: PaymentStatus | null
  public_token: string | null
  created_by: string
  sent_at: string | null
  viewed_at: string | null
  signed_at: string | null
  paid_at: string | null
  follow_up_enabled: boolean
  follow_up_hours: number
  contact?: { company_name: string; contact_name: string | null; email: string | null } | null
  recipients: ProposalRecipient[]
  activities: ProposalActivity[]
  created_at: string
  updated_at: string
}

export interface ProposalListItem {
  id: string
  proposal_number: string
  contact_id: string
  title: string
  status: ProposalStatus
  value: number
  currency: string
  payment_status: PaymentStatus | null
  public_token: string | null
  created_by: string
  sent_at: string | null
  viewed_at: string | null
  signed_at: string | null
  paid_at: string | null
  contact?: { company_name: string; contact_name: string | null; email: string | null } | null
  created_at: string
  updated_at: string
}

export type ProposalStatus = 'draft' | 'sent' | 'viewed' | 'waiting_signature' | 'signed' | 'declined' | 'paid'
export type PaymentStatus = 'unpaid' | 'processing' | 'paid'

export interface ProposalTemplate {
  id: string
  title: string
  description: string | null
  content_json: string
  thumbnail_url: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface ProposalStats {
  total_proposals: number
  draft_count: number
  sent_count: number
  viewed_count: number
  signed_count: number
  declined_count: number
  paid_count: number
  total_value: number
  signed_value: number
  paid_value: number
}

export interface SigningPageData {
  proposal_id: string
  proposal_title: string
  content_json: string
  recipient_name: string
  recipient_email: string
  recipient_role: string
  recipient_id: string
  already_signed: boolean
  all_signed: boolean
  contact_name: string | null
  company_name: string | null
  collect_payment: boolean
  value: string
  currency: string
}

export interface FollowUpRule {
  id: string
  resource_type: string
  resource_id: string
  trigger_event: string
  delay_hours: number
  message_template: string | null
  channel: string
  is_active: boolean
  last_sent_at: string | null
  send_count: number
  created_at: string
  updated_at: string
}

export interface GhlSettings {
  connected: boolean
  ghl_location_id: string | null
  last_sync_at: string | null
  sync_count: number
}

export interface GhlSyncLog {
  id: string
  entity_type: string
  entity_id: string
  ghl_entity_id: string | null
  direction: string
  status: string
  error_message: string | null
  synced_at: string
}

// Proposal CRUD
export async function listProposals(params: Record<string, string | undefined> = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v) query.set(k, v) })
  const qs = query.toString()
  return api.get<ApiListResponse<ProposalListItem>>(`/proposals${qs ? `?${qs}` : ''}`)
}

export async function getProposal(id: string) {
  return api.get<ApiResponse<Proposal>>(`/proposals/${id}`)
}

export async function createProposal(data: {
  contact_id: string
  title: string
  content_json?: string
  value?: number
  currency?: string
  template_id?: string
  collect_payment?: boolean
  payment_mode?: string
  payment_frequency?: string
  recipients?: { email: string; name: string; role?: string; signing_order?: number }[]
  follow_up_enabled?: boolean
  follow_up_hours?: number
}) {
  return api.post<ApiResponse<Proposal>>('/proposals', data)
}

export async function updateProposal(id: string, data: Partial<Proposal>) {
  return api.put<ApiResponse<Proposal>>(`/proposals/${id}`, data)
}

export async function deleteProposal(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/proposals/${id}`)
}

// Actions
export async function sendProposal(id: string) {
  return api.post<ApiResponse<Proposal>>(`/proposals/${id}/send`)
}

export async function cloneProposal(id: string) {
  return api.post<ApiResponse<Proposal>>(`/proposals/${id}/clone`)
}

export async function declineProposal(id: string) {
  return api.post<ApiResponse<Proposal>>(`/proposals/${id}/decline`)
}

export async function completeProposal(id: string) {
  return api.post<ApiResponse<Proposal>>(`/proposals/${id}/complete`)
}

export async function convertToTemplate(id: string) {
  return api.post<ApiResponse<ProposalTemplate>>(`/proposals/${id}/convert-template`)
}

export async function createCheckout(id: string) {
  return api.post<ApiResponse<{ checkout_url: string; session_id: string }>>(`/proposals/${id}/checkout`)
}

// Recipients
export async function addRecipient(proposalId: string, data: { email: string; name: string; role?: string; signing_order?: number }) {
  return api.post<ApiResponse<ProposalRecipient>>(`/proposals/${proposalId}/recipients`, data)
}

export async function removeRecipient(proposalId: string, recipientId: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/proposals/${proposalId}/recipients/${recipientId}`)
}

// Stats
export async function getProposalStats() {
  return api.get<ApiResponse<ProposalStats>>('/proposals/stats')
}

// Templates
export async function listTemplates(params: Record<string, string | undefined> = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v) query.set(k, v) })
  const qs = query.toString()
  return api.get<ApiListResponse<ProposalTemplate>>(`/proposals/templates${qs ? `?${qs}` : ''}`)
}

export async function getTemplate(id: string) {
  return api.get<ApiResponse<ProposalTemplate>>(`/proposals/templates/${id}`)
}

export async function createTemplate(data: { title: string; description?: string; content_json: string }) {
  return api.post<ApiResponse<ProposalTemplate>>('/proposals/templates', data)
}

export async function updateTemplate(id: string, data: Partial<ProposalTemplate>) {
  return api.put<ApiResponse<ProposalTemplate>>(`/proposals/templates/${id}`, data)
}

export async function deleteTemplate(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/proposals/templates/${id}`)
}

// Public signing (no auth)
export async function getSigningData(token: string) {
  return api.get<ApiResponse<SigningPageData>>(`/proposals/sign/${token}`)
}

export async function signProposal(token: string, data: { recipient_id: string; signature_data: string; signature_type: string }) {
  return api.post<ApiResponse<{ signed: boolean; all_signed: boolean; redirect_to_payment: boolean; proposal_id: string }>>(`/proposals/sign/${token}`, data)
}

// GHL
export async function getGhlSettings() {
  return api.get<ApiResponse<GhlSettings>>('/proposals/ghl/settings')
}

export async function getGhlLogs(params: Record<string, string | undefined> = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v) query.set(k, v) })
  const qs = query.toString()
  return api.get<ApiListResponse<GhlSyncLog>>(`/proposals/ghl/logs${qs ? `?${qs}` : ''}`)
}

export async function triggerGhlSync(data: { entity_type: string; direction: string }) {
  return api.post<ApiResponse<GhlSyncLog>>('/proposals/ghl/sync', data)
}

// Follow-ups
export async function listFollowUps(params: Record<string, string | undefined> = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v) query.set(k, v) })
  const qs = query.toString()
  return api.get<ApiResponse<FollowUpRule[]>>(`/proposals/follow-ups${qs ? `?${qs}` : ''}`)
}

export async function createFollowUp(data: {
  resource_type: string
  resource_id: string
  trigger_event: string
  delay_hours?: number
  message_template?: string
  channel?: string
}) {
  return api.post<ApiResponse<FollowUpRule>>('/proposals/follow-ups', data)
}

export async function toggleFollowUp(ruleId: string, active: boolean) {
  return api.put<ApiResponse<FollowUpRule>>(`/proposals/follow-ups/${ruleId}/toggle?active=${active}`)
}
