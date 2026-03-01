import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type { OfficeDocument, OfficeDocListItem, OfficeCollaborator, DocType, OfficePermission } from '@/types/models'

export interface OfficeDocFilters {
  doc_type?: DocType
  view?: 'owned' | 'shared' | 'starred' | 'recent'
  search?: string
}

export async function createOfficeDoc(data: { title?: string; doc_type: DocType; folder_id?: string }) {
  return api.post<ApiResponse<OfficeDocument>>('/office', data)
}

export async function listOfficeDocs(filters: OfficeDocFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== '') params.set(key, String(val))
  })
  const query = params.toString()
  return api.get<ApiListResponse<OfficeDocListItem>>(`/office${query ? `?${query}` : ''}`)
}

export async function getOfficeDoc(id: string) {
  return api.get<ApiResponse<OfficeDocument>>(`/office/${id}`)
}

export async function updateOfficeDoc(id: string, data: { title?: string; folder_id?: string; content_json?: Record<string, unknown> }) {
  return api.put<ApiResponse<OfficeDocument>>(`/office/${id}`, data)
}

export async function deleteOfficeDoc(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/office/${id}`)
}

export async function shareOfficeDoc(id: string, data: { user_id: string; permission: OfficePermission }) {
  return api.post<ApiResponse<{ message: string }>>(`/office/${id}/share`, data)
}

export async function unshareOfficeDoc(id: string, userId: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/office/${id}/share/${userId}`)
}

export async function duplicateOfficeDoc(id: string) {
  return api.post<ApiResponse<OfficeDocument>>(`/office/${id}/duplicate`)
}

export async function starOfficeDoc(id: string, starred: boolean) {
  return api.post<ApiResponse<{ message: string }>>(`/office/${id}/star`, { starred })
}

export async function trashOfficeDoc(id: string) {
  return api.post<ApiResponse<{ message: string }>>(`/office/${id}/trash`)
}

export async function restoreOfficeDoc(id: string) {
  return api.post<ApiResponse<{ message: string }>>(`/office/${id}/restore`)
}

export async function getOfficeCollaborators(id: string) {
  return api.get<ApiResponse<OfficeCollaborator[]>>(`/office/${id}/collaborators`)
}
