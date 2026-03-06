import { api } from './client'
import type { ApiResponse, ApiListResponse } from '@/types/api'
import type {
  Workflow,
  WorkflowListItem,
  WorkflowTemplate,
  WorkflowExecution,
} from '@/types/models'

export interface WorkflowCreateData {
  name: string
  description?: string
  trigger_type: string
  trigger_config_json?: string
  is_active?: boolean
  steps?: {
    step_order: number
    action_type: string
    action_config_json?: string
    condition_json?: string
    wait_duration_seconds?: number
  }[]
}

export interface WorkflowUpdateData {
  name?: string
  description?: string
  trigger_type?: string
  trigger_config_json?: string
  is_active?: boolean
  steps?: {
    step_order: number
    action_type: string
    action_config_json?: string
    condition_json?: string
    wait_duration_seconds?: number
  }[]
}

export async function listWorkflows(page = 1, pageSize = 25) {
  return api.get<ApiListResponse<WorkflowListItem>>(
    `/workflows?page=${page}&page_size=${pageSize}`
  )
}

export async function createWorkflow(data: WorkflowCreateData) {
  return api.post<ApiResponse<Workflow>>('/workflows', data)
}

export async function getWorkflow(id: string) {
  return api.get<ApiResponse<Workflow>>(`/workflows/${id}`)
}

export async function updateWorkflow(id: string, data: WorkflowUpdateData) {
  return api.put<ApiResponse<Workflow>>(`/workflows/${id}`, data)
}

export async function deleteWorkflow(id: string) {
  return api.delete<ApiResponse<{ message: string }>>(`/workflows/${id}`)
}

export async function toggleWorkflow(id: string, isActive: boolean) {
  return api.put<ApiResponse<Workflow>>(`/workflows/${id}`, { is_active: isActive })
}

export async function getTemplates() {
  return api.get<ApiResponse<WorkflowTemplate[]>>('/workflows/templates')
}

export async function getExecutions(workflowId: string, page = 1) {
  return api.get<ApiListResponse<WorkflowExecution>>(
    `/workflows/${workflowId}/executions?page=${page}`
  )
}

export async function dispatchEvent(eventType: string, payload: Record<string, unknown>) {
  return api.post<ApiResponse<{ triggered: number }>>('/workflows/dispatch', {
    event_type: eventType,
    payload,
  })
}
