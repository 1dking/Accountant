import { api } from './client'

export const schedulingApi = {
  // Calendars
  listCalendars: (page = 1, pageSize = 50) =>
    api.get(`/scheduling?page=${page}&page_size=${pageSize}`),

  getCalendar: (id: string) => api.get(`/scheduling/${id}`),

  createCalendar: (data: Record<string, unknown>) =>
    api.post('/scheduling', data),

  updateCalendar: (id: string, data: Record<string, unknown>) =>
    api.put(`/scheduling/${id}`, data),

  deleteCalendar: (id: string) => api.delete(`/scheduling/${id}`),

  // Members
  listMembers: (calendarId: string) =>
    api.get(`/scheduling/${calendarId}/members`),

  addMember: (calendarId: string, data: { user_id: string; priority?: number }) =>
    api.post(`/scheduling/${calendarId}/members`, data),

  removeMember: (calendarId: string, memberId: string) =>
    api.delete(`/scheduling/${calendarId}/members/${memberId}`),

  // Bookings
  listBookings: (calendarId: string, page = 1, pageSize = 50, status?: string) => {
    let url = `/scheduling/${calendarId}/bookings?page=${page}&page_size=${pageSize}`
    if (status) url += `&status=${status}`
    return api.get(url)
  },

  listAllBookings: (page = 1, pageSize = 50, status?: string) => {
    let url = `/scheduling/bookings/all?page=${page}&page_size=${pageSize}`
    if (status) url += `&status=${status}`
    return api.get(url)
  },

  createBooking: (calendarId: string, data: Record<string, unknown>) =>
    api.post(`/scheduling/${calendarId}/bookings`, data),

  updateBooking: (calendarId: string, bookingId: string, data: Record<string, unknown>) =>
    api.put(`/scheduling/${calendarId}/bookings/${bookingId}`, data),

  cancelBooking: (calendarId: string, bookingId: string, reason?: string) =>
    api.post(`/scheduling/${calendarId}/bookings/${bookingId}/cancel${reason ? `?reason=${encodeURIComponent(reason)}` : ''}`),

  // Available slots
  getSlots: (calendarId: string, date: string) =>
    api.get(`/scheduling/${calendarId}/slots?date=${date}`),

  // Public
  getPublicCalendar: (slug: string, date?: string) =>
    api.get(`/scheduling/public/${slug}${date ? `?date=${date}` : ''}`),
}
