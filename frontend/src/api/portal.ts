import { api } from './client'
import type { ApiResponse } from '@/types/api'

export interface PortalDashboard {
  contact_name: string | null
  company_name: string
  pending_invoices: number
  total_outstanding: number
  pending_proposals: number
  shared_files: number
  upcoming_meetings: number
}

export interface PortalInvoice {
  id: string
  invoice_number: string
  issue_date: string
  due_date: string
  total: number
  currency: string
  status: string
  payment_url: string | null
}

export interface PortalProposal {
  id: string
  title: string
  status: string
  total: number | null
  created_at: string
  signing_token: string | null
}

export interface PortalFile {
  share_id: string
  file_id: string
  filename: string
  mime_type: string
  file_size: number
  permission: string
  shared_at: string
}

export interface PortalMeeting {
  id: string
  title: string
  scheduled_start: string | null
  scheduled_end: string | null
  status: string
}

export async function getPortalDashboard() {
  return api.get<ApiResponse<PortalDashboard>>('/portal/dashboard')
}

export async function getPortalInvoices() {
  return api.get<ApiResponse<PortalInvoice[]>>('/portal/invoices')
}

export async function getPortalProposals() {
  return api.get<ApiResponse<PortalProposal[]>>('/portal/proposals')
}

export async function getPortalFiles() {
  return api.get<ApiResponse<PortalFile[]>>('/portal/files')
}

export async function getPortalMeetings() {
  return api.get<ApiResponse<PortalMeeting[]>>('/portal/meetings')
}
