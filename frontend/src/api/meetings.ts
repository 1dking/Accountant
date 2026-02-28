import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type { Meeting, MeetingListItem, MeetingRecording, MeetingParticipant } from '@/types/models'

export interface MeetingFilters {
  status?: string
  contact_id?: string
  page?: number
  page_size?: number
}

export interface MeetingCreateData {
  title: string
  scheduled_start: string
  scheduled_end?: string
  description?: string
  contact_id?: string
  record_meeting?: boolean
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

export async function uploadRecording(meetingId: string, file: Blob): Promise<ApiResponse<MeetingRecording>> {
  const formData = new FormData()
  formData.append('file', file, `recording-${Date.now()}.webm`)
  const token = localStorage.getItem('access_token') || ''
  const response = await fetch(`/api/meetings/${meetingId}/recordings/upload`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.error?.message || `Failed to upload recording (${response.status})`)
  }
  return response.json() as Promise<ApiResponse<MeetingRecording>>
}

export async function addParticipant(meetingId: string, data: { email?: string; contact_id?: string; guest_name?: string; guest_email?: string }) {
  return api.post<ApiResponse<MeetingParticipant>>(`/meetings/${meetingId}/participants`, data)
}

export async function removeParticipant(meetingId: string, participantId: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/meetings/${meetingId}/participants/${participantId}`)
}
