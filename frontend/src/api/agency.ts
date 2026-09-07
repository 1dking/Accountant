import { api } from './client'
import type { ApiResponse } from '@/types/api'

export type OnboardingTemplate = 'marketing_agency' | 'accounting_practice' | 'custom'
export type SubAccountStatus = 'active' | 'suspended' | 'archived'
export type DataEntryMode = 'doer' | 'recipient'
export type CrmStyle = 'full' | 'client_style'

export interface TemplateInfo {
  key: OnboardingTemplate
  label: string
  description: string
  denies: string[]
}

export interface SubAccount {
  id: string
  name: string
  slug: string
  status: SubAccountStatus
  template: OnboardingTemplate
  data_entry_mode: DataEntryMode
  crm_style: CrmStyle
  notes: string | null
  brand_logo_url: string | null
  brand_primary_color: string | null
  features: Record<string, boolean>
  books_enabled: boolean
  member_count: number
  created_at: string
  updated_at: string
}

export interface SubAccountCreate {
  name: string
  slug?: string
  template: OnboardingTemplate
  data_entry_mode?: DataEntryMode
  crm_style?: CrmStyle
  notes?: string | null
  client_email?: string | null
  client_name?: string | null
}

export interface Member {
  id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
}

export interface MemberInvite {
  email: string
  full_name: string
  role?: string
  password?: string
}

export const listTemplates = () => api.get<ApiResponse<TemplateInfo[]>>('/operators/templates')
export const listSubAccounts = () => api.get<ApiResponse<SubAccount[]>>('/operators/sub-accounts')
export const createSubAccount = (data: SubAccountCreate) => api.post<ApiResponse<SubAccount>>('/operators/sub-accounts', data)
export const updateSubAccount = (id: string, data: Partial<Pick<SubAccount, 'name' | 'status' | 'data_entry_mode' | 'crm_style' | 'notes' | 'brand_logo_url' | 'brand_primary_color'>>) =>
  api.put<ApiResponse<SubAccount>>(`/operators/sub-accounts/${id}`, data)
export const setSubAccountFeature = (id: string, key: string, enabled: boolean) =>
  api.put<ApiResponse<SubAccount>>(`/operators/sub-accounts/${id}/features/${key}`, { enabled })
export const unlockBooks = (id: string) => api.post<ApiResponse<SubAccount>>(`/operators/sub-accounts/${id}/books/unlock`)
export const lockBooks = (id: string) => api.post<ApiResponse<SubAccount>>(`/operators/sub-accounts/${id}/books/lock`)
export const listMembers = (id: string) => api.get<ApiResponse<Member[]>>(`/operators/sub-accounts/${id}/members`)
export const inviteMember = (id: string, data: MemberInvite) => api.post<ApiResponse<Member>>(`/operators/sub-accounts/${id}/members`, data)
