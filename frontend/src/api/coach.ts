import { api } from './client'

export const coachApi = {
  // Meeting intelligence
  analyzeMeeting: (meetingId: string) =>
    api.post(`/coach/meetings/${meetingId}/analyze`, {}),
  getMeetingIntelligence: (meetingId: string) =>
    api.get(`/coach/meetings/${meetingId}/intelligence`),
  toggleActionItem: (intelId: string, index: number, completed: boolean) =>
    api.post(`/coach/intelligence/${intelId}/action-items`, { index, completed }),

  // Monthly reports
  listReports: () => api.get('/coach/reports'),
  generateReport: (month?: string) =>
    api.post('/coach/reports/generate', { month: month || null }),
  getReport: (month: string) => api.get(`/coach/reports/${month}`),

  // Deal outcomes
  trackDeal: (proposalId: string) =>
    api.post(`/coach/deals/track/${proposalId}`, {}),
  getDealsSummary: () => api.get('/coach/deals/summary'),

  // Coaching nudges
  listNudges: (unreadOnly?: boolean) =>
    api.get(`/coach/nudges${unreadOnly ? '?unread_only=true' : ''}`),
  markNudgeRead: (nudgeId: string) =>
    api.post(`/coach/nudges/${nudgeId}/read`, {}),
  markNudgeActed: (nudgeId: string) =>
    api.post(`/coach/nudges/${nudgeId}/acted`, {}),
}
