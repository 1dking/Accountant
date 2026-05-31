import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type { Meeting, MeetingListItem, MeetingRecording, MeetingParticipant } from '@/types/models'

export interface MeetingFilters {
  status?: string
  contact_id?: string
  page?: number
  page_size?: number
}

export type MeetingTemplate =
  | 'generic'
  | 'discovery_call'
  | 'client_review'
  | 'internal_sync'

export interface MeetingCreateData {
  title: string
  scheduled_start: string
  scheduled_end?: string
  description?: string
  contact_id?: string
  record_meeting?: boolean
  /** Commit 16 — biases the AI pipeline. DISCOVERY_CALL auto-enables
   *  recording; INTERNAL_SYNC skips quote-draft entirely. */
  template?: MeetingTemplate
  participant_emails?: string[]
}

export interface MeetingUpdateData {
  title?: string
  scheduled_start?: string
  scheduled_end?: string
  description?: string
  contact_id?: string
  record_meeting?: boolean
}

export interface LiveKitTokenResponse {
  token: string
  room_name: string
  identity: string
  /** Commit 7 — when true, the backend has started server-side
   *  recording via LiveKit Egress. Client should hide the manual
   *  Record button and show a "Recording" indicator instead. */
  record_meeting?: boolean
  /** Commit 22 — slug surfaces here so the host's meeting room can
   *  render the public share link without a second fetch. */
  slug?: string | null
}

export interface RecordingsByContact {
  contact_id: string | null
  contact_name: string | null
  recordings: MeetingRecording[]
}

export async function listMeetings(filters: MeetingFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== '' && val !== null) params.set(key, String(val))
  })
  const query = params.toString()
  return api.get<ApiListResponse<MeetingListItem>>(`/meetings${query ? `?${query}` : ''}`)
}

export async function getMeeting(id: string) {
  return api.get<ApiResponse<Meeting>>(`/meetings/${id}`)
}

export async function createMeeting(data: MeetingCreateData) {
  return api.post<ApiResponse<Meeting>>('/meetings', data)
}

export async function updateMeeting(id: string, data: MeetingUpdateData) {
  return api.put<ApiResponse<Meeting>>(`/meetings/${id}`, data)
}

export async function cancelMeeting(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/meetings/${id}`)
}

export async function startMeeting(id: string) {
  return api.post<ApiResponse<LiveKitTokenResponse>>(`/meetings/${id}/start`)
}

export async function joinMeeting(id: string) {
  return api.post<ApiResponse<LiveKitTokenResponse>>(`/meetings/${id}/join`)
}

export async function endMeeting(id: string) {
  return api.post<ApiResponse<Meeting>>(`/meetings/${id}/end`)
}

export async function joinMeetingAsGuest(id: string, token: string, guestName: string) {
  const response = await fetch(`/api/meetings/${id}/join-guest?token=${encodeURIComponent(token)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ guest_name: guestName }),
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.error?.message || `Failed to join meeting (${response.status})`)
  }
  return response.json() as Promise<ApiResponse<LiveKitTokenResponse>>
}

export async function startRecording(meetingId: string) {
  return api.post<ApiResponse<MeetingRecording>>(`/meetings/${meetingId}/recordings/start`)
}

export async function stopRecording(meetingId: string) {
  return api.post<ApiResponse<MeetingRecording>>(`/meetings/${meetingId}/recordings/stop`)
}

export async function listRecordings(meetingId?: string) {
  if (meetingId) {
    return api.get<ApiListResponse<MeetingRecording>>(`/meetings/${meetingId}/recordings`)
  }
  return api.get<ApiListResponse<MeetingRecording>>('/meetings/recordings/all')
}

export async function listRecordingsByContact() {
  return api.get<ApiResponse<RecordingsByContact[]>>('/meetings/recordings/by-contact')
}

export function getRecordingStreamUrl(recordingId: string): string {
  const token = localStorage.getItem('access_token') || ''
  return `/api/meetings/recordings/${recordingId}/stream?token=${encodeURIComponent(token)}`
}

// ---------------------------------------------------------------------------
// Commit 8 — Google-Meet-style instant + slug + lobby flow
// ---------------------------------------------------------------------------

export interface InstantMeetingResponse {
  meeting: Meeting
  join: LiveKitTokenResponse
}

export async function startInstantMeeting(opts: {
  title?: string
  record_meeting?: boolean
  template?: MeetingTemplate
} = {}) {
  return api.post<ApiResponse<InstantMeetingResponse>>('/meetings/instant', opts)
}

