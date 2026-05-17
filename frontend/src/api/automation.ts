import { api } from './client'
import type { ApiResponse } from '@/types/api'

export type AutomationTriggerType = 'missed_call' | 'voicemail' | 'inbound_sms_unknown'

export interface AutomationStep {
  id?: string
  step_order: number
  message_body: string
  delay_minutes: number
  include_booking_link: boolean
}

export interface AutomationFlow {
  id: string
  user_id: string
  name: string
  trigger_type: AutomationTriggerType
  is_active: boolean
  created_at: string | null
  updated_at: string | null
  steps: AutomationStep[]
}

export interface AutomationFlowInput {
  name: string
  trigger_type: AutomationTriggerType
  is_active?: boolean
  steps: AutomationStep[]
}

export async function listAutomationFlows() {
  return api.get<ApiResponse<AutomationFlow[]>>('/communication/automation-flows')
}

export async function createAutomationFlow(data: AutomationFlowInput) {
  return api.post<ApiResponse<AutomationFlow>>('/communication/automation-flows', data)
}

export async function updateAutomationFlow(flowId: string, data: AutomationFlowInput) {
  return api.put<ApiResponse<AutomationFlow>>(
    `/communication/automation-flows/${flowId}`,
    data,
  )
}

export async function deleteAutomationFlow(flowId: string) {
  return api.delete<ApiResponse<{ deleted: boolean }>>(
    `/communication/automation-flows/${flowId}`,
  )
}

export async function toggleAutomationFlow(flowId: string, isActive: boolean) {
  return api.post<ApiResponse<{ id: string; is_active: boolean }>>(
    `/communication/automation-flows/${flowId}/toggle`,
    { is_active: isActive },
  )
}

// ─── Contact Memories ───

export interface ContactMemory {
  id: string
  contact_id: string
  source_type: 'voicemail' | 'sms_thread' | 'manual' | 'voice_call'
  source_id: string | null
  summary: string | null
  commitments: string | null
  cares_about: string | null
  talking_points: string | null
  raw_input: string | null
  created_at: string | null
}

export async function listContactMemories(contactId: string) {
  return api.get<ApiResponse<ContactMemory[]>>(`/contacts/${contactId}/memories`)
}

export async function createContactMemory(contactId: string, rawInput: string) {
  return api.post<ApiResponse<ContactMemory>>(
    `/contacts/${contactId}/memories`,
    { raw_input: rawInput, source_type: 'manual' },
  )
}

export async function deleteContactMemory(contactId: string, memoryId: string) {
  return api.delete<ApiResponse<{ deleted: boolean }>>(
    `/contacts/${contactId}/memories/${memoryId}`,
  )
}

// ─── AI Brief ───

export interface ContactBrief {
  brief: string | null
  generated_at: string | null
  is_fresh: boolean
}

export async function getContactBrief(contactId: string) {
  return api.get<ApiResponse<ContactBrief>>(`/contacts/${contactId}/brief`)
}

export async function regenerateContactBrief(contactId: string) {
  return api.post<ApiResponse<ContactBrief>>(
    `/contacts/${contactId}/brief/regenerate`,
    {},
  )
}
