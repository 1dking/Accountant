import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type { OfficeDocument, OfficeDocListItem, OfficeCollaborator, OfficeVersion, OfficeComment, DocType, OfficePermission } from '@/types/models'

export interface OfficeDocFilters {
  doc_type?: DocType
  view?: 'owned' | 'shared' | 'starred' | 'trashed' | 'recent'
  search?: string
}

export async function createOfficeDoc(data: { title?: string; doc_type: DocType; folder_id?: string; content_json?: Record<string, unknown> }) {
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

// ─── Version history ────────────────────────────────────────────────────────

export async function listOfficeVersions(id: string) {
  return api.get<ApiResponse<OfficeVersion[]>>(`/office/${id}/versions`)
}

export async function createOfficeVersion(id: string) {
  return api.post<ApiResponse<OfficeVersion>>(`/office/${id}/versions`)
}

export async function getOfficeVersion(id: string, versionId: string) {
  return api.get<ApiResponse<OfficeVersion>>(`/office/${id}/versions/${versionId}`)
}

export async function restoreOfficeVersion(id: string, versionId: string) {
  return api.post<ApiResponse<OfficeDocument>>(`/office/${id}/versions/${versionId}/restore`)
}

// ─── Comments ────────────────────────────────────────────────────────────────

export async function listOfficeComments(id: string) {
  return api.get<ApiResponse<OfficeComment[]>>(`/office/${id}/comments`)
}

export async function addOfficeComment(
  id: string,
  data: { content: string; parent_id?: string | null; mentioned_user_ids?: string[] }
) {
  return api.post<ApiResponse<OfficeComment>>(`/office/${id}/comments`, data)
}

export async function updateOfficeComment(commentId: string, content: string) {
  return api.put<ApiResponse<OfficeComment>>(`/office/comments/${commentId}`, { content })
}

export async function deleteOfficeComment(commentId: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/office/comments/${commentId}`)
}

// ─── AI writing assistant ────────────────────────────────────────────────────

export async function streamOfficeAiAssist(
  id: string,
  instruction: string,
  selectedText: string | null,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (error: string) => void,
): Promise<void> {
  const token = localStorage.getItem('access_token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  try {
    const response = await fetch(`/api/office/${id}/ai/assist`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ instruction, selected_text: selectedText }),
    })

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.error?.message || `Request failed (${response.status})`)
    }

    const reader = response.body?.getReader()
    if (!reader) throw new Error('No response body')

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') {
            onDone()
            return
          }
          onChunk(data)
        }
      }
    }
    onDone()
  } catch (err) {
    onError(err instanceof Error ? err.message : 'AI assist request failed')
  }
}
