import { api } from './client'

interface ApiResponse<T> {
  data: T
}

export interface SmartImportItem {
  id: string
  status: string
  entry_type: string
  date: string | null
  description: string
  amount: number
  tax_amount: number | null
  category_suggestion: string | null
  confidence: number
  is_duplicate: boolean
  duplicate_entry_id: string | null
  cashbook_entry_id: string | null
}

export interface SmartImport {
  id: string
  original_filename: string
  mime_type: string
  file_size: number
  status: string
  document_type: string | null
  ai_summary: string | null
  error_message: string | null
  processing_time_ms: number | null
  item_count: number
  created_at: string
  items?: SmartImportItem[]
}

export function uploadForImport(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return api.upload<ApiResponse<SmartImport & { items: SmartImportItem[] }>>('/smart-import/upload', fd)
}

export function listImports() {
  return api.get<ApiResponse<SmartImport[]>>('/smart-import')
}

export function getImport(id: string) {
  return api.get<ApiResponse<SmartImport & { items: SmartImportItem[] }>>(`/smart-import/${id}`)
}

export function updateImportItem(itemId: string, data: Partial<SmartImportItem>) {
  return api.put<ApiResponse<SmartImportItem>>(`/smart-import/items/${itemId}`, data)
}

export function confirmImport(importId: string, accountId: string, itemIds?: string[]) {
  return api.post<ApiResponse<{ imported_count: number; total_items: number; errors: string[] }>>(
    `/smart-import/${importId}/confirm`,
    { account_id: accountId, item_ids: itemIds }
  )
}
