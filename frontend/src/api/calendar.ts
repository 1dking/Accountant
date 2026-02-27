import { api } from './client'
import type { ApiResponse } from '@/types/api'
import type { CalendarEvent } from '@/types/models'

export async function listEvents(dateFrom?: string, dateTo?: string) {
  const params = new URLSearchParams()
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo) params.set('date_to', dateTo)
  const query = params.toString()
  return api.get<ApiResponse<CalendarEvent[]>>(`/calendar/events${query ? `?${query}` : ''}`)
}

export async function createEvent(data: {
  title: string
  description?: string
  event_type: string
  date: string
  recurrence?: string
  document_id?: string
}) {
  return api.post<ApiResponse<CalendarEvent>>('/calendar/events', data)
}

export async function updateEvent(id: string, data: Partial<CalendarEvent>) {
  return api.put<ApiResponse<CalendarEvent>>(`/calendar/events/${id}`, data)
}

export async function deleteEvent(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/calendar/events/${id}`)
}

export async function getUpcoming(days: number = 7) {
  return api.get<ApiResponse<CalendarEvent[]>>(`/calendar/upcoming?days=${days}`)
}
