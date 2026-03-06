import { api } from './client'
import type { ApiResponse, ApiListResponse, DocumentFilters } from '@/types/api'
import type { Document, DocumentListItem, DocumentVersion, Folder, Tag } from '@/types/models'

// Documents
export interface UploadResult {
  file: File
  document?: Document
  error?: string
}

export async function uploadDocuments(
  files: File[],
  folderId?: string,
  tags?: string[],
  onFileComplete?: (result: UploadResult, index: number, total: number) => void,
) {
  const results: UploadResult[] = []
  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    const formData = new FormData()
    formData.append('file', file)
    if (folderId) formData.append('folder_id', folderId)
    if (tags?.length) tags.forEach((t) => formData.append('tags', t))
    // Preserve folder structure for webkitdirectory uploads
    const relativePath = (file as any).webkitRelativePath as string | undefined
    if (relativePath) formData.append('relative_path', relativePath)
    try {
      const res = await api.upload<ApiResponse<Document>>('/documents/upload', formData)
      const result: UploadResult = { file, document: res.data }
      results.push(result)
      onFileComplete?.(result, i, files.length)
    } catch (err: any) {
      const result: UploadResult = { file, error: err.message || 'Upload failed' }
      results.push(result)
      onFileComplete?.(result, i, files.length)
    }
  }
  const successes = results.filter((r) => r.document)
  const failures = results.filter((r) => r.error)
  if (failures.length > 0 && successes.length === 0) {
    throw new Error(
      failures.length === 1
        ? failures[0].error!
        : `All ${failures.length} files failed to upload`,
    )
  }
  return { data: successes.map((r) => r.document!), failures }
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
  return api.get<ApiResponse<Folder[]>>('/documents/folders')
}

export async function createFolder(data: { name: string; parent_id?: string; description?: string }) {
  return api.post<ApiResponse<Folder>>('/documents/folders', data)
}

export async function updateFolder(id: string, data: { name?: string; parent_id?: string }) {
  return api.put<ApiResponse<Folder>>(`/documents/folders/${id}`, data)
}

export async function deleteFolder(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/documents/folders/${id}`)
}

// Tags
export async function listTags() {
  return api.get<ApiResponse<Tag[]>>('/documents/tags')
}

export async function createTag(data: { name: string; color?: string }) {
  return api.post<ApiResponse<Tag>>('/documents/tags', data)
}

export async function updateTag(id: string, data: { name?: string; color?: string }) {
  return api.put<ApiResponse<Tag>>(`/documents/tags/${id}`, data)
}

export async function deleteTag(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/documents/tags/${id}`)
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

// Drive file manager API
export async function starDocument(id: string, starred: boolean) {
  return api.post<ApiResponse<{ message: string }>>(`/documents/${id}/star`, { starred })
}

export async function trashDocument(id: string) {
  return api.post<ApiResponse<{ message: string }>>(`/documents/${id}/trash`)
}

export async function restoreDocument(id: string) {
  return api.post<ApiResponse<{ message: string }>>(`/documents/${id}/restore`)
}

export async function moveDocument(id: string, folderId: string | null) {
  return api.post<ApiResponse<{ message: string }>>(`/documents/${id}/move`, { folder_id: folderId })
}

export async function listStarred() {
  return api.get<ApiResponse<any[]>>('/documents/starred')
}

export async function listTrashed() {
  return api.get<ApiResponse<any[]>>('/documents/trash')
}

export async function listRecent() {
  return api.get<ApiResponse<any[]>>('/documents/recent')
}

export async function getStorageUsage() {
  return api.get<ApiResponse<{ used_bytes: number; file_count: number; folder_count: number }>>('/documents/storage-usage')
}

export async function emptyTrash() {
  return api.delete<ApiResponse<{ message: string }>>('/documents/trash/empty')
}

export async function moveFolder(id: string, parentId: string | null) {
  return api.post<ApiResponse<{ message: string }>>(`/documents/folders/${id}/move`, { parent_id: parentId })
}

export function getStreamUrl(id: string) {
  const token = localStorage.getItem('access_token')
  return `/api/documents/${id}/stream${token ? `?token=${encodeURIComponent(token)}` : ''}`
}

// Bulk operations
export async function bulkDelete(documentIds: string[], folderIds: string[]) {
  return api.post<ApiResponse<{ documents_deleted: number; folders_deleted: number }>>(
    '/documents/bulk/delete',
    { document_ids: documentIds, folder_ids: folderIds },
  )
}

export async function bulkMove(documentIds: string[], folderIds: string[], targetFolderId: string | null) {
  return api.post<ApiResponse<{ documents_moved: number; folders_moved: number }>>(
    '/documents/bulk/move',
    { document_ids: documentIds, folder_ids: folderIds, target_folder_id: targetFolderId },
  )
}

export async function bulkStar(documentIds: string[], folderIds: string[], starred: boolean) {
  return api.post<ApiResponse<{ documents_updated: number; folders_updated: number }>>(
    '/documents/bulk/star',
    { document_ids: documentIds, folder_ids: folderIds, starred },
  )
}

// Rename
export async function renameDocument(id: string, name: string) {
  return api.put<ApiResponse<Document>>(`/documents/${id}/rename`, { name })
}

export async function renameFolder(id: string, name: string) {
  return api.put<ApiResponse<Folder>>(`/documents/folders/${id}/rename`, { name })
}

// Star folder
export async function starFolder(id: string, starred: boolean) {
  return api.post<ApiResponse<Folder>>(`/documents/folders/${id}/star`, { starred })
}

// Recursive folder delete
export async function deleteFolderRecursive(id: string) {
  return api.post<ApiResponse<{ message: string; documents_deleted: number }>>(
    `/documents/folders/${id}/delete-recursive`,
  )
}

// Permanent document delete
export async function deleteDocumentPermanent(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/documents/${id}?permanent=true`)
}
