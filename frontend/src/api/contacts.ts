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

// Tags
export async function addContactTag(contactId: string, tag_name: string) {
  return api.post(`/contacts/${contactId}/tags`, { tag_name })
}

export async function removeContactTag(contactId: string, tagName: string) {
  return api.delete(`/contacts/${contactId}/tags/${tagName}`)
}

export async function getContactTags(contactId: string) {
  return api.get(`/contacts/${contactId}/tags`)
}

export async function bulkTagContacts(contact_ids: string[], tag_name: string) {
  return api.post('/contacts/bulk-tag', { contact_ids, tag_name })
}

export async function getAllTagNames() {
  return api.get<ApiResponse<string[]>>('/contacts/tags/all')
}

// Activities
export async function getContactActivities(contactId: string, page = 1) {
  return api.get(`/contacts/${contactId}/activities?page=${page}`)
}

export async function addContactActivity(contactId: string, data: { activity_type: string; title: string; description?: string }) {
  return api.post(`/contacts/${contactId}/activities`, data)
}

// File shares
export async function shareFile(data: { file_id: string; contact_id: string; permission: string }) {
  return api.post('/contacts/file-shares', data)
}

export async function getFileShares(contactId: string) {
  return api.get(`/contacts/${contactId}/file-shares`)
}

export async function removeFileShare(shareId: string) {
  return api.delete(`/contacts/file-shares/${shareId}`)
}

// Duplicates
export async function detectDuplicates() {
  return api.get('/contacts/duplicates/detect')
}

export async function mergeContacts(primary_contact_id: string, duplicate_contact_ids: string[]) {
  return api.post('/contacts/merge', { primary_contact_id, duplicate_contact_ids })
}

// Invitations
export async function createInvitation(data: { email: string; role: string; contact_id?: string }) {
  return api.post('/contacts/invitations', data)
}

export async function listInvitations(page = 1) {
  return api.get(`/contacts/invitations?page=${page}`)
}

export async function resendInvitation(id: string) {
  return api.post(`/contacts/invitations/${id}/resend`, {})
}

export async function acceptInvitation(data: { token: string; password: string; full_name: string }) {
  return api.post('/contacts/invitations/accept', data)
}
