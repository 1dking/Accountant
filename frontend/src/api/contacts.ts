import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type { Contact, ContactListItem } from '@/types/models'

export interface ContactFilters {
  search?: string
  type?: string
  is_active?: boolean
  page?: number
  page_size?: number
}

export interface ContactCreateData {
  type: string
  company_name: string
  contact_name?: string
  email?: string
  phone?: string
  address_line1?: string
  address_line2?: string
  city?: string
  state?: string
  zip_code?: string
  country?: string
  tax_id?: string
  notes?: string
}

export interface ContactUpdateData {
  type?: string
  company_name?: string
  contact_name?: string
  email?: string
  phone?: string
  address_line1?: string
  address_line2?: string
  city?: string
  state?: string
  zip_code?: string
  country?: string
  tax_id?: string
  notes?: string
  is_active?: boolean
}

export async function listContacts(filters: ContactFilters = {}) {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== '' && val !== null) params.set(key, String(val))
  })
  const query = params.toString()
  return api.get<ApiListResponse<ContactListItem>>(`/contacts${query ? `?${query}` : ''}`)
}

export async function getContact(id: string) {
  return api.get<ApiResponse<Contact>>(`/contacts/${id}`)
}

export async function createContact(data: ContactCreateData) {
  return api.post<ApiResponse<Contact>>('/contacts', data)
}

export async function updateContact(id: string, data: ContactUpdateData) {
  return api.put<ApiResponse<Contact>>(`/contacts/${id}`, data)
}

export async function deleteContact(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/contacts/${id}`)
}
