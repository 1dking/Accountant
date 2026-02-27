import { api } from './client'
import type { ApiResponse, ApiListResponse, ActivityFilters } from '@/types/api'
import type { Comment, ActivityLogEntry, Approval } from '@/types/models'

// Comments
export async function listComments(documentId: string) {
  return api.get<ApiResponse<Comment[]>>(`/documents/${documentId}/comments`)
}

export async function createComment(documentId: string, data: { content: string; parent_id?: string }) {
  return api.post<ApiResponse<Comment>>(`/documents/${documentId}/comments`, data)
}

export async function updateComment(commentId: string, data: { content: string }) {
  return api.put<ApiResponse<Comment>>(`/comments/${commentId}`, data)
}

export async function deleteComment(commentId: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/comments/${commentId}`)
}

// Activity
export async function listActivity(filters: ActivityFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== '') params.set(key, String(val))
  })
  const query = params.toString()
  return api.get<ApiListResponse<ActivityLogEntry>>(`/activity${query ? `?${query}` : ''}`)
}

// Approvals
export async function requestApproval(documentId: string, assignedTo: string) {
  return api.post<ApiResponse<Approval>>(`/documents/${documentId}/approve`, { assigned_to: assignedTo })
}

export async function resolveApproval(approvalId: string, data: { status: 'approved' | 'rejected'; comment?: string }) {
  return api.put<ApiResponse<Approval>>(`/approvals/${approvalId}`, data)
}

export async function listPendingApprovals() {
  return api.get<ApiResponse<Approval[]>>('/approvals')
}