/** Commit 29 — get the user's persistent personal meeting room.
 *  Creates it on first call. Slug never changes — safe to paste into
 *  Calendly / Google Calendar / email signature. */
export async function getPersonalRoom() {
  return api.get<ApiResponse<Meeting>>('/meetings/personal-room')
}

export interface PublicMeetingInfo {
  slug: string
  title: string
  status: 'scheduled' | 'in_progress' | 'completed' | 'cancelled'
  scheduled_start: string | null
  host_name: string | null
  /** Commit 25 — surfaced so the guest knock screen can show the
   *  recording notice + consent banner before the guest knocks. */
  record_meeting?: boolean
}

export async function getPublicMeetingInfo(slug: string) {
  // No auth — guest pre-join page. Use plain fetch so the api client
  // doesn't attach a bearer token.
  const resp = await fetch(`/api/meetings/public/${encodeURIComponent(slug)}`)
  if (!resp.ok) {
    const body = await resp.json().catch(() => null)
    throw new Error(body?.error?.message || `Meeting not found (${resp.status})`)
  }
  return resp.json() as Promise<ApiResponse<PublicMeetingInfo>>
}

export interface LobbyKnockResponse {
  lobby_id: string
  status: 'waiting' | 'admitted' | 'denied'
}

export async function knockAtLobby(slug: string, name: string, email: string) {
  const resp = await fetch(`/api/meetings/public/${encodeURIComponent(slug)}/knock`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, email }),
  })
  if (resp.status === 403) {
    // Special-cased so the UI can render the friendly "not on the
    // invite list" message inline instead of a generic error toast.
    const body = await resp.json().catch(() => null)
    throw new Error(
      body?.error?.message
        || "We can't find an invite for that email on this meeting.",
    )
  }
  if (!resp.ok) {
    const body = await resp.json().catch(() => null)
    throw new Error(body?.error?.message || `Knock failed (${resp.status})`)
  }
  return resp.json() as Promise<ApiResponse<LobbyKnockResponse>>
}

export interface LobbyStatusPollResponse {
  status: 'waiting' | 'admitted' | 'denied' | 'ended'
  token?: string
  room_name?: string
  identity?: string
  record_meeting?: boolean
}

export async function pollLobbyStatus(slug: string, lobbyId: string) {
  const resp = await fetch(
    `/api/meetings/public/${encodeURIComponent(slug)}/lobby/${encodeURIComponent(lobbyId)}`,
  )
  if (!resp.ok) {
    const body = await resp.json().catch(() => null)
    throw new Error(body?.error?.message || `Lobby poll failed (${resp.status})`)
  }
  return resp.json() as Promise<ApiResponse<LobbyStatusPollResponse>>
}

export async function listLobby(meetingId: string) {
  return api.get<ApiListResponse<MeetingParticipant>>(`/meetings/${meetingId}/lobby`)
}

export async function admitFromLobby(meetingId: string, lobbyId: string) {
  return api.post<ApiResponse<MeetingParticipant>>(
    `/meetings/${meetingId}/lobby/${lobbyId}/admit`,
  )
}

/** Commit 19 — Admit-all for large meetings. Calls /admit per row
 *  in sequence; the backend's per-row admit is the source of truth. */
export async function admitAllFromLobby(
  meetingId: string, lobbyIds: string[],
) {
  for (const id of lobbyIds) {
    await admitFromLobby(meetingId, id)
  }
}

export async function denyFromLobby(meetingId: string, lobbyId: string) {
  return api.post<ApiResponse<MeetingParticipant>>(
    `/meetings/${meetingId}/lobby/${lobbyId}/deny`,
  )
}

// ---------------------------------------------------------------------------
// Commit 9 — calendar invite (add-to-calendar URLs + email send)
// ---------------------------------------------------------------------------

export interface CalendarUrls {
  google: string
  outlook: string
  ics_url: string
}

export async function getCalendarUrls(meetingId: string) {
  return api.get<ApiResponse<CalendarUrls>>(`/meetings/${meetingId}/calendar-urls`)
}

export interface SendInvitesResult {
  sent: number
  failed: number
  errors: string[]
}

export async function sendMeetingInvites(meetingId: string) {
  return api.post<ApiResponse<SendInvitesResult>>(`/meetings/${meetingId}/send-invites`)
}

// ---------------------------------------------------------------------------
// Commit 11 — transcript
// ---------------------------------------------------------------------------

export interface TranscriptSegment {
  start: number
  end: number
  text: string
  speaker: string
}

