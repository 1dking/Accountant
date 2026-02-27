// API envelope types
export interface ApiResponse<T> {
  data: T
  meta?: PaginationMeta | null
}

export interface ApiListResponse<T> {
  data: T[]
  meta: PaginationMeta
}

export interface ApiError {
  error: {
    code: string
    message: string
    details: unknown
  }
}

export interface PaginationMeta {
  page: number
  page_size: number
  total_count: number
  total_pages: number
}

// Query params
export interface DocumentFilters {
  search?: string
  folder_id?: string
  document_type?: string
  tag?: string
  status?: string
  date_from?: string
  date_to?: string
  uploaded_by?: string
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

export interface ActivityFilters {
  user_id?: string
  action?: string
  resource_type?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

export interface CalendarFilters {
  date_from?: string
  date_to?: string
}
