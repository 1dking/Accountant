import { api } from './client'
import type { ApiResponse } from '@/types/api'

export type TaskStatus = 'todo' | 'in_progress' | 'done' | 'cancelled'
export type TaskPriority = 'low' | 'medium' | 'high'

export interface Task {
  id: string
  title: string
  description: string | null
  contact_id: string | null
  assigned_user_id: string | null
  status: TaskStatus
  priority: TaskPriority
  due_date: string | null
  completed_at: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface TaskCreateData {
  title: string
  description?: string | null
  contact_id?: string | null
  assigned_user_id?: string | null
  status?: TaskStatus
  priority?: TaskPriority
  due_date?: string | null
}

export async function listTasks(params: { contact_id?: string; status?: TaskStatus } = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v) search.set(k, String(v))
  })
  const query = search.toString()
  return api.get<ApiResponse<Task[]>>(`/tasks${query ? `?${query}` : ''}`)
}

export async function createTask(data: TaskCreateData) {
  return api.post<ApiResponse<Task>>('/tasks', data)
}

export async function updateTask(id: string, data: Partial<TaskCreateData>) {
  return api.patch<ApiResponse<Task>>(`/tasks/${id}`, data)
}

export async function deleteTask(id: string) {
  return api.delete(`/tasks/${id}`)
}
