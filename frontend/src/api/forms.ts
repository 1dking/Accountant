import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type { FormDef, FormListItem, FormSubmission } from '@/types/models'

export interface FormCreateData {
  name: string
  description?: string
  fields_json: string
  thank_you_type?: string
  thank_you_config_json?: string
  style_json?: string
  is_active?: boolean
}

export interface FormUpdateData {
  name?: string
  description?: string
  fields_json?: string
  thank_you_type?: string
  thank_you_config_json?: string
  style_json?: string
  is_active?: boolean
}

export async function listForms(page = 1, pageSize = 25) {
  return api.get<ApiListResponse<FormListItem>>(
    `/forms?page=${page}&page_size=${pageSize}`
  )
}

export async function createForm(data: FormCreateData) {
  return api.post<ApiResponse<FormDef>>('/forms', data)
}

export async function getForm(id: string) {
  return api.get<ApiResponse<FormDef>>(`/forms/${id}`)
}

export async function updateForm(id: string, data: FormUpdateData) {
  return api.put<ApiResponse<FormDef>>(`/forms/${id}`, data)
}

export async function deleteForm(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/forms/${id}`)
}

export async function getSubmissions(formId: string, page = 1) {
  return api.get<ApiListResponse<FormSubmission>>(
    `/forms/${formId}/submissions?page=${page}`
  )
}

export async function getPublicForm(id: string) {
  return api.get<ApiResponse<FormDef>>(`/forms/public/${id}`)
}

export async function submitPublicForm(id: string, data: Record<string, unknown>) {
  return api.post<ApiResponse<{ message: string }>>(`/forms/public/${id}/submit`, data)
}
