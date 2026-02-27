import { api } from './client'
import type { ApiResponse, ApiListResponse, DocumentFilters } from '@/types/api'
import type { Document, DocumentListItem, DocumentVersion, Folder, Tag } from '@/types/models'

// Documents
export async function uploadDocuments(files: File[], folderId?: string, tags?: string[]) {
  const results: Document[] = []
  for (const file of files) {
    const formData = new FormData()
    formData.append('file', file)
    if (folderId) formData.append('folder_id', folderId)
    if (tags?.length) tags.forEach((t) => formData.append('tags', t))
    const res = await api.upload<ApiResponse<Document>>('/documents/upload', formData)
    results.push(res.data)
  }
  return { data: results }
}

export async function listDocuments(filters: DocumentFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== '') params.set(key, String(val))
  })
  const query = params.toString()
  return api.get<ApiListResponse<DocumentListItem>>(`/documents${query ? `?${query}` : ''}`)
}

export async function getDocument(id: string) {
  return api.get<ApiResponse<Document>>(`/documents/${id}`)
}

export async function updateDocument(id: string, data: Partial<Document>) {
  return api.put<ApiResponse<Document>>(`/documents/${id}`, data)
}

export async function deleteDocument(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/documents/${id}`)
}

export function getDownloadUrl(id: string) {
  const token = localStorage.getItem('access_token')
  const params = token ? `?token=${encodeURIComponent(token)}` : ''
  return `/api/documents/${id}/download${params}`
}

export function getPreviewUrl(id: string) {
  const token = localStorage.getItem('access_token')
  const params = token ? `?token=${encodeURIComponent(token)}` : ''
  return `/api/documents/${id}/preview${params}`
}

// Versions
export async function listVersions(documentId: string) {
  return api.get<ApiResponse<DocumentVersion[]>>(`/documents/${documentId}/versions`)
}

export async function uploadVersion(documentId: string, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.upload<ApiResponse<DocumentVersion>>(`/documents/${documentId}/versions`, formData)
}

// Folders
export async function getFolderTree() {
  return api.get<ApiResponse<Folder[]>>('/folders')
}

export async function createFolder(data: { name: string; parent_id?: string; description?: string }) {
  return api.post<ApiResponse<Folder>>('/folders', data)
}

export async function updateFolder(id: string, data: { name?: string; parent_id?: string }) {
  return api.put<ApiResponse<Folder>>(`/folders/${id}`, data)
}

export async function deleteFolder(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/folders/${id}`)
}

// Tags
export async function listTags() {
  return api.get<ApiResponse<Tag[]>>('/tags')
}

export async function createTag(data: { name: string; color?: string }) {
  return api.post<ApiResponse<Tag>>('/tags', data)
}

export async function updateTag(id: string, data: { name?: string; color?: string }) {
  return api.put<ApiResponse<Tag>>(`/tags/${id}`, data)
}

export async function deleteTag(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/tags/${id}`)
}

export async function addTagsToDocument(documentId: string, tagIds: string[]) {
  return api.post<ApiResponse<{ message: string }>>(`/documents/${documentId}/tags`, { tag_ids: tagIds })
}

export async function removeTagFromDocument(documentId: string, tagId: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/documents/${documentId}/tags/${tagId}`)
}

// Quick Capture
export interface QuickCaptureResult {
  document_id: string
  document_title: string
  extraction: Record<string, unknown> | null
  expense_id: string | null
  expense_amount: number | null
  expense_vendor: string | null
  expense_date: string | null
  processing_time_ms: number
}

export async function quickCapture(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api.upload<ApiResponse<QuickCaptureResult>>('/documents/quick-capture', formData)
}
