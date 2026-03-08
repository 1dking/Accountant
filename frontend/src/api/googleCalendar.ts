import { api } from './client'

export const googleCalendarApi = {
  connect: () => api.get('/integrations/google-calendar/connect'),

  listAccounts: () => api.get('/integrations/google-calendar/accounts'),

  disconnectAccount: (accountId: string) =>
    api.delete(`/integrations/google-calendar/accounts/${accountId}`),

  listCalendars: (accountId: string) =>
    api.get(`/integrations/google-calendar/accounts/${accountId}/calendars`),

  setSyncCalendar: (accountId: string, googleCalendarId: string) =>
    api.post(`/integrations/google-calendar/accounts/${accountId}/sync-calendar`, {
      google_calendar_id: googleCalendarId,
    }),

  triggerSync: () => api.post('/integrations/google-calendar/sync'),
}