export interface RecordingTranscript {
  id: string
  meeting_id: string
  recording_id: string
  status: 'pending' | 'processing' | 'available' | 'failed'
  provider: string
  full_text: string | null
  segments: TranscriptSegment[]
  language: string | null
  duration_seconds: number | null
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}

export async function getMeetingTranscript(meetingId: string) {
  return api.get<ApiResponse<RecordingTranscript>>(`/meetings/${meetingId}/transcript`)
}

// ---------------------------------------------------------------------------
// Commit 12 — Claude summary + action items
// ---------------------------------------------------------------------------

export interface SummaryActionItem {
  text: string
  assignee: string | null
  due_hint: string | null
}

export interface SummaryTopic {
  topic: string
  decision: string | null
}

export interface MeetingSummary {
  id: string
  meeting_id: string
  status: 'pending' | 'processing' | 'available' | 'failed'
  summary_text: string | null
  topics: SummaryTopic[]
  action_items: SummaryActionItem[]
  next_steps: string[]
  model_used: string | null
  input_tokens: number | null
  output_tokens: number | null
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}

export async function getMeetingSummary(meetingId: string) {
  return api.get<ApiResponse<MeetingSummary>>(`/meetings/${meetingId}/summary`)
}

// ---------------------------------------------------------------------------
// Commit 13 — searchable transcript across all meetings
// ---------------------------------------------------------------------------

export interface TranscriptSearchHit {
  meeting_id: string
  meeting_title: string
  meeting_slug: string | null
  snippet: string
  match_time_seconds: number | null
  scheduled_start: string | null
}

export async function searchMeetingTranscripts(q: string, limit = 10) {
  const params = new URLSearchParams({ q, limit: String(limit) })
  return api.get<ApiListResponse<TranscriptSearchHit>>(`/meetings/search?${params}`)
}

// ---------------------------------------------------------------------------
// Commit 15 — AI quote/invoice draft + review gate
// ---------------------------------------------------------------------------

export interface QuoteLineItem {
  description: string
  quantity: number
  unit_price: number
  total: number
}

export interface MeetingQuoteDraft {
  id: string
  meeting_id: string
  summary_id: string
  status: 'pending' | 'processing' | 'available' | 'skipped' | 'reviewed' | 'sent' | 'failed'
  draft_title: string | null
  draft_summary: string | null
  line_items: QuoteLineItem[]
  estimated_total: number | null
  currency: string | null
  notes: string | null
  confidence: 'high' | 'medium' | 'low' | null
  model_used: string | null
  input_tokens: number | null
  output_tokens: number | null
  reviewed_at: string | null
  sent_at: string | null
  promoted_proposal_id: string | null
  error_message: string | null
  created_at: string | null
  updated_at: string | null
}

export async function getMeetingQuoteDraft(meetingId: string) {
  return api.get<ApiResponse<MeetingQuoteDraft>>(`/meetings/${meetingId}/quote-draft`)
}

export async function reviewMeetingQuoteDraft(meetingId: string) {
  return api.post<ApiResponse<{ reviewed_at: string }>>(
    `/meetings/${meetingId}/quote-draft/review`,
  )
}

// ---------------------------------------------------------------------------
// Commit 17 — cross-meeting context
// ---------------------------------------------------------------------------

export interface PriorMeetingContext {
  contact_id?: string
  last_meeting?: {
    id: string
    title: string
    scheduled_start: string | null
    actual_end: string | null
    summary_text: string | null
  } | null
  recent_action_items?: Array<{
    title: string
    description: string | null
    source_summary_id: string | null
    created_at: string | null
  }>
  recent_topics?: Array<{ topic: string; decision: string | null }>
}

export async function getMeetingPriorContext(meetingId: string) {
  return api.get<ApiResponse<PriorMeetingContext>>(
    `/meetings/${meetingId}/prior-context`,
  )
}

export async function uploadRecording(meetingId: string, file: Blob): Promise<ApiResponse<MeetingRecording>> {
  const formData = new FormData()
  formData.append('file', file, `recording-${Date.now()}.webm`)
  return api.upload<ApiResponse<MeetingRecording>>(`/meetings/${meetingId}/recordings/upload`, formData)
}

export function deleteRecording(recordingId: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/meetings/recordings/${recordingId}`)
}

export async function addParticipant(meetingId: string, data: { email?: string; contact_id?: string; guest_name?: string; guest_email?: string }) {
  return api.post<ApiResponse<MeetingParticipant>>(`/meetings/${meetingId}/participants`, data)
}

export async function removeParticipant(meetingId: string, participantId: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/meetings/${meetingId}/participants/${participantId}`)
}
